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
        "tomorrow_query": tomorrow.strftime("%Y-%m-%d")    
    }

def detect_new_releases():
    dates = get_kst_dates()
    print(f"📡 [1단계: 정찰] 검색망({dates['yesterday_query']} ~ {dates['tomorrow_query']}) 내의 기사를 검사합니다...")
    
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
            
            if any(w in title.lower() for w in ['rumor', 'concept', 'reportedly']):
                continue
                
            try:
                art_resp = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                art_soup = BeautifulSoup(art_resp.text, 'html.parser')
                article_text = "\n".join([p.text for p in art_soup.find_all('p')[:3]])
            except Exception:
                article_text = "본문 수집 불가"

            check_prompt = f"""
            당신은 수석 모바일 상품기획자의 스마트폰 신제품 감별사입니다.
            
            기사 제목: '{title}'
            초반부: '{article_text}'
            
            이 기사가 스마트폰 신제품의 공식 발표일이나 출시 행사를 다루고 있나요?

            <유연한 판별 기준>
            1. 출시 행사를 시청하는 법(How to watch), 오늘 글로벌 런칭 이벤트(Global launch event today) 등은 제품이 오늘 공개된다는 팩트이므로 인정합니다.
            2. [지각 출시 필터링] 과거에 이미 출시된 폰이 특정 국가에 뒤늦게 런칭하는 기사는 무조건 '아니오'로 답하세요.
            3. 예정(Expected), 유출(Leak), 루머(Rumor) 등 아직 발표되지 않은 소식은 '아니오'로 답하세요.
            4. 기사 내용이 제품의 공식적인 최초 등장이나 발표를 다룬다면 인정하세요.

            위 기준에 미달하면 '아니오'라고 답하고, 신제품이 맞다면 모델명만 정확히 적으세요. '예'나 다른 문장은 절대 포함하지 말고 오직 결과값(모델명)만 출력하세요.
            """
            
            ai_response = lite_model.generate_content(check_prompt).text.strip()
            
            cleaned_name = ai_response.replace("예,", "").replace("Yes,", "").replace("예", "").replace("Yes", "").strip()
            
            if "아니오" not in ai_response and len(cleaned_name) > 2:
                model_name = cleaned_name
                print(f"  ㄴ 🚨 실제 소식 확인됨: {model_name}")
                found_models.append({"model_name": model_name, "primary_url": link, "intro_text": article_text})
                
            time.sleep(5) 
            
        return found_models
    except Exception as e:
        print(f"⚠️ 정찰 에러 발생: {e}")
        return []

def fetch_usp_and_target(model_name, intro_text):
    print(f"🧠 [{model_name}] 기사 심층 분석 및 인사이트 도출 중 (Pro 모델 가동)...")
    
    raw_query = f'"{model_name}" (launch OR feature OR market OR target OR premium OR price OR strategy)'
    search_query = urllib.parse.quote(raw_query)
    url = f"https://news.google.com/rss/search?q={search_query}&hl=en-US&gl=US&ceid=US:en"
    combined_text = intro_text + "\n"
    
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'xml')
        items = soup.find_all('item')
        
        for item in items[:4]:
            try:
                res = requests.get(item.link.text, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                art_soup = BeautifulSoup(res.text, 'html.parser')
                elements = art_soup.find_all(['p', 'h1', 'h2', 'li'])
                extracted_texts = [el.text.strip() for el in elements if len(el.text.strip()) > 10]
                combined_text += "\n".join(extracted_texts[:40]) + "\n"
            except: pass
            time.sleep(3) 
            
        usp_prompt = f"""
        수집된 정보 (최대 10,000자): {combined_text[:10000]}
        
        위 글로벌 출시 기사들을 바탕으로 '{model_name}'의 마케팅 전략 핵심 요소를 추출해 주세요.
        당신은 수석 모바일 상품기획자입니다. 철저히 비즈니스 관점에서 분석하세요.
        
        출력 형식:
        제조사:
        모델명: {model_name}
        주요 타겟 고객층: 
        핵심 셀링 포인트(USP): 
        가격대 및 포지셔닝: 
        제품 인사이트 요약(1줄): 
        """
        result = pro_model.generate_content(usp_prompt).text
        time.sleep(5)
        return result
    except Exception as e:
        return f"전략 분석 실패: {e}"

def save_to_cumulative_sheet(model_name, strategy_text, url):
    service = get_sheets_service()
    if not service: return
    try:
        # 💡 [테스트용 타임머신] 
        current_date = "2026-07-08"
        
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID, range="스펙_누적_데이터!A:F",
            valueInputOption="USER_ENTERED", body={'values': [[current_date, "Google News Deep Dive", model_name, strategy_text, url]]}
        ).execute()
    except Exception as e: 
        print(f"⚠️ 시트 저장 에러: {e}")

if __name__ == "__main__":
    print(f"[2026-07-08 12:00:00] 🚀 명시적 날짜 & 출시 임박 포함 신제품 분석 파이프라인 가동 (타임머신 테스트 모드)")
    
    final_target_models = detect_new_releases()
    
    if final_target_models:
        print(f"\n총 {len(final_target_models)}건의 소식(출시 임박 포함) 마케팅 전략 분석을 시작합니다.")
        
        # 💡 동일한 런타임(오늘 한 번 도는 동안) 내에서의 단순 중복 기사 방지용
        analyzed_models = set()
        
        for device in final_target_models:
            clean_name = device['model_name'].strip().lower()
            if clean_name in analyzed_models:
                continue
            analyzed_models.add(clean_name)
            
            strategy_info = fetch_usp_and_target(device['model_name'], device['intro_text'])
            print(f"  ㄴ {device['model_name']} 분석 완료")
            save_to_cumulative_sheet(device['model_name'], strategy_info, device['primary_url'])
            print(f"✔️ {device['model_name']} 기획 전략 시트 저장 완료")
        
        print("\n✅ 모든 상품기획 파이프라인 처리가 성공적으로 완료되었습니다!")
    else:
        print("\n✅ 시스템 정상 작동: 오늘(최근 2일 이내) 새롭게 추가할 신제품 소식이 없습니다.")
