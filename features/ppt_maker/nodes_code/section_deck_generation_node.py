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
    # "섹션별 호출" 전제: 한 섹션 텍스트만 주고 그 섹션에 해당하는 슬라이드만 만들도록 강제
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
- 허용: 도형 기반 인포그래픽, 차트, 표

--------------------------------

시각요소 규칙:
- 목차 / 표지 / Q&A 제외 모든 슬라이드는 반드시 아래 중 최소 1개 포함:
  (1) TABLE_MD
  (2) DIAGRAM_SPEC_KO
  (3) CHART_SPEC_KO

--------------------------------

슬라이드 구성 규칙:

각 섹션은 충분히 설명 가능한 수준까지 슬라이드를 분리한다.

최소 슬라이드 수 규칙:
- 연구 내용: 최소 4장 이상
- 추진 계획: 최소 3장 이상

여러 주제가 나오면 반드시 슬라이드를 분리한다.
한 장에 과도하게 요약하지 않는다.

--------------------------------

[연구 내용 섹션 전용 규칙]

연구 내용 섹션에서는 반드시 다음 유형의 슬라이드를 각각 별도의 슬라이드로 포함한다:

1. 전체 시스템 구성도
2. 주요 모듈 설명
3. 데이터 흐름 또는 처리 과정
4. 핵심 기술 요소 설명

전체 시스템 구성도는 반드시 포함한다.
DIAGRAM_SPEC_KO는 반드시 작성한다.

구성도 작성 규칙:
- 최소 8개 이상의 구성요소 포함
- 최소 2계층 이상 구조
- 데이터 흐름과 시스템 구성요소를 함께 표현

구성 요소 확장 규칙:
원문에 기술 요소가 충분히 구체적이지 않더라도,
일반적인 시스템 구조 수준에서 아래 계층은 구성요소로 확장할 수 있다:

- 데이터 수집
- 저장소
- 처리 또는 모델
- API 또는 서비스 계층
- 시각화 또는 플랫폼

단,
특정 알고리즘명, 성능 수치, 존재하지 않는 기술은 임의로 생성하지 않는다.

DIAGRAM_SPEC_KO 작성 방식:
- 각 블록 이름
- 블록 역할
- 연결 관계
- 데이터 흐름 방향

--------------------------------

[추진 계획 섹션 규칙]

추진 계획 섹션에서는 반드시 다음 슬라이드를 포함한다:

1. 조직도(수행체계)
2. 추진 일정 또는 단계
3. 역할 분담 또는 업무 체계

조직도 작성 방식:

구조:
최상단: 총괄기관 또는 총괄연구책임자

그 아래:
참여기관 박스들을 가로로 배치

각 박스에는 반드시 포함:
- 기관명
- 담당 기술 또는 역할
- 연구 인원 또는 담당 범위(있으면)

DIAGRAM_SPEC_KO 작성 규칙:
- 상단 1개 박스
- 하단 최소 3개 기관 박스
- 상하 연결선 포함
- 각 기관 역할 한 줄 설명 포함

--------------------------------

작성 원칙:
- 추측 금지
- 원문 기반 재구성만 허용
- 표현은 간결하고 실제 발표자료 스타일로 작성
- 설명은 발표자가 읽고 바로 설명할 수 있는 수준으로 작성
- "수립", "제시", "기술", "정의" 같은 메타 설명 문장은 최소화하고 실제 내용 중심으로 작성

슬라이드 수 규칙:

서로 다른 기술이나 모델은 반드시 별도의 슬라이드로 작성한다.
연구 내용 섹션은 최소 6장의 슬라이드로 구성한다.

발표자료 전체 슬라이드 수는 최소 20장 이상이 되도록 작성한다.

다음 섹션은 반드시 여러 장으로 나눈다:

기관 소개: 최소 3장
- 조직 및 역할
- 핵심역량
- 인프라 및 실적

사업 개요: 최소 2장
- 과제 개요
- 개발 대상 기술

연구 목표: 최소 2장
- 최종 목표
- 단계별 목표 또는 KPI

연구 내용: 최소 5장
- 전체 시스템 구조
- 핵심 모델 또는 기술 1
- 핵심 모델 또는 기술 2
- 데이터 흐름 또는 처리 과정
- 통합 플랫폼 또는 서비스 구조

추진 계획: 최소 3장
- 조직도
- 일정 또는 단계
- 역할 분담 또는 관리 체계
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


def _fallback_min_slide(sec_title: str, order: int, deck_title: str) -> Dict[str, Any]:
    # 섹션 드랍 방지용 최소 슬라이드 1장
    return {
        "section": sec_title,
        "deck_title": deck_title or "발표자료",
        "slides": [
            {
                "order": order,
                "section": sec_title,
                "slide_title": sec_title,
                "key_message": "",
                "bullets": ["(미기재)"],
                "evidence": [{"type": "미기재", "text": "미기재"}],
                "image_needed": False,
                "image_type": "none",
                "image_brief_ko": "",
                "TABLE_MD": "",
                "DIAGRAM_SPEC_KO": "",
                "CHART_SPEC_KO": "",
            }
        ],
    }


