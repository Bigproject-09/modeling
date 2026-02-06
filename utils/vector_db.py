import os
import re
import chromadb
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import sys

load_dotenv()

# 상위 폴더(modeling/)에서 agency_utils를 찾을 수 있도록 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

try:
    from agency_utils import get_ministry_variants
except ImportError:
    def get_ministry_variants(name): return [name] if name else []

# [ChromaDB 설정 - HttpClient로 변경]
CHROMA_HOST = os.getenv('CHROMA_HOST', 'localhost')
CHROMA_PORT = int(os.getenv('CHROMA_PORT', 8001))
COLLECTION_NAME = "strategy_chunks_norm"
EMBED_MODEL_NAME = "intfloat/multilingual-e5-base"

def search_two_tracks(
    notice_text: str,
    ministry_name: str,
    top_k_a: int = 5,
    top_k_b: int = 5,
    exclude_same_ministry_in_b: bool = True,
    score_threshold: float = 0.0 
) -> Dict[str, List[Dict[str, Any]]]:

    print(f"[*] ChromaDB 서버 연결: {CHROMA_HOST}:{CHROMA_PORT}")
    
    try:
        # PersistentClient → HttpClient로 변경
        client = chromadb.HttpClient(
            host=CHROMA_HOST,
            port=CHROMA_PORT
        )
        collection = client.get_collection(name=COLLECTION_NAME)
    except Exception as e:
        print(f"[오류] ChromaDB 서버 연결 실패: {e}")
        print(f"[힌트] ChromaDB 서버가 실행 중인지 확인하세요: chroma run --path C:\\chroma_db --port {CHROMA_PORT}")
        return {"track_a": [], "track_b": []}

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