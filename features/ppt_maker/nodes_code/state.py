"""
LangGraph State 정의 (최종 버전)
- SlideState: 슬라이드 1장의 구조
- GraphState: 전체 그래프 상태
"""

import operator
from typing import TypedDict, List, Annotated, Optional

# ============================================================
# 슬라이드 1장(Page)에 대한 정의
# ============================================================
class SubtitleContent(TypedDict):
    subtitle: str       # 부제목 (예: "사업 배경", "사업 목적")
    content: str        # 해당 부제목에 대한 내용
    
class SlideState(TypedDict):
    """
    PPT 슬라이드 1장의 데이터 구조
    
    Attributes:
        page_number: 페이지 번호 (정렬용, 1부터 시작)
        section: 슬라이드가 속한 섹션명 (예: "기관 소개", "연구 목표")
        title: 슬라이드 제목 (메인 타이틀)
        subtitle: 슬라이드 부제 (선택사항, 없으면 빈 문자열)
        content: 슬라이드 본문 내용 (글머리 기호 포함)
        image_request: 이미지 생성을 위한 프롬프트 (없으면 빈 문자열)
        image_position: 이미지 위치 및 크기 (예: "right:50%", "bottom:40%")
        text_position: 텍스트 위치 및 크기 (예: "left:45%", "top:55%")
        image_path: 생성된 이미지 파일 경로 (초기값 빈 문자열, 이미지 생성 노드에서 채움)
    
    Note:
        - image_position과 text_position은 PPT 레이아웃에서 영역 배분을 의미
        - 예: image_position="right:50%" → 오른쪽 50% 영역에 이미지 배치
        - text_position="left:45%" → 왼쪽 45% 영역에 텍스트 배치
        - subtitle은 선택사항 (있으면 title 아래 작은 글씨로 표시)
    """
    page_number: int
    section: str
    title: str
    items: List[SubtitleContent]  # ← subtitle과 content 쌍들의 리스트   
    content: str
    image_request: str
    image_position: str
    text_position: str
    image_path: str


# ============================================================
# 전체 그래프 상태(GraphState) 정의
# ============================================================
class GraphState(TypedDict):
    """
    LangGraph 전체 워크플로우의 상태
    
    Attributes:
        rfp_text: PDF/DOCX에서 추출한 RFP 전체 텍스트
        analyzed_json: 분석 노드(PM)가 생성한 JSON 구조
            - project_summary: 과제 전체 요약 (상세 버전)
                - title: 과제명
                - subtitle: 부제 (있는 경우)
                - purpose: 최종 목표
                - background: 추진 배경
                - period: 수행 기간
                - budget: 예산
                - keywords: 핵심 키워드 목록
                - target_technology: 개발 대상 기술
                - expected_impact: 기대 효과
                - evaluation_criteria: 평가 기준
            - tasks: 8개 노드별 작업 배분 정보
                - role: 담당 역할
                - instruction: 구체적 작성 지침
                - relevant_context: RFP 원문 발췌
                - key_points: 핵심 포인트 목록
        slides: 각 노드가 생성한 슬라이드 목록 (병렬 추가)
        final_ppt_path: 최종 생성된 PPT 파일 경로
    
    Note:
        - slides는 Annotated[List[SlideState], operator.add]로 정의
        - 여러 노드가 동시에 slides에 값을 추가해도 자동으로 병합됨
        - analyzed_json은 단일 노드(PM)만 업데이트하므로 일반 dict
    """
    # (1) 입력 데이터
    rfp_text: str
    
    # (2) 분석 결과 (PM 노드의 산출물)
    # 덮어쓰기 모드 - 단일 노드만 업데이트
    analyzed_json: dict
    
    # (3) 생성된 슬라이드들 (8개 노드의 산출물)
    # ★핵심★ operator.add로 병렬 추가 가능
    # 각 노드가 {"slides": [slide1, slide2, ...]}를 반환하면
    # LangGraph가 자동으로 전체 slides 리스트에 병합
    slides: Annotated[List[SlideState], operator.add]
    
    # (4) 최종 결과물
    final_ppt_path: str


# ============================================================
# 유틸리티 함수
# ============================================================
def create_empty_state() -> GraphState:
    """
    빈 초기 상태 생성 함수
    
    Returns:
        GraphState: 모든 필드가 기본값으로 초기화된 상태
    """
    return {
        "rfp_text": "",
        "analyzed_json": {},
        "slides": [],
        "final_ppt_path": ""
    }


def create_slide(
    page_number: int,
    section: str,
    title: str,
    content: str,
    subtitle: str = "",
    image_request: str = "",
    image_position: str = "right:50%",
    text_position: str = "left:45%"
) -> SlideState:
    """
    SlideState 생성 헬퍼 함수
    
    Args:
        page_number: 페이지 번호
        section: 섹션명
        title: 제목
        content: 내용
        subtitle: 부제 (선택)
        image_request: 이미지 프롬프트 (선택)
        image_position: 이미지 위치 (기본값: "right:50%")
        text_position: 텍스트 위치 (기본값: "left:45%")
    
    Returns:
        SlideState: 슬라이드 객체
    """
    return {
        "page_number": page_number,
        "section": section,
        "title": title,
        "subtitle": subtitle,
        "content": content,
        "image_request": image_request,
        "image_position": image_position,
        "text_position": text_position,
        "image_path": ""
    }


