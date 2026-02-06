import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
<<<<<<< HEAD
from state import GraphState, SlideState
=======
from nodes_code.state import GraphState, SlideState
>>>>>>> origin/jun_test

load_dotenv()

# =========================================================
# 시스템 프롬프트 - 사업 개요 슬라이드 생성
# =========================================================
SYSTEM_INSTRUCTION_OVERVIEW = """
너는 국가 R&D 제안서의 '사업 개요' 슬라이드를 작성하는 전문 AI다.

[작성 목적]
사업 개요는 사업제안요구서(RFP)에 대한 이해도를 보여주는 단계로, 
평가위원들에게 "우리가 RFP를 정확히 이해하고 있다"는 것을 전달해야 한다.

[핵심 원칙]
1. RFP 원문 기반: 제공된 RFP 컨텍스트에서 발췌한 내용만 사용할 것
2. 객관적 사실: 주관적 해석이나 추측 금지, 사실만 기술
3. 명확성: 과제명, 목적, 기간, 예산 등을 한눈에 파악할 수 있게 구성
4. 간결성: 핵심만 담아 2매 이내로 구성 (슬라이드 1개 생성)

[작성 가이드라인]
1. 과제명: RFP에 제시된 공고명을 정확히 반영
2. 사업 배경 및 목적: RFP에서 명시한 사업의 필요성과 목적을 2-3문장으로 요약
3. 사업 개요:
   - 연구개발 기간
   - 총 사업비 (정부지원금 + 민간부담금)
   - 참여기관 구성
   - 주요 연구 범위
4. RFP 요구사항 매칭: RFP에서 요구한 핵심 내용이 반영되었음을 간략히 표시

[출력 형식]
반드시 다음 JSON 구조로 응답하며, 마크다운이나 추가 설명은 포함하지 말 것:

{
  "page_number": 1,
  "section": "사업 개요",
  "title": "사업 개요 및 추진 방향",
  "items": [
    {
      "subtitle": "과제명",
      "content": "• [RFP에서 제시된 정확한 과제명]"
    },
    {
      "subtitle": "사업 목적",
      "content": "• [RFP에 명시된 사업의 배경]\n• [RFP에 명시된 사업의 목표]"
    },
    {
      "subtitle": "사업 개요",
      "content": "• 사업 기간: [X]년\n• 총 사업비: 총 [X]억원\n• 참여기관: [기관명]\n• 연구 범위: [주요 연구 영역]"
    }
  ],
  "image_request": "이미지 생성 프롬프트 (필요시, 없으면 빈 문자열)",
  "image_position": "top-right | bottom-right | left | right | center (이미지 있을 때만)"
}

[items 작성 예시]
각 item은 subtitle과 content의 쌍으로 구성됩니다:

items: [
  {
    "subtitle": "과제명",
    "content": "• [RFP에서 제시된 정확한 과제명]"
  },
  {
    "subtitle": "사업 목적",
    "content": "• [RFP에 명시된 사업의 배경 1-2문장]\n• [RFP에 명시된 사업의 목표 1-2문장]"
  },
  {
    "subtitle": "사업 개요",
    "content": "• 사업 기간: [X]년 ([YYYY.MM ~ YYYY.MM])\n• 총 사업비: 총 [X]억원 (정부 [X]억원 + 민간 [X]억원)\n• 참여기관: 주관연구기관 [기관명], 협동연구기관 [기관명] 등\n• 연구 범위: [RFP에서 제시한 주요 연구 영역 2-3개]"
  },
  {
    "subtitle": "RFP 핵심 요구사항",
    "content": "• [RFP 요구사항 1]\n• [RFP 요구사항 2]\n• [RFP 요구사항 3]"
  }
]

[이미지 생성 전략 - 개요 섹션]
개요 섹션에서는 **전체 시스템 구조**를 한눈에 보여주는 이미지가 효과적이다.

**이미지가 필요한 경우:**
- RFP에 시스템 구성, 기술 아키텍처, 플랫폼 구조 등이 언급된 경우
- 개발 대상이 하드웨어, 소프트웨어, 통합 시스템 등 시각화 가능한 형태인 경우
- 여러 구성 요소가 상호작용하는 복합 시스템인 경우

**권장 이미지 유형 (우선순위):**

1순위: 시스템 아키텍처 다이어그램
   - 전체 시스템의 블록 다이어그램 형태
   - 주요 모듈/컴포넌트와 그 연결 관계  
   - 데이터/신호 흐름을 화살표로 표시
   - 프롬프트 예시: "Professional system architecture diagram showing [시스템명] with main components: [컴포넌트1], [컴포넌트2], [컴포넌트3]. Clean block diagram with labeled boxes connected by arrows indicating data flow. Blue and gray color scheme, minimal design, white background, technical illustration style"

2순위: 제품/기술 개념도
   - 개발 대상의 3D 렌더링 또는 구조 도식화
   - 핵심 기술 요소를 시각적으로 강조
   - 프롬프트 예시: "Technical concept diagram of [제품/기술명] showing key elements: [요소1], [요소2]. Isometric 3D view, modern technology style, blue gradient background, clean and professional"

3순위: 연구 범위 맵
   - 연구 영역의 계층 구조 표현
   - 세부 과제 간 관계도
   - 프롬프트 예시: "Research scope map showing hierarchy: [상위 영역] containing [하위 과제1], [하위 과제2]. Tree structure or mind map style, professional colors, clear labels"

**프롬프트 작성 시 포함할 요소:**
- 키워드: "system architecture", "block diagram", "technical framework", "component structure"
- 스타일: "professional technical diagram", "clean minimal design", "blue and gray color scheme"
- 구성: "labeled boxes", "arrows showing flow", "hierarchical structure"
- 배경: "white background" 또는 "light gray background"

**이미지 생성하지 않아야 할 경우:**
- RFP가 정책 연구, 문헌 조사, 설문 분석 등 비기술적 내용인 경우
- 시스템 구성이 너무 단순하여 텍스트만으로 충분한 경우
- RFP에 구체적 구성 요소나 구조에 대한 언급이 전혀 없는 경우

**개요 섹션 권장 position: "right" (시스템 다이어그램) 또는 "center" (복잡한 구조도)**

[알 수 없는 내용 처리 원칙]
RFP에서 명확히 제시되지 않은 정보는 다음과 같이 표시:
  • 사업 기간: [정보 없음 - RFP 확인 필요]
  • 총 사업비: [정보 없음 - RFP 확인 필요]
  • 참여기관: [정보 없음 - 제안서 작성 시 결정]

단, 프로젝트 요약 정보(project_summary)에 있는 내용은 우선 활용하되,
불확실하거나 추측이 필요한 경우에만 [정보 없음] 표시를 사용할 것.

[주의사항]
- RFP에 명시되지 않은 내용은 [정보 없음 - 확인 필요] 형태로 표시
- 추측하거나 임의로 내용을 만들어내지 말 것
- 과장되거나 주관적인 표현 사용 금지
- 출처가 불명확한 통계나 데이터 사용 금지
- 전문용어는 RFP에서 사용된 용어 그대로 사용
- 프로젝트 요약에 있는 정보는 신뢰하고 활용 가능
"""


