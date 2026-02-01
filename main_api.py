import os
import shutil
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 우리가 정리한 모듈들 불러오기
from modules.step1_analysis import main as run_step1
from modules.step2_search import main as run_step2
from modules.step4_script import main as run_step4 

app = FastAPI(title="R&D Agent API", description="공고 분석부터 대본 생성까지")

# [CORS 설정] React(3000번 포트)에서 접속 허용
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 기본 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
NOTICE_INPUT_DIR = os.path.join(DATA_DIR, "notice_input")
PPT_INPUT_DIR = os.path.join(DATA_DIR, "script_input")
REPORT_DIR = os.path.join(DATA_DIR, "report")
ANALYSIS_DIR = os.path.join(DATA_DIR, "analysis")

# 폴더 자동 생성
for d in [NOTICE_INPUT_DIR, PPT_INPUT_DIR, REPORT_DIR, ANALYSIS_DIR]:
    os.makedirs(d, exist_ok=True)

# =================================================================
# 1. 파일 업로드 API (공고 PDF)
# =================================================================
@app.post("/upload/notice")
async def upload_notice(file: UploadFile = File(...)):
    try:
        file_path = os.path.join(NOTICE_INPUT_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {"message": f"파일 업로드 성공: {file.filename}", "path": file_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"업로드 실패: {str(e)}")

# =================================================================
# 2. [1단계] 공고 분석 API
# =================================================================
@app.post("/analyze")
async def api_analyze_notice():
    """
    저장된 공고 PDF를 분석하여 결과 JSON을 반환합니다.
    """
    try:
        print("[API] 1단계 분석 시작...")
        # 기존 모듈 실행
        run_step1()
        
        # 결과 파일 읽어서 반환
        result_path = os.path.join(ANALYSIS_DIR, "analysis_result.json")
        if os.path.exists(result_path):
            with open(result_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            return {"message": "분석은 완료되었으나 결과 파일이 없습니다."}
            
    except Exception as e:
        print(f"[API 오류] {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =================================================================
# 3. [2단계] 유사 과제 검색 API
# =================================================================
@app.post("/search")
async def api_search_projects():
    """
    분석된 내용을 바탕으로 유사 과제를 검색하고 리포트를 반환합니다.
    """
    try:
        print("[API] 2단계 검색 시작...")
        run_step2()
        
        # 결과 파일 읽어서 반환
        result_path = os.path.join(REPORT_DIR, "final_result.json")
        if os.path.exists(result_path):
            with open(result_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            return {"message": "검색은 완료되었으나 결과 파일이 없습니다."}
            
    except Exception as e:
        print(f"[API 오류] {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =================================================================
# 4. [4단계] 대본 생성 API (PPT 업로드 포함)
# =================================================================
@app.post("/script")
async def api_generate_script(file: UploadFile = File(...)):
    """
    PPT 파일을 업로드받아 바로 대본을 생성합니다.
    """
    try:
        # 1. PPT 저장
        ppt_path = os.path.join(PPT_INPUT_DIR, "ppt_ex.pptx") # 파일명을 고정하거나 동적으로 처리 가능
        with open(ppt_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        print(f"[API] 4단계 대본 생성 시작 (파일: {file.filename})...")
        
        # 2. 대본 생성 모듈 실행 (비동기 함수 호출)
        run_step4()
        
        # 3. 결과 반환
        result_path = os.path.join(REPORT_DIR, "script_flow.json")
        if os.path.exists(result_path):
            with open(result_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            return {"message": "생성은 완료되었으나 결과 파일이 없습니다."}

    except Exception as e:
        print(f"[API 오류] {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =================================================================
# 서버 실행 안내
# =================================================================
if __name__ == "__main__":
    import uvicorn
    print("FastAPI 서버를 시작합니다: http://127.0.0.1:8000")
    print("Swagger 문서 확인: http://127.0.0.1:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)