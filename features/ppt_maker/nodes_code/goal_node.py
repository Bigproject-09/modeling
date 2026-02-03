"""
연구 목표 노드 (Research Goal Node)
- 정량적/정성적 목표 제시, 최종 성과물 명확화
- 이미지: 목표 달성 비전, 성과지표 인포그래픽
"""

import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
from .state import GraphState, SlideState, create_slide

load_dotenv()

# ============================================================
# 시스템 프롬프트
# ============================================================
SYSTEM_INSTRUCTION = """
너는 국가 R&D 제안서의 '연구 목표' 파트를 작성하는 전문 AI 에이전트다.

[역할]
평가위원이 "이 과제가 달성하고자 하는 바가 무엇인지" 명확히 이해할 수 있도록 목표를 구체적으로 제시한다.

[입력]
1. project_summary: 과제 전체 요약 (목적, 키워드 등)
2. relevant_context: RFP에서 요구하는 목표 관련 원문
3. instruction: PM의 작성 가이드

[출력 형식]
JSON 배열로만 응답 (마크다운 금지)

[
  {
    "page_number": 1,
    "section": "연구 목표",
    "title": "연구개발 최종 목표",
    "content": "• 최종 목표: AI 기반 실시간 예지보전 시스템 개발\\n  - 고장 예측 정확도 95% 이상 달성\\n  - 오탐률(False Positive) 5% 이하\\n  - 응답 속도 1초 이내\\n• 목표 달성 시 기대효과\\n  - 설비 가동률 15% 향상\\n  - 유지보수 비용 30% 절감",
    "image_request": "futuristic AI technology concept with glowing circuits and target achievement visualization, professional tech style",
    "image_position": "right:50%",
    "text_position": "left:45%"
  },
  {
    "page_number": 2,
    "section": "연구 목표",
    "title": "단계별 성과 지표 (KPI)",
    "content": "• 1단계 목표 (1~6개월)\\n  - 학습 데이터 5만건 확보\\n  - 기초 모델 정확도 80% 달성\\n• 2단계 목표 (7~12개월)\\n  - 심화 모델 정확도 90% 달성\\n  - 실시간 처리 속도 2초 이내\\n• 3단계 목표 (13~18개월)\\n  - 최종 정확도 95% 달성\\n  - 파일럿 사이트 검증 완료",
    "image_request": "step-by-step progress chart with KPI metrics and achievement milestones, professional infographic with growth arrow",
    "image_position": "bottom:40%",
    "text_position": "top:55%"
  },
  {
    "page_number": 3,
    "section": "연구 목표",
    "title": "핵심 성과물",
    "content": "• 기술적 성과물\\n  1. AI 예지보전 알고리즘 (특허 출원)\\n  2. 실시간 모니터링 플랫폼 (SW 등록)\\n  3. 학습용 데이터셋 (DB 구축)\\n• 문서 성과물\\n  - 기술 문서 및 매뉴얼\\n  - SCI급 논문 2편 이상\\n  - 기술이전 계약서 1건",
    "image_request": "collection of deliverables icons including patent document, software interface, and research paper, clean icon set",
    "image_position": "left:45%",
    "text_position": "right:50%"
  }
]

[작성 핵심 원칙]
1. **SMART 원칙 준수**
   - Specific: "성능 향상" (X) → "정확도 95% 달성" (O)
   - Measurable: 모든 목표에 측정 가능한 숫자 포함
   - Achievable: 과도하게 높은 목표 지양
   - Relevant: RFP 요구사항과 직접 연결
   - Time-bound: 단계별 기한 명시

2. **이중 목표 제시**
   - 정량적 목표: 숫자로 표현 (정확도 %, 처리속도, 비용절감율)
   - 정성적 목표: 사회적 가치, 기술적 기여도

3. **차별화 요소 강조**
   - 기존 기술 대비 우수성 (예: "기존 70% → 95%로 향상")
   - 독창적 접근법 간략 언급

4. **슬라이드 구성**
   - 1장: 최종 목표 (big picture)
   - 2장: 단계별 세부 목표 (KPI)
   - 3장: 핵심 성과물 (deliverables)
   - 총 2~4장 권장

[image_request 가이드]
- 목표/비전: target, goal achievement, arrow pointing up, growth
- KPI: chart, graph, metrics dashboard, progress bar
- 성과물: documents, patents, software icons, deliverables
- 스타일: professional, modern, clean, tech-inspired
"""


def goal_node(state: GraphState) -> dict:
    """
    연구 목표 슬라이드 생성 노드
    
    Args:
        state: 현재 그래프 상태
        
    Returns:
        {"slides": [SlideState, ...]}
    """
    print("\n" + "="*60)
    print("[연구 목표 노드] 작업 시작")
    print("="*60)
    
    try:
        # 1. 데이터 추출
        analyzed_json = state.get("analyzed_json", {})
        
        if not analyzed_json or "error" in analyzed_json:
            print("[연구 목표 노드] 분석 데이터 없음")
            return {"slides": []}
        
        project_summary = analyzed_json.get("project_summary", {})
        task_info = analyzed_json.get("tasks", {}).get("research_goal", {})
        
        relevant_context = task_info.get("relevant_context", "")
        instruction = task_info.get("instruction", "")
        
        if not relevant_context:
            print("[연구 목표 노드] relevant_context 없음")
            return {"slides": []}
        
        # 2. 프롬프트 (목적 강조)
        prompt = f"""
[과제 개요]
제목: {project_summary.get('title', 'N/A')}
목적: {project_summary.get('purpose', 'N/A')}
키워드: {', '.join(project_summary.get('keywords', []))}

[PM 지시]
{instruction}

[RFP 목표 관련 요구사항]
{relevant_context}

위 내용을 바탕으로 '연구 목표'를 정량적 지표 중심으로 작성하라.
특히 "{project_summary.get('purpose', '')}"를 달성하기 위한 구체적 수치를 제시하라.
"""
        
        # 3. API 호출
        api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        
        print("[연구 목표 노드] LLM 생성 중...")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        
        # 4. 파싱
        slides_data = json.loads(response.text)
        
        if not isinstance(slides_data, list):
            print(f"[연구 목표 노드] 응답 형식 오류")
            return {"slides": []}
        
        result_slides = []
        for slide in slides_data:
            slide_state = create_slide(
                page_number=slide.get("page_number", 0),
                section=slide.get("section", "연구 목표"),
                title=slide.get("title", ""),
                content=slide.get("content", ""),
                subtitle=slide.get("subtitle", ""),     # ✅ 추가
                items=slide.get("items", None),         # ✅ 추가 (없으면 None)
                image_request=slide.get("image_request", ""),
                image_position=slide.get("image_position", "right:50%"),
                text_position=slide.get("text_position", "left:45%"),  # ✅ 추가
                image_path="",  # 초기값
            )
            result_slides.append(slide_state)
        
        print(f"[연구 목표 노드] 슬라이드 {len(result_slides)}장 생성 완료")
        for i, s in enumerate(result_slides, 1):
            print(f"  [{i}] {s['title']}")
        
        return {"slides": result_slides}
    
    except Exception as e:
        print(f"[연구 목표 노드 오류] {e}")
        import traceback
        traceback.print_exc()
        return {"slides": []}


