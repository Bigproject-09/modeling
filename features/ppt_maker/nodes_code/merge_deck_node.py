from __future__ import annotations

import os
import re
from typing import Any, Dict, List

# ✅ 발표 순서 고정 (사용자 요구 순서)
SECTION_ORDER = [
    "기관 소개",
    "사업 개요",
    "연구 목표",
    "연구 필요성",
    "연구 내용",
    "추진 계획",
    "기대 효과",
    "활용 계획",
]
AGENDA_SUBTITLE = {
    "기관 소개": "수행기관의 핵심역량 및 인프라",
    "사업 개요": "연구개발의 최종 목표 및 대상 기술",
    "연구 목표": "구체적인 연구 목표 설정",
    "연구 필요성": "기술 현황 및 시장 분석",
    "연구 내용": "선행 연구 및 핵심 역량",
    "추진 계획": "단계별 연구개발 추진 전략",
    "기대 효과": "연구개발 성과 및 파급효과",
    "활용 계획": "최종 결과물 및 실용화 목표",
}


def _norm(s: Any) -> str:
    s = str(s or "").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", s).strip()

def _wrap_cover_title(title: str, max_line: int = 24, max_lines: int = 3) -> str:
    t = _norm(title)
    if not t:
        return "(과제명 미기재)"

    # 콜론이 있으면 기준으로 먼저 줄바꿈
    for sep in [":", "："]:
        if sep in t:
            left, right = t.split(sep, 1)
            left = _norm(left) + sep
            right = _norm(right)
            t = left + "\n" + right
            break

    # 이미 줄바꿈 있으면 추가 래핑만
    lines: List[str] = []
    for raw in t.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        while len(raw) > max_line:
            cut = raw.rfind(" ", 0, max_line + 1)
            if cut <= 0:
                cut = max_line
            lines.append(raw[:cut].strip())
            raw = raw[cut:].strip()
            if len(lines) >= max_lines:
                break
        if len(lines) >= max_lines:
            break
        lines.append(raw)

    out = "\n".join(lines[:max_lines])

    # ✅ (추가) 표지 제목이 전체적으로 너무 길면 과감히 축약
    # - 줄바꿈 포함 전체 문장 길이 제한
    flat = out.replace("\n", " ").strip()
    if len(flat) > 60:
        flat = flat[:60].rstrip() + "…"
        # 축약된 건 한 줄로(잘림 방지)
        out = flat

    return out


def _short_cover_title(title: str, max_chars: int = 42) -> str:
    t = _norm(title)
    if not t:
        return "(과제명 미기재)"

    # 콜론이 있으면 좌측을 우선 사용
    for sep in [":", "："]:
        if sep in t:
            left = _norm(t.split(sep, 1)[0])
            if left:
                t = left
            break

    if len(t) > max_chars:
        t = t[:max_chars].rstrip() + "…"
    return t or "(과제명 미기재)"


def _extract_title_from_extracted_text(extracted_text: str) -> str:
    t = (extracted_text or "").replace("\u00a0", " ")

    patterns = [
        r"과제명\s*[:：]\s*(.+)",
        r"연구개발\s*과제명\s*[:：]\s*(.+)",
        r"과제\s*제목\s*[:：]\s*(.+)",
        r"사업명\s*[:：]\s*(.+)",
    ]
    for pat in patterns:
        m = re.search(pat, t)
        if m:
            cand = _norm(m.group(1))
            return cand[:80]

    # 라벨이 없을 때: 문서 앞부분에서 제목처럼 보이는 한 줄을 찾기(추측은 안 함)
    head = "\n".join((extracted_text or "").splitlines()[:160]).replace("\u00a0", " ")
    for line in head.splitlines():
        line = _norm(line)
        if 10 <= len(line) <= 90:
            # 너무 일반 섹션/메타 단어 제외
            if any(x in line for x in ["목차", "요약", "기관", "사업", "연구", "필요성", "목표", "내용", "추진", "기대", "활용"]):
                continue
            # 제목 후보로 자주 나오는 패턴
            if any(k in line for k in ["개발", "시스템", "플랫폼", "모델", "예측", "분석"]):
                return line

    return ""


def _fallback_title_from_filename(state: Dict[str, Any]) -> str:
    src = _norm(state.get("source_path") or "")
    if not src:
        return ""
    base = os.path.splitext(os.path.basename(src))[0]
    base = _norm(base)
    # 너무 흔한 파일명 제거
    for bad in ["제안서", "사용자업로드", "업로드", "최종", "본", "양식"]:
        base = base.replace(bad, "").strip()
    base = _norm(base)
    return base[:80]


