import os
import json
import datetime
import time
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ==========================================
# ⚙️ 1. 설정 및 API 준비
# ==========================================
SPREADSHEET_ID = "1fKrSktMeXJmnqwUGOgk4QLtwfpAlkkFi5SvYJSrbT5o"

gemini_key = os.environ.get("GEMINI_API_KEY")
gcp_creds_json = os.environ.get("GCP_CREDENTIALS")

if gemini_key:
    genai.configure(api_key=gemini_key)
    ai_model = genai.GenerativeModel('gemini-3.5-flash')

def get_sheets_service():
    if not gcp_creds_json:
        return None
    creds_dict = json.loads(gcp_creds_json)
    creds = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    return build('sheets', 'v4', credentials=creds)

# ==========================================
# 📡 2. [1단계: 정찰] 신제품 모델명만 싹쓸이 수집
# ==========================================
def detect_new_releases():
    print("📡 [1단계: 정찰] 6월 27일 테스트: 기사 40개를 검사하여 신제품 모델명을 찾습니다...")
    url = "https://news.google.com/rss/search?q=smartphone+(launch+OR+announcement)+after:2026-06-25+before:2026-06-28&hl=en-US&gl=US&ceid=US:en"
    
    found_models = []
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'xml') 
        items = soup.find_all('item')
        
        for i, item in enumerate(items[:40]):
            title = item.title.text
            link = item.link.text
            print(f"[{i+1}/40] 검사 중: {title}")
            
            if any(w in title.lower() for w in ['rumor', 'leak', 'concept', 'reportedly']):
                continue
                
            try:
                # 기사 첫 3문단만 가져오기 (노이즈 방지)
                art_resp = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                art_soup = BeautifulSoup(art_resp.text, 'html.parser')
                article_text = "\n".join([p.text for p in art_soup.find_all('p')[:3]])
            except Exception:
                article_text = "본문 수집 불가"

            # AI에게 신제품 여부와 모델명을 한 번에 묻기 (프롬프트 유연화)
            check_prompt = f"""
            기사 제목: '{title}'
            기사 초반부: '{article_text}'
            이 기사가 새로운 스마트폰의 '공식 신제품 발표'를 다루고 있나요? 
            단순 루머나 출시 국가 확대라면 '아니오'라고 답하고, 
            진짜 공식 신제품 발표가 맞다면 해당 신제품의 '모델명(예: Samsung Galaxy A27)'만 정확히 적어주세요. 다른 말은 덧붙이지 마세요.
            """
            ai_response = ai_model.generate_content(check_prompt).text.strip()
            
            if "아니오" not in ai_response and len(ai_response) > 2:
                model_name = ai_response
                print(f"\n🚨 [감지 성공] 신제품 모델명 확보: {model_name}\n")
                found_models.append({"model_name": model_name, "primary_url": link, "intro_text": article_text})
            else:
                print("  ㄴ 🤖 AI: 신제품 발표 아님.")
                
            time.sleep(12) # API 1분 5회 제한 보호
            
        return found_models

    except Exception as e:
        print(f"⚠️ 정찰 에러 발생: {e}")
        return []

