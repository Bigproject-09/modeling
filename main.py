# main.py
import os
import uuid
import json
import requests
import chromadb
from typing import Any, Dict, Optional, List

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

# utils.document_parsing 기반 파싱만 사용
from utils.document_parsing import parse_docx_to_blocks, extract_text_from_pdf

# Step1/2/4에서 쓰는 기존 모듈들
from features.rfp_analysis_checklist.main_notice import run_notice_step1
from features.rnd_search.main_search import main as run_search
from features.ppt_script.main_script import main as run_script_gen

app = FastAPI()

# ============================================
# ChromaDB (그대로 유지)
# ============================================
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8001"))

chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/chroma/collection/create")
def create_collection(name: str):
    try:
        chroma_client.create_collection(name=name)
        return {"status": "success", "collection": name}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/chroma/collections")
def list_collections():
    try:
        collections = chroma_client.list_collections()
        return {"collections": [col.name for col in collections]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/chroma/search")
def search_documents(collection_name: str, query: str, n_results: int = 5):
    try:
        collection = chroma_client.get_collection(name=collection_name)
        results = collection.query(query_texts=[query], n_results=n_results)
        return {"status": "success", "results": results}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/chroma/add")
def add_documents(collection_name: str, documents: List[str], metadatas: List[dict] = None, ids: List[str] = None):
    try:
        collection = chroma_client.get_collection(name=collection_name)
        collection.add(documents=documents, metadatas=metadatas, ids=ids)
        return {"status": "success", "added": len(documents)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# bytes 해결용
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import json
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # bytes가 섞여있어도 절대 터지지 않게 "문자열로" 고정
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "message": "Request validation failed",
            "errors": exc.errors(),  # 여기엔 bytes가 안 들어가야 정상인데, 들어가도 아래에서 안전 처리
            "body_preview": (await request.body())[:200].hex()  # 바디 일부를 hex로 보여줌
        },
    )

# ============================================
# /parse (충돌 제거: utils.document_parsing만 사용)
# ============================================
@app.post("/parse")
async def parse_notice(file: UploadFile = File(...)):
    """
    파일 파싱만 수행 (DB 저장은 Spring Boot에서 처리)
    - pdf: extract_text_from_pdf
    - docx: parse_docx_to_blocks
    """
    os.makedirs("tmp", exist_ok=True)
    ext = os.path.splitext(file.filename)[1].lower()
    tmp_path = os.path.join("tmp", f"{uuid.uuid4().hex}{ext}")

    try:
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)

        if ext == ".pdf":
            parsed = {"file_type": "pdf", "pages": extract_text_from_pdf(tmp_path)}
        elif ext == ".docx":
            parsed = {"file_type": "docx", "content": parse_docx_to_blocks(tmp_path, "tmp")}
        else:
            return JSONResponse(status_code=400, content={"error": f"Unsupported extension: {ext}"})

        return JSONResponse(status_code=200, content=parsed)

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "FastAPI is running"}

@app.get("/parse/formats")
def supported_formats():
    return {"supported_formats": [".pdf", ".docx"], "max_file_size_mb": 50}

# ============================================
# Step1 (JSON 그대로)
# ============================================
class Step1Request(BaseModel):
    notice_id: int
    company_id: int = 1

@app.post("/api/analyze/step1")
def api_run_step1(req: Step1Request):
    result = run_notice_step1(notice_id=req.notice_id, company_id=req.company_id)
    return {"status": "success", "data": result}

# ============================================
# ✅ JSON Step2/Step4를 위해 Spring Boot에서 공고 파일/PPT 경로를 가져오는 헬퍼
# ============================================
SPRING_BASE_URL = os.getenv("SPRING_BASE_URL", "http://localhost:8080")

def _auth_headers(token: Optional[str]) -> Dict[str, str]:
    if not token:
        return {}
    return {"Authorization": token if token.startswith("Bearer ") else f"Bearer {token}"}

def _spring_get_notice_detail(notice_id: int, token: Optional[str] = None) -> Dict[str, Any]:
    url = f"{SPRING_BASE_URL}/api/notices/{notice_id}"
    r = requests.get(url, headers=_auth_headers(token), timeout=20)
    r.raise_for_status()
    return r.json()

def _spring_download_notice_file(notice_id: int, file_id: int, token: Optional[str] = None) -> str:
    """
    Spring에서 파일을 내려받아 FastAPI tmp에 저장 후 경로 리턴
    """
    url = f"{SPRING_BASE_URL}/api/notices/{notice_id}/files/{file_id}/download"
    r = requests.get(url, headers=_auth_headers(token), timeout=60)
    r.raise_for_status()

    cd = r.headers.get("content-disposition", "")
    filename = f"notice_{notice_id}_{file_id}"
    if "filename=" in cd:
        filename = cd.split("filename=")[-1].strip().strip('"')

    os.makedirs("tmp", exist_ok=True)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in [".pdf", ".docx"]:
        ext = ext or ".bin"

    tmp_path = os.path.join("tmp", f"{uuid.uuid4().hex}{ext}")
    with open(tmp_path, "wb") as f:
        f.write(r.content)

    return tmp_path