def _make_cover(deck_title: str, org_name: str = "") -> Dict[str, Any]:
    short_title = _short_cover_title(deck_title, max_chars=34)
    full_title = _norm(deck_title) or "(과제명 미기재)"
    subtitle = "국가 R&D 선정평가 발표자료"
    org = _norm(org_name)
    org_line = org if org else "(미기재)"

    cover_table = (
        "| 항목 | 내용 |\n"
        "|---|---|\n"
        f"| 발표 과제명 | {full_title} |\n"
        f"| 주관기관 | {org_line} |\n"
        "| 발표 구분 | 선정평가 발표 |\n"
    )

    return {
        "section": "표지",
        "slide_title": short_title,
        "key_message": subtitle,
        "bullets": ["핵심 목표와 추진 전략을 중심으로 설명드립니다."],
        "evidence": [],
        "image_needed": False,
        "image_type": "none",
        "image_brief_ko": "",
        "TABLE_MD": cover_table,
        "DIAGRAM_SPEC_KO": "",
        "CHART_SPEC_KO": "",
        "order": 1,
    }


def _make_agenda(items: List[str]) -> Dict[str, Any]:
    rows: List[str] = []
    for i, sec in enumerate(items[:8], 1):
        sub = AGENDA_SUBTITLE.get(sec, "")
        rows.append(f"| {i:02d} | {i:02d}. {sec} | {sub} |")
    agenda_table = (
        "| 번호 | 항목 | 설명 |\n"
        "|---|---|---|\n"
        + "\n".join(rows)
        + "\n"
    )

    return {
        "section": "목차",
        "slide_title": "목차",
        "key_message": "아래 순서에 따라 발표를 진행하겠습니다.",
        "bullets": [],
        "evidence": [],
        "image_needed": False,
        "image_type": "none",
        "image_brief_ko": "",
        "TABLE_MD": agenda_table,
        "DIAGRAM_SPEC_KO": "",
        "CHART_SPEC_KO": "",
        "order": 2,
    }



def _make_thanks(order: int, org_name: str = "") -> Dict[str, Any]:
    org = _norm(org_name)
    org_line = org if org else "(미기재)"
    thanks_table = (
        "| 항목 | 내용 |\n"
        "|---|---|\n"
        "| Q&A 진행 | 질의응답(Q&A) |\n"
        "| 질의 권장 | 연구 목표 · 추진계획 · 기대효과 중심 |\n"
        "| 마무리 | 질문 주시면 바로 답변드리겠습니다 |\n"
        f"| 주관기관 | {org_line} |\n"
    )

    return {
        "section": "Q&A",
        "slide_title": "감사합니다",
        "key_message": "질의응답",
        "bullets": ["경청해 주셔서 감사합니다."],
        "evidence": [],
        "image_needed": False,
        "image_type": "none",
        "image_brief_ko": "",
        "TABLE_MD": thanks_table,
        "DIAGRAM_SPEC_KO": "",
        "CHART_SPEC_KO": "",
        "order": order,
    }


