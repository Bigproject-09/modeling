"""
추진 계획 노드 (Promotion Plan Node)
- 연구개발 일정, 단계별 마일스톤, 추진체계를 시각화
- 이미지: 간트차트, 조직도, 워크플로우 다이어그램
"""

import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
from .state import GraphState, SlideState

load_dotenv()

# ============================================================
# 시스템 프롬프트
# ============================================================
SYSTEM_INSTRUCTION = """
너는 국가 R&D 제안서의 '추진 계획' 파트를 작성하는 전문 AI 에이전트다.

[역할]
과제 수행 일정, 추진체계, 위험관리 계획을 구체적이고 실현 가능하게 제시한다.

[입력]
1. project_summary: 전체 과제 요약 (수행기간 등 참고)
2. relevant_context: 추진 계획 관련 RFP 요구사항 원문
3. instruction: PM의 작성 가이드

[출력 형식]
반드시 아래 JSON 배열 형태로만 응답해라.

[
  {
    "page_number": 1,
    "section": "추진 계획",
    "title": "연구개발 추진 체계",
    "content": "• 총괄 책임: 김OO 박사 (AI 전문, 경력 15년)\\n• 1세부: 데이터 수집 및 전처리팀 (5명)\\n• 2세부: AI 모델 개발팀 (7명)\\n• 3세부: 시스템 통합 및 검증팀 (4명)\\n• 자문위원: 산업계 전문가 3명",
    "image_request": "organizational chart diagram with hierarchical structure, professional business infographic style, blue and white color scheme",
    "image_position": "right:50%",
    "text_position": "left:45%"
  },
  {
    "page_number": 2,
    "section": "추진 계획",
    "title": "단계별 추진 일정",
    "content": "• 1단계 (1~6개월): 요구사항 분석 및 데이터 수집\\n  - 산업현장 조사 완료\\n  - 학습 데이터 5만건 확보\\n• 2단계 (7~12개월): AI 모델 개발\\n  - 예지보전 알고리즘 구현\\n  - 정확도 90% 이상 달성\\n• 3단계 (13~18개월): 시스템 통합 및 실증\\n  - 파일럿 사이트 적용\\n  - 성능 검증 완료",
    "image_request": "gantt chart timeline visualization with milestones and phases, colorful professional project management style",
    "image_position": "bottom:45%",
    "text_position": "top:50%"
  },
  {
    "page_number": 3,
    "section": "추진 계획",
    "title": "위험 관리 계획",
    "content": "• 기술적 위험\\n  - 데이터 품질 이슈 → 다중 소스 확보\\n  - 모델 성능 미달 → 앙상블 기법 적용\\n• 일정 위험\\n  - 지연 발생 시 → 주간 진도 점검, 자원 재배치\\n• 협력 위험\\n  - 참여기관 이탈 → 계약서 페널티 조항 명시",
    "image_request": "risk management matrix with mitigation strategies, professional business diagram with warning icons",
    "image_position": "left:45%",
    "text_position": "right:50%"
  }
]

[작성 원칙]
1. **구체적 일정**: "신속히 추진" (X) → "1~6개월: 데이터 수집" (O)
2. **정량적 목표**: 각 단계마다 측정 가능한 성과지표 제시
3. **현실성**: RFP의 수행기간을 준수하되, 여유있는 버퍼 설정
4. **책임소재 명확화**: 각 세부과제별 담당자/팀 명시
5. **위험 대응**: 예상 문제와 해결책을 쌍으로 제시

[슬라이드 구성 가이드]
- 추진체계 (조직도) → 일정계획 (간트차트) → 위험관리 순서 권장
- 슬라이드 수: 3~5장 (과제 규모에 따라 조정)
- 이미지: 차트/다이어그램 중심 (간트차트, 조직도, 플로우차트)

[image_request 작성 시 참고]
- gantt chart, timeline, organizational chart, workflow diagram, risk matrix 등
- 색상 힌트: blue/white (신뢰), green (진행), red/yellow (위험)
- 스타일: professional, clean, infographic style
"""


