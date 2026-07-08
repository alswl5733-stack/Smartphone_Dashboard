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

def fetch_article_text(url, max_paragraphs=15):
    try:
        res = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=12,
            allow_redirects=True
        )
        soup = BeautifulSoup(res.text, "html.parser")

        for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            tag.decompose()

        paragraphs = []
        for p in soup.find_all("p"):
            txt = re.sub(r"\s+", " ", p.get_text(" ", strip=True)).strip()
            if len(txt) >= 40:
                paragraphs.append(txt)

        return "\n".join(paragraphs[:max_paragraphs]).strip()

    except Exception:
        return ""


def build_detail_queries(model_name):
    return [
        f'"{model_name}" "specifications"',
        f'"{model_name}" "specs"',
        f'"{model_name}" "release date"',
        f'"{model_name}" "launch date"',
        f'"{model_name}" "processor" "battery" "camera"',
        f'"{model_name}" "display" "chipset" "camera"',
        f'"{model_name}" "price" "specifications"',
        f'"{model_name}" "official" "specifications"',
        f'"{model_name}" "GSMArena"',
        f'"{model_name}" "PhoneArena"',
        f'"{model_name}" "Notebookcheck"',
        f'"{model_name}" "Android Authority"',
    ]


def fetch_detailed_specs(model_name, intro_text):
    print(f"🔍 [{model_name}] 세부 스펙 2차 검색 중...")

    today_date = datetime.datetime.now().strftime("%Y년 %m월 %d일")
    collected_sources = []
    seen_links = set()

    try:
        queries = build_detail_queries(model_name)

        for q in queries[:10]:
            encoded_query = requests.utils.quote(q)
            url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

            try:
                response = requests.get(url, timeout=10)
                soup = BeautifulSoup(response.content, "xml")
                items = soup.find_all("item")
            except Exception:
                continue

            for item in items[:5]:
                title = item.title.text if item.title else ""
                link = item.link.text if item.link else ""

                if not link or link in seen_links:
                    continue

                seen_links.add(link)

                article_text = fetch_article_text(link, max_paragraphs=15)

                if len(article_text) < 250:
                    continue

                collected_sources.append({
                    "title": title,
                    "url": link,
                    "text": article_text[:3000]
                })

                print(f"  ㄴ 수집: {title[:80]}")

                if len(collected_sources) >= 10:
                    break

                time.sleep(2)

            if len(collected_sources) >= 10:
                break

            time.sleep(2)

        if not collected_sources:
            return f"""
모델명: {model_name}
출시 상태: 기사 내 확인 불가
발표 연월: 기사 내 확인 불가
출시 연월: 기사 내 확인 불가
AP(칩셋): 기사 내 확인 불가
디스플레이: 기사 내 확인 불가
배터리: 기사 내 확인 불가
카메라: 기사 내 확인 불가
가격: 기사 내 확인 불가
정보 신뢰도: 낮음
세부정보 부족 여부: 매우 부족
근거 요약:
- 세부 스펙을 확인할 수 있는 충분한 출처를 찾지 못했습니다.
"""

        source_text = f"[Initial Detection Article]\n{intro_text[:2500]}\n\n"

        for idx, src in enumerate(collected_sources):
            source_text += f"""
[Source {idx + 1}]
Title: {src["title"]}
URL: {src["url"]}
Text:
{src["text"]}

"""

        spec_prompt = f"""
현재 날짜는 {today_date}입니다.

아래는 '{model_name}'에 대해 수집된 기사/웹 문서 내용입니다.

{source_text[:22000]}

당신은 스마트폰 신제품 세부 정보를 추출하는 분석가입니다.

규칙:
1. 제공된 본문에 명시된 정보만 사용하세요.
2. 본문에 없는 스펙은 추정하지 말고 "기사 내 확인 불가"라고 쓰세요.
3. rumored, leaked, expected, tipped, reportedly, likely, may, could 등의 표현이 붙은 정보는 "루머/예상"으로 표시하세요.
4. 공식 발표, 제조사 발표, 출시 기사에서 명확히 언급된 정보만 "확정"으로 표시하세요.
5. 서로 다른 출처의 정보가 충돌하면 "출처 간 불일치"라고 표시하세요.
6. 출시일과 발표일을 구분하세요.
7. 상대 날짜는 현재 날짜 {today_date} 기준으로 계산하세요.

출력 형식:
모델명: {model_name}
출시 상태: 공식 출시 / 공식 발표 / 사전예약 / 루머·유출 / 기사 내 확인 불가
발표 연월:
출시 연월:
AP(칩셋):
디스플레이:
배터리:
카메라:
가격:
주요 특징:
정보 신뢰도: 높음 / 중간 / 낮음
세부정보 부족 여부: 충분 / 일부 부족 / 매우 부족
근거 요약:
-
참고 출처:
-
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