def merge_deck_node(state: Dict[str, Any]) -> Dict[str, Any]:
    
    print("[DEBUG][merge] FILE =", __file__)
    print("[DEBUG][merge] merge_deck_node FILE =", __file__)
    print("[DEBUG][merge] deck_title BEFORE =", state.get("deck_title"))

    # 1) deck_title 보정
    deck_title = _norm(state.get("deck_title") or "")
    extracted_text = state.get("extracted_text") or ""
    guessed = _extract_title_from_extracted_text(extracted_text)

    if (not deck_title) or (deck_title == "(과제명 미기재)"):
        if guessed:
            deck_title = guessed
        else:
            # ✅ 마지막 fallback: 파일명
            fn = _fallback_title_from_filename(state)
            deck_title = fn or "(과제명 미기재)"

    section_decks: Dict[str, Any] = state.get("section_decks") or {}

    # 2) 키 정규화
    normalized: Dict[str, Any] = {}
    for k, v in section_decks.items():
        nk = _norm(k)
        if nk:
            normalized[nk] = v
    section_decks = normalized

    org_name = _norm((state.get("company_profile") or {}).get("name") or state.get("org_name") or "")
    slides: List[Dict[str, Any]] = []
    slides.append(_make_cover(deck_title, org_name=org_name))
    slides.append(_make_agenda(SECTION_ORDER))


    # 3) 본문 슬라이드 병합(순서 고정)
    order = 3
    for sec in SECTION_ORDER:
        v = section_decks.get(sec)
        sec_slides: List[Dict[str, Any]] = []
        if isinstance(v, dict):
            sec_slides = v.get("slides") or []

        for s in sec_slides:
            if not isinstance(s, dict):
                continue
            s2 = dict(s)

            # 섹션 확정 + 텍스트 정규화
            s2["section"] = sec
            s2["slide_title"] = _norm(s2.get("slide_title"))
            s2["key_message"] = _norm(s2.get("key_message"))

            # 이미지 생성 플래그는 끔
            s2["image_needed"] = False
            s2["image_type"] = "none"
            s2["image_brief_ko"] = ""

            # 시각요소 기본키 보장
            s2.setdefault("TABLE_MD", "")
            s2.setdefault("DIAGRAM_SPEC_KO", "")
            s2.setdefault("CHART_SPEC_KO", "")
            # ✅ 기대 효과 섹션은 이미지 대신 표/다이어그램 강제
            if sec == "기대 효과":
                has_table = bool((s2.get("TABLE_MD") or "").strip())
                has_diag = bool((s2.get("DIAGRAM_SPEC_KO") or "").strip())
                has_chart = bool((s2.get("CHART_SPEC_KO") or "").strip())

                if not (has_table or has_diag or has_chart):
                    # 1) 기본은 표로 채우기(가장 안정적)
                    s2["TABLE_MD"] = (
                        "| 구분 | 핵심 효과 | 정량/정성 지표 |\n"
                        "|---|---|---|\n"
                        "| 기술적 | 예측 정확도/해상도 향상, 결합모델 확보 | 공고 성능지표 달성, 정확도 향상(%) |\n"
                        "| 경제·산업 | 재해 피해 저감, 서비스 시장 창출 | 연간 파급효과(추정), 기술이전/사업화 |\n"
                        "| 사회적 | 국민 안전/정책지원, 국제 위상 | 조기경보 강화, 유관기관 활용 |\n"
                    )

            # ✅ placeholder(이미지 빈칸) 방지: 표/다이어그램 스펙 자동 주입
            title_n = re.sub(r"\s+", "", (s2.get("slide_title") or ""))

            has_table = bool((s2.get("TABLE_MD") or "").strip())
            has_diag = bool((s2.get("DIAGRAM_SPEC_KO") or "").strip())
            has_chart = bool((s2.get("CHART_SPEC_KO") or "").strip())

            if not (has_table or has_diag or has_chart):
                if any(k in title_n for k in ["구성도", "아키텍처", "모듈", "플랫폼", "구조", "시스템구성"]):
                    s2["DIAGRAM_SPEC_KO"] = (
                        "NODES:\n"
                        "- id: N1 | label: 입력/수집 | role: (미기재)\n"
                        "- id: N2 | label: 전처리 | role: (미기재)\n"
                        "- id: N3 | label: 핵심 처리 | role: (미기재)\n"
                        "- id: N4 | label: 저장/관리 | role: (미기재)\n"
                        "- id: N5 | label: 서비스/출력 | role: (미기재)\n"
                        "EDGES:\n"
                        "- from: N1 | to: N2 | label: 데이터\n"
                        "- from: N2 | to: N3 | label: 데이터\n"
                        "- from: N3 | to: N4 | label: 결과/메타\n"
                        "- from: N4 | to: N5 | label: 제공\n"
                    )
                elif any(k in title_n for k in ["데이터흐름", "처리과정", "처리흐름", "파이프라인", "워크플로우"]):
                    s2["DIAGRAM_SPEC_KO"] = (
                        "NODES:\n"
                        "- id: N1 | label: 데이터 입력 | role: (미기재)\n"
                        "- id: N2 | label: 정제/전처리 | role: (미기재)\n"
                        "- id: N3 | label: 분석/모델링 | role: (미기재)\n"
                        "- id: N4 | label: 검증/평가 | role: (미기재)\n"
                        "- id: N5 | label: 결과 제공 | role: (미기재)\n"
                        "EDGES:\n"
                        "- from: N1 | to: N2 | label: raw\n"
                        "- from: N2 | to: N3 | label: clean\n"
                        "- from: N3 | to: N4 | label: output\n"
                        "- from: N4 | to: N5 | label: report\n"
                    )
                elif any(k in title_n for k in ["조직도", "수행체계", "추진체계", "거버넌스", "역할분담"]):
                    s2["DIAGRAM_SPEC_KO"] = (
                        "NODES:\n"
                        "- id: N1 | label: 총괄/PM | role: (미기재)\n"
                        "- id: N2 | label: 기술개발 | role: (미기재)\n"
                        "- id: N3 | label: 데이터/플랫폼 | role: (미기재)\n"
                        "- id: N4 | label: 검증/실증 | role: (미기재)\n"
                        "- id: N5 | label: 사업화/확산 | role: (미기재)\n"
                        "EDGES:\n"
                        "- from: N1 | to: N2 | label: 관리\n"
                        "- from: N1 | to: N3 | label: 관리\n"
                        "- from: N1 | to: N4 | label: 관리\n"
                        "- from: N1 | to: N5 | label: 관리\n"
                    )
                elif any(k in title_n for k in ["일정", "로드맵", "단계", "성과", "지표", "계획"]):
                    s2["TABLE_MD"] = (
                        "| 구분 | 내용 |\n"
                        "|---|---|\n"
                        "| 1단계 | (미기재) |\n"
                        "| 2단계 | (미기재) |\n"
                        "| 3단계 | (미기재) |\n"
                    )

            s2["order"] = order
            order += 1
            slides.append(s2)

    # 4) 마지막 감사/Q&A
    slides.append(_make_thanks(order, org_name=org_name))

    state["deck_title"] = deck_title
    state["deck_json"] = {
        "deck_title": deck_title,
        "slides": slides,
    }
    return state
