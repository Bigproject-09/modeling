import hashlib
import os
import re
from typing import Dict, Optional

import chromadb
import pandas as pd
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer


load_dotenv()


def s(v) -> str:
    if pd.isna(v):
        return ""
    return str(v).strip()


def detect_column(df: pd.DataFrame, candidates) -> Optional[str]:
    for name in candidates:
        if name in df.columns:
            return name
    return None


def parse_article_number(text: str) -> str:
    m = re.search(r"제\s*([0-9]+(?:의[0-9]+)?)\s*조", text or "")
    return m.group(1) if m else ""


def parse_article_title(text: str) -> str:
    m = re.search(r"제\s*[0-9]+(?:의[0-9]+)?\s*조\s*\(([^)]+)\)", text or "")
    return m.group(1).strip() if m else ""


def split_chunks(text: str, size: int = 800, overlap: int = 120):
    text = (text or "").strip()
    if not text:
        return []

    out = []
    i = 0
    n = len(text)
    while i < n:
        j = min(i + size, n)
        out.append(text[i:j])
        if j == n:
            break
        i = max(0, j - overlap)
    return out


def build_full_reference(law_name: str, article_number: str, article_title: str) -> str:
    parts = []
    if law_name:
        parts.append(law_name)
    if article_number:
        parts.append(f"제{article_number}조")
    if article_title:
        parts.append(article_title)
    return " ".join(parts).strip()


def normalize_meta(row, colmap: Dict[str, Optional[str]], text: str) -> Dict[str, str]:
    def pick(key: str, default: str = "") -> str:
        c = colmap.get(key)
        if c is None:
            return default
        return s(row[c]) or default

    law_name = pick("law_name")
    law_type = pick("law_type", "unknown")
    source_file = pick("source_file")
    regulation_type = pick("regulation_type")
    regulation_number = pick("regulation_number")
    article_number = pick("article_number")
    article_title = pick("article_title")
    full_reference = pick("full_reference")

    if not article_number:
        article_number = parse_article_number(text)
    if not article_title:
        article_title = parse_article_title(text)
    if not full_reference:
        full_reference = build_full_reference(law_name, article_number, article_title)

    return {
        "law_name": law_name,
        "law_type": law_type,
        "source_file": source_file,
        "regulation_type": regulation_type,
        "regulation_number": regulation_number,
        "article_number": article_number,
        "article_title": article_title,
        "full_reference": full_reference,
    }


def main():
    parquet_path = os.environ.get("LAW_PARQUET_PATH", "/tmp/law_manual.parquet")
    host = os.environ.get("LAW_CHROMA_HOST", "chroma_law")
    port = int(os.environ.get("LAW_CHROMA_PORT", "8000"))
    collection_name = os.environ.get("LAW_COLLECTION_NAME", "law_regulations")
    model_name = os.environ.get("LAW_EMBED_MODEL_NAME", "intfloat/multilingual-e5-base")
    recreate = os.environ.get("LAW_RECREATE", "false").lower() in {"1", "true", "yes", "y"}
    batch_size = int(os.environ.get("LAW_BATCH_SIZE", "64"))

    print("=" * 60)
    print("[LAW INGEST] parquet -> chroma")
    print(f"parquet: {parquet_path}")
    print(f"chroma : {host}:{port}, collection={collection_name}")
    print(f"model  : {model_name}")
    print(f"recreate={recreate}, batch_size={batch_size}")

    if not os.path.exists(parquet_path):
        raise FileNotFoundError(parquet_path)

    df = pd.read_parquet(parquet_path)
    print(f"rows={len(df)}, columns={list(df.columns)}")

    colmap = {
        "text": detect_column(df, ["chunk_text", "content", "text", "document", "body", "raw_text"]),
        "law_name": detect_column(df, ["law_name", "law", "law_title"]),
        "law_type": detect_column(df, ["law_type", "doc_type", "type"]),
        "source_file": detect_column(df, ["source_file", "file_name", "filename", "pdf_name"]),
        "regulation_type": detect_column(df, ["regulation_type", "reg_type"]),
        "regulation_number": detect_column(df, ["regulation_number", "reg_number", "law_number"]),
        "article_number": detect_column(df, ["article_number", "article_no", "article"]),
        "article_title": detect_column(df, ["article_title", "article_name", "article_subject"]),
        "full_reference": detect_column(df, ["full_reference", "reference"]),
    }
    if colmap["text"] is None:
        raise RuntimeError("text column missing")

    print(f"column map={colmap}")

    client = chromadb.HttpClient(host=host, port=port)
    if recreate:
        try:
            client.delete_collection(name=collection_name)
            print(f"deleted existing collection: {collection_name}")
        except Exception:
            pass
    col = client.get_or_create_collection(name=collection_name)

    model = SentenceTransformer(model_name)

    ids = []
    docs = []
    metas = []
    total_added = 0

    for i, row in df.iterrows():
        text = s(row[colmap["text"]])  # type: ignore[index]
        if not text:
            continue

        meta = normalize_meta(row, colmap, text)
        chunk_list = split_chunks(text)

        for j, chunk in enumerate(chunk_list):
            uid_seed = f"{meta['law_name']}|{meta['source_file']}|{meta['article_number']}|{i}|{j}|{chunk[:120]}"
            uid = hashlib.sha1(uid_seed.encode("utf-8")).hexdigest()[:24]
            doc = f"passage: {meta['law_name']} {meta['law_type']}: {chunk}".strip()

            ids.append(uid)
            docs.append(doc)
            metas.append(meta)

            if len(ids) >= batch_size:
                emb = model.encode(docs, normalize_embeddings=True).tolist()
                col.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=emb)
                total_added += len(ids)
                print(f"upserted={total_added}")
                ids, docs, metas = [], [], []

    if ids:
        emb = model.encode(docs, normalize_embeddings=True).tolist()
        col.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=emb)
        total_added += len(ids)

    print("=" * 60)
    print(f"done. added={total_added}, final_count={col.count()}")

    sample = col.get(limit=100, offset=0, include=["metadatas"]).get("metadatas", [])
    key_counter = {}
    for m in sample:
        if not isinstance(m, dict):
            continue
        for k in m.keys():
            key_counter[k] = key_counter.get(k, 0) + 1
    print(f"sample_meta_keys={key_counter}")


if __name__ == "__main__":
    main()
