"""섹션별 슬라이드 결과를 최종 deck_json으로 병합(규칙 기반).

입력(state 계약)
- state["section_decks"]: {섹션명: {"slides":[...], ...}, ...}
- state["deck_title"]

출력
- state["deck_json"] = {"deck_title": ..., "slides":[...]}
"""
#merge_deck_node.py
from __future__ import annotations

from typing import Any, Dict, List

from .state import GraphState

# ✅ 발표 순서(고정)
SECTION_ORDER: List[str] = [
    "기관 소개",
    "사업 개요",
    "연구 목표",
    "연구 필요성",
    "연구 내용",
    "추진 계획",
    "기대 효과",
    "활용 계획",
    "Q&A",
]

# ✅ 목차 표기(발표 순서와 동일)
AGENDA_ITEMS: List[str] = [
    "기관 소개",
    "사업 개요",
    "연구 목표",
    "연구 필요성",
    "연구 내용",
    "추진 계획",
    "기대 효과",
    "활용 계획",
]

# ✅ 섹션명 흔들림 통일 (Gemini가 기대성과/기대효과 섞는 문제)
SECTION_ALIASES = {
    "기대 성과": "기대 효과",
    "기대효과": "기대 효과",
    "기대성과": "기대 효과",
    "활용방안": "활용 계획",
    "활용 계획": "활용 계획",
    "활용계획": "활용 계획",
    "기관소개": "기관 소개",
    "사업개요": "사업 개요",
    "연구목표": "연구 목표",
    "연구필요성": "연구 필요성",
    "연구내용": "연구 내용",
    "추진계획": "추진 계획",
    "질의응답": "Q&A",
    "질문": "Q&A",
}


def _norm(s: str) -> str:
    s = (s or "").strip()
    return SECTION_ALIASES.get(s, s)


def _make_cover_slide(deck_title: str) -> Dict[str, Any]:
    return {
        "section": "표지",
        "slide_title": deck_title or "발표자료",
        "key_message": "",
        "bullets": [],
        "evidence": [],
        "image_needed": False,
        "image_type": "",
        "image_brief_ko": "",
        "TABLE_MD": "",
        "DIAGRAM_SPEC_KO": "",
        "CHART_SPEC_KO": "",
    }


def _make_agenda_slide() -> Dict[str, Any]:
    return {
        "section": "목차",
        "slide_title": "목차",
        "key_message": "발표 내용 구성",
        "bullets": [f"{i+1}. {t}" for i, t in enumerate(AGENDA_ITEMS)],
        "evidence": [],
        "image_needed": False,
        "image_type": "",
        "image_brief_ko": "",
        "TABLE_MD": "",
        "DIAGRAM_SPEC_KO": "",
        "CHART_SPEC_KO": "",
    }


def _is_chapter_like(slide: Dict[str, Any]) -> bool:
    t = ((slide.get("slide_title") or "") + " " + (slide.get("section") or "")).upper()
    # 구분용 타이틀 슬라이드(대개 bullets 없음)
    if any(x in t for x in ["CHAPTER", "PART", "SECTION"]) and len(slide.get("bullets") or []) == 0:
        return True
    return False


def _ensure_minimum_slide(section_decks: Dict[str, Any], sec: str, slide: Dict[str, Any]) -> None:
    if sec not in section_decks or not (section_decks.get(sec) or {}).get("slides"):
        section_decks[sec] = {"section": sec, "slides": [slide]}
def _ensure_minimum_slides(section_decks: Dict[str, Any], sec: str, min_count: int, make_slide_fn) -> None:
    d = section_decks.get(sec)
    if not d:
        section_decks[sec] = {"section": sec, "slides": []}
        d = section_decks[sec]

    slides = d.get("slides") or []
    if not isinstance(slides, list):
        slides = []

    while len(slides) < min_count:
        slides.append(make_slide_fn(len(slides) + 1))

    d["slides"] = slides


