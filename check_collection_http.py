# inspect_hnsw_files.py
import os, sqlite3

DB_PATH = r"C:\chroma_db"
SQLITE = os.path.join(DB_PATH, "chroma.sqlite3")

con = sqlite3.connect(SQLITE)
cur = con.cursor()

segs = cur.execute("SELECT id, type, collection FROM segments").fetchall()
cols = cur.execute("SELECT id, name FROM collections").fetchall()
coll_map = {cid: name for cid, name in cols}

def walk_files(folder):
    out = []
    for root, _, files in os.walk(folder):
        for fn in files:
            p = os.path.join(root, fn)
            try:
                out.append((os.path.relpath(p, folder), os.path.getsize(p)))
            except OSError:
                out.append((os.path.relpath(p, folder), None))
    return sorted(out, key=lambda x: x[0])

for sid, typ, coll in segs:
    if "hnsw-local-persisted" in (typ or ""):
        name = coll_map.get(coll, coll)
        folder = os.path.join(DB_PATH, sid)
        print("\n===", name, sid, "===")
        if not os.path.isdir(folder):
            print("MISSING FOLDER")
            continue
        files = walk_files(folder)
        print("file_count =", len(files))
        # 너무 많을 수 있으니 상위 50개만
        for rel, sz in files[:50]:
            print(f"{rel}  ({sz} bytes)")
        # 0바이트 파일 있으면 표시
        zeros = [rel for rel, sz in files if sz == 0]
        if zeros:
            print("ZERO-SIZE FILES:", zeros[:20])
con.close()
