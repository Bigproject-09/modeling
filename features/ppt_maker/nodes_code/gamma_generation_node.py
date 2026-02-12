"""Gamma API로 PPTX 생성.

- POST https://public-api.gamma.app/v1.0/generations
- GET  https://public-api.gamma.app/v1.0/generations/{generationId}

입력(state 계약)
- state["deck_json"] = {"deck_title": ..., "slides":[...]}  (merge_deck_node 결과)
옵션
- state["gamma_theme"] (선택)
- state["gamma_timeout_sec"] (선택)
- state["output_dir"], state["output_filename"] (선택)
"""

from __future__ import annotations

import os
import time
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

import requests

GAMMA_API_BASE = "https://public-api.gamma.app/v1.0"


def _save_checkpoint(state: dict) -> str:
    outdir = Path("output") / "checkpoints"
    outdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = outdir / f"deck_checkpoint_{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state.get("deck_json", {}), f, ensure_ascii=False, indent=2)
    print(f"[CHECKPOINT] deck_json saved: {path}")
    return str(path)


def _slides_to_input_text(deck: Dict[str, Any]) -> str:
    """Gamma Generate API용 inputText 생성.

    카드 구분: "\n---\n"
    """
    slides: List[Dict[str, Any]] = deck.get("slides") or []
    parts: List[str] = []

    for s in slides:
        section = (s.get("section") or "").strip()
        slide_title = (s.get("slide_title") or "").strip()
        key_message = (s.get("key_message") or "").strip()
        bullets = s.get("bullets") or []
        evidence = s.get("evidence") or []
        image_needed = bool(s.get("image_needed"))

        table_md = (s.get("TABLE_MD") or "").strip()
        diagram_spec = (s.get("DIAGRAM_SPEC_KO") or "").strip()
        chart_spec = (s.get("CHART_SPEC_KO") or "").strip()

        image_type = (s.get("image_type") or "").strip()
        image_brief = (s.get("image_brief_ko") or "").strip()

        card_lines: List[str] = []

        # 제목 라인
        if section:
            card_lines.append(f"## [{section}] {slide_title or ''}".strip())
        else:
            card_lines.append(f"## {slide_title or '슬라이드'}")

        # 핵심 메시지
        if key_message:
            card_lines.append(f"**핵심 메시지:** {key_message}")

        # 본문 bullets
        if isinstance(bullets, list) and bullets:
            for b in bullets[:6]:
                b = str(b).strip()
                if b:
                    card_lines.append(f"- {b}")

        # 근거/수치/출처
        if isinstance(evidence, list) and evidence:
            ev_lines: List[str] = []
            for ev in evidence[:4]:
                if isinstance(ev, dict):
                    t = (ev.get("type") or "근거").strip()
                    tx = (ev.get("text") or "").strip()
                    if tx:
                        ev_lines.append(f"- ({t}) {tx}")
                else:
                    tx = str(ev).strip()
                    if tx:
                        ev_lines.append(f"- {tx}")
            if ev_lines:
                card_lines.append("")
                card_lines.append("**근거/수치/출처**")
                card_lines.extend(ev_lines)

        # 표/도식/차트 스펙 (중요: 도표 늘리는 핵심)
        if table_md:
            card_lines.append("")
            card_lines.append("**표(그대로 포함)**")
            card_lines.append(table_md)

        if diagram_spec:
            card_lines.append("")
            card_lines.append("**도식 스펙(도형/선/텍스트만, 사진 금지)**")
            card_lines.append(diagram_spec)

        if chart_spec:
            card_lines.append("")
            card_lines.append("**차트 스펙(벡터 차트만, 사진 금지)**")
            card_lines.append(chart_spec)

        # 이미지/도식 요청
        if image_needed:
            card_lines.append("")
            card_lines.append("**이미지/도식 요청**")
            if image_type:
                card_lines.append(f"- 유형: {image_type}")
            if image_brief:
                card_lines.append(f"- 지시: {image_brief}")

        allow_ai_image = (section in ["추진 계획", "Q&A"]) and ("조직도" in slide_title or section == "Q&A")
        if allow_ai_image:
            card_lines.append("")
            card_lines.append("**이미지 생성 허용**")
            card_lines.append("- 스타일: 깔끔한 발표자료용 벡터/플랫 아이콘 느낌, 과한 AI 렌더링 금지")
            card_lines.append("- 용도: 조직도(기관 박스/연결선) 또는 Q&A 배경(심플한 추상 패턴)")

        parts.append("\n".join(card_lines).strip())

    return "\n---\n".join([p for p in parts if p.strip()])


def _gamma_headers(api_key: str) -> Dict[str, str]:
    return {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }


