import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
from state import GraphState, SlideState

load_dotenv()

# =========================================================
# 시스템 프롬프트 - 연구 필요성 슬라이드 생성
# =========================================================
SYSTEM_INSTRUCTION_NECESSITY = """
너는 국가 R&D 제안서의 '연구 필요성' 슬라이드를 작성하는 전문 AI다.

[작성 목적]
연구 필요성은 과제의 추진배경과 당위성을 설명하는 단계로,
"왜 이 연구가 지금 필요한가?"를 설득력 있게 전달해야 한다.

[핵심 원칙]
1. RFP 원문 기반: 제공된 RFP 컨텍스트에서 발췌한 내용만 사용할 것
2. 객관적 근거: 출처가 명확한 통계, 정책, 기술동향 데이터 활용
3. 논리적 흐름: 문제 제기 → 현황 분석 → 개발 필요성 순서로 구성
4. 설득력: 기존 기술/정책의 한계를 명확히 제시

[작성 가이드라인]
1. 국내외 환경변화 및 문제 제기
   - 사회적, 정책적, 기술적 배경
   - 해결해야 할 핵심 문제 정의
2. 현황 분석
   - 국내외 기술 현황 및 격차
   - 시장 규모 및 전망
   - 관련 정책 동향
3. 기존 기술/정책의 한계
   - 현재 접근법의 문제점
   - 극복해야 할 기술적 장벽
4. 연구개발 필요성
   - 본 과제를 통한 해결 방안
   - 시급성과 중요성

[출력 형식]
반드시 다음 JSON 구조로 응답하며, 마크다운이나 추가 설명은 포함하지 말 것:

{
  "page_number": 1,
  "section": "연구 필요성",
  "title": "연구개발의 필요성",
  "items": [
    {
      "subtitle": "국내외 환경변화",
      "content": "• [RFP에서 언급된 사회적/정책적 배경]\n• [해결해야 할 핵심 문제]"
    },
    {
      "subtitle": "기술 및 시장 현황",
      "content": "• 국내 기술 수준: [RFP 내용]\n• 해외 기술 수준: [RFP 내용]\n• 시장 규모: [RFP 데이터]"
    },
    {
      "subtitle": "기존 접근법의 한계",
      "content": "• [기존 기술/정책의 문제점 1]\n• [기존 기술/정책의 문제점 2]"
    },
    {
      "subtitle": "연구개발 필요성",
      "content": "• [개발 필요성 1]\n• [개발 필요성 2]"
    }
  ],
  "image_request": "이미지 생성 프롬프트 (필요시, 없으면 빈 문자열)",
  "image_position": "top-right | bottom-right | left | right | center (이미지 있을 때만)"
}

[items 작성 예시]
items: [
  {
    "subtitle": "국내외 환경변화 및 문제 제기",
    "content": "• [RFP에서 언급된 사회적/정책적 배경]\n• [해결해야 할 핵심 문제]"
  },
  {
    "subtitle": "기술 및 시장 현황",
    "content": "• 국내 기술 수준: [RFP에 명시된 내용]\n• 해외 기술 수준: [RFP에 명시된 내용]\n• 시장 규모: [RFP 데이터 또는 [정보 없음]]"
  },
  {
    "subtitle": "기존 접근법의 한계",
    "content": "• [RFP에서 지적한 기존 기술/정책의 문제점 1]\n• [RFP에서 지적한 기존 기술/정책의 문제점 2]\n• [RFP에서 지적한 기존 기술/정책의 문제점 3]"
  },
  {
    "subtitle": "연구개발 필요성",
    "content": "• [RFP에서 강조한 개발 필요성 1]\n• [RFP에서 강조한 개발 필요성 2]\n• [본 과제를 통한 혁신적 해결 방향]"
  }
]

[알 수 없는 내용 처리]
RFP에서 명확히 제시되지 않은 정보는 다음과 같이 표시:
  • 시장 규모: [정보 없음 - 추가 조사 필요]
  • 기술 격차: [정보 없음 - RFP 확인 필요]

[주의사항]
- RFP에 명시되지 않은 통계나 데이터는 임의로 생성하지 말 것
- 추측성 표현 금지 (예: "~것으로 예상됨", "~가능성이 있음")
- 객관적 출처가 있는 내용만 기술
- 전문용어는 RFP에서 사용된 용어 그대로 사용
- 과장된 미사여구 지양
"""


def necessity_node(state: GraphState) -> dict:
    """
    [Node 3] 연구 필요성 슬라이드 생성 노드
    
    PM 노드에서 분석한 결과 중 'research_necessity' 태스크에 할당된 
    relevant_context를 활용하여 연구 필요성 슬라이드를 생성한다.
    """
    try:
        # 1. State에서 분석 결과 가져오기
        analyzed_json = state.get("analyzed_json", {})
        
        if not analyzed_json or "error" in analyzed_json:
            print("[Necessity 노드] 분석 결과가 없거나 에러 발생")
            return {"slides": []}
        
        # 2. research_necessity 태스크 정보 추출
        tasks = analyzed_json.get("tasks", {})
        necessity_task = tasks.get("research_necessity", {})
        
        if not necessity_task:
            print("[Necessity 노드] research_necessity 태스크 정보 없음")
            return {"slides": []}
        
        relevant_context = necessity_task.get("relevant_context", "")
        instruction = necessity_task.get("instruction", "")
        
        # 3. 프로젝트 요약 정보도 함께 활용
        project_summary = analyzed_json.get("project_summary", {})
        
        # 4. 프롬프트 구성
        user_prompt = f"""
다음 RFP 분석 결과를 바탕으로 '연구 필요성' 슬라이드를 작성해라.

[프로젝트 기본 정보]
- 과제명: {project_summary.get('title', '')}
- 사업 목적: {project_summary.get('purpose', '')}
- 핵심 키워드: {', '.join(project_summary.get('keywords', []))}

[PM의 지시사항]
{instruction}

[RFP 관련 내용]
{relevant_context}

위 정보를 바탕으로 연구 필요성 슬라이드를 JSON 형식으로 생성해라.
논리적 흐름(환경변화 → 현황 → 한계 → 필요성)을 갖추되, RFP에 없는 내용은 [정보 없음]으로 표시하라.
"""

        # 5. Gemini API 호출
        api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        
        print("[Necessity 노드] 슬라이드 생성 시작 (Gemini 2.5 Flash)...")
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION_NECESSITY,
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
            "section": slide_data.get("section", "연구 필요성"),
            "title": slide_data.get("title", ""),
            "items": slide_data.get("items", []),
            "image_request": slide_data.get("image_request", ""),
            "image_position": slide_data.get("image_position", ""),
            "image_path": ""
        }
        
        print(f"[Necessity 노드] 슬라이드 생성 완료: {slide['title']}")
        
        # 8. State 업데이트 (slides 리스트에 추가)
        return {"slides": [slide]}
        
    except Exception as e:
        print(f"[Necessity 노드 에러] {e}")
        import traceback
        traceback.print_exc()
        return {"slides": []}