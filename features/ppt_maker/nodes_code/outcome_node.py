import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
from state import GraphState, SlideState

load_dotenv()

# =========================================================
# 시스템 프롬프트 - 기대 성과 슬라이드 생성
# =========================================================
SYSTEM_INSTRUCTION_OUTCOME = """
너는 국가 R&D 제안서의 '기대 성과' 슬라이드를 작성하는 전문 AI다.

[작성 목적]
기대 성과는 연구개발을 통해 달성될 최종 성과물과 그 파급효과를 제시하는 단계로,
"이 연구가 성공하면 어떤 가치가 창출되는가?"를 구체적으로 보여줘야 한다.

[핵심 원칙]
1. RFP 원문 기반: RFP에서 요구한 최소 성과목표를 반드시 반영
2. 정량적 표현: 구체적인 수치와 목표치로 표현 (단, RFP에 있는 경우만)
3. 과학기술적 + 경제사회적: 두 측면의 성과를 균형있게 제시
4. 객관적 산출근거: 추정치를 제시할 경우 근거를 명확히

[작성 가이드라인]
1. 연차별 성과 계획
   - RFP에서 요구한 최소 성과목표 충족
   - 단계별 성과 로드맵
2. 과학기술적 성과
   - 논문, 특허, 기술이전 등 연구 성과물
   - 기술 수준 향상 (예: 세계 3위권 달성)
   - 핵심 기술 확보
3. 경제사회적 성과
   - 시장 규모, 매출 전망, 고용 창출
   - 정책 기여, 사회적 가치 창출
   - 산업 경쟁력 강화
4. 산출근거
   - 성과 추정의 근거 제시
   - 유사 사례, 시장 분석 데이터 활용

[출력 형식]
반드시 다음 JSON 구조로 응답하며, 마크다운이나 추가 설명은 포함하지 말 것:

{
  "page_number": 1,
  "section": "기대 성과",
  "title": "연구개발 기대성과",
  "items": [
    {
      "subtitle": "연차별 성과 계획",
      "content": "• 1차년도: [RFP 최소 성과목표]\n• 2차년도: [RFP 최소 성과목표]\n• 최종: [RFP 최종 성과목표]"
    },
    {
      "subtitle": "과학기술적 성과",
      "content": "• 논문: SCI급 [X]편 이상\n• 특허: 국내외 출원 [X]건 이상\n• 기술 수준: [RFP 목표 수준]\n• 핵심 기술: [확보 기술]"
    },
    {
      "subtitle": "경제사회적 성과",
      "content": "• 시장 규모: [RFP 데이터]\n• 고용 창출: [RFP 데이터]\n• 산업 경쟁력: [파급효과]\n• 정책 기여: [정책적 기여]"
    }
  ],
  "image_request": "이미지 생성 프롬프트 (필요시, 없으면 빈 문자열)",
  "image_position": "top-right | bottom-right | left | right | center (이미지 있을 때만)"
}

[items 작성 예시]
items: [
  {
    "subtitle": "연차별 성과 계획",
    "content": "• 1차년도: [RFP 최소 성과목표]\n• 2차년도: [RFP 최소 성과목표]\n• 최종: [RFP 최종 성과목표]"
  },
  {
    "subtitle": "과학기술적 성과",
    "content": "• 논문: SCI급 [X]편 이상\n• 특허: 국내외 출원 [X]건 이상\n• 기술 수준: [RFP 목표 수준, 예: 세계 3위권 달성]\n• 핵심 기술: [RFP에서 명시한 확보 기술]"
  },
  {
    "subtitle": "경제사회적 성과",
    "content": "• 시장 규모: [RFP 데이터 또는 [정보 없음]]\n• 고용 창출: [RFP 데이터 또는 [정보 없음]]\n• 산업 경쟁력: [RFP에서 언급한 파급효과]\n• 정책 기여: [RFP에서 언급한 정책적 기여]"
  },
  {
    "subtitle": "성과 산출근거",
    "content": "• [성과 추정의 근거가 RFP에 명시된 경우만 기술]"
  }
]

[알 수 없는 내용 처리]
RFP에서 명확히 제시되지 않은 정보는 다음과 같이 표시:
  • 시장 규모: [정보 없음 - 추가 조사 필요]
  • 매출 전망: [정보 없음 - 사업화 계획 수립 시 산정]
  • 고용 창출: [정보 없음]

[주의사항]
- RFP에 없는 수치는 절대 임의로 생성하지 말 것
- "~예상", "~전망"과 같은 모호한 표현보다는 RFP 기반의 목표치 명시
- 과장된 경제적 성과 지양
- RFP에서 제시한 최소 성과목표는 반드시 포함
- 산출근거가 불분명한 경우 [정보 없음] 표시
"""


