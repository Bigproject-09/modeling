# utils/notice_storage.py
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

import mysql.connector


def get_db_conn():
    return mysql.connector.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        charset="utf8mb4",
        use_unicode=True,
    )


def _strip_html(s: str) -> str:
    if not s:
        return ""

    s = re.sub(r"<\s*(script|style)[^>]*>.*?<\s*/\s*\1\s*>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<\s*br\s*/?\s*>", "\n", s, flags=re.I)
    s = re.sub(r"<\s*/\s*p\s*>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)

    s = s.replace("&nbsp;", " ")
    s = s.replace("&amp;", "&")
    s = s.replace("&lt;", "<")
    s = s.replace("&gt;", ">")
    s = s.replace("&quot;", '"')
    s = s.replace("&#39;", "'")

    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def load_notice_from_db(notice_id: int) -> Dict[str, Any]:
    conn = get_db_conn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """
            SELECT notice_id, seq, title, link, description,
                   notice_parsing_json, notice_sections_json
            FROM project_notices
            WHERE notice_id = %s
            """,
            (notice_id,),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"존재하지 않는 notice_id={notice_id}")
        return row
    finally:
        cur.close()
        conn.close()


def build_announcement_chunks(notice_row: Dict[str, Any], max_chunk_chars: int = 1500) -> List[Dict[str, Any]]:
    raw_text = ""

    sections_json = notice_row.get("notice_sections_json")
    if sections_json:
        try:
            sections = json.loads(sections_json)
            pieces: List[str] = []
            if isinstance(sections, list):
                for sec in sections:
                    if not isinstance(sec, dict):
                        continue
                    title = str(sec.get("title", "")).strip()
                    content = sec.get("content", [])
                    if isinstance(content, list):
                        body = "\n".join(str(x) for x in content)
                    else:
                        body = str(content)
                    chunk = f"[{title}]\n{body}".strip()
                    if chunk:
                        pieces.append(chunk)
            raw_text = "\n\n".join(pieces)
        except Exception:
            raw_text = ""

    if not raw_text:
        parsing_json = notice_row.get("notice_parsing_json")
        if parsing_json:
            try:
                parsed = json.loads(parsing_json)
                blocks = parsed.get("blocks") if isinstance(parsed, dict) else parsed
                pieces = []
                if isinstance(blocks, list):
                    for b in blocks:
                        if isinstance(b, dict):
                            t = str(b.get("text", "")).strip()
                        else:
                            t = str(b).strip()
                        if t:
                            pieces.append(t)
                raw_text = "\n\n".join(pieces)
            except Exception:
                raw_text = ""

    if not raw_text:
        raw_text = _strip_html(str(notice_row.get("description") or ""))

    if not raw_text:
        raise RuntimeError("공고문 텍스트를 만들 수 없습니다. (description/sections/parsing 모두 비어있음)")

    paragraphs = [p.strip() for p in raw_text.split("\n") if p.strip()]

    chunks: List[Dict[str, Any]] = []
    buf = ""
    idx = 1

    for p in paragraphs:
        if len(p) > max_chunk_chars:
            if buf:
                chunks.append({"chunk_id": idx, "text": buf.strip()})
                idx += 1
                buf = ""
            for i in range(0, len(p), max_chunk_chars):
                part = p[i : i + max_chunk_chars]
                if part.strip():
                    chunks.append({"chunk_id": idx, "text": part.strip()})
                    idx += 1
            continue

        candidate = (buf + "\n" + p).strip() if buf else p
        if len(candidate) <= max_chunk_chars:
            buf = candidate
        else:
            chunks.append({"chunk_id": idx, "text": buf.strip()})
            idx += 1
            buf = p

    if buf:
        chunks.append({"chunk_id": idx, "text": buf.strip()})

    return chunks


def map_checklist_type(category: str, requirement_text: str) -> str:
    s = f"{category} {requirement_text}".lower()
    if any(k in s for k in ["서류", "제출", "증빙", "첨부"]):
        return "DOCUMENT"
    if any(k in s for k in ["자격", "대상", "신청", "기업", "주체"]):
        return "QUALIFICATION"
    return "CONTENT"


def _pick(d: dict, keys: list[str], default=""):
    for k in keys:
        v = d.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return default

def save_step1_results(notice_id: int, checklist_json: dict, analysis_json: dict) -> dict:
    conn = get_db_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE project_notices
            SET checklist_json = %s,
                analysis_json = %s
            WHERE notice_id = %s
            """,
            (json.dumps(checklist_json, ensure_ascii=False),
             json.dumps(analysis_json, ensure_ascii=False),
             notice_id),
        )

        cur.execute("DELETE FROM checklists WHERE notice_id = %s", (notice_id,))

        # ✅ judgments 후보키 여러개 대응
        judgments = []
        if isinstance(checklist_json, dict):
            for k in ["judgments", "items", "results", "details"]:
                v = checklist_json.get(k)
                if isinstance(v, list):
                    judgments = v
                    break

        saved_count = 0
        for j in judgments:
            if not isinstance(j, dict):
                continue

            category = _pick(j, ["category", "type", "section"], default="")
            requirement_text = _pick(j, ["requirement_text", "requirementText", "requirement", "text"], default="")
            judgment = _pick(j, ["judgment", "status", "result"], default="")

            # ✅ requirement_text 없으면, 그래도 뭔가 텍스트가 있으면 저장 시도
            if not requirement_text:
                continue

            ctype = map_checklist_type(category, requirement_text)
            content = f"[{judgment}] {requirement_text}".strip()
            if len(content) > 500:
                content = content[:497] + "..."

            cur.execute(
                "INSERT INTO checklists (notice_id, type, content) VALUES (%s, %s, %s)",
                (notice_id, ctype, content),
            )
            saved_count += 1

        conn.commit()
        return {"notice_id": notice_id, "saved_checklists": saved_count, "updated_project_notices": 1}
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()