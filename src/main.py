import os
import google.generativeai as genai

def run_diagnostic():
    print("🔍 [진단 시작] 깃허브 금고의 Gemini API 출입증 상태를 점검합니다...")
    
    gemini_key = os.environ.get("GEMINI_API_KEY")
    
    if not gemini_key:
        print("❌ 에러: GEMINI_API_KEY 금고가 비어있습니다.")
        return

    # AIza 검사 로직 삭제 (AQ 키 정상 인식)
    print(f"✔️ 출입증(API Key) 인식 완료! (시작 부분: {gemini_key[:4]}... 길이는 {len(gemini_key)}자)")
    
    try:
        print("📡 구글 서버에 접속하여 이 출입증으로 사용 가능한 모델 목록을 요청합니다...\n")
        genai.configure(api_key=gemini_key)
        
        print("--- 📋 현재 출입증으로 사용 가능한 모델 리스트 ---")
        available_models = False
        
        # 구글 서버에서 디렉터님의 키로 쓸 수 있는 모든 모델 목록을 가져옵니다.
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"  ✅ {m.name}")
                available_models = True
                
        if not available_models:
            print("⚠️ 텍스트 생성 모델이 없습니다. 프로젝트에 Gemini API 사용 설정이 안 되어 있을 수 있습니다.")
        else:
            print("--------------------------------------------------")
            print("💡 진단 결과: 위 리스트에 나온 이름(예: models/gemini-1.5-flash)을 사용하면 무조건 작동합니다!")
            
    except Exception as e:
        print(f"❌ 구글 서버 통신 중 치명적 에러 발생: {e}")

if __name__ == "__main__":
    run_diagnostic()
