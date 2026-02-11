#search_llm.py
import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# [설정] 2.0-flash 모델 사용 (가장 안정적)
GEMINI_MODEL_NAME = "gemini-2.5-flash" 

SYSTEM_INSTRUCTION_SEARCH = """
당신은 국가 R&D 전략기획 전문가입니다.
사용자가 입력한 [신규 기획 과제]와 ChromaDB에서 검색된 [기존 전략계획서 내용]을 비교 분석하십시오.

검색된 자료는 'Track A(동일 부처)'와 'Track B(타 부처)'로 명확히 구분됩니다.
분석 결과 역시 이 두 가지 Track을 구분하여 제시해야 합니다.

[출력 필독]
반드시 아래 JSON 포맷으로만 응답하세요. (마크다운 ```json 사용 금지)
{
  "summary_opinion": "전략계획서 분석 결과, 본 과제는 [~~] 측면에서 기존 전략과 차별화가 필수적임 (3줄 요약)",
  "track_a_comparison": [
    {
      "year": "연도",
      "ministry": "부처",
      "title": "유사 전략/과제명",
      "similarity": "상/중/하",
      "difference": "기존 [~~] 전략은 인프라 구축 위주였으나, 본 과제는 [~~] 알고리즘 고도화에 집중함 (본문 기반 차이점)"
    }
  ],
  "track_b_comparison": [
    {
      "year": "연도",
      "ministry": "부처",
      "title": "유사 전략/과제명",
      "similarity": "상/중/하",
      "difference": "타 부처 과제는 [~~] 분야에 특화되어 있어 본 과제와는 [~~] 측면에서 차이가 있음"
    }
  ],
  "strategies": [
    "전략 1: (구체적 차별화 방안)",
    "전략 2: (기술적 중복 회피 방안)",
    "전략 3: (기대 효과 및 연계 방안)"
  ]
}
"""

def summarize_report(new_project_info: dict, track_a: list, track_b: list) -> dict:
    """
    RAG 기반 분석: 신규 과제 vs (Track A + Track B) 전략계획서 본문
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key: return {"error": "No API Key"}

    client = genai.Client(api_key=api_key)
    
    # Context 텍스트 구성
    context_text = ""
    
    # 1. Track A (동일 부처) 데이터 처리
    if track_a:
        context_text += "\n[Track A: 동일 부처 유사 전략 (중복성 집중 검토)]\n"
        for item in track_a:
            meta = item.get('metadata', {})
            content = item.get('document', '')[:500] 
            
            title = meta.get('title', '제목 없음')
            year = meta.get('year', '연도미상')
            ministry = meta.get('ministry', '부처미상')
            
            context_text += f"- {title} ({year}, {ministry}): {content}\n"
    else:
        context_text += "\n[Track A: 동일 부처 유사 전략 없음]\n"

    # 2. Track B (타 부처) 데이터 처리
    if track_b:
        context_text += "\n[Track B: 타 부처 유사 전략 (차별성 집중 검토)]\n"
        for item in track_b:
            meta = item.get('metadata', {})
            content = item.get('document', '')[:500]
            
            title = meta.get('title', '제목 없음')
            year = meta.get('year', '연도미상')
            ministry = meta.get('ministry', '부처미상')
            
            context_text += f"- {title} ({year}, {ministry}): {content}\n"
    else:
        context_text += "\n[Track B: 타 부처 유사 전략 없음]\n"

    prompt = f"""
    # [임무] 신규 R&D 과제 차별화 전략 수립

    ## 1. 분석 대상 (신규 과제)
    - 과제명: {new_project_info.get('project_name')}
    - 개요: {new_project_info.get('summary')}

    ## 2. 기존 전략계획서 내용 (Context)
    아래 내용을 바탕으로 Track A(동일 부처)와 Track B(타 부처)를 구분하여 분석하시오.

    {context_text}

    위 자료를 바탕으로 정의된 JSON 포맷에 맞춰 보고서를 작성하시오.
    """

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION_SEARCH,
                response_mime_type="application/json",
                temperature=0.3
            )
        )
        return json.loads(response.text)

    except Exception as e:
        print(f"[LLM Error] {str(e)}")
        return {
            "summary_opinion": "AI 분석 중 오류가 발생했습니다.",
            "track_a_comparison": [],
            "track_b_comparison": [],
            "strategies": ["서버 오류로 인해 전략을 도출할 수 없습니다."]
        }