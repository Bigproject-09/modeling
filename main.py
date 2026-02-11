# main.py (정리된 버전)
import os
import uuid
import requests
import chromadb
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware 
from pydantic import BaseModel
from dotenv import load_dotenv
from pydantic import BaseModel
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
    """ChromaDB 컬렉션 생성"""
    try:
        collection = chroma_client.create_collection(name=name)
        return {"status": "success", "collection": name}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/chroma/collections")
def list_collections():
    """ChromaDB 컬렉션 목록 조회"""
    try:
        collections = chroma_client.list_collections()
        return {"collections": [col.name for col in collections]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/chroma/search")
def search_documents(collection_name: str, query: str, n_results: int = 5):
    """ChromaDB에서 유사 문서 검색"""
    try:
        collection = chroma_client.get_collection(name=collection_name)
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
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
    """ChromaDB에 문서 추가"""
    try:
        collection = chroma_client.get_collection(name=collection_name)
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        return {"status": "success", "added": len(documents)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ============================================
# 파일 파싱 (DB 저장은 Spring에서)
# ============================================
@app.post("/parse")
async def parse_notice(file: UploadFile = File(...)):
    """
    파일 파싱만 수행 (DB 저장은 Spring Boot에서 처리)
    
    Flow:
    1. Spring Boot: NoticeFile 생성 + NoticeAttachment 생성 (WAIT 상태)
    2. Spring Boot → FastAPI: 파일 전송
    3. FastAPI: 파싱 수행 후 결과 JSON 반환 ← 이 함수
    4. Spring Boot: NoticeAttachment.markDone(parsedJson) 호출
    """
    print(f"PARSE CALLED: {file.filename}")
    print(f"PARSE CALLED: {file.filename}")

    os.makedirs("tmp", exist_ok=True)
    ext = os.path.splitext(file.filename)[1].lower()
    tmp_path = os.path.join("tmp", f"{uuid.uuid4().hex}{ext}")

    try:
        # 파일 임시 저장
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)

        # 파싱
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
            return JSONResponse(
                status_code=400,
                content={"error": f"Unsupported extension: {ext}"}
            )

        print(f"PARSE SUCCESS: {file.filename}")

        # 파싱 결과만 반환 (DB 저장은 Spring에서)
        return JSONResponse(
            content=result,
            status_code=200
        )

    except Exception as e:
        print(f"❌ PARSE FAILED: {file.filename} - {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

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
    """지원하는 파일 형식 조회"""
    return {
        "supported_formats": [".pdf", ".docx"],
        "max_file_size_mb": 50
    }

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
    """
    Step 2는 Spring에서 /parse로 파일을 먼저 파싱한 뒤,
    notice_text(+ ministry_name)를 JSON으로 넘겨받아 유관 RFP를 검색한다.
    """
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
# Step 3: PPT 생성 (전체 워크플로우)
# ============================================
@app.post("/api/analyze/step3")
async def api_run_step4(
    file: UploadFile = File(...),
    notice_id: int = Form(None),
    token: str = Form(None)
):
    """PPT 생성 전체 워크플로우"""
    from features.ppt_maker.nodes_code.extract_text_node import extract_text
    from features.ppt_maker.nodes_code.section_split_node import section_split_node
    from features.ppt_maker.nodes_code.section_deck_generation_node import section_deck_generation_node
    from features.ppt_maker.nodes_code.merge_deck_node import merge_deck_node
    from features.ppt_maker.nodes_code.gamma_generation_node import gamma_generation_node
    
    print(f"[Step 3] PPT 생성 요청: {file.filename}, notice_id={notice_id}")
    
    os.makedirs("tmp", exist_ok=True)
    ext = os.path.splitext(file.filename)[1].lower()
    tmp_path = os.path.join("tmp", f"{uuid.uuid4().hex}{ext}")
    
    try:
        # 파일 저장
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)
        print(f"  ✅ 파일 저장: {tmp_path}")
        
        # State 초기화
        state = {
            "source_path": tmp_path,
            "parsing_out_dir": "tmp/parsing",
            "gemini_model": "gemini-2.5-flash",
            "gemini_temperature": 0.4,
            "gemini_max_output_tokens": 4096,
            "gamma_timeout_sec": 600,
            "output_dir": "output",
        }
        
        # 1) 텍스트 추출
        print(f"  [1/5] 텍스트 추출...")
        extract_text(state)
        print(f"  ✅ {len(state.get('extracted_text', ''))} 글자")
        
        # 2) 섹션 분할
        print(f"  [2/5] 섹션 분할...")
        section_split_node(state)
        sections = state.get("sections", [])
        print(f"  ✅ {len(sections)}개 섹션")
        
        # 3) 슬라이드 생성 (Gemini)
        print(f"  [3/5] 슬라이드 생성...")
        section_deck_generation_node(state)
        total = sum(len(v.get("slides", [])) for v in state.get("section_decks", {}).values())
        print(f"  ✅ {total}장")
        
        # 4) 병합
        print(f"  [4/5] 병합...")
        merge_deck_node(state)
        merged = len(state.get("deck_json", {}).get("slides", []))
        print(f"  ✅ {merged}장")
        
        # 5) PPTX 생성 (Gamma)
        print(f"  [5/5] PPTX 생성...")
        gamma_generation_node(state)
        pptx_path = state.get("pptx_path")
        print(f"  ✅ {pptx_path}")
        
        # 결과
        result = {
            "deck_title": state.get("deck_title"),
            "total_slides": merged,
            "pptx_path": pptx_path,
        }
        
        # Spring Boot 저장 (선택)
        if notice_id and token:
            try:
                spring_response = requests.post(
                    "http://localhost:8080/api/ppt/save",
                    json={
                        "noticeId": notice_id,
                        "deckTitle": result["deck_title"],
                        "pptxPath": pptx_path,
                    },
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10
                )
                result["db_saved"] = spring_response.status_code == 200
            except:
                result["db_saved"] = False
        
        return JSONResponse({"status": "success", "data": result})
    
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )
    
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
    """
    Step 4: PPT 스크립트 생성 및 DB 저장
    """
    print(f"[Step 4] 스크립트 생성 요청: {file.filename}, notice_id={notice_id}")
    
    os.makedirs("tmp", exist_ok=True)
    tmp_path = os.path.join("tmp", f"{uuid.uuid4().hex}.pptx")
    
    try:
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)
        
        result = run_script_gen(pptx_path=tmp_path)
        
        if result:
            # Spring Boot로 저장 요청
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
            
            return JSONResponse(
                content={"status": "success", "data": result},
                status_code=200
            )
        else:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": "스크립트 생성 실패"}
            )
    
    except Exception as e:
        print(f"[Step 4] 오류: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )
    
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

# ============================================
# 서버 실행
# ============================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
