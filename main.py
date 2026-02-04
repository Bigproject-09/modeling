# main.py
import os
import uuid
import json
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from dotenv import load_dotenv
load_dotenv()
from parsing import parse_file_to_json
from features.gamma_ppt.pipeline import generate_gamma_pptx
from features.gamma_ppt.gamma_client import get_generation, choose_pptx_url
from pydantic import BaseModel
from features.rnd_search.main_search import main as run_search
from features.ppt_script.main_script import main as run_script_gen

app = FastAPI()


# =========================
# 기업마당 공고 수집
# =========================
@app.post("/collect/notices")
def collect_notices():
    """
    ?????? ?????? ???
    - document_api.ingest_to_db() ???
    - project_notices, notice_files, notice_hashtags ?????? ????
    """
    try:
        from document_api import ingest_to_db, API_KEY
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"document_api import failed: {e}"})

    print("?? COLLECT CALLED")
    inserted = ingest_to_db(API_KEY)
    print(f"?? COLLECT DONE: {inserted}?????")
    return {"inserted": inserted}


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
        parsed = parse_file_to_json(tmp_path)

        print(f"✅ PARSE SUCCESS: {file.filename}")

        # 3️⃣ 파싱 결과만 반환 (DB 저장은 Spring에서)
        return JSONResponse(
            content=parsed,
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


# --- Helpers ---
def _parse_bool(value, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "on"}:
        return True
    if text in {"false", "0", "no", "n", "off"}:
        return False
    return default


def _parse_folder_ids(raw: str):
    if not raw:
        return None
    text = raw.strip()
    if text.lower() in {"string", "null", "none"}:
        return None
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass
    items = [part.strip() for part in text.split(",") if part.strip()]
    return items if items else None


def _normalize_optional_str(value: str):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"string", "null", "none"}:
        return None
    return text

def _parse_env_folder_ids():
    raw = os.environ.get("GAMMA_FOLDER_IDS")
    return _parse_folder_ids(raw)


# --- [도현님 추가] API 엔드포인트 ---
class AnalyzeRequest(BaseModel):
    notice_id: int

@app.post("/api/analyze/step2")
def api_run_step2(req: AnalyzeRequest):
    print(f"[Step 2] 분석 요청: notice_id={req.notice_id}")
    result = run_search(notice_id=req.notice_id)
    return {"status": "success", "data": result}

@app.post("/api/analyze/step4")
def api_run_step4():
    print("[Step 4] 대본 생성 요청")
    run_script_gen()
    return {"status": "success", "message": "대본 생성 완료"}


@app.post("/api/ppt/gamma")
async def api_generate_gamma_ppt(
    file: UploadFile = File(...),
    wait: str = Form("true", description="Wait for completion and return PPTX.", example="true"),
    num_cards: Optional[int] = Form(None, description="Leave empty for auto (16-28).", example=18),
    card_split: str = Form("inputTextBreaks", description="inputTextBreaks or auto.", example="inputTextBreaks"),
    theme_id: str = Form(None, description="Gamma themeId. Leave empty to use default.", example=""),
    folder_ids: str = Form(None, description="Comma-separated folderIds or JSON array.", example=""),
    additional_instructions: str = Form(None, description="Extra instructions for Gamma.", example=""),
    image_source: str = Form("aiGenerated", description="aiGenerated | placeholder | pexels | etc.", example="aiGenerated"),
    mode: str = Form("generate", description="generate or template.", example="generate"),
    template_id: str = Form(None, description="Gamma templateId (for template mode).", example=""),
    fallback: str = Form("true", description="Allow fallback when template fails.", example="true"),
    template_strict: str = Form("false", description="If true, template failures error.", example="false"),
    condense_auto: str = Form("false", description="Auto reduce summary length to save cost/time.", example="false"),
    overflow_report: str = Form("false", description="Generate overflow report for PPTX.", example="false"),
):
    if not file.filename.lower().endswith(".pdf"):
        return JSONResponse(status_code=400, content={"error": "Only PDF files are supported."})

    os.makedirs("tmp", exist_ok=True)
    ext = os.path.splitext(file.filename)[1].lower()
    tmp_path = os.path.join("tmp", f"{uuid.uuid4().hex}{ext}")

    try:
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)

        wait_flag = _parse_bool(wait, default=True)
        fallback_flag = _parse_bool(fallback, default=True)
        template_strict_flag = _parse_bool(template_strict, default=False)
        condense_auto_flag = _parse_bool(condense_auto, default=False)
        overflow_report_flag = _parse_bool(overflow_report, default=False)
        card_split = card_split if card_split in {"inputTextBreaks", "auto"} else "inputTextBreaks"
        mode = mode if mode in {"generate", "template"} else "generate"

        folder_list = _parse_folder_ids(folder_ids)
        if folder_list is None:
            folder_list = _parse_env_folder_ids()

        theme_id_norm = _normalize_optional_str(theme_id)
        theme_id_from_request = theme_id_norm is not None
        if theme_id_norm is None:
            theme_id_norm = os.environ.get("GAMMA_THEME_ID")

        template_id_norm = _normalize_optional_str(template_id)
        if template_id_norm is None:
            template_id_norm = os.environ.get("GAMMA_TEMPLATE_ID")

        result = generate_gamma_pptx(
            pdf_path=tmp_path,
            wait=wait_flag,
            num_cards=num_cards,
            card_split=card_split,
            theme_id=theme_id_norm,
            theme_id_from_request=theme_id_from_request,
            folder_ids=folder_list,
            additional_instructions=additional_instructions,
            image_source=image_source or "placeholder",
            mode=mode,
            template_id=template_id_norm,
            fallback=fallback_flag,
            template_strict=template_strict_flag,
            condense_auto=condense_auto_flag,
            overflow_report=overflow_report_flag,
        )

        if wait_flag and result.get("status") == "completed" and result.get("pptxPath"):
            pptx_path = result["pptxPath"]
            filename = os.path.basename(pptx_path)
            headers = {}
            warnings = result.get("warnings") or []
            if warnings:
                headers["X-Gamma-Warnings"] = " | ".join(warnings)
            if result.get("modeUsed"):
                headers["X-Gamma-Mode"] = result.get("modeUsed")
            overflow_path = result.get("overflowReportPath")
            overflow_summary = (result.get("overflowReport") or {}).get("summary", {})
            if overflow_path:
                headers["X-Gamma-Overflow-Report"] = os.path.basename(overflow_path)
                overflow_shapes = overflow_summary.get("overflowShapes") if isinstance(overflow_summary, dict) else 0
                small_fonts = overflow_summary.get("slidesWithSmallFont") if isinstance(overflow_summary, dict) else 0
                if overflow_shapes or small_fonts:
                    headers["X-Gamma-Overflow"] = "true"
            return FileResponse(
                pptx_path,
                media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                filename=filename,
                headers=headers,
            )

        return JSONResponse(content=result, status_code=200)

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.get("/api/ppt/gamma/{generation_id}")
def api_gamma_status(generation_id: str):
    try:
        api_key = os.environ.get("GAMMA_API_KEY")
        if not api_key:
            return JSONResponse(status_code=500, content={"error": "GAMMA_API_KEY is not set."})

        data = get_generation(api_key, generation_id)
        pptx_url, warnings = choose_pptx_url(data)
        return {
            "status": data.get("status"),
            "generationId": generation_id,
            "gammaUrl": data.get("gammaUrl"),
            "pptxUrl": pptx_url,
            "warnings": warnings,
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    import uvicorn
    # host="0.0.0.0"은 외부 접속 허용, reload=True는 코드 수정 시 자동 재시작
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
