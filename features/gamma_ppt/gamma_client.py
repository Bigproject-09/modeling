"""
Gamma API client helpers.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

BASE_URL = "https://public-api.gamma.app/v1.0"

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

DEFAULT_ADDITIONAL_INSTRUCTIONS = "입력 텍스트를 수정하지 말고 그대로 사용."


def _headers(api_key: str) -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-API-KEY": api_key,
        "accept": "application/json",
    }


def build_gamma_payload(
    input_text: str,
    card_split: str,
    num_cards: int,
    theme_id: Optional[str] = None,
    folder_ids: Optional[List[str]] = None,
    additional_instructions: Optional[str] = None,
    image_source: str = "aiGenerated",
    image_style: Optional[str] = None,
    image_model: Optional[str] = None,
) -> Dict[str, Any]:
    instructions = DEFAULT_ADDITIONAL_INSTRUCTIONS
    if additional_instructions:
        instructions = f"{instructions}\n{additional_instructions.strip()}"

    image_options: Dict[str, Any] = {"source": image_source}
    if image_style:
        image_options["style"] = image_style
    if image_model:
        image_options["model"] = image_model

    payload: Dict[str, Any] = {
        "inputText": input_text,
        "textMode": "preserve",
        "format": "presentation",
        "cardSplit": card_split,
        "exportAs": "pptx",
        "additionalInstructions": instructions,
        "textOptions": {"language": "ko"},
        "imageOptions": image_options,
        "cardOptions": {
            "dimensions": "16x9",
            "headerFooter": {
                "bottomRight": {"type": "cardNumber"},
                "hideFromFirstCard": True,
            },
        },
    }

    if card_split == "auto":
        payload["numCards"] = int(num_cards)

    if theme_id:
        payload["themeId"] = theme_id

    if folder_ids:
        payload["folderIds"] = folder_ids

    return payload


def build_template_payload(
    gamma_id: str,
    prompt: str,
    theme_id: Optional[str] = None,
    folder_ids: Optional[List[str]] = None,
    export_as: str = "pptx",
    image_style: Optional[str] = None,
    image_model: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "gammaId": gamma_id,
        "prompt": prompt,
        "exportAs": export_as,
    }
    if theme_id:
        payload["themeId"] = theme_id
    if folder_ids:
        payload["folderIds"] = folder_ids
    if image_style or image_model:
        image_opts: Dict[str, Any] = {}
        if image_style:
            image_opts["style"] = image_style
        if image_model:
            image_opts["model"] = image_model
        payload["imageOptions"] = image_opts
    return payload


def create_generation(api_key: str, payload: Dict[str, Any]) -> str:
    url = f"{BASE_URL}/generations"
    resp = requests.post(url, headers=_headers(api_key), data=json.dumps(payload), timeout=30)
    if resp.status_code >= 400:
        raise RuntimeError(f"Gamma POST failed: {resp.status_code} {resp.text}")
    data = resp.json()
    generation_id = data.get("generationId")
    if not generation_id:
        raise RuntimeError(f"Gamma POST missing generationId: {data}")
    return generation_id


def create_generation_from_template(api_key: str, payload: Dict[str, Any]) -> str:
    url = f"{BASE_URL}/generations/from-template"
    resp = requests.post(url, headers=_headers(api_key), data=json.dumps(payload), timeout=30)
    if resp.status_code >= 400:
        raise RuntimeError(f"Gamma Template POST failed: {resp.status_code} {resp.text}")
    data = resp.json()
    generation_id = data.get("generationId")
    if not generation_id:
        raise RuntimeError(f"Gamma Template POST missing generationId: {data}")
    return generation_id


def get_generation(api_key: str, generation_id: str) -> Dict[str, Any]:
    url = f"{BASE_URL}/generations/{generation_id}"
    resp = requests.get(url, headers=_headers(api_key), timeout=30)
    if resp.status_code >= 400:
        raise RuntimeError(f"Gamma GET failed: {resp.status_code} {resp.text}")
    return resp.json()


def poll_generation(
    api_key: str,
    generation_id: str,
    timeout_sec: int = 300,
    poll_interval_sec: int = 3,
) -> Tuple[Dict[str, Any], str]:
    start = time.time()
    last_data: Dict[str, Any] = {"status": "pending", "generationId": generation_id}
    while True:
        elapsed = time.time() - start
        if elapsed >= timeout_sec:
            return last_data, "timeout"

        data = get_generation(api_key, generation_id)
        last_data = data
        status = str(data.get("status", "")).lower()
        if status and status not in {"pending", "processing"}:
            return data, status

        time.sleep(poll_interval_sec)


def _collect_urls(obj: Any, out: List[str]) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            _collect_urls(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect_urls(v, out)
    elif isinstance(obj, str):
        if obj.startswith("http://") or obj.startswith("https://"):
            out.append(obj)


def _rank_url(url: str) -> int:
    if re.search(r"\.pptx($|[?#])", url, re.IGNORECASE):
        return 2
    if "pptx" in url.lower():
        return 1
    return 0


def find_all_urls(obj: Any) -> List[str]:
    urls: List[str] = []
    _collect_urls(obj, urls)
    seen = set()
    ordered: List[str] = []
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        ordered.append(u)
    return ordered


def find_pptx_urls(obj: Any) -> List[str]:
    urls = find_all_urls(obj)
    ranked: List[Tuple[int, str]] = []
    seen = set()
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        rank = _rank_url(u)
        if rank > 0:
            ranked.append((rank, u))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [u for _, u in ranked]


def choose_pptx_url(data: Dict[str, Any]) -> Tuple[Optional[str], List[str]]:
    warnings: List[str] = []
    all_urls = find_all_urls(data)
    if not all_urls:
        warnings.append("No URL candidates found in Gamma response.")
        return None, warnings

    candidates = find_pptx_urls(data)
    search_list = candidates if candidates else all_urls

    for url in search_list:
        try:
            head = requests.head(url, allow_redirects=True, timeout=10)
            if head.status_code == 405:
                warnings.append("HEAD not allowed; falling back to best candidate URL.")
                return url, warnings
            if head.status_code >= 400:
                continue
            ctype = head.headers.get("Content-Type", "")
            if PPTX_MIME in ctype or "pptx" in ctype.lower():
                return url, warnings
        except requests.RequestException:
            continue

    warnings.append("Could not verify PPTX Content-Type; using best candidate URL.")
    fallback = candidates[0] if candidates else all_urls[0]
    return fallback, warnings


def download_pptx(url: str, out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
