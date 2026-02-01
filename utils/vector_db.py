# modeling/vector_search.py

import os
import re
import chromadb
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer

try:
    from agency_utils import get_ministry_variants
except ImportError:
    def get_ministry_variants(name): return [name] if name else []

# [경로 고정]
CHROMA_DIR = r"C:\chroma_db"
COLLECTION_NAME = "strategy_chunks_norm"
EMBED_MODEL_NAME = "intfloat/multilingual-e5-base"

def search_two_tracks(
    notice_text: str,
    ministry_name: str,
    top_k_a: int = 5,
    top_k_b: int = 5,
    exclude_same_ministry_in_b: bool = True,
    score_threshold: float = 0.0  # [필수] 이 인자가 있어야 합니다!
) -> Dict[str, List[Dict[str, Any]]]:

    if not os.path.exists(CHROMA_DIR):
        backup_path = r"G:\내 드라이브\bigproject\chroma_db"
        if os.path.exists(backup_path):
             client = chromadb.PersistentClient(path=backup_path)
             print(f"[*] ChromaDB 연결(Backup): {backup_path}")
        else:
            raise FileNotFoundError(f"DB 경로가 없습니다: {CHROMA_DIR}")
    else:
        print(f"[*] ChromaDB 연결: {CHROMA_DIR}")
        client = chromadb.PersistentClient(path=CHROMA_DIR)
    
    try:
        collection = client.get_collection(name=COLLECTION_NAME)
    except Exception:
        cols = client.list_collections()
        names = [c.name for c in cols]
        raise ValueError(f"컬렉션 '{COLLECTION_NAME}' 없음. (보유 중: {names})")

    print(f"[*] 임베딩 모델 로드: {EMBED_MODEL_NAME}")
    model = SentenceTransformer(EMBED_MODEL_NAME)
    
    query_text = "query: " + notice_text[:2000]
    query_embedding = model.encode([query_text]).tolist()

    target_variants = get_ministry_variants(ministry_name)
    track_a = []
    track_b = []

    # --- Track A ---
    if target_variants:
        where_a = {"agency_norm": {"$in": target_variants}}
        try:
            results_a = collection.query(
                query_embeddings=query_embedding,
                n_results=top_k_a,
                where=where_a,
                include=["metadatas", "documents", "distances"]
            )
            track_a = _pack_results(results_a, score_threshold)
        except Exception as e:
            print(f"[Track A 검색 오류] {e}")

    # --- Track B ---
    where_b = {}
    if exclude_same_ministry_in_b and target_variants:
        where_b = {"agency_norm": {"$nin": target_variants}}
    
    try:
        results_b = collection.query(
            query_embeddings=query_embedding,
            n_results=top_k_b,
            where=where_b if where_b else None,
            include=["metadatas", "documents", "distances"]
        )
        track_b = _pack_results(results_b, score_threshold)
    except Exception as e:
        print(f"[Track B 검색 오류] {e}")

    return {"track_a": track_a, "track_b": track_b}

def _pack_results(raw: dict, threshold: float = 0.0) -> List[Dict[str, Any]]:
    packed = []
    if not raw or not raw.get('ids'): return []
    count = len(raw['ids'][0])
    pattern = re.compile(r"\[paragraph#\d+\]\s*")

    for i in range(count):
        dist = raw['distances'][0][i]
        similarity_score = (1 - dist) * 100
        
        if similarity_score < threshold:
            continue

        raw_text = raw['documents'][0][i]
        clean_text = pattern.sub("", raw_text)

        packed.append({
            "id": raw['ids'][0][i],
            "metadata": raw['metadatas'][0][i],
            "document": clean_text.strip(),
            "distance": dist,
            "score": round(similarity_score, 1)
        })
    return packed