def validate_slide(slide: SlideState) -> bool:
    """
    SlideState 유효성 검사
    
    Args:
        slide: 검사할 슬라이드
        
    Returns:
        bool: 필수 필드가 모두 있으면 True
    """
    required_fields = ["page_number", "section", "title", "content"]
    return all(field in slide and slide[field] for field in required_fields)


def validate_analyzed_json(analyzed_json: dict) -> tuple[bool, str]:
    """
    analyzed_json 유효성 검사
    
    Args:
        analyzed_json: 검사할 분석 결과
        
    Returns:
        tuple[bool, str]: (유효성 여부, 에러 메시지)
    """
    if not analyzed_json:
        return False, "분석 결과가 비어있음"
    
    if "error" in analyzed_json:
        return False, f"분석 중 오류: {analyzed_json['error']}"
    
    if "project_summary" not in analyzed_json:
        return False, "project_summary 누락"
    
    if "tasks" not in analyzed_json:
        return False, "tasks 누락"
    
    # project_summary 필수 필드 검사
    summary = analyzed_json["project_summary"]
    required_summary_fields = ["title", "purpose", "period", "budget", "keywords"]
    missing_fields = [f for f in required_summary_fields if f not in summary]
    
    if missing_fields:
        return False, f"project_summary에서 누락된 필드: {', '.join(missing_fields)}"
    
    # tasks 검사
    expected_tasks = [
        "agency_intro", "project_overview", "research_necessity", "research_goal",
        "research_content", "promotion_plan", "expected_outcome", "utilization_plan"
    ]
    
    missing_tasks = [t for t in expected_tasks if t not in analyzed_json["tasks"]]
    if missing_tasks:
        return False, f"tasks에서 누락된 항목: {', '.join(missing_tasks)}"
    
    return True, "정상"


# ============================================================
# 테스트 코드
# ============================================================
if __name__ == "__main__":
    print("=" * 80)
    print("State 구조 테스트 (최종 버전)")
    print("=" * 80)
    
    # 1. SlideState 예시
    sample_slide = create_slide(
        page_number=1,
        section="연구 목표",
        title="연구개발 최종 목표",
        subtitle="AI 기반 예지보전 시스템 개발",  # ← subtitle 추가
        content="• 목표1: AI 정확도 95%\n• 목표2: 처리속도 1초 이내",
        image_request="target achievement visualization with arrows",
        image_position="right:50%",
        text_position="left:45%"
    )
    
    print("\n[SlideState 예시]")
    print(f"  제목: {sample_slide['title']}")
    print(f"  부제: {sample_slide['subtitle']}")  # ← 출력
    print(f"  섹션: {sample_slide['section']}")
    print(f"  이미지 위치: {sample_slide['image_position']}")
    print(f"  텍스트 위치: {sample_slide['text_position']}")
    print(f"  유효성: {validate_slide(sample_slide)}")
    
    # 2. GraphState 예시
    sample_state = create_empty_state()
    sample_state["slides"] = [sample_slide]
    
    print(f"\n[GraphState 예시]")
    print(f"  슬라이드 수: {len(sample_state['slides'])}")
    print(f"  RFP 텍스트: {'있음' if sample_state['rfp_text'] else '없음'}")
    
    # 3. analyzed_json 검증 테스트
    print("\n[analyzed_json 검증 테스트]")
    
    # 정상 케이스
    valid_json = {
        "project_summary": {
            "title": "AI 플랫폼 개발",
            "subtitle": "스마트팩토리용",
            "purpose": "예지보전 시스템 구축",
            "background": "현재 고장 예측 어려움",
            "period": "24개월",
            "budget": "10억원",
            "keywords": ["AI", "예지보전"],
            "target_technology": "LSTM 기반 시스템",
            "expected_impact": "가동률 15% 향상",
            "evaluation_criteria": "기술성 50%, 사업성 30%"
        },
        "tasks": {
            "agency_intro": {"role": "기관 소개", "instruction": "...", "relevant_context": "...", "key_points": []},
            "project_overview": {"role": "사업 개요", "instruction": "...", "relevant_context": "...", "key_points": []},
            "research_necessity": {"role": "연구 필요성", "instruction": "...", "relevant_context": "...", "key_points": []},
            "research_goal": {"role": "연구 목표", "instruction": "...", "relevant_context": "...", "key_points": []},
            "research_content": {"role": "연구 내용", "instruction": "...", "relevant_context": "...", "key_points": []},
            "promotion_plan": {"role": "추진 계획", "instruction": "...", "relevant_context": "...", "key_points": []},
            "expected_outcome": {"role": "기대 성과", "instruction": "...", "relevant_context": "...", "key_points": []},
            "utilization_plan": {"role": "활용 계획", "instruction": "...", "relevant_context": "...", "key_points": []}
        }
    }
    
    is_valid, message = validate_analyzed_json(valid_json)
    print(f"  정상 케이스: {is_valid} - {message}")
    
    # 오류 케이스
    invalid_json = {"project_summary": {}}
    is_valid, message = validate_analyzed_json(invalid_json)
    print(f"  오류 케이스: {is_valid} - {message}")
    
    print("\n" + "=" * 80)
    print("테스트 완료!")
    print("=" * 80)