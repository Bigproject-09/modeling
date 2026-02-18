# main.py (정리된 버전)
import os
import uuid
import requests
import chromadb
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from features.rnd_search.main_search import main as run_search
from features.ppt_script.main_script import main as run_script_gen

load_dotenv()

from utils.document_parsing import parse_docx_to_blocks, extract_text_from_pdf

app = FastAPI()

# ============================================
# ChromaDB 클라이언트 초기화
# ============================================
CHROMA_HOST = os.getenv('CHROMA_HOST', 'localhost')
CHROMA_PORT = int(os.getenv('CHROMA_PORT', 8001))

chroma_client = chromadb.HttpClient(
    host=CHROMA_HOST,
    port=CHROMA_PORT
)

# ============================================
# CORS 설정
# ============================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# ChromaDB 관련 엔드포인트
# ============================================
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
def add_documents(
    collection_name: str,
    documents: list[str],
    metadatas: list[dict] = None,
    ids: list[str] = None
):
    try:
        collection = chroma_client.get_collection(name=collection_name)
        collection.add(documents=documents, metadatas=metadatas, ids=ids)
        return {"status": "success", "added": len(documents)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ============================================
# 파일 파싱 (DB 저장은 Spring에서)
# ============================================
@app.post("/parse")
async def parse_notice(file: UploadFile = File(...)):
    print(f"PARSE CALLED: {file.filename}")

    os.makedirs("tmp", exist_ok=True)
    ext = os.path.splitext(file.filename)[1].lower()
    tmp_path = os.path.join("tmp", f"{uuid.uuid4().hex}{ext}")

    try:
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)

        if ext == ".pdf":
            result = {
                "file_type": "pdf",
                "pages": extract_text_from_pdf(tmp_path)
            }
        elif ext == ".docx":
            result = {
                "file_type": "docx",
                "content": parse_docx_to_blocks(tmp_path, "tmp")
            }
        else:
            return JSONResponse(status_code=400, content={"error": f"Unsupported extension: {ext}"})

        print(f"PARSE SUCCESS: {file.filename}")
        return JSONResponse(content=result, status_code=200)

    except Exception as e:
        print(f"❌ PARSE FAILED: {file.filename} - {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

# ============================================
# 헬스체크
# ============================================
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "FastAPI is running"}

# ============================================
# 파싱 지원 형식 조회
# ============================================
@app.get("/parse/formats")
def supported_formats():
    return {"supported_formats": [".pdf", ".docx"], "max_file_size_mb": 50}

# ============================================
# Step 1: RFP 분석 체크리스트
# ============================================
class Step1Request(BaseModel):
    notice_id: int
    company_id: int = 1

@app.post("/api/analyze/step1")
def api_run_step1(req: Step1Request):
    from features.rfp_analysis_checklist.main_notice import run_notice_step1
    print(f"[Step 1] 분석 요청: notice_id={req.notice_id}, company_id={req.company_id}")
    result = run_notice_step1(notice_id=req.notice_id, company_id=req.company_id)
    return {"status": "success", "data": result}

# ============================================
# Step 2: RFP 검색
# ============================================
class Step2Request(BaseModel):
    notice_id: int | None = None
    notice_text: str | None = None
    ministry_name: str | None = None

@app.post("/api/analyze/step2")
def api_run_step2(req: Step2Request):
    print(f"[Step 2] 유관 RFP 검색 요청")
    print(f"  - notice_id: {req.notice_id}")
    print(f"  - ministry_name: {req.ministry_name}")
    print(f"  - notice_text: {len(req.notice_text or '')} chars")

    try:
        result = run_search(
            notice_id=req.notice_id,
            notice_text=req.notice_text,
            ministry_name=req.ministry_name,
        )
        return JSONResponse(content={"status": "success", "data": result}, status_code=200)
    except Exception as e:
        import traceback
        print(f"  ❌ 오류: {str(e)}")
        print(traceback.format_exc())
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

# ============================================
# ✅ 다운로드: output 폴더의 pptx 직접 내려주기
# ============================================
@app.get("/download/pptx/{filename}")
def download_pptx(filename: str):
    # 보안: 파일명만 허용 (경로 주입 차단)
    safe_name = os.path.basename(filename)
    if safe_name != filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    output_dir = os.path.join(os.getcwd(), "output")
    file_path = os.path.join(output_dir, safe_name)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {safe_name}")

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail=f"Not a file: {safe_name}")

    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=safe_name,
    )

