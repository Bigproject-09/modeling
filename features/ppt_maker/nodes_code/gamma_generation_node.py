from __future__ import annotations

import os
import re
import time
import json
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
    title = (deck.get("deck_title") or "").strip() or "(과제명 미기재)"
    slides: List[Dict[str, Any]] = deck.get("slides") or []
    n = len(slides)

    header = f"""[DECK]
DECK_TITLE: {title}
TOTAL_SLIDES: {n}

ABSOLUTE RULES:
- 정확히 {n}장만 생성. 추가/삭제/분할/병합 금지.
- 순서 변경 금지.
- 사진/일러스트/캐릭터/AI그림/배경이미지/아이콘 생성 금지.
- 이미지 placeholder(빈 이미지 영역) 만들지 말 것.
- 표/차트/도형(박스/선) 기반 다이어그램은 허용(텍스트 스펙을 그대로 반영).
- 모든 텍스트는 한국어로 작성(약어/고유명사만 예외).
[/DECK]
""".strip()

    def _clean_lines(xs: List[str], limit: int) -> List[str]:
        out: List[str] = []
        for x in xs:
            x = str(x or "").strip()
            if not x:
                continue
            if x in {"**POST_DIAGRAM_SYSTEM**", "**POST_DIAGRAM_ORGCHART**", "**도식 후처리 대상**"}:
                continue
            out.append(x)
            if len(out) >= limit:
                break
        return out

    slide_blocks: List[str] = []
    for i, s in enumerate(slides, 1):
        section = (s.get("section") or "").strip()
        slide_title = (s.get("slide_title") or "").strip() or "슬라이드"
        key_message = (s.get("key_message") or "").strip()

        bullets = _clean_lines(s.get("bullets") or [], limit=7)

        table_md = (s.get("TABLE_MD") or "").strip()
        diagram_spec = (s.get("DIAGRAM_SPEC_KO") or "").strip()
        chart_spec = (s.get("CHART_SPEC_KO") or "").strip()

        evidence = s.get("evidence") or []
        ev_lines: List[str] = []
        if isinstance(evidence, list):
            for ev in evidence[:3]:
                if isinstance(ev, dict):
                    t = (ev.get("type") or "근거").strip()
                    tx = (ev.get("text") or "").strip()
                    if tx:
                        ev_lines.append(f"- ({t}) {tx}")
                else:
                    tx = str(ev or "").strip()
                    if tx:
                        ev_lines.append(f"- {tx}")

        lines: List[str] = []
        lines.append(f"[SLIDE {i}/{n}]")
        lines.append(f"SECTION: {section}")
        lines.append(f"TITLE: {slide_title}")
        if key_message:
            lines.append(f"KEY_MESSAGE: {key_message}")

        lines.append("BULLETS:")
        if bullets:
            for b in bullets:
                lines.append(f"- {b}")
        else:
            lines.append("- (미기재)")

        if ev_lines:
            lines.append("EVIDENCE:")
            lines.extend(ev_lines)

        if table_md:
            lines.append("TABLE_MD:")
            lines.append(table_md)
        if diagram_spec:
            lines.append("DIAGRAM_SPEC_KO:")
            lines.append(diagram_spec)
        if chart_spec:
            lines.append("CHART_SPEC_KO:")
            lines.append(chart_spec)

        lines.append("[ENDSLIDE]")
        slide_blocks.append("\n".join(lines))

    body = "\n\n---\n\n".join(slide_blocks)
    return header + "\n\n" + body


