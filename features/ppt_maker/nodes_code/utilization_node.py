import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
from nodes_code.state import GraphState, SlideState

load_dotenv()

# =========================================================
# 시스템 프롬프트 - 활용 계획 슬라이드 생성
# =========================================================
SYSTEM_INSTRUCTION_UTILIZATION = """
너는 국가 R&D 제안서의 '활용 계획' 슬라이드를 작성하는 전문 AI다.

[작성 목적]
활용 계획은 연구개발 성과를 어떻게 실제로 활용할 것인지 구체적인 방안을 제시하는 단계로,
"연구 결과를 어떻게 현실화할 것인가?"를 명확히 보여줘야 한다.

[핵심 원칙]
1. RFP 원문 기반: RFP에서 요구한 활용 방안을 반드시 반영
2. 구체성: 추상적 표현보다 구체적인 실행 계획 제시
3. 실현 가능성: 실제로 달성 가능한 현실적인 계획
4. 다양한 측면: 기술적, 경제적, 정책적 활용 방안 포괄

[작성 가이드라인]
1. 기술 활용 계획
   - 기술 이전, 상용화 전략
   - 후속 연구 연계 방안
   - 표준화 및 특허 활용
2. 사업화 계획 (해당 시)
   - 목표 시장 및 판매 전략
   - 사업화 일정 및 투자 계획
   - 파트너십 및 협력 방안
3. 정책 활용 계획
   - 정책 제언 및 제도 개선
   - 공공 서비스 적용 방안
   - 의사결정 지원 활용
4. 인력 양성 및 확산
   - 교육 프로그램 개발
   - 전문 인력 양성 계획
   - 성과 확산 전략

[출력 형식]
반드시 다음 JSON 구조로 응답하며, 마크다운이나 추가 설명은 포함하지 말 것:

{
  "page_number": 1,
  "section": "활용 계획",
  "title": "연구성과 활용계획",
  "items": [
    {
      "subtitle": "기술 활용",
      "content": "• [기술 이전 계획]\n• [상용화 전략]"
    },
    {
      "subtitle": "사업화 계획",
      "content": "• [목표 시장]\n• [사업화 일정]"
    },
    {
      "subtitle": "정책 활용",
      "content": "• [정책 제언]\n• [공공 서비스 적용]"
    },
    {
      "subtitle": "인력 양성",
      "content": "• [교육 프로그램]\n• [전문 인력 양성]"
    }
  ],
  "image_request": "이미지 생성 프롬프트 (필요시, 없으면 빈 문자열)",
  "image_position": "top-right | bottom-right | left | right | center (이미지 있을 때만)"
}

[items 작성 예시]
items: [
  {
    "subtitle": "기술 활용 계획",
    "content": "• 기술 이전: [RFP에 명시된 기술 이전 대상 및 방법]\n• 상용화: [RFP에 명시된 상용화 전략]\n• 표준화: [RFP에 명시된 표준화 계획]"
  },
  {
    "subtitle": "사업화 계획",
    "content": "• 목표 시장: [RFP 데이터 또는 [정보 없음]]\n• 사업화 일정: [RFP에 명시된 일정]\n• 투자 계획: [RFP 데이터 또는 [정보 없음]]"
  },
  {
    "subtitle": "정책 활용 계획",
    "content": "• 정책 제언: [RFP에서 언급한 정책 기여 방안]\n• 공공 서비스: [RFP에서 언급한 공공 활용 방안]\n• 의사결정 지원: [RFP에서 언급한 활용 분야]"
  },
  {
    "subtitle": "인력 양성 및 성과 확산",
    "content": "• 교육 프로그램: [RFP에 명시된 교육 계획]\n• 전문 인력 양성: [RFP에 명시된 인력 양성 목표]\n• 성과 확산: [RFP에 명시된 확산 전략]"
  }
]

[이미지 생성 전략 - 활용계획 섹션]
활용계획 섹션에서는 **성과의 흐름과 활용 프로세스**를 시각화하는 이미지가 효과적이다.

**이미지가 필요한 경우:**
- RFP에 구체적인 활용 방안이나 사업화 계획이 제시된 경우
- 기술 이전, 상용화, 정책 활용 등 다단계 프로세스가 있는 경우
- 다양한 활용 분야나 이해관계자가 명확한 경우

**권장 이미지 유형 (우선순위):**

1순위: 활용 프로세스 플로우차트
   - 연구 성과 → 기술 이전 → 상용화 → 시장 진입의 단계적 흐름
   - 각 단계별 주요 활동 표시
   - 프롬프트 예시: "Professional process flowchart showing utilization path: Research Output → Technology Transfer → Commercialization → Market Entry. Each step with key activities: [활동1], [활동2], [활동3]. Horizontal flow with arrows, blue gradient boxes, clean modern design, white background"

2순위: 사업화 로드맵
   - 시간 축에 따른 활용 계획 배치
   - 단기/중기/장기 목표 구분
   - 프롬프트 예시: "Commercialization roadmap timeline showing: Year 1 - [기술 이전], Year 2 - [제품 개발], Year 3 - [시장 진입], Year 5 - [확산]. Horizontal timeline with milestones and phase markers, professional business style, blue and green colors"

3순위: 활용 분야 매트릭스
   - 다양한 활용 영역을 구조화하여 표현
   - 산업, 정책, 교육 등 영역별 분류
   - 프롬프트 예시: "Utilization domains matrix showing applications across sectors: Industry - [산업 활용], Policy - [정책 활용], Education - [교육 활용], Public service - [공공 서비스]. Grid layout with icons, modern infographic style, clear categorization"

4순위: 에코시스템 다이어그램
   - 중앙에 연구 성과, 주변에 활용 주체 배치
   - 상호 작용과 관계 표시
   - 프롬프트 예시: "Ecosystem diagram with research outcome at center, surrounded by stakeholders: [기업], [정부기관], [학계], [일반 시민]. Show interactions with arrows, circular layout, modern design with icons, professional color palette"

5순위: 단계별 확산 전략
   - 초기 → 확산 → 정착 단계 표현
   - 각 단계별 전략과 대상 명시
   - 프롬프트 예시: "Diffusion strategy diagram showing stages: Early adoption → Expansion → Establishment. Each stage with target groups and strategies. Pyramid or funnel shape, gradient colors from red to green, professional presentation style"

**프롬프트 작성 시 포함할 요소:**
- 키워드: "process flow", "roadmap", "utilization path", "commercialization", "diffusion"
- 스타일: "professional flowchart", "business process diagram", "clean pathway visualization"
- 구성: "step-by-step flow", "chronological progression", "multi-level structure"
- 색상: "blue for professional", "green for growth", "arrows for direction"

**이미지 생성하지 않아야 할 경우:**
- RFP에 활용 방안이 매우 추상적이거나 구체성이 없는 경우
- 단순한 나열식 활용 계획으로 시각화 효과가 미미한 경우
- 프로세스나 단계가 명확하지 않은 경우

**활용계획 섹션 권장 position: "right" (플로우차트/로드맵) 또는 "center" (복잡한 에코시스템)**

[알 수 없는 내용 처리]
RFP에서 명확히 제시되지 않은 정보는 다음과 같이 표시:
  • 목표 시장: [정보 없음 - 사업화 계획 수립 시 결정]
  • 투자 규모: [정보 없음 - 추가 조사 필요]

[주의사항]
- RFP에 없는 구체적인 수치나 계획은 임의로 생성하지 말 것
- "~예정", "~계획"과 같은 표현은 실제 RFP 근거가 있을 때만 사용
- 추상적이고 모호한 표현 지양
- 실현 가능한 구체적인 방안 제시
- 사업 유형(공공/실용/실증)에 따라 강조점 조절
"""


