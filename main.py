# # main.py
# import os
# import uuid
# from fastapi import FastAPI, UploadFile, File
# from fastapi.responses import JSONResponse
# from dotenv import load_dotenv
# load_dotenv()

# # ✅ 수정: utils/document_parsing.py에서 import
# from utils.document_parsing import parse_docx_to_blocks, extract_text_from_pdf

# app = FastAPI()


# # =========================
# # ❌ 삭제: 공고 수집 엔드포인트 (Spring에서 처리)
# # =========================
# # @app.post("/collect/notices")
# # def collect_notices():
# #     ...


# # =========================
# # 파일 파싱 (DB 저장은 Spring에서)
# # =========================
# @app.post("/parse")
# async def parse_notice(file: UploadFile = File(...)):
#     """
#     파일 파싱만 수행 (DB 저장은 Spring Boot에서 처리)
    
#     Flow:
#     1. Spring Boot: NoticeFile 생성 + NoticeAttachment 생성 (WAIT 상태)
#     2. Spring Boot → FastAPI: 파일 전송
#     3. FastAPI: 파싱 수행 후 결과 JSON 반환 ← 이 함수
#     4. Spring Boot: NoticeAttachment.markDone(parsedJson) 호출
#     """
#     print(f"🔥 PARSE CALLED: {file.filename}")

#     os.makedirs("tmp", exist_ok=True)
#     ext = os.path.splitext(file.filename)[1].lower()
#     tmp_path = os.path.join("tmp", f"{uuid.uuid4().hex}{ext}")

#     try:
#         # 1️⃣ 파일 임시 저장
#         content = await file.read()
#         with open(tmp_path, "wb") as f:
#             f.write(content)

#         # 2️⃣ 파싱
#         if ext == ".pdf":
#             result = {
#                 "file_type": "pdf",
#                 "pages": extract_text_from_pdf(tmp_path)
#             }
#         elif ext == ".docx":
#             result = {
#                 "file_type": "docx",
#                 "content": parse_docx_to_blocks(tmp_path, "tmp")
#             }
#         else:
#             return JSONResponse(
#                 status_code=400,
#                 content={"error": f"Unsupported extension: {ext}"}
#             )

#         print(f"✅ PARSE SUCCESS: {file.filename}")

#         # 3️⃣ 파싱 결과만 반환 (DB 저장은 Spring에서)
#         return JSONResponse(
#             content=result,
#             status_code=200
#         )

#     except Exception as e:
#         print(f"❌ PARSE FAILED: {file.filename} - {str(e)}")
        
#         return JSONResponse(
#             status_code=500,
#             content={"error": str(e)}
#         )

#     finally:
#         # 임시 파일 삭제
#         if os.path.exists(tmp_path):
#             os.remove(tmp_path)


# # =========================
# # 헬스체크
# # =========================
# @app.get("/health")
# def health_check():
#     return {"status": "ok", "message": "FastAPI is running"}


# # =========================
# # 파싱 지원 형식 조회
# # =========================
# @app.get("/parse/formats")
# def supported_formats():
#     """
#     지원하는 파일 형식 조회
#     """
#     return {
#         "supported_formats": [".pdf", ".docx"],
#         "max_file_size_mb": 50
#     }


# # =========================
# # 도현님 추가 엔드포인트
# # =========================
# from pydantic import BaseModel
# from features.rnd_search.main_search import main as run_search
# from features.ppt_script.main_script import main as run_script_gen

# class AnalyzeRequest(BaseModel):
#     notice_id: int

# @app.post("/api/analyze/step2")
# def api_run_step2(req: AnalyzeRequest):
#     print(f"[Step 2] 분석 요청: notice_id={req.notice_id}")
#     result = run_search(notice_id=req.notice_id)
#     return {"status": "success", "data": result}

# @app.post("/api/analyze/step4")
# def api_run_step4():
#     print("[Step 4] 대본 생성 요청")
#     run_script_gen()
#     return {"status": "success", "message": "대본 생성 완료"}


# if __name__ == "__main__":
#     import uvicorn
#     # host="0.0.0.0"은 외부 접속 허용, reload=True는 코드 수정 시 자동 재시작
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import os
import sys

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 모델링 모듈 import
from features.rfp_analysis_checklist.main_notice import main as run_checklist_analysis
from features.rnd_search.main_search import main as run_search
from features.ppt_maker.main_ppt import run_ppt_generation
from features.ppt_script.main_script import main as run_script_gen

from utils.db_lookup import get_notice_info_by_id
from utils.document_parsing import parse_docx_to_blocks, extract_text_from_pdf

app = FastAPI()

class AnalyzeRequest(BaseModel):
    notice_id: int
    company_id: Optional[int] = 1


