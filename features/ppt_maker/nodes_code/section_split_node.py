"""규칙 기반 섹션 분할 노드.

목표
- extracted_text를 '발표 순서' 기준 섹션별로 분할한다.
- LLM을 이용하지 않는다(재현성/호출수/안정성).

출력(state 계약)
- section_chunks: {섹션명: 텍스트}
- sections: [{"title": 섹션명, "text": 텍스트}, ...]  ✅ 이후 노드가 이 형태를 사용
"""
#section_split_node.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple
import re

# 발표 순서(고정) + 섹션 헤딩 후보(규칙 기반)
# ✅ 섹션명은 merge_deck_node의 SECTION_ORDER/AGENDA_ITEMS와 반드시 동일해야 함
# ✅ 사용자가 요구한 발표 순서로 고정: 기관소개 → 사업개요 → 연구목표 → 연구필요성 → 연구내용 → 추진계획 → 기대효과 → 활용계획
SECTION_RULES: Dict[str, List[str]] = {
    "기관 소개": ["기관소개", "기관 소개", "수행기관", "수행 기관", "기관 개요", "기관 현황"],
    "사업 개요": [
        "사업개요", "사업 개요", "과제 개요", "연구개요", "연구 개요",
        "연구개발의 개요", "연구개발 개요", "사업 목적"
    ],
    "연구 목표": ["연구 목표", "최종 목표", "단계별 목표", "정량 목표", "정성 목표"],
    "연구 필요성": ["연구 필요성", "추진 배경", "국내외 현황", "국외 현황", "국내 현황"],
    "연구 내용": [
    "연구 내용",
    "연구개발 내용",
    "연구개발과제의 내용",
    "연구개발과제 내용",
    "연구 수행 내용",
    "세부 내용",
    "세부과제",
    "세부 과제",
    "핵심기술",
    "핵심 기술",
    "개발 내용",
    "기술 개발 내용"
],

    "추진 계획": ["추진 계획", "수행 계획", "연구 추진 계획", "추진전략", "추진 전략", "추진 체계", "추진체계", "일정", "로드맵"],
    # 기존 문서/LLM이 '기대 성과'로 쓰더라도 결과 섹션명은 '기대 효과'로 통일
    "기대 효과": ["기대 효과", "기대효과", "기대 성과", "기대성과", "파급효과", "파급 효과", "성과 확산"],
    "활용 계획": ["활용 계획", "활용방안", "활용 방안", "사업화 계획", "활용 전략", "확산 계획", "기술이전", "기술 이전"],
    "Q&A": ["Q&A", "질의응답", "질의 응답"],
}

SECTION_ORDER = list(SECTION_RULES.keys())


def _normalize(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", "", s)
    # 특수문자 제거(목차 기호/점선 등)
    s = re.sub(r"[^0-9A-Za-z가-힣]", "", s)
    return s

def _strip_heading_prefix(s: str) -> str:
    # 예: "05 연구 내용", "5. 연구내용", "Ⅰ. 연구내용", "01 기관 소개" 같은 접두 제거
    s = (s or "").strip()
    s = re.sub(r"^[\(\[]?\s*(?:\d{1,2}|[IVXⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+)\s*[\)\].-]?\s*", "", s)
    return s

def _looks_like_heading(line: str) -> bool:
    # 너무 긴 문장은 헤딩일 확률 낮음
    raw = (line or "").strip()
    if not raw:
        return False
    if len(raw) > 40:
        return False
    # 문장형(마침표/다수 조사 포함) 줄은 헤딩 확률 낮음
    if raw.count("다") >= 2 or raw.count("니다") >= 1:
        return False
    # 콜론이 있으면 설명문일 가능성
    if ":" in raw:
        return False
    return True

def section_split_node(state: Dict[str, Any]) -> Dict[str, Any]:
    extracted_text = state.get("extracted_text") or ""
    if not extracted_text.strip():
        return {"section_chunks": {}, "sections": []}

    lines = extracted_text.splitlines()

    # 1) 헤딩 위치 탐색
    hits: List[Tuple[int, str]] = []
    for idx, line in enumerate(lines):
        raw0 = (line or "").strip()
        if not raw0:
            continue

        raw = _strip_heading_prefix(raw0)
        if not _looks_like_heading(raw0) and not _looks_like_heading(raw):
            continue

        norm = _normalize(raw)

        nxt0 = (lines[idx + 1].strip() if idx + 1 < len(lines) else "")
        nxt = _strip_heading_prefix(nxt0)
        window = f"{raw} {nxt}".strip()
        window_norm = _normalize(window)

        found_section = None
        for section, keywords in SECTION_RULES.items():
            for kw in keywords:
                if not kw:
                    continue
                nkw = _normalize(kw)
                if not nkw:
                    continue

                # 공백/특수문자 제거 기준으로만 비교 (오탐 줄이기)
                if nkw in norm or nkw in window_norm:
                    # '일정' 같은 흔한 키워드는 헤딩일 때만 인정
                    if kw in ["일정", "로드맵"] and not _looks_like_heading(raw0):
                        continue
                    found_section = section
                    break
            if found_section:
                break

        if found_section:
            hits.append((idx, found_section))

    # 2) 섹션 시작점 정렬/중복 제거(첫 등장만 사용)
    hits.sort(key=lambda x: x[0])
    seen = set()
    ordered_hits: List[Tuple[int, str]] = []
    for idx, sec in hits:
        if sec in seen:
            continue
        ordered_hits.append((idx, sec))
        seen.add(sec)

    # 3) 섹션별 chunk 생성
    section_chunks: Dict[str, str] = {}
    if ordered_hits:
        for i, (start_idx, section_name) in enumerate(ordered_hits):
            end_idx = ordered_hits[i + 1][0] if i + 1 < len(ordered_hits) else len(lines)
            chunk_text = "\n".join(lines[start_idx:end_idx]).strip()
            section_chunks[section_name] = chunk_text
    else:
        section_chunks["사업 개요"] = extracted_text.strip()

    # 4) sections(list)
    section_chunks = {_canon_title(k): v for k, v in section_chunks.items()}

    sections = [{"title": sec, "text": section_chunks[sec]} for sec in SECTION_ORDER if sec in section_chunks]
    
    print("[DEBUG][split] section_chunks keys:", list(section_chunks.keys()))
    print("[DEBUG][split] missing:", [s for s in SECTION_ORDER if s not in section_chunks])
    
def _canon_title(t: str) -> str:
    # 연속 공백 -> 1개, 앞뒤 공백 제거
    return re.sub(r"\s+", " ", (t or "").strip())

    return {"section_chunks": section_chunks, "sections": sections}