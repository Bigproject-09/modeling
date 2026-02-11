from __future__ import annotations

import re
from typing import Any, Dict, List

from google import genai
from google.genai import types

from .llm_utils import generate_content_with_retry, get_gemini_client


# -----------------------------
# Prompt
# -----------------------------
def _build_prompt() -> str:
    return """
역할: 너는 국가 R&D 선정평가 발표자료(PPT)를 작성하는 실무 PM/총괄기획자다.

목표:
'AI가 만든 티'가 아니라 실제 선정평가장에서 쓰는 자료처럼,
보편적·사실적·증빙가능한 근거 중심으로
논리 완결성을 갖춘 발표자료를 작성한다.

제약:
- 지금 입력에는 특정 '섹션'의 원문만 들어있다.
- 반드시 그 섹션에 해당하는 슬라이드만 생성한다.
- 근거/수치가 없으면 추정하지 말고 '미기재'로 둔다.
- 출력은 아래 포맷을 100% 지켜라. (추가 텍스트 금지)

중요 원칙:
슬라이드 수를 최소화하려 하지 말고,
발표자가 실제로 설명할 수 있는 수준까지 충분히 분리하여 작성한다.

--------------------------------

출력 포맷:

DECK_TITLE: <발표자료 전체 제목 1줄>

DECK_TITLE은 섹션과 무관하게 항상 동일한 전체 과제명 형태로 1줄로 작성한다(원문에 없으면 '(과제명 미기재)'). 

SLIDE
SECTION: <섹션명>
TITLE: <슬라이드 제목 1줄>
KEY_MESSAGE: <핵심 메시지 1줄>

BULLETS:
- <불릿 1>
- <불릿 2>
- <불릿 3 이상 작성>

EVIDENCE:
- type: <출처/수치/근거>
  text: <텍스트>

IMAGE_NEEDED: <true/false>
IMAGE_TYPE: <diagram/chart/table/none 중 하나>
IMAGE_BRIEF_KO: <(사진/일러스트 금지) 벡터 인포그래픽/도형/차트 지시문 (없으면 빈 문자열)>

TABLE_MD: <마크다운 표(여러 줄 가능). 없으면 빈 문자열>
DIAGRAM_SPEC_KO: <도형 기반 도식 스펙(여러 줄 가능). 없으면 빈 문자열>
CHART_SPEC_KO: <차트 스펙(여러 줄 가능). 없으면 빈 문자열>

ENDSLIDE

--------------------------------

절대 금지:
- CHAPTER / PART / SECTION 같은 구분용 단독 슬라이드 생성 금지
- 표지 전용 슬라이드 생성 금지
- 사진 / 실사 / 캐릭터 / 3D / AI그림 금지
- (중요) IMAGE_NEEDED는 항상 false. 이미지 파일 생성 지시 금지. (텍스트 없는 아이콘/도형은 PPT에서 수동 삽입 가능)
- 허용: 도형 기반 인포그래픽, 차트, 표

--------------------------------

시각요소 규칙:
- 시각요소(TABLE_MD / DIAGRAM_SPEC_KO / CHART_SPEC_KO)는 선택 사항이다. 없어도 된다.
- 넣더라도 '이미지 생성'이 아니라, 발표자가 직접 도형/표를 그릴 수 있을 만큼의 텍스트 지시서만 작성한다.

추가 제약(최우선):
- 출력의 모든 문장/표현은 한국어로 작성한다.
- 영어 문장/영어 소제목/영어 불릿 금지.
- 단, 고유명사/약어(API, GPU 등)만 예외적으로 허용.
- 가능한 한 '한글 용어(괄호에 약어)' 형태로 쓴다. 예: 그래픽처리장치(GPU)

""".strip()


# -----------------------------
# Parsing helpers
# -----------------------------
def _parse_deck_title(raw: str) -> str:
    m = re.search(r"(?m)^DECK_TITLE:\s*(.+)$", raw)
    return (m.group(1).strip() if m else "").strip()


def _iter_slide_blocks(raw: str) -> List[str]:
    blocks: List[str] = []
    pattern = re.compile(r"(?s)\bSLIDE\b(.*?)\bENDSLIDE\b")
    for m in pattern.finditer(raw):
        blocks.append(m.group(1).strip())
    return blocks


def _grab_field(block: str, field: str) -> str:
    m = re.search(rf"(?m)^{re.escape(field)}\s*:\s*(.+)$", block)
    return (m.group(1).strip() if m else "").strip()


def _grab_multiline_field(block: str, field: str) -> str:
    m = re.search(
        rf"(?s)^{re.escape(field)}\s*:\s*(.*?)(?=\n[A-Z_]+\s*:|\Z)",
        block.strip(),
        flags=re.MULTILINE,
    )
    return (m.group(1).strip() if m else "").strip()