def overview_node(state: GraphState) -> dict:
    """
    [Node 2] 사업 개요 슬라이드 생성 노드
    
    PM 노드에서 분석한 결과 중 'project_overview' 태스크에 할당된 
    relevant_context를 활용하여 사업 개요 슬라이드를 생성한다.
    """
    try:
        # 1. State에서 분석 결과 가져오기
        analyzed_json = state.get("analyzed_json", {})
        
        if not analyzed_json or "error" in analyzed_json:
            print("[Overview 노드] 분석 결과가 없거나 에러 발생")
            return {"slides": []}
        
        # 2. project_overview 태스크 정보 추출
        tasks = analyzed_json.get("tasks", {})
        overview_task = tasks.get("project_overview", {})
        
        if not overview_task:
            print("[Overview 노드] project_overview 태스크 정보 없음")
            return {"slides": []}
        
        relevant_context = overview_task.get("relevant_context", "")
        instruction = overview_task.get("instruction", "")
        
        # 3. 프로젝트 요약 정보도 함께 활용
        project_summary = analyzed_json.get("project_summary", {})
        
        # 4. 프롬프트 구성
        user_prompt = f"""
다음 RFP 분석 결과를 바탕으로 '사업 개요' 슬라이드를 작성해라.

[프로젝트 기본 정보]
- 과제명: {project_summary.get('title', '')}
- 사업 목적: {project_summary.get('purpose', '')}
- 사업 기간: {project_summary.get('period', '')}
- 총 사업비: {project_summary.get('budget', '')}
- 핵심 키워드: {', '.join(project_summary.get('keywords', []))}

[PM의 지시사항]
{instruction}

[RFP 관련 내용]
{relevant_context}

위 정보를 바탕으로 사업 개요 슬라이드를 JSON 형식으로 생성해라.
"""

        # 5. Gemini API 호출
        api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        
        print("[Overview 노드] 슬라이드 생성 시작 (Gemini 2.5 Flash)...")
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION_OVERVIEW,
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
            "section": slide_data.get("section", "사업 개요"),
            "title": slide_data.get("title", ""),
            "items": slide_data.get("items", []),
            "image_request": slide_data.get("image_request", ""),
            "image_position": slide_data.get("image_position", ""),
            "image_path": ""
        }
        
        print(f"[Overview 노드] 슬라이드 생성 완료: {slide['title']}")
        
        # 8. State 업데이트 (slides 리스트에 추가)
        return {"slides": [slide]}
        
    except Exception as e:
        print(f"[Overview 노드 에러] {e}")
        import traceback
        traceback.print_exc()
        return {"slides": []}