# ==========================================
# 🔍 3. [2단계: 심층 발굴] 특정 모델 세부 스펙 2차 검색
# ==========================================
def fetch_detailed_specs(model_name, intro_text):
    print(f"🔍 [{model_name}] 세부 스펙 2차 검색을 시작합니다...")
    
    # 해당 모델명으로 구글 뉴스 스펙 전용 2차 검색
    search_query = f"{model_name} specifications OR specs"
    url = f"https://news.google.com/rss/search?q={search_query}&hl=en-US&gl=US&ceid=US:en"
    
    combined_text = intro_text + "\n\n--- 2차 검색 추가 정보 ---\n"
    
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'xml')
        items = soup.find_all('item')
        
        # 상위 2개 기사의 첫 3문단씩만 더 긁어와서 단서 조합
        for item in items[:2]:
            try:
                res = requests.get(item.link.text, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                art_soup = BeautifulSoup(res.text, 'html.parser')
                combined_text += "\n".join([p.text for p in art_soup.find_all('p')[:3]]) + "\n"
            except: pass
            time.sleep(5) # 짧은 대기
            
        spec_prompt = f"""
        다음은 '{model_name}' 스마트폰에 대해 수집된 여러 기사의 초반부 내용들입니다.
        이 종합된 정보를 바탕으로 '{model_name}'의 세부 스펙을 추출해 주세요.
        수집된 정보: {combined_text[:3000]}
        
        출력 형식:
        모델명: {model_name}
        AP(칩셋):
        디스플레이:
        배터리:
        카메라:
        """
        extracted_specs = ai_model.generate_content(spec_prompt).text
        return extracted_specs
        
    except Exception as e:
        print(f"⚠️ 세부 스펙 검색 에러: {e}")
        return "스펙 수집 실패"

# ==========================================
# 📊 4. 골드 스탠다드 대조 및 시트 저장
# ==========================================
def generate_ai_insight(specs):
    print("🧠 [분석] 골드 스탠다드 대조 및 인사이트 도출 중...")
    service = get_sheets_service()
    benchmarks = "벤치마크 데이터를 불러오지 못했습니다."
    try:
        result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range="골드_스탠다드!A1:AQ").execute()
        benchmarks = json.dumps(result.get('values', [])[:3], ensure_ascii=False)
    except Exception: pass

    prompt = f"신제품 스펙: {specs}\n벤치마크 기준: {benchmarks}\n신제품이 벤치마크 대비 어떤 수치적 우위가 있는지, 시장 타겟팅 관점에서 3줄 이내로 정리하세요."
    try:
        return ai_model.generate_content(prompt).text
    except: return "인사이트 에러"

def save_to_cumulative_sheet(model_name, specs, url, insight_text):
    print("💾 [저장] 구글 시트 2곳에 데이터를 누적 기록합니다...")
    service = get_sheets_service()
    if not service: return
    try:
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # 1. 스펙 시트
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID, range="스펙_누적_데이터!A:F",
            valueInputOption="USER_ENTERED", body={'values': [[current_date, "Google News (2차 심층검색)", model_name, specs, url]]}
        ).execute()

        # 2. 오늘의 신제품 시트
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID, range="오늘의_신제품!A:E",
            valueInputOption="USER_ENTERED", body={'values': [[current_date, model_name, "AI 감지 (투트랙)", url, insight_text]]}
        ).execute()
        print("✔️ 저장 완료!")
    except Exception as e: print(f"⚠️ 저장 에러: {e}")

# ==========================================
# 🤖 메인 파이프라인
# ==========================================
if __name__ == "__main__":
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🤖 스마트폰 봇 가동 (투트랙 심층 분석 모드)")
    
    # 1단계: 정찰 (모델명 찾기)
    detected_models = detect_new_releases()
    
    if detected_models:
        print(f"\n🎉 총 {len(detected_models)}개의 신제품이 감지되었습니다! 세부 스펙 조사를 시작합니다.")
        
        for idx, device in enumerate(detected_models):
            print(f"\n========================================")
            print(f"📱 [{idx+1}/{len(detected_models)}] 타겟 모델: {device['model_name']}")
            
            # 2단계: 심층 발굴 (세부 스펙 채우기)
            detailed_specs = fetch_detailed_specs(device['model_name'], device['intro_text'])
            print(f"\n[추출된 세부 스펙]\n{detailed_specs}\n")
            time.sleep(12) # AI 과부하 방지
            
            # 3단계: 분석 및 저장
            insight = generate_ai_insight(detailed_specs)
            save_to_cumulative_sheet(device['model_name'], detailed_specs, device['primary_url'], insight)
            time.sleep(12) # AI 과부하 방지
            
            print(f"========================================\n")
            
        print("✅ 모든 신제품에 대한 투트랙 심층 파이프라인이 성공적으로 완료되었습니다!")
    else:
        print("✅ 시스템 정상 작동: 지정된 기간 내에 출시된 신제품이 없습니다.")