def _parse_bullets(block: str) -> List[str]:
    m = re.search(r"(?s)\bBULLETS\s*:\s*(.*?)(?:\n[A-Z_]+\s*:|\Z)", block)
    if not m:
        return []
    body = m.group(1)
    bullets: List[str] = []
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("-"):
            t = line[1:].strip()
            if t:
                bullets.append(t)
    return bullets


def _parse_evidence(block: str) -> List[Dict[str, str]]:
    m = re.search(r"(?s)\bEVIDENCE\s*:\s*(.*?)(?:\n[A-Z_]+\s*:|\Z)", block)
    if not m:
        return []
    body = m.group(1)
    items: List[Dict[str, str]] = []

    cur: Dict[str, str] = {}
    for line in body.splitlines():
        line = line.rstrip()
        if not line.strip():
            continue

        if line.lstrip().startswith("- type:"):
            if cur:
                items.append(cur)
            cur = {"type": line.split(":", 1)[1].strip(), "text": ""}
            continue

        if line.strip().startswith("text:"):
            cur["text"] = line.split(":", 1)[1].strip()
            continue

        if line.lstrip().startswith("-"):
            t = line.lstrip()[1:].strip()
            if t:
                items.append({"type": "근거", "text": t})
            cur = {}
            continue

    if cur:
        items.append(cur)

    cleaned: List[Dict[str, str]] = []
    for it in items:
        t = (it.get("text") or "").strip()
        if t:
            cleaned.append({"type": (it.get("type") or "근거").strip(), "text": t})
    return cleaned


def _parse_bool(s: str) -> bool:
    return (s or "").strip().lower() in {"true", "1", "yes", "y"}


def _parse_slides_from_text(raw: str, *, default_section: str, start_order: int) -> List[Dict[str, Any]]:
    slides: List[Dict[str, Any]] = []
    order = start_order

    for block in _iter_slide_blocks(raw):
        section = (_grab_field(block, "SECTION") or default_section).strip()
        title = _grab_field(block, "TITLE").strip()
        key_message = _grab_field(block, "KEY_MESSAGE").strip()

        image_needed = _parse_bool(_grab_field(block, "IMAGE_NEEDED"))
        image_type = (_grab_field(block, "IMAGE_TYPE") or "none").strip().lower()
        if image_type not in {"diagram", "chart", "table", "none"}:
            image_type = "none"

        image_brief_ko = _grab_multiline_field(block, "IMAGE_BRIEF_KO")

        # ✅ 강제: 이미지 생성 사용 안 함 (사용자 요구)
        image_needed = False
        image_type = "none"
        image_brief_ko = ""

        table_md = _grab_multiline_field(block, "TABLE_MD")
        diagram_spec_ko = _grab_multiline_field(block, "DIAGRAM_SPEC_KO")
        chart_spec_ko = _grab_multiline_field(block, "CHART_SPEC_KO")

        bullets = _parse_bullets(block)
        evidence = _parse_evidence(block)

        # 챕터/파트/섹션 단독 슬라이드 제거
        upper_title = (title or "").upper()
        upper_section = (section or "").upper()
        if any(x in upper_title for x in ["CHAPTER", "PART", "SECTION"]) or any(
            x in upper_section for x in ["CHAPTER", "PART", "SECTION"]
        ):
            continue

        slides.append(
            {
                "order": order,
                "section": section,
                "slide_title": title,
                "key_message": key_message,
                "bullets": bullets,
                "evidence": evidence,
                "image_needed": False,
                "image_type": "none",
                "image_brief_ko": "",
                "TABLE_MD": table_md,
                "DIAGRAM_SPEC_KO": diagram_spec_ko,
                "CHART_SPEC_KO": chart_spec_ko,
            }
        )
        order += 1

    return slides


