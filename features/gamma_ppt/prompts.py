"""
Prompt templates for Gemini (Gamma PPT pipeline).
"""

from __future__ import annotations

SYSTEM_INSTRUCTION_CONDENSE = (
    "You are a careful technical summarizer. "
    "Condense the input while preserving numbers, dates, and key facts. "
    "Do not invent information. Output in Korean."
)

SYSTEM_INSTRUCTION_CARDS = (
    "You are a helpful planner. "
    "Return JSON only with an integer recommended_cards."
)

SYSTEM_INSTRUCTION_DECK = (
    "You are an expert at writing Korean R&D proposal slide decks. "
    "Follow formatting rules exactly. Do not invent facts."
)

SYSTEM_INSTRUCTION_TEMPLATE_JSON = (
    "You are an expert at structuring Korean R&D proposal decks. "
    "Return JSON only, no markdown."
)


def build_condense_prompt(rfp_text: str, target_chars: int) -> str:
    return (
        "다음 RFP 원문을 핵심 정보 중심으로 요약해 주세요. "
        f"출력은 {target_chars}자 이내로 유지하세요. "
        "숫자/기간/예산/성과/요구사항은 반드시 보존하세요.\n\n"
        "[RFP 원문]\n"
        f"{rfp_text}"
    )


def build_recommended_cards_prompt(rfp_text: str, min_cards: int, max_cards: int) -> str:
    return (
        "다음 RFP 내용을 보고 발표용 PPT에 적정한 카드 수를 제안하세요.\n"
        f"- 범위: {min_cards} ~ {max_cards}\n"
        "- 정보량이 많으면 상한 쪽, 적으면 하한 쪽\n"
        "- 반드시 JSON만 출력: {\"recommended_cards\": N}\n\n"
        "[RFP 원문]\n"
        f"{rfp_text}"
    )


def build_deck_prompt(rfp_text: str, num_cards: int) -> str:
    return (
        "다음 RFP를 바탕으로 국가 R&D 발표용 PPT 카드 내용을 작성하세요.\n"
        "요구사항:\n"
        f"- 총 {num_cards}장\n"
        f"- 정확히 {num_cards}개의 카드이며, 카드 구분선은 {num_cards - 1}개(\n---\n)만 사용\n"
        "- 각 카드는 제목 1개와 3~5개의 불릿으로 구성\n"
        "- 각 불릿은 1문장, 가능한 60~80자 이내로 간결하게 작성\n"
        "- 한국어로 작성\n"
        "- 메모/지시 문장 금지: '차트/그래프/표로 표시', '확인 필요', 'TODO', 'Bar Chart'\n"
        "- 출력 형식 엄수: '# 제목' 다음 줄부터 '- 불릿'만 사용\n"
        "- 카드 구분은 반드시 \n---\n 를 사용\n"
        "\n"
        "[섹션/순서 고정]\n"
        "1. 표지\n"
        "2. 목차\n"
        "3. 배경/필요성\n"
        "4. 문제정의/현황\n"
        "5. 목표/세부목표\n"
        "6. KPI/성과지표\n"
        "7. 기술개요\n"
        "8. 아키텍처/데이터흐름\n"
        "9. 추진전략/연차계획\n"
        "10. 일정/로드맵\n"
        "11. 추진체계\n"
        "12. 리스크/대응\n"
        "13. 기대효과/활용·사업화\n"
        "14. 마무리\n"
        "\n"
        "[장수 조정 규칙]\n"
        "- 총 장수가 부족하면 위 섹션 내에서 슬라이드를 추가 분할하되 섹션 순서를 유지\n"
        "- 총 장수가 많으면 인접 섹션을 병합하거나 한 섹션 내 슬라이드를 합쳐서 맞출 것\n"
        "- 섹션 디바이더는 필요할 때만 1장으로 제한\n\n"
        "[RFP 원문]\n"
        f"{rfp_text}"
    )


