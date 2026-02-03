import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

GEMINI_MODEL_NAME = "gemini-2.5-flash"

SYSTEM_INSTRUCTION_SCRIPT = """
당신은 R&D 과제 발표 전문가입니다.
제공된 PPT 슬라이드 내용을 바탕으로 실전 발표용 대본과 예상 질문 답변을 작성하세요.

[작성 원칙]
1. 각 슬라이드별로 자연스러운 발표 대본 작성
2. 청중을 고려한 명확하고 설득력 있는 표현
3. 기술적 용어는 쉽게 풀어서 설명
4. 발표 시간을 고려한 적절한 분량
5. 예상 질문은 실제 평가위원이 물을 만한 핵심 사항 중심

[출력 형식]
JSON 형식으로 다음 구조를 준수:
{
  "slides": [
    {
      "page": 1,
      "title": "슬라이드 제목",
      "script": "발표 대본 (3-5문장)"
    }
  ],
  "qna": [
    {
      "question": "예상 질문",
      "answer": "모범 답변",
      "tips": "답변 시 유의사항"
    }
  ]
}
"""

def generate_script_and_qna(ppt_text: str) -> dict:
    """
    PPT 텍스트를 기반으로 발표 대본 및 Q&A 생성
    
    Args:
        ppt_text: PPT에서 추출한 텍스트 (슬라이드별로 구조화된 형태)
    
    Returns:
        dict: 슬라이드별 대본과 Q&A가 포함된 JSON 객체
              {
                "slides": [{"page": 1, "title": "...", "script": "..."}],
                "qna": [{"question": "...", "answer": "...", "tips": "..."}]
              }
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[오류] GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
        return None
    
    client = genai.Client(api_key=api_key)
    
    # 프롬프트 구성
    prompt = f"""
아래 PPT 내용을 바탕으로 실전 발표용 대본과 예상 질문/답변을 JSON 형식으로 생성하세요.

[PPT 내용]
{ppt_text}

[요구사항]
1. 각 슬라이드마다 발표 대본 작성 (자연스럽고 설득력 있게)
2. 전체 발표를 고려한 예상 질문 5개 이상 작성
3. 각 질문에 대한 모범 답변과 답변 시 유의사항 포함
4. 반드시 유효한 JSON 형식으로만 출력 (코드 블록 없이)

[JSON 구조]
{{
  "slides": [
    {{"page": 1, "title": "제목", "script": "대본 내용"}}
  ],
  "qna": [
    {{"question": "질문", "answer": "답변", "tips": "유의사항"}}
  ]
}}
"""
    
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION_SCRIPT,
                temperature=0.5
            )
        )
        
        text = response.text.strip()
        
        # JSON 코드 블록 제거
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        
        # JSON 파싱
        result = json.loads(text.strip())
        return result
        
    except json.JSONDecodeError as e:
        print(f"[오류] JSON 파싱 실패: {e}")
        print(f"응답 내용:\n{text[:500]}...")
        return None
    except Exception as e:
        print(f"[오류] 대본 생성 실패: {e}")
        import traceback
        traceback.print_exc()
        return None