def _build_text_from_file(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()

    if ext == ".pdf":
        pages = extract_text_from_pdf(path)
        return "\n".join(json.dumps(p, ensure_ascii=False) for p in pages) if isinstance(pages, list) else str(pages)

    if ext == ".docx":
        blocks = parse_docx_to_blocks(path, "tmp")
        return json.dumps(blocks, ensure_ascii=False)

    return ""

def _pick_first_supported_notice_file_id(notice_detail: Dict[str, Any]) -> Optional[int]:
    for key in ["files", "noticeFiles", "notice_files"]:
        arr = notice_detail.get(key)
        if isinstance(arr, list) and arr:
            for it in arr:
                if isinstance(it, dict):
                    for id_key in ["fileId", "id", "noticeFileId", "file_id"]:
                        v = it.get(id_key)
                        if isinstance(v, int):
                            return v
                        if isinstance(v, str) and v.isdigit():
                            return int(v)
    return None

# ============================================
# ✅ Step2 JSON 버전
# body: {"notice_id": 1, "token": "Bearer ..."(옵션)}
# ============================================
class Step2Request(BaseModel):
    notice_id: int
    notice_text: Optional[str] = None
    ministry_name: Optional[str] = None
    token: Optional[str] = None  # 필요하면 유지

@app.post("/api/analyze/step2")
def api_run_step2_json(req: Step2Request):
    try:
        # ✅ 1) Spring이 준 notice_text 우선
        notice_text = (req.notice_text or "").strip()
        ministry_name = (req.ministry_name or "").strip()

        # ✅ 2) 없으면(백업) 기존 로직으로 Spring에서 파일 받아서 구성(원하면 유지)
        if not notice_text:
            detail = _spring_get_notice_detail(req.notice_id, req.token)
            file_id = _pick_first_supported_notice_file_id(detail)
            if file_id is None:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "message": "공고 파일(fileId)을 찾지 못했습니다. notice detail 응답에 files 목록이 있는지 확인하세요."}
                )

            tmp_path = _spring_download_notice_file(req.notice_id, file_id, req.token)
            try:
                notice_text = _build_text_from_file(tmp_path).strip()
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        if not notice_text:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "notice_text가 비어있습니다. 업로드 파싱/텍스트 변환을 확인하세요."}
            )

        # ✅ run_search가 ministry_name을 받는 구조면 같이 넘기고,
        #    아니라면 run_search 내부에서 Step2 report 만들 때 사용하도록 수정해야 함.
        #    일단 notice_text 기반 검색이 핵심이라 최소 인자만 유지.
        result = run_search(notice_id=req.notice_id, notice_text=notice_text, ministry_name=ministry_name)
        return {"status": "success", "data": result}

    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
# ============================================
# Step3 (PPT 생성)
# ============================================
class Step3Request(BaseModel):
    notice_id: int

@app.post("/api/analyze/step3")
def api_run_step3(req: Step3Request):
    from features.ppt_maker.main_ppt import main as run_ppt
    result = run_ppt(notice_id=req.notice_id)
    return {"status": "success", "data": result}

# ============================================
# ✅ Step4 JSON 버전 (생성만, 저장 없음)
# body: {"notice_id": 1, "token": "Bearer ..."(옵션: notice detail 조회가 인증 필요할 때만)}
# ============================================
class Step4Request(BaseModel):
    notice_id: int
    token: Optional[str] = None

def _find_ppt_path_from_notice_detail(detail: Dict[str, Any]) -> Optional[str]:
    for k in ["pptPath", "ppt_path", "generatedPptPath"]:
        v = detail.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    for key in ["references", "noticeReferences", "notice_references"]:
        arr = detail.get(key)
        if isinstance(arr, list):
            for it in arr:
                if not isinstance(it, dict):
                    continue
                title = str(it.get("title", "")).strip()
                url = str(it.get("url", "")).strip()
                typ = str(it.get("type", "")).strip().upper()
                if url and (title.lower() == "generated ppt" or typ == "FILE"):
                    return url
    return None

@app.post("/api/analyze/step4")
def api_run_step4_json(req: Step4Request):
    try:
        detail = _spring_get_notice_detail(req.notice_id, req.token)
        ppt_path = _find_ppt_path_from_notice_detail(detail)

        if not ppt_path:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "PPT 경로(ppt_path)를 찾지 못했습니다. Step3 결과가 references(FILE)에 저장되어 있는지 확인하세요."}
            )

        local_ppt_path = ppt_path
        tmp_path = None

        # URL이면 다운로드
        if ppt_path.startswith("http://") or ppt_path.startswith("https://"):
            os.makedirs("tmp", exist_ok=True)
            tmp_path = os.path.join("tmp", f"{uuid.uuid4().hex}.pptx")
            r = requests.get(ppt_path, timeout=60)
            r.raise_for_status()
            with open(tmp_path, "wb") as f:
                f.write(r.content)
            local_ppt_path = tmp_path

        try:
            result = run_script_gen(pptx_path=local_ppt_path)
            # ✅ 저장은 여기서 하지 않음 (Spring/프론트에서 /api/scripts/save)
            return {"status": "success", "data": result, "meta": {"saved": False}}
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    except requests.HTTPError as e:
        return JSONResponse(status_code=502, content={"status": "error", "message": f"Spring/URL 호출 실패: {str(e)}"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