def _start_generation(
    api_key: str,
    *,
    input_text: str,
    theme: Optional[str],
    num_cards: int,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "inputText": input_text,
        "format": "presentation",
        "exportAs": "pptx",
        "textMode": "preserve",
        "numCards": int(num_cards),
        "cardOptions": {"dimensions": "16x9"},
        "cardSplit": "inputTextBreaks",
        "textOptions": {
            "language": "ko",
            "tone": "professional, clear",
            "amount": "medium",
        },
        "additionalInstructions": """
- 카드(슬라이드) 순서를 절대 변경하지 말 것.
- 카드 추가/삭제/병합 금지.
- 기본 원칙: 대부분 슬라이드는 이미지 금지(사진/실사/일러스트 금지). 표/차트/도식은 허용.
- 예외: 카드 본문에 '**이미지 생성 허용**' 문구가 있는 슬라이드만 AI 이미지 1개 생성 허용.
- 그 외 슬라이드는 이미지를 넣지 말고, 도형/표/차트로만 구성.
""".strip(),
    }

    if theme:
        payload["theme"] = theme

    url = f"{GAMMA_API_BASE}/generations"
    headers = _gamma_headers(api_key)

    r = requests.post(url, headers=headers, json=payload, timeout=60)

    if r.status_code not in (200, 201):
        print("[GAMMA][ERROR] status:", r.status_code)
        print("[GAMMA][ERROR] body:", r.text[:2000])
        print("[GAMMA][ERROR] sent payload keys:", list(payload.keys()))
        raise RuntimeError(f"Gamma API error {r.status_code}: {r.text}")

    return r.json()


def _poll_generation(api_key: str, generation_id: str, *, timeout_sec: int) -> Dict[str, Any]:
    t0 = time.time()
    last: Dict[str, Any] = {}
    while time.time() - t0 < timeout_sec:
        r = requests.get(
            f"{GAMMA_API_BASE}/generations/{generation_id}",
            headers=_gamma_headers(api_key),
            timeout=60,
        )
        r.raise_for_status()
        last = r.json()

        status = (last.get("status") or "").lower()
        if status in {"completed", "complete", "succeeded", "success"}:
            return last
        if status in {"failed", "error"}:
            raise RuntimeError(f"Gamma generation failed: {last}")

        time.sleep(3)

    raise TimeoutError(f"Gamma generation polling timeout ({timeout_sec}s). last={last}")


def _download_file(url: str, out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)


def _avoid_windows_lock(path: str) -> str:
    """같은 파일이 열려(잠김) 덮어쓰기 실패하는 경우를 피하기 위해 suffix로 새 파일명 생성"""
    base, ext = os.path.splitext(path)
    if not os.path.exists(path):
        return path

    for i in range(1, 200):
        cand = f"{base} ({i}){ext}"
        if not os.path.exists(cand):
            return cand

    return f"{base}_{int(time.time())}{ext}"


def gamma_generation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    api_key = os.environ.get("GAMMA_API_KEY")
    if not api_key:
        raise RuntimeError("GAMMA_API_KEY가 없습니다. .env 또는 환경변수에 설정하세요.")

    deck = state.get("deck_json") or {}
    if not isinstance(deck, dict) or not (deck.get("slides") or []):
        raise RuntimeError("deck_json(slides)이 비어 있습니다. merge_deck_node 출력 확인 필요.")

    # deck checkpoint 저장(선택)
    if not state.get("deck_checkpoint_path") and not os.environ.get("DECK_CHECKPOINT_PATH"):
        checkpoint_path = _save_checkpoint(state)
        state["deck_checkpoint_path"] = checkpoint_path

    input_text = _slides_to_input_text(deck)
    theme = (state.get("gamma_theme") or "").strip() or None
    timeout_sec = int(state.get("gamma_timeout_sec") or 600)

    slides = deck.get("slides") or []
    num_cards = len(slides)

    started = _start_generation(api_key, input_text=input_text, theme=theme, num_cards=num_cards)

    generation_id = started.get("generationId") or started.get("id")
    if not generation_id:
        raise RuntimeError(f"Gamma generationId를 받지 못했습니다: {started}")

    state["gamma_generation_id"] = str(generation_id)

    result = _poll_generation(api_key, str(generation_id), timeout_sec=timeout_sec)
    state["gamma_result"] = result

    pptx_url = (
        result.get("pptxUrl")
        or result.get("exportUrl")
        or result.get("pptx_url")
        or result.get("export_url")
    )
    if not pptx_url:
        raise RuntimeError(f"PPTX URL을 찾지 못했습니다. gamma_result 확인: {result}")

    state["pptx_url"] = pptx_url

    out_dir = state.get("output_dir") or os.path.join(os.getcwd(), "output")
    out_name = state.get("output_filename")
    if not out_name:
        deck_title = ((state.get("deck_json") or {}).get("deck_title") or "발표자료").strip()
        safe_title = re.sub(r"[^0-9A-Za-z가-힣 _-]+", "", deck_title).strip()
        safe_title = re.sub(r"\s+", "_", safe_title)[:40] or "발표자료"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_name = f"RanDi_{safe_title}_{ts}.pptx"

    out_path = os.path.join(out_dir, out_name)
    out_path = _avoid_windows_lock(out_path)
    _download_file(pptx_url, out_path)

    state["pptx_path"] = out_path
    state["final_ppt_path"] = out_path

    # ✅ 다운로드용 정보 추가 (FastAPI main.py가 이걸 그대로 응답에 포함시키면 됨)
    state["pptx_filename"] = os.path.basename(out_path)
    state["download_url"] = f"/download/pptx/{state['pptx_filename']}"

    print("[DEBUG] Gamma PPTX saved:", out_path)
    return state
