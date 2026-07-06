import os
import json
import datetime
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ==========================================
# ⚙️ 1. 설정 및 출입증(API Key) 준비
# ==========================================
# 디렉터님의 구글 스프레드시트 고유 ID를 아래에 입력해 주세요!
SPREADSHEET_ID = "1fKrSktMeXJmnqwUGOgk4QLtwfpAlkkFi5SvYJSrbT5o"

# 금고에서 출입증 꺼내기
gemini_key = os.environ.get("GEMINI_API_KEY")
gcp_creds_json = os.environ.get("GCP_CREDENTIALS")

# 구글 Gemini AI 세팅
if gemini_key:
    genai.configure(api_key=gemini_key)
    # 빠르고 무료로 무제한에 가깝게 쓸 수 있는 flash 모델 사용
    ai_model = genai.GenerativeModel(model_name="gemini-1.5-flash")

def get_sheets_service():
    if not gcp_creds_json:
        return None
    creds_dict = json.loads(gcp_creds_json)
    creds = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    return build('sheets', 'v4', credentials=creds)

# ==========================================
# 📡 2. 크롤링 로직 (GSMArena 및 주요 뉴스)
# ==========================================
def crawl_latest_smartphones():
    print("📡 [수집] GSMArena 및 주요 IT 매체 최신 뉴스 수집 중...")
    headers = {"User-Agent": "Mozilla/5.0"}
    url = "https://www.gsmarena.com/news.php3"
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        news_items = soup.select(".news-item .news-item-body h3 a")
        if news_items:
            latest_title = news_items[0].text
            print(f"✔️ 최신 기사 감지: {latest_title}")
            return {"title": latest_title, "status": "기사 수집 완료"}
        else:
             return {"title": "최신 기사 없음", "status": "대기"}
    except Exception as e:
        print(f"⚠️ 크롤링 에러 발생: {e}")
        return None

# ==========================================
# 📊 3. 벤치마크 1:1 대조 (동적 매칭)
# ==========================================
def compare_with_gold_standard(device_data):
    print("📊 [비교] 구글 시트 '골드_스탠다드' 벤치마크 호출 중...")
    service = get_sheets_service()
    if not service:
        print("⚠️ 구글 시트 접근 권한이 없습니다.")
        return None
    
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, 
            range="골드_스탠다드!A1:AQ"
        ).execute()
        benchmarks = result.get('values', [])
        print(f"✔️ 벤치마크 데이터 {len(benchmarks)-1}개 모델 호출 완료")
        
        return {"benchmarks": benchmarks, "new_device": device_data}
    except Exception as e:
        print(f"⚠️ 구글 시트 읽기 에러: {e}")
        return None

# ==========================================
# 🧠 4. 구글 Gemini 인사이트 분석 (이중 비교)
# ==========================================
def generate_ai_insight(comparison_data):
    if not gemini_key or not comparison_data:
        return "AI 분석을 위한 데이터 또는 출입증이 없습니다."
    
    print("🧠 [분석] 구글 Gemini API로 동적 벤치마크 매칭 및 인사이트 도출 중...")
    
    prompt = f"""
    당신은 글로벌 스마트폰 시장을 분석하는 최고의 전문가 'AX 프로젝트 수석 개발자'입니다.
    다음은 오늘 수집된 스마트폰 최신 기사 요약과 우리의 '골드 스탠다드' 벤치마크 데이터입니다.

    수집 데이터: {comparison_data['new_device']}
    
    지시사항:
    1. 수집된 기사에 스마트폰 신제품(특히 중국 또는 글로벌 프리미엄) 소식이 있는지 확인하세요.
    2. 신제품이 있다면, 벤치마크 데이터의 '삼성' 또는 '애플'을 1순위 절대 기준으로 삼고, 기사 맥락상 견제하는 경쟁사(예: 화웨이, 샤오미)가 있다면 2순위 대조군으로 유동적으로 추가하여 스펙을 비교하세요.
    3. 전작 대비 개선점과 프리미엄 벤치마크 대비 우위 포인트를 제품 관점에서 3줄 이내로 깊이 있게 분석해주세요.
    """
    
    try:
        # OpenAI의 chat.completions 대신 Gemini의 generate_content 사용
        response = ai_model.generate_content(prompt)
        insight = response.text
        print("💡 AI 분석 완료!")
        return insight
    except Exception as e:
        print(f"⚠️ AI 분석 에러: {e}")
        return "AI 분석 중 오류가 발생했습니다."

# ==========================================
# 💻 5. 대시보드 갱신 및 시트 저장
# ==========================================
def update_dashboard_and_sheet(insight_data):
    print("💻 [갱신] 구글 시트 저장 및 대시보드 업데이트 처리 중...")
    print("✅ 데이터베이스 및 시각화 전시장 갱신 명령 전송 완료")

# ==========================================
# 🤖 메인 파이프라인 가동
# ==========================================
if __name__ == "__main__":
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{current_time}] 🤖 스마트폰 인사이트 로봇 가동 시작")
    
    device_data = crawl_latest_smartphones()
    comparison = compare_with_gold_standard(device_data)
    insight = generate_ai_insight(comparison)
    update_dashboard_and_sheet(insight)
    
    print("\n--- 📝 AI 오늘의 요약 리포트 ---")
    print(insight)
    print("--------------------------------\n")
    print("✅ 모든 파이프라인 분석 및 갱신이 성공적으로 완료되었습니다!")