# ============================================
# Step 3: PPT 생성 (전체 워크플로우)
# ============================================
@app.post("/api/analyze/step3")
async def api_run_step3(
    file: UploadFile = File(...),
    notice_id: int = Form(None),
    token: str = Form(None),
):
    """
    PPT generation workflow.
    - Stores output under local output directory.
    - Does not write DB in this step.
    """
    from features.ppt_maker.main_ppt import run_ppt_generation

    print(f"[Step 3] PPT generation request: {file.filename}, notice_id={notice_id}")

    os.makedirs("tmp", exist_ok=True)
    ext = os.path.splitext(file.filename)[1].lower()
    tmp_path = os.path.join("tmp", f"{uuid.uuid4().hex}{ext}")

    try:
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)
        print(f"  file saved: {tmp_path}")

        render_mode = (os.getenv("PPT_RENDER_MODE", "gamma") or "gamma").strip().lower()
        gamma_timeout_sec = int(os.getenv("PPT_GAMMA_TIMEOUT_SEC", "900"))

        final_state = run_ppt_generation(
            source_path=tmp_path,
            notice_id=str(notice_id or ""),
            output_dir="output",
            render_mode=render_mode,
            gamma_timeout_sec=gamma_timeout_sec,
        )
        if not isinstance(final_state, dict) or not final_state:
            raise RuntimeError("run_ppt_generation returned empty result")

        deck_json = final_state.get("deck_json") or {}
        slides = deck_json.get("slides") if isinstance(deck_json, dict) else []
        total_slides = len(slides) if isinstance(slides, list) else 0
        if total_slides == 0:
            try:
                total_slides = int(final_state.get("total_slides") or 0)
            except Exception:
                total_slides = 0

        deck_title = ""
        if isinstance(deck_json, dict):
            deck_title = str(deck_json.get("deck_title") or "").strip()
        if not deck_title:
            deck_title = str(final_state.get("deck_title") or "").strip()

        def _pick_first_non_empty(*values):
            for value in values:
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return ""

        pptx_path = _pick_first_non_empty(
            final_state.get("final_ppt_path"),
            final_state.get("gamma_ppt_path"),
            final_state.get("pptx_path"),
        )
        if not pptx_path:
            raise RuntimeError("PPT generation failed: final pptx_path is empty")
        print(f"  pptx_path={pptx_path}")

        pptx_filename = os.path.basename(pptx_path)
        download_url = f"/download/pptx/{pptx_filename}"

        result = {
            "deck_title": deck_title,
            "total_slides": total_slides,
            "pptx_path": pptx_path,
            "pptx_filename": pptx_filename,
            "download_url": download_url,
        }

        return JSONResponse({"status": "success", "data": result})

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

# ============================================
# Step 4: PPT 스크립트 생성
# ============================================
@app.post("/api/analyze/step4")
async def api_run_step4(
    file: UploadFile = File(...),
    notice_id: int = None,
    token: str = None
):
    print(f"[Step 4] 스크립트 생성 요청: {file.filename}, notice_id={notice_id}")

    os.makedirs("tmp", exist_ok=True)
    tmp_path = os.path.join("tmp", f"{uuid.uuid4().hex}.pptx")

    try:
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)

        result = run_script_gen(pptx_path=tmp_path)

        if result:
            # Spring Boot로 저장 요청(너가 원하면 여기만 남겨도 됨)
            if notice_id and token:
                try:
                    spring_url = "http://localhost:8080/api/scripts/save"
                    headers = {"Authorization": f"Bearer {token}"}
                    payload = {
                        "noticeId": notice_id,
                        "slides": result.get("slides", []),
                        "qna": result.get("qna", [])
                    }

                    spring_response = requests.post(
                        spring_url,
                        json=payload,
                        headers=headers,
                        timeout=10
                    )

                    if spring_response.status_code == 200:
                        print("[Step 4] DB 저장 성공")
                    else:
                        print(f"[Step 4] DB 저장 실패: {spring_response.status_code}")
                except Exception as e:
                    print(f"[Step 4] Spring Boot 연동 오류: {str(e)}")

            return JSONResponse(content={"status": "success", "data": result}, status_code=200)

        return JSONResponse(status_code=500, content={"status": "error", "message": "스크립트 생성 실패"})

    except Exception as e:
        print(f"[Step 4] 오류: {str(e)}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

# ============================================
# 서버 실행
# ============================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
