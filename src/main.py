import os
import json
import time
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
model = genai.GenerativeModel(
    model_name="gemini-3.1-flash-lite",
    tools="google_search_retrieval"
)

def get_sheets_service():
    creds_dict = json.loads(GCP_CREDENTIALS)
    creds = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return build('sheets', 'v4', credentials=creds)

# ---------------------------------------------------------
# 2. 골드 스탠다드(벤치마크) 불러오기 (맞춤형 스펙 + RAM)
# ---------------------------------------------------------
def get_gold_standards(service):
    print("🔍 [준비] 구글 시트에서 프리미엄 벤치마크 데이터를 불러옵니다 (맞춤형 스펙)...")
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
                "RAM": get_val(12), # RAM 항목 추가
                "배터리_용량": get_val(15),
                "카메라_화소": get_val(19),
                "디스플레이_특이사항": get_val(23),
                "화면크기": get_val(24)
            })
    return gold_standards

# ---------------------------------------------------------
# 3. 1단계: 신제품 감지 (Gemini 검색 그라운딩)
# ---------------------------------------------------------
def detect_new_releases():
    print("🌐 [1단계] Gemini 구글 검색을 통한 24시간 내 신제품 탐색 중...")
    prompt = """
    최근 24시간 동안 전 세계 스마트폰 시장에서 새롭게 '공식 발표(Announced)'되거나 '출시(Launched)'된 
    스마트폰 신제품이 있는지 구글 검색을 통해 찾아줘. 단순 루머나 유출(Leak) 기사는 철저히 제외해.
    만약 공식 발표된 신제품이 있다면 그 '모델명'들만 콤마(,)로 구분해서 텍스트로 적어줘. 
    만약 없다면 오직 '없음' 이라고만 대답해. 다른 부가적인 설명은 절대 쓰지 마.
    """
    try:
        response = model.generate_content(prompt)
        result = response.text.strip()
        
        if "없음" in result or not result:
            print("ℹ️ 오늘 새롭게 공식 발표된 스마트폰 신제품이 없습니다.")
            return []
        
        models = [m.strip() for m in result.split(",") if m.strip()]
        print(f"🚨 [감지 완료] 신제품 발견: {models}")
        return models
    except Exception as e:
        print(f"⚠️ [에러] 신제품 감지 중 문제 발생: {e}")
        return []

# ---------------------------------------------------------
# 4. 2단계: 맞춤형 스펙 추출 및 인사이트 분석
# ---------------------------------------------------------
def analyze_and_extract_specs(model_name, gold_standards):
    print(f"🧠 [2단계] '{model_name}' 맞춤형 스펙 검색 및 골드 스탠다드 대조 중...")
    
    # 벤치마크 텍스트 압축 (RAM 포함)
    benchmark_text = ""
    for g in gold_standards:
        benchmark_text += f"- {g['제조사']} {g['모델명']} (AP:{g['AP_모델명']}, RAM:{g['RAM']}, 배터리:{g['배터리_용량']}, 카메라:{g['카메라_화소']}, 디스플레이:{g['디스플레이_특이사항']}, 화면크기:{g['화면크기']})\n"
    
    prompt = f"""
    구글 검색을 활용하여 방금 발표된 스마트폰 '{model_name}'의 핵심 스펙만 빠르고 간결하게 검색해줘.
    반드시 검색해야 할 스펙 항목: 제조사, 제품레벨, 폼팩터, AP 모델명, RAM, 배터리 용량, 화면 크기, 전작 대비 개선점, 카메라 화소, 디스플레이 특이 사항.
    
    그리고 아래 제시된 [글로벌 벤치마크 모델들]의 핵심 스펙과 위에서 찾은 신제품의 스펙을 비교해서 우위점과 인사이트를 도출해.
    
    [글로벌 벤치마크 모델들 핵심 스펙]
    {benchmark_text}
    
    반드시 아래의 JSON 형식에 맞춰서 데이터만 정확하게 출력해. 다른 텍스트는 덧붙이지 마.
    {{
        "출시연월": "YYYY-MM 형태",
        "모델명": "{model_name}",
        "제조사": "",
        "제품레벨": "플래그십/중급형/보급형 중 택1",
        "폼팩터": "Bar/Foldable 중 택1",
        "AP_모델명": "",
        "RAM": "",
        "배터리_용량": "",
        "화면크기": "",
        "카메라_화소": "메인 카메라 위주로 간략히",
        "디스플레이_특이사항": "가장 눈에 띄는 디스플레이 특징 1줄 요약",
        "전작대비_개선점": "1줄 요약",
        "벤치마크_우위포인트": "골드 스탠다드 대비 스펙상 우위나 포지셔닝 전략을 2줄 이내로 서술"
    }}
    """
    try:
        response = model.generate_content(prompt)
        text_result = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text_result)
        return data
    except Exception as e:
        print(f"⚠️ [에러] '{model_name}' 스펙 분석 중 문제 발생: {e}")
        return None

# ---------------------------------------------------------
# 5. 구글 시트 맵핑 및 저장 (43열 구조에 맞춤)
# ---------------------------------------------------------
def save_to_sheets(service, data):
    print(f"💾 [3단계] '{data['모델명']}' 데이터를 구글 시트에 저장합니다...")
    
    # 1. 오늘의_신제품 시트에 추가
    today_row = [
        datetime.now().strftime("%Y-%m-%d"), 
        data.get("모델명", ""), 
        data.get("제조사", ""), 
        "-", 
        data.get("벤치마크_우위포인트", "")
    ]
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range="오늘의_신제품!A:E",
        valueInputOption="USER_ENTERED",
        body={"values": [today_row]}
    ).execute()

    # 2. 스펙_누적_데이터 시트에 추가 (추출한 항목만 정확한 인덱스에 매핑)
    spec_row = [""] * 43
    spec_row[0] = data.get("출시연월", "")
    spec_row[1] = data.get("모델명", "")
    spec_row[2] = data.get("제조사", "")
    spec_row[3] = data.get("제품레벨", "")
    spec_row[4] = data.get("폼팩터", "")
    spec_row[10] = data.get("AP_모델명", "")
    spec_row[12] = data.get("RAM", "") # RAM 저장 위치 맵핑
    spec_row[15] = data.get("배터리_용량", "")
    spec_row[19] = data.get("카메라_화소", "")
    spec_row[23] = data.get("디스플레이_특이사항", "")
    spec_row[24] = data.get("화면크기", "")
    spec_row[41] = data.get("전작대비_개선점", "")
    spec_row[42] = data.get("벤치마크_우위포인트", "")
    
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range="스펙_누적_데이터!A:AQ",
        valueInputOption="USER_ENTERED",
        body={"values": [spec_row]}
    ).execute()
    print("✅ 저장 완료!")
# ---------------------------------------------------------
# 메인 실행 파이프라인
# ---------------------------------------------------------
def main():
    print("🚀 스마트폰 인사이트 API 검색 엔진 가동 시작...")
    service = get_sheets_service()
    
    gold_standards = get_gold_standards(service)
    new_models = detect_new_releases()
    
    if not new_models:
        print("✅ 파이프라인 종료 (업데이트 사항 없음)")
        return
        
    for model_name in new_models:
        time.sleep(20) # ⏳ 구글 API 1분당 요청 제한(RPM) 회피를 위해 20초 대기
        spec_data = analyze_and_extract_specs(model_name, gold_standards)
        
        if spec_data:
            save_to_sheets(service, spec_data)

    print("🎉 모든 파이프라인 처리가 성공적으로 완료되었습니다!")

if __name__ == "__main__":
    main()
