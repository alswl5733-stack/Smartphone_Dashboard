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
# ⚠️ 디렉터님의 구글 스프레드시트 ID를 입력해주세요.
SPREADSHEET_ID = "1fKrSktMeXJmnqwUGOgk4QLtwfpAlkkFi5SvYJSrbT5o"

# 타임머신 타겟 날짜 설정 (GSMArena 표기법 기준)
TARGET_DATE = "26 Jun"

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
# 📡 2. 특정 날짜 기사 탐색 및 신제품 감지
# ==========================================
def find_and_extract_new_release():
    print(f"📡 [수집] GSMArena에서 '{TARGET_DATE}' 날짜의 기사를 탐색합니다...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # 1페이지부터 3페이지까지 탐색 (과거 기사이므로 뒤로 밀렸을 수 있음)
    for page in range(1, 4):
        url = f"https://www.gsmarena.com/news.php3?sPage={page}"
        try:
            response = requests.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            news_items = soup.select(".news-item")
            
            for item in news_items:
                # 기사 날짜 확인
                meta_line = item.select_one(".meta-line")
                if meta_line and TARGET_DATE in meta_line.text:
                    title = item.select_one("h3").text
                    link = item.select_one("a")['href']
                    article_url = f"https://www.gsmarena.com/{link}"
                    
                    print(f"✔️ {TARGET_DATE} 기사 발견: {title}")
                    
                    # AI에게 이 기사가 스마트폰 '신제품 출시' 기사인지 물어봄
                    check_prompt = f"기사 제목: '{title}'\n이 기사가 새로운 스마트폰의 공식 발표나 출시를 다루고 있나요? '예' 또는 '아니오'로만 답하세요."
                    is_release = ai_model.generate_content(check_prompt).text.strip()
                    
                    if "예" in is_release:
                        print(f"🚨 [감지] 신제품 출시 기사입니다! 스펙을 긁어옵니다...")
                        
                        # 기사 본문 스크랩
                        art_resp = requests.get(article_url, headers=headers)
                        art_soup = BeautifulSoup(art_resp.text, 'html.parser')
                        paragraphs = art_soup.select("#review-body p")
                        article_text = "\n".join([p.text for p in paragraphs])
                        
                        # AI를 이용해 본문에서 핵심 스펙 데이터 정제
                        spec_prompt = f"""
                        다음 기사에서 스마트폰의 핵심 스펙을 추출해 주세요.
                        기사 본문: {article_text[:2000]}
                        
                        출력 형식 (반드시 아래 양식을 지켜주세요):
                        모델명: [여기에 작성]
                        AP(칩셋): [여기에 작성]
                        디스플레이: [여기에 작성]
                        배터리: [여기에 작성]
                        카메라: [여기에 작성]
                        """
                        extracted_specs = ai_model.generate_content(spec_prompt).text
                        return {"model": title, "specs": extracted_specs, "url": article_url}
            time.sleep(1) # 크롤링 매너용 대기
        except Exception as e:
            print(f"⚠️ 크롤링 에러: {e}")
            
    print(f"⚠️ {TARGET_DATE}에 신제품 출시 기사가 없습니다.")
    return None

# ==========================================
# 💾 3. 구글 시트 '스펙_누적_데이터'에 저장
# ==========================================
def save_to_cumulative_sheet(device_data):
    if not device_data:
        return
    print("💾 [저장] 구글 시트 '스펙_누적_데이터' 탭에 새로운 스펙을 누적 기록합니다...")
    service = get_sheets_service()
    try:
        # 누적 데이터 시트(예: 시트 이름이 '스펙_누적_데이터'인 경우)에 행 추가
        range_name = "스펙_누적_데이터!A:F"
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        row_data = [
            current_date, 
            TARGET_DATE, 
            device_data['model'], 
            device_data['specs'], 
            device_data['url']
        ]
        
        body = {'values': [row_data]}
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID, 
            range=range_name,
            valueInputOption="USER_ENTERED", 
            body=body
        ).execute()
        print("✔️ 시트 누적 저장 완료!")
    except Exception as e:
        print(f"⚠️ 시트 저장 에러: {e}")

# ==========================================
# 📊 4. 골드 스탠다드 대조 및 인사이트 추출
# ==========================================
def generate_ai_insight(device_data):
    if not device_data:
        return "신제품 데이터가 없어 인사이트 분석을 건너뜁니다."
    print("🧠 [분석] 골드 스탠다드 대조 및 인사이트 도출 중...")
    
    service = get_sheets_service()
    benchmarks = "벤치마크 데이터를 불러오지 못했습니다."
    try:
        # 3번 시트 골드 스탠다드 불러오기
        result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range="골드_스탠다드!A1:AQ").execute()
        benchmarks_data = result.get('values', [])
        benchmarks = json.dumps(benchmarks_data[:3], ensure_ascii=False) # 상위 기준점만 전달
    except Exception:
        pass

    prompt = f"""
    당신은 글로벌 스마트폰 시장 분석가입니다.
    오늘(타겟일) 수집된 신제품 스펙과 프리미엄 벤치마크 기준(골드 스탠다드)을 대조하여 인사이트를 도출하세요.
    
    신제품 정보: {device_data['specs']}
    벤치마크 기준: {benchmarks}
    
    1. 신제품이 기존 벤치마크(삼성/애플 등) 대비 어떤 수치적 우위가 있는지
    2. 시장 타겟팅 관점에서 3줄 이내로 깔끔하게 정리해 주세요.
    """
    try:
        insight = ai_model.generate_content(prompt).text
        return insight
    except Exception as e:
        return f"⚠️ 인사이트 에러: {e}"

# ==========================================
# 🤖 메인 파이프라인
# ==========================================
if __name__ == "__main__":
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🤖 6월 29일 타임머신 테스트 가동 시작\n")
    
    # 1. 6월 29일 기사 탐색 및 스펙 추출
    device_data = find_and_extract_new_release()
    
    if device_data:
        print(f"\n📱 [추출된 데이터 요약]\n{device_data['specs']}\n")
        
        # 2. 구글 시트 누적 탭에 저장
        save_to_cumulative_sheet(device_data)
        
        # 3. 골드 스탠다드 비교 및 인사이트 생성
        insight = generate_ai_insight(device_data)
        
        # 4. 결과 출력 (실제 대시보드 갱신 로직이 들어갈 자리)
        print("\n--- 📝 대시보드 게시용 AI 요약 리포트 ---")
        print(insight)
        print("----------------------------------------\n")
        print("✅ 모든 파이프라인 실전 테스트가 성공적으로 완료되었습니다!")
    else:
        print("✅ 시스템 정상 작동: 해당 날짜에 부합하는 신제품 기사가 없습니다.")