# -----------------------------
# Repair (keep only cleaning; no extra image instructions)
# -----------------------------
def _repair_slides(slides: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    banned = ["본 슬라이드", "추후 보완", "제공되지 않아", "원문 근거 부족"]
    for s in slides:
        s["image_needed"] = False
        s["image_type"] = "none"
        s["image_brief_ko"] = ""

        km = str(s.get("key_message") or "")
        if any(b in km for b in banned):
            s["key_message"] = ""

        bullets = s.get("bullets") or []
        nb = []
        if isinstance(bullets, list):
            for b in bullets:
                bt = str(b or "").strip()
                if not bt:
                    continue
                if any(x in bt for x in banned):
                    continue
                nb.append(bt)
        s["bullets"] = nb

        # "미기재" 도식 강제는 하지 않음(후처리에서 이미지 제거/도식 그리기)
        for k in ["TABLE_MD", "DIAGRAM_SPEC_KO", "CHART_SPEC_KO"]:
            v = str(s.get(k) or "").strip()
            if "미기재" in v or "원문" in v:
                s[k] = ""

    return slides


# -----------------------------
# Node
# -----------------------------
def section_deck_generation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    sections = state.get("sections")
    extracted_text = (state.get("extracted_text") or "").strip()

    if not (isinstance(sections, list) and sections):
        if not extracted_text:
            raise RuntimeError("입력 텍스트가 비어 있습니다. (extracted_text/sections)")
        sections = [{"title": (state.get("default_section") or "사업 개요"), "text": extracted_text}]

    client: genai.Client = get_gemini_client()
    prompt = _build_prompt()

    section_decks: Dict[str, Any] = {}
    deck_title = (state.get("deck_title") or "").strip()
    order_cursor = 1

    for s in sections:
        sec_title = re.sub(r"\s+", " ", (s.get("title") or "")).strip()  # ✅ 핵심: strip
        sec_text = (s.get("text") or "").strip()

        # 표준화
        alias = {
            "연구내용": "연구 내용",
            "기관소개": "기관 소개",
            "추진계획": "추진 계획",
            "기대효과": "기대 효과",
            "활용계획": "활용 계획",
        }
        sec_title = alias.get(sec_title, sec_title).strip()  # ✅ 핵심: strip

        if not sec_title:
            continue

        # Q&A는 여기서 만들지 않음(merge에서 강제 추가)
        if sec_title.upper() in {"Q&A", "QNA", "QA"} or sec_title in {"질의응답", "질문", "응답"}:
            continue

        # 너무 짧아도 그냥 넘기지 말고 그대로 보냄(“미기재” 덧붙이지 않음)
        if len(sec_text) > int(state.get("max_section_chars") or 6000):
            sec_text = sec_text[: int(state.get("max_section_chars") or 6000)] + "\n...(이하 생략)"

        common_rules = """
        [공통 강제 규칙]
        - 모든 출력은 한국어. 영어 문장 금지(고유명사/약어만 예외).
        - 메타 문장(본 슬라이드/추후 보완/제공되지 않아) 절대 금지. 부족하면 '미기재'로만 표기.
        - 목차/표지/챕터/파트 같은 구분용 단독 슬라이드 생성 금지.
        - 시각요소(TABLE/도식/차트)는 선택 사항이다.
        - 이미지 생성(IMAGE_NEEDED)은 항상 false.
        """.strip()


        # 섹션별 추가 규칙(필요 최소만)
        if sec_title == "기관 소개":
            section_rules = """
[추가 규칙]
- '기관 소개' 섹션은 슬라이드 1장만 생성한다.
- TITLE은 '기관 소개 및 수행역량'
""".strip()
        else:
            section_rules = ""

        prompt_for_section = f"{prompt}\n\n{common_rules}\n\n{section_rules}".strip()
        input_text = f"[섹션: {sec_title}]\n{sec_text}"

        print("[DEBUG][gemini] section:", repr(sec_title), "len:", len(sec_text))

        resp = generate_content_with_retry(
            client,
            model=state.get("gemini_model") or "gemini-2.5-flash",
            contents=[prompt_for_section, input_text],
            config=types.GenerateContentConfig(
                max_output_tokens=int(state.get("gemini_max_output_tokens") or 8192),
                temperature=float(state.get("gemini_temperature") or 0.4),
            ),
            max_retries=int(state.get("gemini_max_retries") or 5),
        )

        raw = (getattr(resp, "text", None) or "").strip()
        print("[DEBUG][gemini] raw_len:", len(raw), "section:", repr(sec_title))

        if not raw:
            # ✅ fallback 슬라이드 만들지 않음(merge에서 목차/감사합니다는 강제)
            continue

        if not deck_title:
            deck_title = _parse_deck_title(raw).strip()

        slides = _parse_slides_from_text(raw, default_section=sec_title, start_order=order_cursor)
        slides = _repair_slides(slides)

        if not slides:
            continue

        order_cursor = max(order_cursor, max(sl.get("order", 0) for sl in slides) + 1)

        section_decks[sec_title] = {
            "section": sec_title,
            "deck_title": deck_title or "발표자료",
            "slides": slides,
        }

    if not section_decks:
        raise RuntimeError("Gemini가 섹션별 슬라이드를 생성하지 못했습니다. (section_decks=empty)")

    state["deck_title"] = deck_title or "(과제명 미기재)"
    state["section_decks"] = section_decks

    print("[DEBUG] deck_title:", state["deck_title"])
    print("[DEBUG] section_decks keys:", list(section_decks.keys()))
    total_slides = sum(len(v.get("slides") or []) for v in section_decks.values())
    print("[DEBUG] total slides:", total_slides)

    return state
