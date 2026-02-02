"""
LangGraph State 정의 (최종 버전)
- SlideState: 슬라이드 1장의 구조
- GraphState: 전체 그래프 상태
"""

import operator
from typing import TypedDict, List, Annotated, Optional, Dict, Any
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
    page_number: int          # 페이지 번호 (나중에 정렬용)
    section: str              # 어느 파트인지 (예: 연구 목표)
    title: str                # 슬라이드 제목
    items: List[SubtitleContent]
    image_request: str        # 그림 프롬프트 (없으면 빈 문자열)
    image_position: str       # 그림 좌표
    image_path: str           # 생성된 이미지 파일 경로 (초기엔 비어있음)

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
    content: str = "",
    subtitle: str = "",
    items: Optional[List[Dict[str, str]]] = None,
    image_request: str = "",
    image_position: str = "right:50%",
    text_position: str = "left:45%",
    image_path: str = "",
) -> "SlideState":
    """
    SlideState 생성 헬퍼 함수
    - subtitle/items/text_position을 항상 포함해 KeyError 방지
    - items는 [{"subtitle": "...", "content": "..."}, ...] 형태
    """

    normalized_items: List[Dict[str, str]] = []
    if items:
        for it in items:
            if isinstance(it, dict):
                normalized_items.append({
                    "subtitle": str(it.get("subtitle", "")),
                    "content": str(it.get("content", "")),
                })

    return {
        "page_number": int(page_number),
        "section": str(section),
        "title": str(title),
        "subtitle": str(subtitle or ""),
        "items": normalized_items,
        "content": str(content or ""),
        "image_request": str(image_request or ""),
        "image_position": str(image_position or "right:50%"),
        "text_position": str(text_position or "left:45%"),
        "image_path": str(image_path or ""),
    }


def validate_slide(slide: SlideState) -> bool:
    """
    SlideState 유효성 검사

    통과 조건:
    - page_number/section/title 키가 존재하고 값이 유효
    - 본문은 (content가 비어있지 않음) OR (items에 유효한 항목이 1개 이상) 중 하나면 OK
    """

    # 1) 키 존재 + 기본값 검사
    for key in ["page_number", "section", "title"]:
        if key not in slide:
            return False

    # page_number는 0보다 큰 정수 권장(0 허용 여부는 팀 룰)
    try:
        if int(slide["page_number"]) <= 0:
            return False
    except Exception:
        return False

    if not str(slide["section"]).strip():
        return False
    if not str(slide["title"]).strip():
        return False

    # 2) 본문 검사: content 또는 items 중 하나
    content_ok = bool(str(slide.get("content", "")).strip())

    items = slide.get("items", [])
    items_ok = False
    if isinstance(items, list) and len(items) > 0:
        # items 안에 subtitle/content 중 하나라도 채워진 항목이 있으면 OK
        for it in items:
            if isinstance(it, dict):
                sub_ok = bool(str(it.get("subtitle", "")).strip())
                txt_ok = bool(str(it.get("content", "")).strip())
                if sub_ok or txt_ok:
                    items_ok = True
                    break

    return content_ok or items_ok


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


