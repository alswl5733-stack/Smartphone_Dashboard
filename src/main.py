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
# 📡 2. 구글 뉴스 일괄 스캔 (50개 묶음 & 6/27 테스트)
# ==========================================
def find_and_extract_new_release():
    print("📡 [수집] 6월 27일 테스트 가동: 구글 뉴스에서 기사 50개를 한 번에 스캔합니다...")
    
    # 6월 27일 아침 8시 상황을 시뮬레이션하기 위해 6월 25일~28일 사이의 기사를 검색
    query = "smartphone (launch OR announcement OR official specs) after:2026-06-25 before:2026-06-28"
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    
    try:
        response = requests.get(url, timeout=10)
        # RSS 파싱을 위해 xml 파서 사용
        soup = BeautifulSoup(response.content, 'xml') 
        items = soup.find_all('item')
        
        if not items:
            print("⚠️ 검색된 기사가 없습니다.")
            return None
            
        target_items = items[:50]
        print(f"▶️ 관련 기사 {len(target_items)}개 발견! AI에게 한 번에 던져 필터링을 시작합니다... (API 호출 1회)")
        
        # 50개의 제목을 하나의 텍스트로 예쁘게 묶기
        titles_text = ""
        for i, item in enumerate(target_items):
            titles_text += f"[{i}] {item.title.text}\n"
            
        batch_prompt = f"""
        당신은 스마트폰 트렌드 분석가입니다. 다음은 구글 뉴스에서 수집한 스마트폰 관련 기사 제목 {len(target_items)}개입니다.
        이 중에서 주요 스마트폰(삼성, 애플, 구글, 샤오미, 비보, 오포, 화웨이 등)의 새로운 '공식 신제품 발표'나 '공식 스펙 공개'를 다루고 있는 기사의 번호만 골라주세요.
        단순 루머, 케이스 유출, 칩셋 단독 발표, 출시 국가 확대 소식은 무시하세요.
        해당하는 기사가 없다면 '없음'이라고 답하고, 있다면 '[번호]' 형식으로만 답해주세요. (예: [3])
        
        기사 목록:
        {titles_text}
        """
        
        filter_result = ai_model.generate_content(batch_prompt).text.strip()
        print(f"  ㄴ 🤖 AI 판단 결과: {filter_result}")
        
        # 정규식으로 [숫자] 형태의 번호만 쏙 뽑아내기
        matched_indices = re.findall(r'\[(\d+)\]', filter_result)
        
        if not matched_indices:
            print("✔️ 50개의 기사 중 '공식 신제품 출시'에 해당하는 기사는 없었습니다.")
            return None
            
        # 첫 번째로 발견된 신제품 기사의 번호 채택
        target_index = int(matched_indices[0])
        if target_index >= len(target_items):
            return None
            
        selected_item = target_items[target_index]
        title = selected_item.title.text
        link = selected_item.link.text
        
        print(f"\n🚨 [감지 성공] {target_index}번 기사 채택: {title}\n본문 및 스펙 추출을 시작합니다... (API 호출 2회차)\n")
        
        # 기사 본문 스크랩
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            art_resp = requests.get(link, headers=headers, timeout=10)
            art_soup = BeautifulSoup(art_resp.text, 'html.parser')
            article_text = "\n".join([p.text for p in art_soup.find_all('p')])
        except Exception:
            article_text = "본문 수집 지연. 기사 제목을 바탕으로 스펙을 추론합니다."

        spec_prompt = f"다음 스마트폰 출시 기사에서 핵심 스펙을 추출해 주세요.\n제목: {title}\n본문: {article_text[:2000]}\n\n출력 형식:\n모델명:\nAP(칩셋):\n디스플레이:\n배터리:\n카메라:"
        extracted_specs = ai_model.generate_content(spec_prompt).text
        
        return {"model": title, "specs": extracted_specs, "url": link}

    except Exception as e:
        print(f"⚠️ 에러 발생: {e}")
        return None

# ==========================================
# 📊 3. 골드 스탠다드 대조 및 인사이트 추출
# ==========================================
def generate_ai_insight(device_data):
    if not device_data: return "신제품이 감지되지 않았습니다."
    print("🧠 [분석] 골드 스탠다드 대조 및 인사이트 도출 중... (API 호출 3회차)")
    service = get_sheets_service()
    benchmarks = "벤치마크 데이터를 불러오지 못했습니다."
    try:
        result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range="골드_스탠다드!A1:AQ").execute()
        benchmarks = json.dumps(result.get('values', [])[:3], ensure_ascii=False)
    except Exception: pass

    prompt = f"""
    당신은 글로벌 스마트폰 시장 분석가입니다.
    오늘 수집된 신제품 스펙과 프리미엄 벤치마크 기준(골드 스탠다드)을 대조하여 인사이트를 도출하세요.
    신제품 정보: {device_data['specs']}
    벤치마크 기준: {benchmarks}
    
    1. 신제품이 기존 벤치마크(삼성/애플 등) 대비 어떤 수치적 우위가 있는지
    2. 시장 타겟팅 관점에서 3줄 이내로 깔끔하게 정리해 주세요.
    """
    try:
        return ai_model.generate_content(prompt).text
    except Exception as e:
        return f"⚠️ 인사이트 에러: {e}"

# ==========================================
# 💾 4. 구글 시트 동시 누적 저장 (스펙 & 오늘의 신제품)
# ==========================================
def save_to_cumulative_sheet(device_data, insight_text):
    if not device_data: return
    print("💾 [저장] 구글 시트 2곳에 데이터를 동시에 누적 기록합니다...")
    service = get_sheets_service()
    if not service: return
    try:
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        range_name_accum = "스펙_누적_데이터!A:F"
        row_data_accum = [current_date, "Google News (Batch 50)", device_data['model'], device_data['specs'], device_data['url']]
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID, range=range_name_accum,
            valueInputOption="USER_ENTERED", body={'values': [row_data_accum]}
        ).execute()

        range_name_today = "오늘의_신제품!A:E"
        row_data_today = [current_date, device_data['model'], "AI 감지 (일괄)", device_data['url'], insight_text]
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID, range=range_name_today,
            valueInputOption="USER_ENTERED", body={'values': [row_data_today]}
        ).execute()
        
        print("✔️ 시트 2곳 누적 저장 완료!")
    except Exception as e:
        print(f"⚠️ 시트 저장 에러: {e}")

# ==========================================
# 🤖 메인 파이프라인
# ==========================================
if __name__ == "__main__":
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🤖 스마트폰 인사이트 봇 가동 (일괄 필터링 & 6/27 테스트)")
    
    device_data = find_and_extract_new_release()
    
    if device_data:
        print(f"\n📱 [추출된 데이터 요약]\n{device_data['specs']}\n")
        insight = generate_ai_insight(device_data)
        save_to_cumulative_sheet(device_data, insight)
        
        print("\n--- 📝 대시보드 게시용 AI 요약 리포트 ---")
        print(insight)
        print("----------------------------------------\n")
        print("✅ 모든 데이터 파이프라인이 성공적으로 완료되었습니다!")
    else:
        print("✅ 시스템 정상 작동: 지정된 기간 내에 출시된 신제품이 없습니다.")
