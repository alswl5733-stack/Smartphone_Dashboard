import os
import json
import datetime
import time
import requests
import re
from bs4 import BeautifulSoup
import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build

SPREADSHEET_ID = "1fKrSktMeXJmnqwUGOgk4QLtwfpAlkkFi5SvYJSrbT5o"

gemini_key = os.environ.get("GEMINI_API_KEY")
gcp_creds_json = os.environ.get("GCP_CREDENTIALS")

if gemini_key:
    genai.configure(api_key=gemini_key)
    lite_model = genai.GenerativeModel('gemini-3.1-flash-lite')
    pro_model = genai.GenerativeModel('gemini-3.5-flash')

def get_sheets_service():
    if not gcp_creds_json:
        return None
    creds_dict = json.loads(gcp_creds_json)
    creds = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    return build('sheets', 'v4', credentials=creds)

def detect_new_releases():
    print("📡 [1단계: 정찰] 최근 24시간 내의 기사 최대 200개를 검사합니다...")
    
    # 💡 [변경] 실전 가동을 위해 최근 24시간(when:1d) 검색어로 변경
    url = "https://news.google.com/rss/search?q=smartphone+(launch+OR+announcement)+when:1d&hl=en-US&gl=US&ceid=US:en"
    
    found_models = []
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'xml') 
        items = soup.find_all('item')
        
        for i, item in enumerate(items[:200]):
            title = item.title.text
            link = item.link.text
            print(f"[{i+1}/{min(200, len(items))}] 검사 중: {title}")
            
            if any(w in title.lower() for w in ['rumor', 'leak', 'concept', 'reportedly']):
                continue
                
            try:
                art_resp = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                art_soup = BeautifulSoup(art_resp.text, 'html.parser')
                article_text = "\n".join([p.text for p in art_soup.find_all('p')[:3]])
            except Exception:
                article_text = "본문 수집 불가"

            check_prompt = f"""
            기사 제목: '{title}'
            초반부: '{article_text}'
            이 기사가 스마트폰 신제품 공식 발표인가요? 단순 루머면 '아니오', 맞다면 해당 신제품의 '모델명(예: Samsung Galaxy A27)'만 적으세요.
            """
            
            ai_response = lite_model.generate_content(check_prompt).text.strip()
            
            if "아니오" not in ai_response and len(ai_response) > 2:
                model_name = ai_response
                print(f"  ㄴ 🚨 감지 성공: {model_name}")
                found_models.append({"model_name": model_name, "primary_url": link, "intro_text": article_text})
                
            time.sleep(5) 
            
        return found_models
    except Exception as e:
        print(f"⚠️ 정찰 에러 발생: {e}")
        return []

def deduplicate_models(models):
    print("\n🔍 [중복 제거] 수집된 모델명 통합 작업을 진행합니다...")
    unique_models = []
    
    for item in models:
        is_duplicate = False
        for u_item in unique_models:
            prompt = f"'{item['model_name']}'와 '{u_item['model_name']}'가 같은 스마트폰 기기를 의미하나요? 표기가 다르거나 축약형(예: Nothing Phone 4b 와 Phone 4b)인 경우도 포함됩니다. 맞으면 '예', 다르면 '아니오'로만 답하세요."
            ans = lite_model.generate_content(prompt).text.strip()
            
            if "예" in ans or "Yes" in ans:
                is_duplicate = True
                print(f"  ㄴ 🗑️ 중복 제외됨: {item['model_name']} (기존 '{u_item['model_name']}'와 동일 기기)")
                break
            time.sleep(5)
            
        if not is_duplicate:
            unique_models.append(item)
            print(f"  ㄴ ✅ 고유 모델 등록: {item['model_name']}")
            
    return unique_models

