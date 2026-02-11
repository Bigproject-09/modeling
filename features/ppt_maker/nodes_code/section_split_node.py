"""규칙 기반 섹션 분할 노드.

목표
- extracted_text를 '발표 순서' 기준 섹션별로 분할한다.
- LLM을 이용하지 않는다(재현성/호출수/안정성).

출력(state 계약)
- section_chunks: {섹션명: 텍스트}
- sections: [{"title": 섹션명, "text": 텍스트}, ...]
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
import re


SECTION_RULES: Dict[str, List[str]] = {
    "기관 소개": ["기관소개", "기관 소개", "수행기관", "수행 기관", "기관 개요", "기관 현황"],
    "사업 개요": ["사업개요", "사업 개요", "과제 개요", "연구개발 개요", "개요"],
    "연구 목표": ["연구목표", "연구 목표", "목표", "최종 목표", "세부 목표"],
    "연구 필요성": ["연구필요성", "연구 필요성", "필요성", "배경", "추진 배경"],
    "연구 내용": ["연구내용", "연구 내용", "핵심 내용", "개발 내용", "세부 내용", "주요 내용"],
    "추진 계획": ["추진계획", "추진 계획", "수행계획", "수행 계획", "일정", "로드맵", "추진 전략"],
    "기대 효과": ["기대효과", "기대 효과", "파급효과", "경제적 효과", "사회적 효과"],
    "활용 계획": ["활용계획", "활용 계획", "활용 방안", "사업화", "확산", "성과 활용"],
    "Q&A": ["Q&A", "QnA", "Q & A", "질의응답", "감사합니다", "문의"],
}

# ✅ 사용자 요구 순서(고정)
SECTION_ORDER = [
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


def _normalize(s: str) -> str:
    s = (s or "").replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _find_section_headers(lines: List[str]) -> List[Tuple[int, str]]:
    """
    각 줄에서 섹션 헤더 후보를 찾아 (line_index, section_name) 목록을 반환
    - 가장 앞쪽에서 발견되는 섹션명을 우선
    """
    found: List[Tuple[int, str]] = []
    for i, raw in enumerate(lines):
        line = _normalize(raw)
        if not line:
            continue

        # 헤더 후보: "1. 연구 목표", "Ⅰ 연구 목표", "[연구 목표]" 등도 잡히게
        line_compact = re.sub(r"[\[\]【】]", "", line)
        line_compact = re.sub(r"^[\s\d\.\-–—ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+", "", line_compact).strip()

        # 후보가 여러 개면 "긴 키워드 우선", 동률은 섹션 순서 우선
        candidates: List[Tuple[int, int, str]] = []
        for sec_idx, sec in enumerate(SECTION_ORDER):
            for key in SECTION_RULES.get(sec, []):
                if key and (key in line_compact):
                    bonus = 0
                    if sec == "연구 목표" and any(k in line_compact for k in ["연구목표", "연구 목표", "최종 목표", "세부 목표"]):
                        bonus = 10
                    score = len(key) + bonus
                    candidates.append((score, -sec_idx, sec))

        if candidates:
            candidates.sort(reverse=True)
            found.append((i, candidates[0][2]))

    # 같은 라인에서 여러 섹션이 잡히는 경우 첫 섹션만 남김
    dedup: Dict[int, str] = {}
    for idx, sec in found:
        if idx not in dedup:
            dedup[idx] = sec

    # 순서대로 정렬
    out = [(idx, dedup[idx]) for idx in sorted(dedup.keys())]
    return out


def section_split_node(state: Dict[str, Any]) -> Dict[str, Any]:
    extracted_text = state.get("extracted_text") or ""
    lines = (extracted_text or "").splitlines()

    headers = _find_section_headers(lines)

    # 헤더가 거의 없으면 전체를 하나로 두고, 나머지는 빈 섹션으로 처리
    if not headers:
        section_chunks = {sec: "" for sec in SECTION_ORDER}
        # 전체를 사업 개요에라도 넣어두면 LLM이 뭔가 만들 여지가 생김
        section_chunks["사업 개요"] = extracted_text
        state["section_chunks"] = section_chunks
        state["sections"] = [{"title": sec, "text": section_chunks[sec]} for sec in SECTION_ORDER]
        return state

    section_chunks: Dict[str, str] = {sec: "" for sec in SECTION_ORDER}

    # 구간 나누기
    for j, (start_idx, sec) in enumerate(headers):
        end_idx = headers[j + 1][0] if (j + 1) < len(headers) else len(lines)
        chunk = "\n".join(lines[start_idx:end_idx]).strip()
        # 동일 섹션이 여러 번 나오면 이어붙임
        if section_chunks.get(sec):
            section_chunks[sec] += "\n\n" + chunk
        else:
            section_chunks[sec] = chunk

    state["section_chunks"] = section_chunks
    state["sections"] = [{"title": sec, "text": section_chunks.get(sec, "")} for sec in SECTION_ORDER]
    return state