def _parse_slides_from_text(raw: str, *, default_section: str, start_order: int) -> List[Dict[str, Any]]:
    slides: List[Dict[str, Any]] = []
    order = start_order

    for block in _iter_slide_blocks(raw):
        section = _grab_field(block, "SECTION") or default_section
        title = _grab_field(block, "TITLE")
        key_message = _grab_field(block, "KEY_MESSAGE")

        image_needed = _parse_bool(_grab_field(block, "IMAGE_NEEDED"))
        image_type = (_grab_field(block, "IMAGE_TYPE") or "none").strip().lower()
        if image_type not in {"diagram", "chart", "table", "none"}:
            image_type = "none"

        image_brief_ko = _grab_multiline_field(block, "IMAGE_BRIEF_KO")
        table_md = _grab_multiline_field(block, "TABLE_MD")
        diagram_spec_ko = _grab_multiline_field(block, "DIAGRAM_SPEC_KO")
        chart_spec_ko = _grab_multiline_field(block, "CHART_SPEC_KO")

        bullets = _parse_bullets(block)
        evidence = _parse_evidence(block)

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
                "image_needed": bool(image_needed),
                "image_type": image_type,
                "image_brief_ko": image_brief_ko,
                "TABLE_MD": table_md,
                "DIAGRAM_SPEC_KO": diagram_spec_ko,
                "CHART_SPEC_KO": chart_spec_ko,
            }
        )
        order += 1

    return slides


# -----------------------------
# Node
# -----------------------------
def section_deck_generation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    섹션별 Gemini 호출 → section_decks 생성

    입력:
      - state["sections"] = [{"title":..., "text":...}, ...] (권장)
      - 없으면 extracted_text 전체를 단일 섹션으로 처리(최소 동작)

    출력:
      - state["deck_title"]
      - state["section_decks"]
    """
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
        sec_title = (s.get("title") or "").strip()
        sec_text = (s.get("text") or "").strip()

        # ✅ 섹션명 공백 정규화: '기대  효과' -> '기대 효과'
        sec_title = re.sub(r"\s+", " ", sec_title).strip()

        if not sec_title:
            continue

        # ✅ Q&A는 LLM 호출하지 않음
        if sec_title.upper() in {"Q&A", "QNA", "QA"} or sec_title in {"질의응답", "질문", "응답"}:
            continue

        # ✅ 텍스트가 비어/짧아도 섹션을 드랍하지 않음
        if not sec_text:
            sec_text = "(원문이 비어있음: 미기재)"
        elif len(sec_text) < 80:
            sec_text = sec_text + "\n(세부 근거/수치는 원문에 미기재)"

        print("[DEBUG][gemini] section:", repr(sec_title), "len:", len(sec_text))

        input_text = f"[섹션: {sec_title}]\n{sec_text}"

        resp = generate_content_with_retry(
            client,
            model=state.get("gemini_model") or "gemini-2.5-flash",
            contents=[prompt, input_text],
            config=types.GenerateContentConfig(
                max_output_tokens=int(state.get("gemini_max_output_tokens") or 4096),
                temperature=float(state.get("gemini_temperature") or 0.4),
            ),
            max_retries=int(state.get("gemini_max_retries") or 5),
        )

        raw = (getattr(resp, "text", None) or "").strip()
        print("[DEBUG][gemini] raw_len:", len(raw), "section:", repr(sec_title))

        # ✅ 응답이 비어도 섹션 드랍 금지 (최소 슬라이드 1장)
        if not raw:
            section_decks[sec_title] = _fallback_min_slide(sec_title, order_cursor, deck_title)
            order_cursor += 1
            continue

        if not deck_title:
            deck_title = _parse_deck_title(raw)

        slides = _parse_slides_from_text(raw, default_section=sec_title, start_order=order_cursor)

        # ✅ 파싱 실패해도 섹션 드랍 금지 (최소 슬라이드 1장)
        if not slides:
            section_decks[sec_title] = _fallback_min_slide(sec_title, order_cursor, deck_title)
            order_cursor += 1
            continue

        order_cursor = max(order_cursor, max(sl["order"] for sl in slides) + 1)

        section_decks[sec_title] = {
            "section": sec_title,
            "deck_title": deck_title or "발표자료",
            "slides": slides,
        }

    if not section_decks:
        raise RuntimeError("Gemini가 섹션별 슬라이드를 생성하지 못했습니다. (section_decks=empty)")

    state["deck_title"] = deck_title or "발표자료"
    state["section_decks"] = section_decks

    print("[DEBUG] deck_title:", state["deck_title"])
    print("[DEBUG] section_decks keys:", list(section_decks.keys()))
    total_slides = sum(len(v.get("slides") or []) for v in section_decks.values())
    print("[DEBUG] total slides:", total_slides)

    return state