def _gamma_headers(api_key: str) -> Dict[str, str]:
    return {"X-API-KEY": api_key, "Content-Type": "application/json"}


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

        # ✅ 핵심: 이미지 완전 차단(지시문으로는 못 막는 경우가 많음)
        "imageOptions": {"source": "noImages"},

        "textOptions": {
            "language": "ko",
            "tone": "professional, clear",
            "amount": "brief",
        },

        "additionalInstructions": (
            f"반드시 {int(num_cards)}장만 생성. 추가/삭제/분할/병합 금지.\n"
            f"슬라이드 순서 변경 금지.\n"
            f"영어 문장/영어 제목 금지(약어/고유명사만 예외).\n"
            f"사진/일러스트/캐릭터/AI그림/배경이미지/아이콘/이미지 placeholder 생성 금지.\n"
            f"표(TABLE_MD), 차트(CHART_SPEC_KO), 도형 다이어그램(DIAGRAM_SPEC_KO)은 허용하며 해당 스펙을 반영.\n"
            f"'추가 정보/문의/연락처/회사 소개' 같은 마무리 슬라이드 생성 금지.\n"
            f"마지막은 제공된 '감사합니다' 1장만 유지(복제 금지).\n"
            f"[SLIDE i/N] ~ [ENDSLIDE] 블록 경계를 반드시 그대로 유지."
        ),
    }

    # ⚠️ theme이 그림을 깔아버리는 경우가 많아서, 기본은 사용 안 함.
    # 사용자가 정말 원할 때만 state["gamma_theme_allow"]=True로 켜도록.
    if theme and bool(os.environ.get("GAMMA_THEME_ALLOW")):
        payload["theme"] = theme

    url = f"{GAMMA_API_BASE}/generations"
    r = requests.post(url, headers=_gamma_headers(api_key), json=payload, timeout=60)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Gamma API error {r.status_code}: {r.text}")
    return r.json()


def _poll_generation(api_key: str, generation_id: str, *, timeout_sec: int) -> Dict[str, Any]:
    t0 = time.time()
    last: Dict[str, Any] = {}
    while time.time() - t0 < timeout_sec:
        r = requests.get(f"{GAMMA_API_BASE}/generations/{generation_id}", headers=_gamma_headers(api_key), timeout=60)
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
    base, ext = os.path.splitext(path)
    if not os.path.exists(path):
        return path
    for i in range(1, 200):
        cand = f"{base} ({i}){ext}"
        if not os.path.exists(cand):
            return cand
    return f"{base}_{int(time.time())}{ext}"


def _safe_filename(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", " ", str(name or ""))
    name = re.sub(r"\s+", " ", name).strip()
    return name[:80] or "result"


def gamma_generation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    api_key = os.environ.get("GAMMA_API_KEY")
    if not api_key:
        raise RuntimeError("GAMMA_API_KEY가 없습니다. .env 또는 환경변수에 설정하세요.")

    deck = state.get("deck_json") or {}
    slides = deck.get("slides") or []
    if not slides:
        raise RuntimeError("deck_json.slides가 비어있습니다. merge_deck_node 결과를 확인하세요.")

    input_text = _slides_to_input_text(deck)

    output_dir = (state.get("output_dir") or "output").strip()

    # ✅ 파일명: 과제명 기반
    if not (state.get("output_filename") or "").strip():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        title = _safe_filename(deck.get("deck_title") or "result")
        output_filename = f"{title}_{ts}.pptx"
    else:
        output_filename = (state.get("output_filename") or "").strip()

    out_path = _avoid_windows_lock(os.path.join(output_dir, output_filename))

    timeout_sec = int(state.get("gamma_timeout_sec") or 600)
    theme = (state.get("gamma_theme") or "").strip() or None

    if state.get("save_checkpoint", True):
        _save_checkpoint(state)


    gen = _start_generation(api_key, input_text=input_text, theme=theme, num_cards=len(slides))
    generation_id = gen.get("generationId") or gen.get("id")
    if not generation_id:
        raise RuntimeError(f"Gamma 응답에 generationId가 없습니다: {gen}")

    done = _poll_generation(api_key, generation_id, timeout_sec=timeout_sec)

    def _extract_url(d: Dict[str, Any]) -> str:
        return (
            d.get("exportUrl")
            or d.get("pptxUrl")
            or (d.get("exports") or {}).get("pptx")
            or ""
        )

    file_url = _extract_url(done)

    # ✅ completed 직후에 URL이 늦게 붙는 케이스 대응(최대 45초)
    if not file_url:
        t1 = time.time()
        while time.time() - t1 < 45:
            time.sleep(2.5)
            r = requests.get(f"{GAMMA_API_BASE}/generations/{generation_id}", headers=_gamma_headers(api_key), timeout=60)
            r.raise_for_status()
            done2 = r.json()
            file_url = _extract_url(done2)
            if file_url:
                done = done2
                break

    if not file_url:
        raise RuntimeError(f"Gamma 완료 응답에 다운로드 URL이 없습니다: {done}")

    _download_file(file_url, out_path)

    state["final_ppt_path"] = out_path
    state["gamma_ppt_path"] = out_path
    return state
