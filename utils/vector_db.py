import os
import re
import sys
from typing import Any, Dict, List

import chromadb
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

# Allow importing `modeling/agency_utils.py` from `modeling/utils`.
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

try:
    from agency_utils import get_ministry_variants
except ImportError:

    def get_ministry_variants(name: str) -> List[str]:
        return [name] if name else []


# =========================================================
# ChromaDB (Strategy / RFP search)
# =========================================================
CHROMA_HOST = os.getenv("CHROMA_HOST", "127.0.0.1")
# RFP search(전략) 기본 포트: 8002
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8002"))
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "strategy_chunks_norm")
EMBED_MODEL_NAME = os.getenv("CHROMA_EMBED_MODEL_NAME", "intfloat/multilingual-e5-base")
CHROMA_DIR_HINT = os.getenv("CHROMA_DB_DIR", r"C:\chroma_strategy")


def search_two_tracks(
    notice_text: str,
    ministry_name: str,
    top_k_a: int = 5,
    top_k_b: int = 5,
    exclude_same_ministry_in_b: bool = True,
    score_threshold: float = 0.0,
) -> Dict[str, List[Dict[str, Any]]]:
    print(f"[*] ChromaDB server: {CHROMA_HOST}:{CHROMA_PORT} (collection={COLLECTION_NAME})")

    try:
        client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
        collection = client.get_collection(name=COLLECTION_NAME)
    except Exception as e:
        print(f"[Error] ChromaDB connect failed: {e}")
        print(f"[Hint] Run: chroma run --host {CHROMA_HOST} --port {CHROMA_PORT} --path {CHROMA_DIR_HINT}")
        return {"track_a": [], "track_b": []}

    print(f"[*] Embed model: {EMBED_MODEL_NAME}")
    model = SentenceTransformer(EMBED_MODEL_NAME)

    query_text = "query: " + (notice_text or "")[:2000]
    query_embedding = model.encode([query_text]).tolist()

    target_variants = get_ministry_variants(ministry_name)
    track_a: List[Dict[str, Any]] = []
    track_b: List[Dict[str, Any]] = []

    # --- Track A (same ministry) ---
    if target_variants:
        where_a = {"agency_norm": {"$in": target_variants}}
        try:
            results_a = collection.query(
                query_embeddings=query_embedding,
                n_results=top_k_a,
                where=where_a,
                include=["metadatas", "documents", "distances"],
            )
            track_a = _pack_results(results_a, score_threshold)
        except Exception as e:
            print(f"[Track A Error] {e}")

    # --- Track B (other ministries) ---
    where_b = None
    if exclude_same_ministry_in_b and target_variants:
        where_b = {"agency_norm": {"$nin": target_variants}}

    try:
        results_b = collection.query(
            query_embeddings=query_embedding,
            n_results=top_k_b,
            where=where_b,
            include=["metadatas", "documents", "distances"],
        )
        track_b = _pack_results(results_b, score_threshold)
    except Exception as e:
        print(f"[Track B Error] {e}")

    return {"track_a": track_a, "track_b": track_b}


def _pack_results(raw: dict, threshold: float = 0.0) -> List[Dict[str, Any]]:
    packed: List[Dict[str, Any]] = []
    if not raw or not raw.get("ids"):
        return []

    count = len(raw["ids"][0])
    pattern = re.compile(r"\[paragraph#\d+\]\s*")

    for i in range(count):
        dist = raw["distances"][0][i]
        similarity_score = (1 - dist) * 100

        if similarity_score < threshold:
            continue

        raw_text = raw["documents"][0][i]
        clean_text = pattern.sub("", raw_text)

        packed.append(
            {
                "id": raw["ids"][0][i],
                "metadata": raw["metadatas"][0][i],
                "document": clean_text.strip(),
                "distance": dist,
                "score": round(similarity_score, 1),
            }
        )

    return packed

