# modeling/ingest_strategy_jsonl.py

import os
import json
import chromadb
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

def main():
    print("="*60)
    print("[DB 생성] JSONL 데이터 적재 시스템")

    # 1. 환경 변수에서 경로 가져오기
    jsonl_path = os.environ.get("STRATEGY_JSONL_PATH")
    chroma_dir = os.environ.get("CHROMA_DB_DIR")
    collection_name = os.environ.get("CHROMA_COLLECTION", "strategy_chunks_norm")
    
    # 모델 설정 (Main과 동일하게 유지)
    EMBED_MODEL_NAME = "intfloat/multilingual-e5-base"

    # 경로 검증
    if not chroma_dir:
        print("[오류] CHROMA_DB_DIR 환경변수가 설정되지 않았습니다.")
        return
    if not jsonl_path or not os.path.exists(jsonl_path):
        print(f"[오류] JSONL 파일을 찾을 수 없습니다: {jsonl_path}")
        return

    print(f"[*] 타겟 DB 경로: {chroma_dir}")
    print(f"[*] 원본 데이터: {jsonl_path}")
    print(f"[*] 임베딩 모델: {EMBED_MODEL_NAME}")

    # 2. DB 연결 (없으면 생성됨)
    client = chromadb.PersistentClient(path=chroma_dir)
    collection = client.get_or_create_collection(name=collection_name)
    
    # 3. 모델 로딩
    print("[*] 모델 로딩 중...")
    model = SentenceTransformer(EMBED_MODEL_NAME)

    # 4. 데이터 로딩 (JSONL 읽기)
    docs = []
    ids = []
    metas = []

    print("[*] 파일 읽는 중...")
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue

            # 텍스트 확인
            text = (item.get("chunk_text") or "").strip()
            if not text: continue
            
            # ID 생성 (doc_id + chunk_id 조합)
            chunk_id = item.get("chunk_id")
            doc_id = item.get("doc_id") or ""
            if not chunk_id: continue
            
            unique_id = f"{doc_id}_{chunk_id}" if doc_id else chunk_id
            
            ids.append(unique_id)
            docs.append(text)
            
            # 메타데이터 구성 (검색에 필요한 필드 위주)
            metas.append({
                "doc_id": doc_id,
                "title": item.get("title_raw", "")[:100], # 너무 길면 자름
                "year": str(item.get("year", "")),
                "agency_norm": item.get("agency_norm", ""),
                "agency_raw": item.get("agency_raw", ""),
            })

    if not docs:
        print("[!] 적재할 데이터가 없습니다.")
        return

    print(f"[*] 총 {len(docs)}개 데이터 적재 시작 (Batch Size: 64)")

    # 5. 배치 단위로 임베딩 및 적재
    batch_size = 64
    total = len(docs)
    
    for i in range(0, total, batch_size):
        batch_docs = docs[i : i + batch_size]
        batch_ids = ids[i : i + batch_size]
        batch_metas = metas[i : i + batch_size]
        
        # [중요] E5 모델은 문서 임베딩 시 'passage: ' 접두어를 권장함
        # DB에는 원본 텍스트를 저장하고, 임베딩 벡터 만들 때만 접두어 사용
        batch_docs_for_embed = ["passage: " + d for d in batch_docs]
        
        # 임베딩 생성
        embeddings = model.encode(batch_docs_for_embed, normalize_embeddings=True).tolist()
        
        # ChromaDB에 저장 (Upsert)
        collection.upsert(
            ids=batch_ids,
            documents=batch_docs, # 원본 텍스트
            metadatas=batch_metas,
            embeddings=embeddings,
        )
        
        # 진행률 표시
        if (i // batch_size) % 10 == 0:
             progress = (i + len(batch_docs)) / total * 100
             print(f"  - 진행률: {i + len(batch_docs)}/{total} ({progress:.1f}%)")

    print("="*60)
    print(f"[완료] '{chroma_dir}' 경로에 {total}개 데이터 적재가 끝났습니다.")
    print("이제 main_1.py를 실행하여 검색할 수 있습니다.")

if __name__ == "__main__":
    main()