def promotion_node(state: GraphState) -> dict:
    """
    추진 계획 슬라이드 생성 노드
    
    Args:
        state: 현재 그래프 상태
        
    Returns:
        {"slides": [SlideState, ...]}
    """
    print("\n" + "="*60)
    print("[추진 계획 노드] 작업 시작")
    print("="*60)
    
    try:
        # 1. 분석 데이터 추출
        analyzed_json = state.get("analyzed_json", {})
        
        if not analyzed_json or "error" in analyzed_json:
            print("[추진 계획 노드] 분석 데이터 없음")
            return {"slides": []}
        
        project_summary = analyzed_json.get("project_summary", {})
        task_info = analyzed_json.get("tasks", {}).get("promotion_plan", {})
        
        relevant_context = task_info.get("relevant_context", "")
        instruction = task_info.get("instruction", "")
        
        if not relevant_context:
            print("[추진 계획 노드] relevant_context 없음")
            return {"slides": []}
        
        # 2. 프롬프트 구성 (과제 기간 정보 강조)
        prompt = f"""
[전체 과제 정보]
제목: {project_summary.get('title', 'N/A')}
수행기간: {project_summary.get('period', 'N/A')}
예산: {project_summary.get('budget', 'N/A')}
키워드: {', '.join(project_summary.get('keywords', []))}

[PM 지시사항]
{instruction}

[RFP 요구사항 (추진 계획 관련)]
{relevant_context}

위 정보를 바탕으로 '추진 계획' 슬라이드를 생성해라.
특히 수행기간({project_summary.get('period', 'N/A')})을 고려하여 현실적인 일정을 수립하라.
"""
        
        # 3. Gemini API 호출
        api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        
        print("[추진 계획 노드] LLM 생성 중...")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                temperature=0.2,  # 일정은 보수적으로
            ),
        )
        
        # 4. 파싱 및 변환
        slides_data = json.loads(response.text)
        
        if not isinstance(slides_data, list):
            print(f"[추진 계획 노드] 잘못된 응답 형식")
            return {"slides": []}
        
        result_slides = []
        for slide in slides_data:
            slide_state: SlideState = {
                "page_number": slide.get("page_number", 0),
                "section": slide.get("section", "추진 계획"),
                "title": slide.get("title", ""),
                "content": slide.get("content", ""),
                "image_request": slide.get("image_request", ""),
                "image_position": slide.get("image_position", "right:50%"),
                "image_path": "",
            }
            result_slides.append(slide_state)
        
        print(f"[추진 계획 노드] 슬라이드 {len(result_slides)}장 생성 완료")
        for i, s in enumerate(result_slides, 1):
            print(f"  [{i}] {s['title']}")
        
        return {"slides": result_slides}
    
    except Exception as e:
        print(f"[추진 계획 노드 오류] {e}")
        import traceback
        traceback.print_exc()
        return {"slides": []}


# ============================================================
# 테스트 코드
# ============================================================
if __name__ == "__main__":
    print("--- [TEST] 추진 계획 노드 단독 실행 ---")
    
    dummy_state: GraphState = {
        "rfp_text": "",
        "analyzed_json": {
            "project_summary": {
                "title": "AI 기반 스마트팩토리 플랫폼 개발",
                "period": "24개월 (2025.03 ~ 2027.02)",
                "budget": "정부지원금 10억원",
                "keywords": ["AI", "예지보전", "스마트팩토리"]
            },
            "tasks": {
                "promotion_plan": {
                    "role": "추진 계획",
                    "instruction": "24개월 일정에 맞춰 3단계로 구분하고, 위험관리 계획 포함",
                    "relevant_context": """
                    [수행 기간]
                    총 24개월 (2025년 3월 ~ 2027년 2월)
                    
                    [추진 체계 요구사항]
                    - 총괄 책임자: 박사급 연구원 (AI 분야 10년 이상)
                    - 세부과제별 책임자 지정 필수
                    - 월 1회 이상 진도 점검 회의 개최
                    
                    [제출 결과물]
                    - 중간보고서 (12개월 차)
                    - 최종보고서 (24개월 차)
                    - 실증 테스트 결과 데이터
                    """
                }
            }
        },
        "slides": [],
        "final_ppt_path": ""
    }
    
    result = promotion_node(dummy_state)
    
    if result["slides"]:
        print("\n[성공] 생성된 슬라이드:")
        for slide in result["slides"]:
            print(f"\n제목: {slide['title']}")
            print(f"내용:\n{slide['content']}")
            print(f"이미지: {slide['image_request'][:70]}...")
    else:
        print("[실패] 슬라이드 생성 안됨")