def build_template_json_prompt(rfp_text: str) -> str:
    return (
        "다음 RFP를 기반으로 국가 R&D 발표 템플릿 18장에 맞춘 요약 JSON을 작성하세요.\n"
        "출력은 반드시 JSON만, 형식은 아래와 같습니다.\n"
        "{\n"
        "  \"slides\": [\n"
        "    {\"slide\": 1, \"title\": \"표지\", \"bullets\": [\"과제명: ...\", \"부처: ...\", \"주관기관: ...\"]},\n"
        "    {\"slide\": 2, \"title\": \"목차\", \"bullets\": [\"1. 배경·필요성\", \"2. 목표·성과\", \"3. 기술·방법\", \"4. 추진계획\", \"5. 기대효과\", \"6. 마무리\"]},\n"
        "    {\"slide\": 3, \"title\": \"배경·필요성\", \"bullets\": [\"섹션 요약 1줄\"]},\n"
        "    {\"slide\": 4, \"title\": \"배경/필요성\", \"bullets\": [\"핵심 근거 1\", \"핵심 근거 2\", \"핵심 근거 3\"]},\n"
        "    {\"slide\": 5, \"title\": \"문제정의/현황\", \"bullets\": [\"핵심 포인트 1\", \"핵심 포인트 2\", \"핵심 포인트 3\"]},\n"
        "    {\"slide\": 6, \"title\": \"목표·성과\", \"bullets\": [\"섹션 요약 1줄\"]},\n"
        "    {\"slide\": 7, \"title\": \"연구목표/세부목표\", \"bullets\": [\"목표1: ... / 세부목표: ...\", \"목표2: ... / 세부목표: ...\", \"목표3: ... / 세부목표: ...\"]},\n"
        "    {\"slide\": 8, \"title\": \"KPI/성과지표\", \"bullets\": [\"KPI1: ...\", \"KPI2: ...\", \"KPI3: ...\"]},\n"
        "    {\"slide\": 9, \"title\": \"기술·방법\", \"bullets\": [\"섹션 요약 1줄\"]},\n"
        "    {\"slide\": 10, \"title\": \"기술개요\", \"bullets\": [\"모듈: ...\", \"핵심기술: ...\", \"차별점: ...\"]},\n"
        "    {\"slide\": 11, \"title\": \"아키텍처/데이터흐름\", \"bullets\": [\"도식 설명 요약 1줄\", \"라벨은 본문에 표기\"]},\n"
        "    {\"slide\": 12, \"title\": \"추진계획\", \"bullets\": [\"섹션 요약 1줄\"]},\n"
        "    {\"slide\": 13, \"title\": \"연차별 계획(로드맵)\", \"bullets\": [\"연차1: ...\", \"연차2: ...\", \"연차3: ...\"]},\n"
        "    {\"slide\": 14, \"title\": \"일정\", \"bullets\": [\"마일스톤1: ...\", \"마일스톤2: ...\", \"마일스톤3: ...\"]},\n"
        "    {\"slide\": 15, \"title\": \"추진체계\", \"bullets\": [\"주관기관: ...\", \"참여기관: ...\", \"역할/책임: ...\"]},\n"
        "    {\"slide\": 16, \"title\": \"리스크/대응\", \"bullets\": [\"리스크1-영향-대응\", \"리스크2-영향-대응\", \"리스크3-영향-대응\"]},\n"
        "    {\"slide\": 17, \"title\": \"기대효과/활용·사업화\", \"bullets\": [\"정량 임팩트: ...\", \"활용처/수요처: ...\", \"사업화 경로: ...\"]},\n"
        "    {\"slide\": 18, \"title\": \"마무리\", \"bullets\": [\"핵심 요약 1\", \"핵심 요약 2\", \"Q&A\"]}\n"
        "  ]\n"
        "}\n\n"
        "규칙:\n"
        "- 각 슬라이드 bullets는 3~5개\n"
        "- 정보가 없으면 '자료 없음'으로 표기\n"
        "- 메모/지시 문장 금지\n"
        "- JSON 외 텍스트 출력 금지\n\n"
        "[RFP 원문]\n"
        f"{rfp_text}"
    )
