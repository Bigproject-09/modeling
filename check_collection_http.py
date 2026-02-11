# check_collection_http.py
import chromadb

COLLECTION_NAME = "strategy_chunks_norm"

client = chromadb.HttpClient(host="localhost", port=8001)

# 1) 전체 컬렉션 목록 확인
cols = client.list_collections()
names = [c.name for c in cols]
print("=== Collections on server ===")
for n in names:
    print("-", n)

# 2) 특정 컬렉션 존재 여부 확인
print("\n=== Exists? ===")
print(COLLECTION_NAME, "->", COLLECTION_NAME in names)

# 3) 실제로 get 가능 여부(없으면 예외)
try:
    col = client.get_collection(COLLECTION_NAME)
    print("\n=== get_collection OK ===")
    print("name:", col.name)
    print("count:", col.count())
except Exception as e:
    print("\n=== get_collection FAILED ===")
    print(type(e).__name__, ":", e)