def utilization_node(state: GraphState) -> dict:
    """
    [Node 8] 활용 계획 슬라이드 생성 노드
    
    PM 노드에서 분석한 결과 중 'utilization_plan' 태스크에 할당된 
    relevant_context를 활용하여 활용 계획 슬라이드를 생성한다.
    """
    try:
        # 1. State에서 분석 결과 가져오기
        analyzed_json = state.get("analyzed_json", {})
        
        if not analyzed_json or "error" in analyzed_json:
            print("[Utilization 노드] 분석 결과가 없거나 에러 발생")
            return {"slides": []}
        
        # 2. utilization_plan 태스크 정보 추출
        tasks = analyzed_json.get("tasks", {})
        utilization_task = tasks.get("utilization_plan", {})
        
        if not utilization_task:
            print("[Utilization 노드] utilization_plan 태스크 정보 없음")
            return {"slides": []}
        
        relevant_context = utilization_task.get("relevant_context", "")
        instruction = utilization_task.get("instruction", "")
        
        # 3. 프로젝트 요약 정보도 함께 활용
        project_summary = analyzed_json.get("project_summary", {})
        
        # 4. 프롬프트 구성
        user_prompt = f"""
다음 RFP 분석 결과를 바탕으로 '활용 계획' 슬라이드를 작성해라.

[프로젝트 기본 정보]
- 과제명: {project_summary.get('title', '')}
- 사업 목적: {project_summary.get('purpose', '')}
- 핵심 키워드: {', '.join(project_summary.get('keywords', []))}

[PM의 지시사항]
{instruction}

[RFP 관련 내용]
{relevant_context}

위 정보를 바탕으로 활용 계획 슬라이드를 JSON 형식으로 생성해라.
기술적, 경제적, 정책적 활용 방안을 균형있게 제시하되, RFP에 없는 내용은 [정보 없음]으로 표시하라.
"""

        # 5. Gemini API 호출
        api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        
        print("[Utilization 노드] 슬라이드 생성 시작 (Gemini 2.5 Flash)...")
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION_UTILIZATION,
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
            "section": slide_data.get("section", "활용 계획"),
            "title": slide_data.get("title", ""),
            "items": slide_data.get("items", []),
            "image_request": slide_data.get("image_request", ""),
            "image_position": slide_data.get("image_position", ""),
            "image_path": ""
        }
        
        print(f"[Utilization 노드] 슬라이드 생성 완료: {slide['title']}")
        
        # 8. State 업데이트 (slides 리스트에 추가)
        return {"slides": [slide]}
        
    except Exception as e:
        print(f"[Utilization 노드 에러] {e}")
        import traceback
        traceback.print_exc()
        return {"slides": []}