# =========================================================
# [Step 1] 공고문 분석 (자격요건 체크리스트 + 심층분석)
# =========================================================
@app.post("/api/analyze/step1")
def analyze_notice(req: AnalyzeRequest):
    """
    공고문 분석
    - DB에서 notice_id로 파일 조회
    - 자격요건 체크리스트 생성 (checklist.json)
    - 심층 전략 분석 (analysis.json)
    
    Returns:
        {
            "status": "success",
            "data": {
                "checklist": {...},
                "analysis": {...}
            }
        }
    """
    print(f"[Step 1] 공고문 분석 요청: notice_id={req.notice_id}")
    
    try:
        # 1. DB에서 공고 정보 조회
        notice_info = get_notice_info_by_id(req.notice_id)
        
        if not notice_info:
            raise HTTPException(status_code=404, detail="공고를 찾을 수 없습니다")
        
        # 2. 분석 실행 (임시: 파일 경로는 고정)
        # 실제로는 DB에서 파일 경로 조회 후 처리
        result = run_checklist_analysis()
        
        # 3. 결과 JSON 파일 읽기
        import json
        checklist_path = "data/analysis/checklist.json"
        analysis_path = "data/analysis/analysis.json"
        
        checklist = {}
        analysis = {}
        
        if os.path.exists(checklist_path):
            with open(checklist_path, 'r', encoding='utf-8') as f:
                checklist = json.load(f)
        
        if os.path.exists(analysis_path):
            with open(analysis_path, 'r', encoding='utf-8') as f:
                analysis = json.load(f)
        
        return {
            "status": "success",
            "data": {
                "checklist": checklist,
                "analysis": analysis
            }
        }
        
    except Exception as e:
        print(f"[오류] {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# [Step 2] 유관 RFP 검색 (기존 코드 유지)
# =========================================================
@app.post("/api/analyze/step2")
def search_similar_rfp(req: AnalyzeRequest):
    """
    유관 RFP 검색
    - ChromaDB 벡터 검색
    - LLM 분석 보고서 생성
    
    Returns:
        {
            "status": "success",
            "data": {
                "summary_opinion": "...",
                "track_a_comparison": [...],
                "track_b_comparison": [...],
                "strategies": [...]
            }
        }
    """
    print(f"[Step 2] 유관 RFP 검색: notice_id={req.notice_id}")
    
    try:
        result = run_search(notice_id=req.notice_id)
        
        return {
            "status": "success",
            "data": result
        }
        
    except Exception as e:
        print(f"[오류] {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# [Step 3] PPT 생성
# =========================================================
@app.post("/api/analyze/step3")
def generate_ppt(req: AnalyzeRequest):
    """
    발표 자료 제작 (PPT 생성)
    - LangGraph 워크플로우 실행
    - PPT 파일 생성
    
    Returns:
        {
            "status": "success",
            "data": {
                "ppt_path": "...",
                "slides_count": 15
            }
        }
    """
    print(f"[Step 3] PPT 생성 요청: notice_id={req.notice_id}")
    
    try:
        # 1. DB에서 공고 정보 조회 (RFP 텍스트)
        notice_info = get_notice_info_by_id(req.notice_id)
        
        # 2. PPT 생성 실행
        # rfp_text는 빈 문자열 전달 (main_ppt.py 내부에서 파일 자동 로드)
        final_state = run_ppt_generation(rfp_text="")
        
        if final_state and final_state.get('final_ppt_path'):
            return {
                "status": "success",
                "data": {
                    "ppt_path": final_state['final_ppt_path'],
                    "slides_count": len(final_state.get('slides', []))
                }
            }
        else:
            raise Exception("PPT 생성 실패")
            
    except Exception as e:
        print(f"[오류] {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# [Step 4] 스크립트 생성 (기존 코드 유지)
# =========================================================
@app.post("/api/analyze/step4")
def generate_script():
    """
    스크립트 및 예상질문 생성
    - PPT 파일 읽기
    - 발표 대본 생성
    - 예상 Q&A 생성
    
    Returns:
        {
            "status": "success",
            "message": "대본 생성 완료"
        }
    """
    print("[Step 4] 대본 생성 요청")
    
    try:
        run_script_gen()
        
        return {
            "status": "success",
            "message": "대본 생성 완료"
        }
        
    except Exception as e:
        print(f"[오류] {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================
# 파일 파싱 (기존 코드 유지)
# =========================================================
@app.post("/parse")
async def parse_notice(file: UploadFile = File(...)):
    """
    파일 파싱 (PDF, DOCX)
    """
    import uuid
    
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
            return JSONResponse(
                status_code=400,
                content={"error": f"Unsupported extension: {ext}"}
            )

        return JSONResponse(content=result, status_code=200)

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "FastAPI is running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)