def merge_deck_node(state: GraphState) -> GraphState:
    raw_title = (state.get("deck_title") or "").strip() or "국가 R&D 선정평가 발표자료"
    deck_title = raw_title
    state["deck_title"] = deck_title

    # 0) 섹션키 정규화(aliases 적용)
    section_decks_in = state.get("section_decks") or {}
    section_decks: Dict[str, Any] = {}
    for k, v in section_decks_in.items():
        nk = _norm(k)
        if not isinstance(v, dict):
            continue
        slides = v.get("slides") or []
        if not isinstance(slides, list):
            continue
        # 슬라이드 내부 section도 통일

        for s in slides:
            if isinstance(s, dict):
                s["section"] = _norm(s.get("section"))
        if nk in section_decks:
            section_decks[nk]["slides"].extend(slides)
        else:
            section_decks[nk] = {"section": nk, "slides": slides}
    # 0-1) 기관 소개 누락 시 최소 1장 보강
    _ensure_minimum_slide(
        section_decks,
        "기관 소개",
        {
            "section": "기관 소개",
            "slide_title": "기관 소개 및 수행역량",
            "key_message": "수행기관의 핵심역량·인프라·유사과제 경험을 간결하게 제시",
            "bullets": [
                "수행조직: 총괄책임자/PM/핵심연구진 구성 및 역할",
                "핵심역량: 관련 기술(모델/데이터/시스템) 수행 경험",
                "인프라: GPU/서버/데이터 파이프라인/실증 환경 보유",
                "유사과제/성과: 논문·특허·실증·기술이전 등(있으면 기재)",
            ],
            "evidence": [],
            "image_needed": False,
            "image_type": "",
            "image_brief_ko": "",
            "TABLE_MD": "",
            "DIAGRAM_SPEC_KO": "",
            "CHART_SPEC_KO": "",
        },
    )

    # 1) 기대 효과 누락 시 최소 1장 보강 (너 코드 유지, 다만 섹션명 통일)
    _ensure_minimum_slide(
        section_decks,
        "기대 효과",
        {
            "section": "기대 효과",
            "slide_title": "기대 효과(요약)",
            "key_message": "기술·경제·사회적 효과를 정량/정성 지표로 제시",
            "bullets": [
                "기술적 효과: 예측 정확도/연산 효율/모델 안정성 개선(원문 기반 지표 우선)",
                "경제·산업적 효과: 활용 분야 확산 및 비용 절감/생산성 향상",
                "사회·정책적 기여: 재난·안전/기후 리스크 대응 고도화",
            ],
            "evidence": [],
            "image_needed": False,
            "image_type": "table",
            "image_brief_ko": "",
            "TABLE_MD": "| 구분 | 성과 내용 | 지표/근거 |\n|---|---|---|\n| 기술 | 예측/모델 고도화 | 미기재 |\n| 경제 | 비용 절감/효율화 | 미기재 |\n| 사회 | 리스크 대응 | 미기재 |",
            "DIAGRAM_SPEC_KO": "",
            "CHART_SPEC_KO": "",
        },
    )

    # 2) 활용 계획 누락 시 최소 1장 보강 (너가 계속 빠진다 했으니 여기서 보장)
    _ensure_minimum_slide(
        section_decks,
        "활용 계획",
        {
            "section": "활용 계획",
            "slide_title": "연구개발성과 활용 계획",
            "key_message": "성과의 현장 적용·사업화·확산 경로를 명확히 제시",
            "bullets": [
                "사업화: 기술이전/라이선스/공동사업화 대상 및 일정(안)",
                "공공활용: 관련 기관·지자체·공공플랫폼 연계(적용 시나리오)",
                "표준/인증: 표준화 로드맵 및 인증/검증 계획",
                "확산: 오픈API/데이터 공유 범위, 사용자 교육·홍보 계획",
            ],
            "evidence": [],
            "image_needed": False,
            "image_type": "diagram",
            "image_brief_ko": "",
            "TABLE_MD": "",
            "DIAGRAM_SPEC_KO": "단계형 로드맵(원천기술→서비스구축→기술이전/사업화→확산) 4단계, 각 단계에 2~3개 핵심 항목 라벨링",
            "CHART_SPEC_KO": "",
        },
    )

    merged: List[Dict[str, Any]] = []

    # 3) 표지/목차 고정
    merged.append(_make_cover_slide(deck_title))
    merged.append(_make_agenda_slide())

    # 4) 섹션 순서대로 결합
    for sec in SECTION_ORDER:
        d = section_decks.get(sec)
        if not d:
            continue
        slides = d.get("slides") if isinstance(d, dict) else None
        if isinstance(slides, list):
            merged.extend(slides)

    # 5) ORDER 밖 슬라이드(디버깅용) 뒤에 붙이되, 챕터류 제거
    for sec, d in section_decks.items():
        if _norm(sec) in set(SECTION_ORDER):
            continue
        slides = d.get("slides") if isinstance(d, dict) else None
        if isinstance(slides, list):
            merged.extend(slides)

    # 6) 챕터/구분 슬라이드 제거 + 이미지 플래그 기본 정리
    cleaned: List[Dict[str, Any]] = []
    for s in merged:
        if not isinstance(s, dict):
            continue
        if _is_chapter_like(s):
            continue
        # 이미지 생성 유발 최소화(너가 “AI 이미지 싫다” 했으니)
        s.setdefault("image_needed", False)
        if s.get("image_needed") is True:
            # Gemini가 실수로 true를 줘도 여기서 끔
            s["image_needed"] = False
        # 필드 기본값
        s.setdefault("image_type", "")
        s.setdefault("image_brief_ko", "")
        s.setdefault("TABLE_MD", "")
        s.setdefault("DIAGRAM_SPEC_KO", "")
        s.setdefault("CHART_SPEC_KO", "")
        cleaned.append(s)
    merged = cleaned

    # 7) 기관 소개는 1장만 유지
    intro_idx = [i for i, s in enumerate(merged) if _norm(s.get("section")) == "기관 소개"]
    if len(intro_idx) > 1:
        keep = intro_idx[0]
        merged = [s for j, s in enumerate(merged) if not (_norm(s.get("section")) == "기관 소개" and j != keep)]

    # 8) Q&A는 항상 마지막 1장으로 고정
    merged = [s for s in merged if _norm(s.get("section")) != "Q&A"]
    merged.append({
        "section": "Q&A",
        "slide_title": "Q&A / 감사합니다",
        "key_message": "",
        "bullets": [],
        "evidence": [],
        "image_needed": False,
        "image_type": "",
        "image_brief_ko": "",
        "TABLE_MD": "",
        "DIAGRAM_SPEC_KO": "",
        "CHART_SPEC_KO": "",
    })

    # 9) order 재부여
    for i, s in enumerate(merged, 1):
        s["order"] = i

    state["deck_json"] = {"deck_title": deck_title, "slides": merged}

    print(f"[DEBUG] merge_deck_node merged slides: {len(merged)}")
    return state