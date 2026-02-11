import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

GEMINI_MODEL_NAME = "gemini-2.5-flash"

SYSTEM_INSTRUCTION_SCRIPT = """ 당신은 R&D 과제 발표 및 전략 기획 전문가입니다. 제공된 PPT 내용을 바탕으로 대본을 작성하기 전, 반드시 다음의 [내부 사고 단계]를 거쳐 논리적이고 설득력 있는 내용을 구성하세요. [내부 사고 단계 (Chain of Thought)] 1. 분석: 각 슬라이드의 핵심 키워드와 발표자가 전달하고자 하는 '최종 목표'를 파악합니다. 2. 연결: 슬라이드 간의 매끄러운 흐름(Bridge)을 설계하여 전체가 하나의 이야기처럼 들리게 합니다. 3. 페르소나 적용: 기술적 전문성을 유지하되, 평가위원이 이해하기 쉬운 비유와 평이한 용어로 변환 전략을 세웁니다. 4. 비판적 검토: '내가 평가위원이라면 어느 부분이 의심스러울까?'를 고민하여 기술적 허점이나 사업성 지표에 대한 날카로운 질문을 도출합니다. 5. 최적화: 발표 시간을 고려하여 대본의 호흡을 조절하고 핵심 메시지가 누락되지 않았는지 확인합니다. [작성 원칙] 1. 각 슬라이드별 자연스러운 구어체 대본 (3-5문장) 2. 청중의 몰입을 돕는 매끄러운 문장 연결 3. 어려운 기술 용어는 반드시 쉬운 개념으로 풀어서 설명 4. 예상 질문은 '기술적 차별성', '현실적 한계', '기대 효과'를 중심으로 선정 [출력 형식] 반드시 아래 구조의 유효한 JSON 형식으로만 응답하세요. (사고 과정은 출력하지 말고 최종 JSON만 출력) {   "slides": [     { "page": 1, "title": "슬라이드 제목", "script": "발표 대본" }   ],   "qna": [     { "question": "예상 질문", "answer": "모범 답변", "tips": "답변 시 유의사항" }   ] } """


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
    prompt = f""" 아래 PPT 텍스트 데이터의 맥락을 깊이 있게 분석하여 실전 발표용 리포트를 생성하세요. [PPT 내용]{ppt_text} [생성 가이드라인] 1. 분석 단계: 각 슬라이드의 데이터(수치, 기술명 등)를 철저히 분석할 것 2. 구성 단계: 서론-본론-결론의 논리적 완결성을 갖춘 대본을 작성할 것 3. Q&A 단계: 질문 5개 이상을 도출하되, 실제 R&D 심사장에서 나올 법한 날카로운 질문을 포함할 것 4. 최종 제약: 반드시 JSON 형식만 출력하고, 다른 설명 문구는 생략할 것 [JSON 구조 준수] {{   "slides": [     {{"page": 1, "title": "제목", "script": "내용"}}   ],   "qna": [     {{"question": "질문", "answer": "답변", "tips": "유의사항"}}   ] }} """
    
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
