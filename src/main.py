import os
import json
import datetime
import time
import requests
import urllib.parse
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

def get_kst_dates():
    kst = datetime.timezone(datetime.timedelta(hours=9))
    
    # 💡 [테스트용 타임머신] 시스템의 오늘 날짜를 2026년 7월 8일로 강제 고정
    today = datetime.datetime(2026, 7, 8, 12, 0, 0, tzinfo=kst)
    yesterday = today - datetime.timedelta(days=1)
    tomorrow = today + datetime.timedelta(days=1)
    day_before_yesterday = today - datetime.timedelta(days=2)
    return {
        "today_str_kr": today.strftime("%Y년 %m월 %d일"),
        "yesterday_str_kr": yesterday.strftime("%Y년 %m월 %d일"),
        "yesterday_query": day_before_yesterday.strftime("%Y-%m-%d"),
        "tomorrow_query": tomorrow.strftime("%Y-%m-%d")    # 💡 before:2026-07-09 로 다시 고정
    }

def get_existing_models_from_sheet():
    print("📂 [DB 확인] 구글 시트에서 기존 수집된 모델명 목록을 불러옵니다...")
    service = get_sheets_service()
    if not service: 
        return []
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, 
            range="스펙_누적_데이터!C:C"
        ).execute()
        values = result.get('values', [])
        existing_models = [row[0].strip().lower() for row in values if row]
        return existing_models
    except Exception as e:
        print(f"⚠️ 기존 데이터 불러오기 에러: {e}")
        return []

def detect_new_releases():
    dates = get_kst_dates()
    print(f"📡 [1단계: 정찰] {dates['yesterday_str_kr']} ~ {dates['today_str_kr']} 구간의 기사를 검사합니다...")
    
    # 💡 검색망을 그저께로 넓히지 않고 기존(어제~내일) 방식 유지
    search_query = f"smartphone (launch OR announcement) after:{dates['yesterday_query']} before:{dates['tomorrow_query']}"
    encoded_query = urllib.parse.quote(search_query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    
    found_models = []
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'xml') 
        items = soup.find_all('item')
        
        for i, item in enumerate(items[:200]):
            title = item.title.text
            link = item.link.text
            print(f"[{i+1}/{min(200, len(items))}] 검사 중: {title}")
            
            # 루머성 짙은 단어 1차 필터링
            if any(w in title.lower() for w in ['rumor', 'concept', 'reportedly']):
                continue
                
            try:
                art_resp = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                art_soup = BeautifulSoup(art_resp.text, 'html.parser')
                article_text = "\n".join([p.text for p in art_soup.find_all('p')[:3]])
            except Exception:
                article_text = "본문 수집 불가"

           # 💡 [핵심] '특정 국가 지각 출시(재탕)'를 걸러내고 '글로벌 최초 공개'만 잡는 똑똑해진 프롬프트 유지
            check_prompt = f"""
            당신은 수석 모바일 상품기획자의 스마트폰 신제품 감별사입니다.
            
            기사 제목: '{title}'
            초반부: '{article_text}'
            
            이 기사가 "전 세계 최초로 공식 발표(First Global Unveil)" 또는 "최초 출시"된 스마트폰 신제품을 다루고 있나요?
            <엄격한 판별 기준>
            1. 과거에 이미 출시된 폰이 오늘 인도, 유럽, 대만 등 특정 국가에 뒤늦게 런칭(Launched in India today 등)하는 기사는 무조건 '아니오'로 답하세요. (예: 이미 몇 달 전 공개된 폰이 오늘 특정 국가에 출시되었다는 뉘앙스면 가짜입니다)
            """
            
            ai_response = lite_model.generate_content(check_prompt).text.strip()
            
            if "아니오" not in ai_response and len(ai_response) > 2:
                model_name = ai_response
                print(f"  ㄴ 🚨 실제 출시 확인됨: {model_name}")
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
            prompt = f"'{item['model_name']}'와 '{u_item['model_name']}'가 같은 스마트폰 기기를 의미하나요? 맞으면 '예', 다르면 '아니오'로만 답하세요."
            ans = lite_model.generate_content(prompt).text.strip()
            if "예" in ans or "Yes" in ans:
                is_duplicate = True
                print(f"  ㄴ 🗑️ 중복 제외됨: {item['model_name']}")
                break
            time.sleep(5)
        if not is_duplicate:
            unique_models.append(item)
            print(f"  ㄴ ✅ 고유 모델 등록: {item['model_name']}")
    return unique_models