def outcome_node(state: GraphState) -> dict:
    """
    [Node 7] 기대 성과 슬라이드 생성 노드
    
    PM 노드에서 분석한 결과 중 'expected_outcome' 태스크에 할당된 
    relevant_context를 활용하여 기대 성과 슬라이드를 생성한다.
    """
    try:
        # 1. State에서 분석 결과 가져오기
        analyzed_json = state.get("analyzed_json", {})
        
        if not analyzed_json or "error" in analyzed_json:
            print("[Outcome 노드] 분석 결과가 없거나 에러 발생")
            return {"slides": []}
        
        # 2. expected_outcome 태스크 정보 추출
        tasks = analyzed_json.get("tasks", {})
        outcome_task = tasks.get("expected_outcome", {})
        
        if not outcome_task:
            print("[Outcome 노드] expected_outcome 태스크 정보 없음")
            return {"slides": []}
        
        relevant_context = outcome_task.get("relevant_context", "")
        instruction = outcome_task.get("instruction", "")
        
        # 3. 프로젝트 요약 정보도 함께 활용
        project_summary = analyzed_json.get("project_summary", {})
        
        # 4. 프롬프트 구성
        user_prompt = f"""
다음 RFP 분석 결과를 바탕으로 '기대 성과' 슬라이드를 작성해라.

[프로젝트 기본 정보]
- 과제명: {project_summary.get('title', '')}
- 사업 목적: {project_summary.get('purpose', '')}
- 사업 기간: {project_summary.get('period', '')}
- 핵심 키워드: {', '.join(project_summary.get('keywords', []))}

[PM의 지시사항]
{instruction}

[RFP 관련 내용]
{relevant_context}

위 정보를 바탕으로 기대 성과 슬라이드를 JSON 형식으로 생성해라.
과학기술적 성과와 경제사회적 성과를 균형있게 제시하되, RFP에 없는 수치는 [정보 없음]으로 표시하라.
"""

        # 5. Gemini API 호출
        api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        
        print("[Outcome 노드] 슬라이드 생성 시작 (Gemini 2.5 Flash)...")
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION_OUTCOME,
                response_mime_type="application/json",
                temperature=0.3,
            )
        )
        
        # 6. 응답 파싱
        response_text = response.text
        
        # Gemini는 response_mime_type="application/json"으로 설정했으므로
        # 깨끗한 JSON을 반환하지만, 혹시 모를 마크다운 코드블록 제거
        if response_text.strip().startswith("```"):
            lines = response_text.strip().split('\n')
            json_lines = []
            in_code_block = False
            
            for line in lines:
                if line.strip().startswith("```"):
                    in_code_block = not in_code_block
                    continue
                if in_code_block or (not line.strip().startswith("```")):
                    json_lines.append(line)
            
            response_text = '\n'.join(json_lines)
        
        slide_data = json.loads(response_text)
        
        # 7. SlideState 형식으로 변환
        slide: SlideState = {
            "page_number": slide_data.get("page_number", 1),
            "section": slide_data.get("section", "기대 성과"),
            "title": slide_data.get("title", ""),
            "items": slide_data.get("items", []),
            "image_request": slide_data.get("image_request", ""),
            "image_position": slide_data.get("image_position", ""),
            "image_path": ""
        }
        
        print(f"[Outcome 노드] 슬라이드 생성 완료: {slide['title']}")
        
        # 8. State 업데이트 (slides 리스트에 추가)
        return {"slides": [slide]}
        
    except Exception as e:
        print(f"[Outcome 노드 에러] {e}")
        import traceback
        traceback.print_exc()
        return {"slides": []}