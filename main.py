# main.py
import os
import uuid
import requests
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware 
from dotenv import load_dotenv
load_dotenv()

from utils.document_parsing import parse_docx_to_blocks, extract_text_from_pdf

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# 파일 파싱 (DB 저장은 Spring에서)
# =========================
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
    print(f"🔥 PARSE CALLED: {file.filename}")

    os.makedirs("tmp", exist_ok=True)
    ext = os.path.splitext(file.filename)[1].lower()
    tmp_path = os.path.join("tmp", f"{uuid.uuid4().hex}{ext}")

    try:
        # 1️⃣ 파일 임시 저장
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)

        # 2️⃣ 파싱
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

        # 3️⃣ 파싱 결과만 반환 (DB 저장은 Spring에서)
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
        # 임시 파일 삭제
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# =========================
# 헬스체크
# =========================
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "FastAPI is running"}


# =========================
# 파싱 지원 형식 조회
# =========================
@app.get("/parse/formats")
def supported_formats():
    """
    지원하는 파일 형식 조회
    """
    return {
        "supported_formats": [".pdf", ".docx"],
        "max_file_size_mb": 50
    }


# =========================
# 도현님 추가 엔드포인트
# =========================
from pydantic import BaseModel
from features.rnd_search.main_search import main as run_search
from features.ppt_script.main_script import main as run_script_gen

class AnalyzeRequest(BaseModel):
    notice_id: int

@app.post("/api/analyze/step2")
def api_run_step2(req: AnalyzeRequest):
    print(f"[Step 2] 분석 요청: notice_id={req.notice_id}")
    result = run_search(notice_id=req.notice_id)
    return {"status": "success", "data": result}

@app.post("/api/analyze/step4")
async def api_run_step4(
    file: UploadFile = File(...),
    notice_id: int = None,  # ✅ notice_id 추가
    token: str = None  # ✅ JWT 토큰 추가
):
    """
    Step 4: PPT 스크립트 생성 및 DB 저장
    - PPT 파일을 받아서 발표 대본 및 Q&A 생성
    - Spring Boot로 결과 전송하여 DB 저장
    """
    print(f"[Step 4] 스크립트 생성 요청: {file.filename}, notice_id={notice_id}")
    
    # 임시 파일 저장
    os.makedirs("tmp", exist_ok=True)
    tmp_path = os.path.join("tmp", f"{uuid.uuid4().hex}.pptx")
    
    try:
        # 파일 저장
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)
        
        # 스크립트 생성
        result = run_script_gen(pptx_path=tmp_path)
        
        if result:
            # ✅ Spring Boot로 저장 요청
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
                    # DB 저장 실패해도 결과는 반환
            
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
        # 임시 파일 삭제
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    import uvicorn
    # host="0.0.0.0"은 외부 접속 허용, reload=True는 코드 수정 시 자동 재시작
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)