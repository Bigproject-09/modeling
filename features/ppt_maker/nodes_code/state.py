"""LangGraph State 정의 (PPT 자동 생성 파이프라인용)

워크플로우(의도):
- Extract -> Split(규칙) -> Gemini(섹션별) -> Merge(규칙) -> Gamma(1회)

원칙:
- state는 "노드 간 데이터 계약"이다.
- total=False 이므로 일부 키는 선택이지만, 파이프라인 핵심 키는 명확히 정의한다.
"""
#state.py
from __future__ import annotations

from typing import Any, Dict, List, TypedDict


class GraphState(TypedDict, total=False):
    # 입력
    source_path: str

    # 추출 텍스트 (전체)
    extracted_text: str

    # Split 결과 (권장: sections 사용)
    # sections: [{"title": "<섹션명>", "text": "<섹션 텍스트>"} ...]
    sections: List[Dict[str, str]]

    # 호환/디버깅 용 (dict 형태)
    section_chunks: Dict[str, str]

    # 섹션별 Gemini 결과
    # section_decks[section] = {"section":..., "deck_title":..., "slides":[...]}
    section_decks: Dict[str, Any]

    # Merge 결과
    deck_json: Dict[str, Any]
    deck_title: str

    # 출력 옵션
    output_dir: str
    output_filename: str

    # Gemini 옵션
    gemini_model: str
    gemini_temperature: float
    gemini_max_output_tokens: int
    gemini_max_retries: int

    # Gamma 옵션/결과
    gamma_theme: str
    gamma_timeout_sec: int
    gamma_generation_id: str
    gamma_result: Dict[str, Any]
    pptx_url: str
    pptx_path: str

    # 최종 결과
    final_ppt_path: str

    # (선택) PPTX 후처리 폰트명
    font_name: str


def create_empty_state() -> GraphState:
    return {
        "source_path": "",
        "extracted_text": "",
        "sections": [],
        "section_chunks": {},
        "section_decks": {},
        "deck_json": {},
        "deck_title": "",
        "final_ppt_path": "",
    }