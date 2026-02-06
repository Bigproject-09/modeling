# main.py (통합 버전)
import os
import uuid
import requests
import chromadb
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware 
from dotenv import load_dotenv
load_dotenv()

from utils.document_parsing import parse_docx_to_blocks, extract_text_from_pdf

app = FastAPI()

# ============================================
# ChromaDB 클라이언트 초기화 (팀원 추가 부분)
# ============================================
CHROMA_HOST = os.getenv('CHROMA_HOST', 'localhost')
CHROMA_PORT = int(os.getenv('CHROMA_PORT', 8001))

chroma_client = chromadb.HttpClient(
    host=CHROMA_HOST,
    port=CHROMA_PORT
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# ChromaDB 관련 엔드포인트 (팀원 추가 부분)
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
# 기존 기능들
# ============================================

# 파일 파싱 (DB 저장은 Spring에서)
@app.post("/parse")
async def parse_notice(file: UploadFile = File(...)):
    """
    파일 파싱만 수행 (DB 저장은 Spring Boot에서 처리)
    """
    print(f"🔥 PARSE CALLED: {file.filename}")

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

        print(f"✅ PARSE SUCCESS: {file.filename}")

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


# 헬스체크
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "FastAPI is running"}


# 파싱 지원 형식 조회
@app.get("/parse/formats")
def supported_formats():
    """지원하는 파일 형식 조회"""
    return {
        "supported_formats": [".pdf", ".docx"],
        "max_file_size_mb": 50
    }


# ============================================
# RFP 검색 (수정된 버전)
# ============================================
from pydantic import BaseModel
from features.rnd_search.main_search import main as run_search
from features.ppt_script.main_script import main as run_script_gen

@app.post("/api/analyze/step2")
async def api_run_step2(
    file: UploadFile = File(...),
    notice_id: int = Form(None)
):
    print(f"[Step 2] 유관 RFP 검색 요청")
    print(f"  - 파일: {file.filename}")
    print(f"  - notice_id: {notice_id}")
    
    os.makedirs("tmp", exist_ok=True)
    ext = os.path.splitext(file.filename)[1].lower()
    tmp_path = os.path.join("tmp", f"{uuid.uuid4().hex}{ext}")
    
    try:
        # 1. 파일 저장
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)
        
        # 2. 파일 파싱
        parsed_text = ""
        
        if ext == ".pdf":
            pages = extract_text_from_pdf(tmp_path)
            # ✅ 수정: pages가 리스트면 문자열로 변환
            if isinstance(pages, list):
                parsed_text = "\n".join(str(p) for p in pages)
            else:
                parsed_text = str(pages)
            print(f"  ✅ PDF 파싱 완료: {len(parsed_text)} 글자")
            
        elif ext == ".docx":
            blocks = parse_docx_to_blocks(tmp_path, "tmp")
            # ✅ 수정: blocks가 dict나 list면 적절히 처리
            if isinstance(blocks, list):
                # 리스트의 각 항목을 문자열로 변환
                parsed_text = "\n".join(
                    str(b.get('text', '') if isinstance(b, dict) else b) 
                    for b in blocks
                )
            elif isinstance(blocks, dict):
                # dict면 'content' 키를 찾아서 사용
                parsed_text = str(blocks.get('content', str(blocks)))
            else:
                parsed_text = str(blocks)
            print(f"  ✅ DOCX 파싱 완료: {len(parsed_text)} 글자")
            
        else:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": f"지원하지 않는 파일 형식: {ext}"}
            )
        
        # 3. 검색 실행
        result = run_search(
            notice_id=notice_id,
            notice_text=parsed_text
        )
        
        print(f"  ✅ 검색 완료")
        
        return JSONResponse(
            content={"status": "success", "data": result},
            status_code=200
        )
    
    except Exception as e:
        import traceback
        print(f"  ❌ 오류: {str(e)}")
        print(traceback.format_exc())  # ← 전체 에러 스택 출력
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )
    
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ============================================
# PPT 스크립트 생성
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)