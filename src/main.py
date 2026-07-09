import os
import json
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import google.generativeai as genai
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ---------------------------------------------------------
# 1. 환경 설정 및 API 키 준비
# ---------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GCP_CREDENTIALS = os.environ.get("GCP_CREDENTIALS")
SPREADSHEET_ID = "1fKrSktMeXJmnqwUGOgk4QLtwfpAlkkFi5SvYJSrbT5o"

genai.configure(api_key=GEMINI_API_KEY)

# 🚀 디렉터님의 환경에 맞춰 최신 gemini-3.5-flash 모델로 고정합니다.
# 구글 검색 도구(tools)를 제거했으므로, 하루 20회 한도 내에서 안전하게 가동됩니다.
model = genai.GenerativeModel(model_name="gemini-3.5-flash")

def get_sheets_service():
    creds_dict = json.loads(GCP_CREDENTIALS)
    creds = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return build('sheets', 'v4', credentials=creds)

# ---------------------------------------------------------
# 2. 골드 스탠다드(벤치마크) 불러오기
# ---------------------------------------------------------
def get_gold_standards(service):
    print("🔍 [준비] 구글 시트에서 프리미엄 벤치마크 데이터를 불러옵니다...")
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range="골드_스탠다드!A2:AQ"
    ).execute()
    rows = result.get('values', [])
    
    gold_standards = []
    for row in rows:
        if len(row) > 2:
            def get_val(idx):
                return row[idx] if len(row) > idx and row[idx] else "N/A"
                
            gold_standards.append({
                "모델명": get_val(1),
                "제조사": get_val(2),
                "AP_모델명": get_val(10),
                "RAM": get_val(12),
                "배터리_용량": get_val(15),
                "카메라_화소": get_val(19),
                "디스플레이_특이사항": get_val(23),
                "화면크기": get_val(24)
            })
    return gold_standards

# ---------------------------------------------------------
# 3. 1단계: 크롤링/RSS 기반 신제품 소식 수집
# ---------------------------------------------------------
def detect_new_releases_via_crawl():
    print("📰 [1단계] GSMArena RSS/News 크롤링을 통해 최신 기사 수집 중...")
    url = "https://www.gsmarena.com/news.php3"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.text, 'lxml')
        
        news_items = soup.select('.news-item')
        combined_text = ""
        
        for item in news_items[:10]: # 최신 기사 10개 추출
            title = item.find('h3').text if item.find('h3') else ""
            desc = item.find('p').text if item.find('p') else ""
            combined_text += f"Title: {title}\nDescription: {desc}\n\n"
            
        prompt = f"""
        아래는 스마트폰 뉴스 기사 목록이야. 이 기사들을 읽고 최근 '공식 발표(Announced)'되거나 '출시(Launched)'된 
        실제 스마트폰 신제품 모델명들이 있다면 콤마(,)로 구분해서 적어줘. 단순 루머나 유출 기사는 엄격히 제외해.
        기사에 신제품 소식이 없다면 오직 '없음'이라고만 대답해.
        
        [뉴스 기사 데이터]
        {combined_text}
        """
        response = model.generate_content(prompt)
        result = response.text.strip()
        
        if "없음" in result or not result:
            print("ℹ️ 크롤링 결과, 오늘 발표된 새로운 스마트폰이 없습니다.")
            return []
            
        models = [m.strip() for m in result.split(",") if m.strip()]
        print(f"🚨 [감지 완료] 크롤링으로 신제품 발견: {models}")
        return models
    except Exception as e:
        print(f"⚠️ [에러] 크롤링 중 문제 발생: {e}")
        return []

# ---------------------------------------------------------
# 4. 2단계: 크롤링 본문 요약 및 10대 핵심 스펙 매핑
# ---------------------------------------------------------
def analyze_specs_from_crawl(model_name, gold_standards):
    print(f"🧠 [2단계] '{model_name}' 크롤링 기반 스펙 정형화 및 골드 스탠다드 대조...")
    
    benchmark_text = ""
    for g in gold_standards:
        benchmark_text += f"- {g['제조사']} {g['모델명']} (AP:{g['AP_모델명']}, RAM:{g['RAM']}, 배터리:{g['배터리_용량']}, 카메라:{g['카메라_화소']}, 디스플레이:{g['디스플레이_특이사항']}, 화면크기:{g['화면크기']})\n"
    
    prompt = f"""
    너의 지식을 바탕으로 스마트폰 '{model_name}'의 핵심 스펙을 명확하게