def fetch_detailed_specs(model_name, intro_text):
    print(f"🔍 [{model_name}] 세부 스펙 2차 검색 중...")
    
    search_query = f'"{model_name}" (specs OR specifications OR processor OR display OR battery OR camera OR "release date" OR "launch date")'
    url = f"https://news.google.com/rss/search?q={search_query}&hl=en-US&gl=US&ceid=US:en"
    combined_text = intro_text + "\n"
    
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'xml')
        items = soup.find_all('item')
        
        for item in items[:2]:
            try:
                res = requests.get(item.link.text, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                combined_text += "\n".join([p.text for p in BeautifulSoup(res.text, 'html.parser').find_all('p')[:3]]) + "\n"
            except: pass
            time.sleep(3) 
            
        # 💡 [변경] 현재 날짜를 구해서 프롬프트에 주입 (상대적 날짜 계산 및 환각 방지)
        today_date = datetime.datetime.now().strftime("%Y년 %m월 %d일")
            
        spec_prompt = f"""
        현재 날짜는 {today_date}입니다.
        수집된 정보: {combined_text[:3000]}
        
        위 정보를 바탕으로 '{model_name}'의 세부 스펙을 추출해 주세요.
        
        [출시 연월 추출 주의사항]
        - 기사 본문에 "today", "this week" 등으로 표현된 경우, 현재 날짜({today_date})를 기준으로 정확한 연/월을 계산하세요.
        - 공식적인 출시(또는 발표) 일정이 기재되어 있지 않거나 추측만 있다면 절대 지어내지 말고 "미정" 또는 "기사 내 확인 불가"로 적으세요.
        
        출력 형식:
        모델명: {model_name}
        출시 연월:
        AP(칩셋):
        디스플레이:
        배터리:
        카메라:
        """
        result = lite_model.generate_content(spec_prompt).text
        time.sleep(5)
        return result
    except Exception as e:
        return f"스펙 수집 실패: {e}"

def generate_batch_insights(specs_list):
    print("🧠 [일괄 분석] Pro 모델 1회 호출로 모든 신제품 인사이트 도출 중...")
    if not specs_list: return []
    
    service = get_sheets_service()
    benchmarks = "데이터 없음"
    if service:
        try:
            result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range="골드_스탠다드!A1:AQ").execute()
            benchmarks = json.dumps(result.get('values', [])[:3], ensure_ascii=False)
        except: pass

    combined_specs = ""
    for i, spec in enumerate(specs_list):
        combined_specs += f"### 모델 {i}\n{spec}\n\n"
        
    prompt = f"""
    신제품 스펙 목록:
    {combined_specs}
    
    벤치마크 기준: {benchmarks}
    
    위 신제품 각각에 대해 벤치마크 대비 수치적 우위와 시장 타겟팅 관점을 3줄 이내로 분석하세요.
    반드시 아래와 같은 형식으로 각 모델의 결과를 '### 모델 번호'로 구분하여 출력하세요.
    
    ### 모델 0
    인사이트 내용...
    ### 모델 1
    인사이트 내용...
    """
    
    try:
        response = pro_model.generate_content(prompt).text
        time.sleep(5)
        
        insights = []
        for i in range(len(specs_list)):
            part = response.split(f"### 모델 {i}")
            if len(part) > 1:
                content = part[1].split("### 모델")[0].strip()
                insights.append(content)
            else:
                insights.append("분석 내용 분리 실패")
        return insights
    except Exception as e:
        return [f"⚠️ 인사이트 에러: {e}"] * len(specs_list)

def save_to_cumulative_sheet(model_name, specs, url, insight_text):
    service = get_sheets_service()
    if not service: return
    try:
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID, range="스펙_누적_데이터!A:F",
            valueInputOption="USER_ENTERED", body={'values': [[current_date, "Google News (Batch/Live)", model_name, specs, url]]}
        ).execute()
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID, range="오늘의_신제품!A:E",
            valueInputOption="USER_ENTERED", body={'values': [[current_date, model_name, "AI 감지 (Batch/Live)", url, insight_text]]}
        ).execute()
    except Exception as e: print(f"⚠️ 저장 에러: {e}")

if __name__ == "__main__":
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 시스템 실전 가동 (최근 24시간 스캔 & 날짜 정확도 강화)")
    
    detected_models = detect_new_releases()
    unique_models = deduplicate_models(detected_models)
    
    if unique_models:
        print(f"\n총 {len(unique_models)}개의 고유 신제품 세부 스펙 조사를 시작합니다.")
        
        all_specs = []
        for device in unique_models:
            specs = fetch_detailed_specs(device['model_name'], device['intro_text'])
            all_specs.append(specs)
            print(f"  ㄴ {device['model_name']} 스펙 확보")
            
        insights = generate_batch_insights(all_specs)
        
        print("\n[최종 데이터 저장 시작]")
        for idx, device in enumerate(unique_models):
            save_to_cumulative_sheet(device['model_name'], all_specs[idx], device['primary_url'], insights[idx])
            print(f"✔️ {device['model_name']} 시트 저장 완료")
            
        print("\n✅ 모든 처리 완료")
    else:
        print("✅ 시스템 정상 작동: 지정된 기간 내에 출시된 신제품이 없습니다.")
