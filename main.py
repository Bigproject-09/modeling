# main.py
import os
import uuid
import json
from fastapi import FastAPI, UploadFile, File, Query
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import tempfile

load_dotenv()

from document_api import ingest_to_db, API_KEY
from parsing import parse_file_to_json

# 섹션 모드용 유틸 (이미 프로젝트에 있는 걸 사용)
from utils.document_parsing import parse_docx_to_blocks, extract_text_from_pdf
from utils.section import SectionSplitter

app = FastAPI()


# =========================
# 기업마당 공고 수집
# =========================
@app.post("/collect/notices")
def collect_notices():
    """
    기업마당 기술공고 수집
    - document_api.ingest_to_db() 호출
    - project_notices, notice_files, notice_hashtags 테이블에 저장
    """
    print("🔥 COLLECT CALLED")
    inserted = ingest_to_db(API_KEY)
    print(f"🔥 COLLECT DONE: {inserted}건 수집")
    return {"inserted": inserted}


# =========================
# 파일 파싱 (DB 저장은 Spring에서 + mode 옵션 추가)
# =========================
@app.post("/parse")
async def parse_notice(file: UploadFile = File(...),
                       mode: str = Query(default="notice", description="notice|sections")):
    """
    파일 파싱만 수행 (DB 저장은 Spring Boot에서 처리)
    
    mode=notice (기본): 기존 공고 파싱 그대로 parse_file_to_json() 결과 반환
    mode=sections        : 사업보고서 섹션 리스트(list[dict]) 반환

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
        # 1) 임시 저장
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)

        # 2) mode에 따라 파싱
        if mode == "notice":
            parsed = parse_file_to_json(tmp_path)
            print(f"PARSE SUCCESS (notice): {file.filename}")
            return JSONResponse(content=parsed, status_code=200)

        elif mode == "sections":
            sections = _parse_to_sections(tmp_path, ext)
            print(f"PARSE SUCCESS (sections): {file.filename} / sections={len(sections)}")
            return JSONResponse(content=sections, status_code=200)

        else:
            return JSONResponse(
                status_code=400,
                content={"error": f"invalid mode: {mode} (allowed: notice|sections)"}
            )

    except Exception as e:
        print(f"❌ PARSE FAILED: {file.filename} - {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def _parse_to_sections(path: str, ext: str) -> list[dict]:
    """
    parse_file_to_json() 결과를 SectionSplitter가 기대하는
    [ {page_index:int, texts:list[str]}, ... ] 형태로 정규화한 뒤,
    목차 기반 섹션 분리 결과를 list[dict]로 반환
    """
    # 1) 기존 파서로 JSON 만들기
    parsed_json = parse_file_to_json(path)

    # 2) SectionSplitter 입력 포맷으로 정규화
    pages = _normalize_parsed_json_for_splitter(parsed_json)

    # 3) 임시 json 파일 생성 (SectionSplitter는 json_path를 받음)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tf:
        json.dump(pages, tf, ensure_ascii=False)
        tmp_json_path = tf.name

    try:
        splitter = SectionSplitter(json_path=tmp_json_path)

        # section.py 기준: split_into_sections()가 정답
        sections = splitter.split_into_sections()

        # dataclass -> dict 정규화
        normalized = []
        for s in sections:
            if isinstance(s, dict):
                normalized.append(s)
            elif hasattr(s, "to_dict"):
                normalized.append(s.to_dict())
            else:
                normalized.append(s.__dict__)
        return normalized

    finally:
        if tmp_json_path and os.path.exists(tmp_json_path):
            os.remove(tmp_json_path)

def _normalize_parsed_json_for_splitter(parsed_json) -> list[dict]:
    """
    parse_file_to_json()의 출력이 무엇이든,
    SectionSplitter가 요구하는 list[dict(page_index, texts)]로 맞춘다.
    """
    # 케이스1) 이미 list라면 그대로 후보
    data = parsed_json

    # 케이스2) dict라면 흔한 키들에서 pages를 꺼내기
    if isinstance(parsed_json, dict):
        for k in ["pages", "page_list", "data", "results"]:
            if k in parsed_json and isinstance(parsed_json[k], list):
                data = parsed_json[k]
                break

    # 그래도 list가 아니면 실패
    if not isinstance(data, list):
        raise RuntimeError(f"parse_file_to_json 결과가 list가 아님. type={type(parsed_json)} keys={list(parsed_json.keys()) if isinstance(parsed_json, dict) else None}")

    normalized_pages: list[dict] = []
    for i, p in enumerate(data):
        # p가 dict가 아니면 텍스트로 취급
        if not isinstance(p, dict):
            normalized_pages.append({"page_index": i, "texts": [str(p)]})
            continue

        # page index 후보들
        page_index = (
            p.get("page_index")
            if p.get("page_index") is not None else
            p.get("page")
            if p.get("page") is not None else
            p.get("page_no")
            if p.get("page_no") is not None else
            p.get("pageNumber")
            if p.get("pageNumber") is not None else
            i
        )

        # texts 후보들
        texts = None

        if isinstance(p.get("texts"), list):
            texts = p["texts"]

        elif isinstance(p.get("contents"), list):
            texts = [str(x) for x in p["contents"] if str(x).strip()]

        elif isinstance(p.get("text"), str):
            # 한 덩어리 텍스트면 줄 단위로 쪼개서 list로
            texts = [line for line in p["text"].splitlines() if line.strip()]

        elif isinstance(p.get("lines"), list):
            texts = [str(x) for x in p["lines"] if str(x).strip()]

        elif isinstance(p.get("blocks"), list):
            # blocks = [{"text": "..."}...] 같은 형태 대응
            tmp = []
            for b in p["blocks"]:
                if isinstance(b, dict) and b.get("text"):
                    tmp.append(str(b["text"]))
                elif isinstance(b, str):
                    tmp.append(b)
            texts = [t for t in tmp if t.strip()]

        elif isinstance(p.get("content"), list):
            texts = [str(x) for x in p["content"] if str(x).strip()]

        else:
            # 최후: dict 전체를 문자열로
            texts = [json.dumps(p, ensure_ascii=False)]

        normalized_pages.append({
            "page_index": int(page_index) if str(page_index).isdigit() else i,
            "texts": texts
        })

    return normalized_pages

# =========================
# 헬스체크
# =========================
@app.get("/health")
def health_check():
    return {"status": "ok", "message": "FastAPI is running"}

# =========================
# 파싱 상태 조회 (선택사항)
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

# ===== 분석 API =====
from pydantic import BaseModel

class Step1Request(BaseModel):
    notice_id: int
    company_id: int = 1

@app.post("/api/analyze/step1")
def api_run_step1(req: Step1Request):
    from features.rfp_analysis_checklist.main_notice import run_notice_step1
    print("RAW REQ:", req.model_dump())
    print(f"[Step 1] 분석 요청: notice_id={req.notice_id}, company_id={req.company_id}")
    result = run_notice_step1(notice_id=req.notice_id, company_id=req.company_id)
    return {"status": "success", "data": result}

class NoticeOnlyRequest(BaseModel):
    notice_id: int

@app.post("/api/analyze/step2")
def api_run_step2(req: NoticeOnlyRequest):
    from features.rnd_search.main_search import main as run_search
    print(f"[Step 2] 유사 RFP 검색 요청: notice_id={req.notice_id}")
    result = run_search(notice_id=req.notice_id)
    return {"status": "success", "data": result}

@app.post("/api/analyze/step3")
def api_run_step3(req: NoticeOnlyRequest):
    # Step3는 호출될 때만 import → nodes_code 없어도 Step1 서버는 뜸
    from features.ppt_maker.main_ppt import main as run_ppt_maker
    print(f"[Step 3] PPT 생성 요청: notice_id={req.notice_id}")
    try:
        result = run_ppt_maker(notice_id=req.notice_id)
    except TypeError:
        result = run_ppt_maker()
    return {"status": "success", "data": result}

@app.post("/api/analyze/step4")
def api_run_step4(req: NoticeOnlyRequest):
    from features.ppt_script.main_script import main as run_script_gen
    print(f"[Step 4] 대본 생성 요청: notice_id={req.notice_id}")
    try:
        result = run_script_gen(notice_id=req.notice_id)
    except TypeError:
        result = run_script_gen()
    return {"status": "success", "data": result}

if __name__ == "__main__":
    import uvicorn
    # host="0.0.0.0"은 외부 접속 허용, reload=True는 코드 수정 시 자동 재시작
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)