def fetch_usp_and_target(model_name, intro_text):
    print(f"🔍 [{model_name}] 마케팅 맥락 및 USP 2차 검색 중...")
    
    raw_query = f'"{model_name}" (launch OR feature OR market OR target OR premium OR price OR strategy)'
    search_query = urllib.parse.quote(raw_query)
    url = f"https://news.google.com/rss/search?q={search_query}&hl=en-US&gl=US&ceid=US:en"
    combined_text = intro_text + "\n"
    
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'xml')
        items = soup.find_all('item')
        
        for item in items[:2]:
            try:
                res = requests.get(item.link.text, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                art_soup = BeautifulSoup(res.text, 'html.parser')
                elements = art_soup.find_all(['p', 'h1', 'h2'])
                extracted_texts = [el.text.strip() for el in elements if len(el.text.strip()) > 10]
                combined_text += "\n".join(extracted_texts[:20]) + "\n"
            except: pass
            time.sleep(3) 
            
        usp_prompt = f"""
        수집된 정보: {combined_text[:4000]}
        위 출시 정보를 바탕으로 '{model_name}'의 마케팅 전략 핵심 요소를 추출해 주세요.
        정확히 명시되지 않았다면 기사 문맥을 바탕으로 기획자적 관점에서 추론하여 작성하세요.
        
        출력 형식:
        제조사:
        모델명: {model_name}
        주요 타겟 고객층: 
        핵심 셀링 포인트(USP): 
        가격대 및 포지셔닝: 
        """
        result = lite_model.generate_content(usp_prompt).text
        time.sleep(5)
        return result
    except Exception as e:
        return f"전략 분석 실패: {e}"

def generate_batch_insights(strategy_list):
    print("🧠 [일괄 전략 분석] Pro 모델 가동하여 기획 시사점 도출 중...")
    if not strategy_list: return []
    
    combined_strategies = ""
    for i, strat in enumerate(strategy_list):
        combined_strategies += f"### 제품 {i}\n{strat}\n\n"
        
    prompt = f"""
    오늘 글로벌 시장에 공식 출시된 스마트폰 전략 정보 목록입니다:
    {combined_strategies}
    
    당신은 수석 모바일 상품기획자입니다. 위 신제품들의 타겟층과 USP를 종합적으로 고려했을 때, 
    우리가 차기 제품을 기획하거나 방어 전략을 짤 때 참고해야 할 '상품 기획적 시사점 및 대응 방향'을 제품별로 딱 3줄 요약하여 작성하세요.
    말을 꾸미지 말고 철저히 비즈니스 관점에서 작성하세요.
    
    반드시 아래 형식을 지키세요:
    ### 제품 0
    시사점 내용...
    ### 제품 1
    시사점 내용...
    """    
    try:
        response = pro_model.generate_content(prompt).text
        time.sleep(5)
        
        insights = []
        for i in range(len(strategy_list)):
            part = response.split(f"### 제품 {i}")
            if len(part) > 1:
                content = part[1].split("### 제품")[0].strip()
                insights.append(content)
            else:
                insights.append("전략 시사점 도출 실패")
        return insights
    except Exception as e:
        return [f"⚠️ 전략 분석 에러: {e}"] * len(strategy_list)

def save_to_cumulative_sheet(model_name, strategy_text, url, insight_text):
    service = get_sheets_service()
    if not service: return
    try:
        current_date = "2026-07-08"
        
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID, range="스펙_누적_데이터!A:F",
            valueInputOption="USER_ENTERED", body={'values': [[current_date, "Google News (USP/Target)", model_name, strategy_text, url]]}
        ).execute()
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID, range="오늘의_신제품!A:E",
            valueInputOption="USER_ENTERED", body={'values': [[current_date, model_name, "AI 기획 전략 분석", url, insight_text]]}
        ).execute()
    except Exception as e: 
        print(f"⚠️ 시트 저장 에러: {e}")

if __name__ == "__main__":
    print(f"[2026-07-08 12:00:00] 🚀 명시적 날짜 & 구글 시트 DB 중복 필터링 시스템 가동 (타임머신 테스트 모드: 7월 8일)")
    
    existing_models_in_db = get_existing_models_from_sheet()
    
    detected_models = detect_new_releases()
    unique_models = deduplicate_models(detected_models)
    
    final_target_models = []
    if unique_models:
        print("\n🛡️ [사전 검증] 구글 시트에 이미 기록된 제품인지 대조합니다...")
        for device in unique_models:
            clean_name = device['model_name'].strip().lower()
            
            is_already_saved = False
            for db_model in existing_models_in_db:
                if clean_name in db_model or db_model in clean_name:
                    is_already_saved = True
                    break
            
            if is_already_saved:
                print(f"  ㄴ ⏩ 패스: '{device['model_name']}' (이미 시트에 저장된 제품입니다)")
            else:
                print(f"  ㄴ 🆕 신규: '{device['model_name']}' (분석 대상에 추가됨)")
                final_target_models.append(device)
    
    if final_target_models:
        print(f"\n총 {len(final_target_models)}개의 완벽한 신제품 마케팅 전략 분석을 시작합니다.")
        all_strategies = []
        for device in final_target_models:
            strategy_info = fetch_usp_and_target(device['model_name'], device['intro_text'])
            all_strategies.append(strategy_info)
            print(f"  ㄴ {device['model_name']} USP 및 타겟 데이터 확보")
            
        insights = generate_batch_insights(all_strategies)
        
        print("\n[최종 대시보드 저장 시작]")
        for idx, device in enumerate(final_target_models):
            save_to_cumulative_sheet(device['model_name'], all_strategies[idx], device['primary_url'], insights[idx])
            print(f"✔️ {device['model_name']} 기획 전략 시트 저장 완료")
        print("\n✅ 모든 상품기획 파이프라인 처리가 성공적으로 완료되었습니다!")
    else:
        print("\n✅ 시스템 정상 작동: 오늘(최근 2일 이내) 새롭게 추가할 공식 신제품이 없습니다.")
