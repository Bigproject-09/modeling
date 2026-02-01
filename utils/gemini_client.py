import os
import json
import logging
import google.generativeai as genai
from pathlib import Path
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========================================================
# [설정] .env 파일 로드 (경로 안전장치 포함)
# ========================================================
def load_api_key_robust():
    current_dir = Path(__file__).resolve().parent
    env_path = current_dir.parent / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        return os.getenv("GEMINI_API_KEY")
    load_dotenv()
    return os.getenv("GEMINI_API_KEY")

api_key = load_api_key_robust()

if not api_key:
    logger.error("[오류] .env 파일에서 'GEMINI_API_KEY'를 찾을 수 없습니다.")
else:
    genai.configure(api_key=api_key)

# ========================================================
# [내부 유틸] 청크 리스트를 하나의 텍스트로 합치기
# ========================================================
def _chunks_to_text(chunks):
    full_text = ""
    if isinstance(chunks, list):
        for chunk in chunks:
            # step1에서 만든 chunk는 딕셔너리일 수도, 문자열일 수도 있음
            if isinstance(chunk, dict) and "text" in chunk:
                full_text += chunk["text"] + "\n\n"
            else:
                full_text += str(chunk) + "\n\n"
    else:
        full_text = str(chunks)
    
    # 토큰 제한 고려 (약 5만 자)
    return full_text[:50000]

# ============================================================================
# [기능 1] 자격 요건 체크리스트 (Step 1 호출 대응)
# ============================================================================
def eligibility_checklist(chunks, source="") -> str:
    """
    Step 1에서 eligibility_checklist(chunks=..., source=...) 형태로 호출함.
    반환값: Markdown String
    """
    if not api_key: return "Error: No API Key"
    
    model = genai.GenerativeModel('gemini-1.5-flash')
    input_text = _chunks_to_text(chunks)
    
    # Step 1 코드에서 company_info를 인자로 안 넘겨주므로, 여기서 직접 읽어와야 함
    company_info_str = "정보 없음"
    try:
        current_dir = Path(__file__).resolve().parent
        company_path = current_dir.parent / "data" / "company" / "company_info.json"
        if company_path.exists():
            with open(company_path, "r", encoding="utf-8") as f:
                company_info_str = f.read()
    except:
        pass

    prompt = f"""
    당신은 R&D 과제 관리 전문가입니다.
    제공된 문서({source})에서 **지원 자격(Eligibility)**과 **필수 요건**을 추출하여 체크리스트를 만들어주세요.

    [우리 회사 정보]
    {company_info_str}

    [작성 형식: Markdown]
    # 지원 자격 체크리스트 ({source})

    | 구분 | 필수 요건 내용 | 우리 회사 현황 | 충족 여부 (O/X/?) | 비고 |
    |---|---|---|---|---|
    | (예: 기업형태) | (예: 중소기업만 가능) | ... | ... | ... |
    
    ## 💡 보완 필요 사항 및 조언
    - (충족되지 않은 항목이나 확인이 필요한 사항에 대해 조언)

    [문서 내용]
    {input_text}
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"# 체크리스트 생성 실패\n오류가 발생했습니다: {str(e)}"


# ============================================================================
# [기능 2] 공고문 심층 분석 (Step 1 호출 대응)
# ============================================================================
def deep_analysis(chunks, source="") -> str:
    """
    Step 1에서 deep_analysis(chunks=..., source=...) 형태로 호출함.
    반환값: Markdown String
    """
    if not api_key: return "Error: No API Key"
    
    model = genai.GenerativeModel('gemini-1.5-flash')
    input_text = _chunks_to_text(chunks)

    prompt = f"""
    당신은 정부 R&D 과제 분석 전문가입니다.
    제공된 문서({source})를 바탕으로 **심층 분석 보고서**를 작성해 주세요.

    [작성 형식: Markdown]
    
    # 심층 분석 결과: {source}

    ## 1. 과제 개요
    - **사업명/과제명**: 
    - **최종 목표**: (명확하게 1문장)
    - **핵심 요약**: (3줄 이내)
    
    ## 2. 주요 지원 내용
    - **기간**: 
    - **예산(지원금)**:
    - **지원 대상**:
    
    ## 3. 핵심 요구사항 (RFP 분석)
    - (RFP나 공고에 명시된 기술적/행정적 요구사항을 상세히 기술)
    
    ## 4. 전략적 제언
    - (선정 확률을 높이기 위한 전략)

    [문서 내용]
    {input_text}
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"# 분석 실패\n오류가 발생했습니다: {str(e)}"


# ============================================================================
# [기능 3] 유사 과제 검색 요약 (Step 2용 - 기존 유지)
# ============================================================================
def summarize_report(json_data: dict) -> str:
    if not api_key: return "Error: No API Key"
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        track_a = json_data.get("track_a_same_ministry", [])
        track_b = json_data.get("track_b_diff_ministry", [])
        author = json_data.get("input_meta", {}).get("author", "미상")

        prompt = f"""
        당신은 정부 R&D 과제 기획 전문가입니다. 
        신규 공고(소관: {author})와 유사한 과거 과제들을 분석하여 **핵심 요약 보고서**를 작성하세요.

        [Track A: 중복성 검토 (동일 부처)]
        {json.dumps(track_a, ensure_ascii=False)}

        [Track B: 벤치마킹 (타 부처)]
        {json.dumps(track_b, ensure_ascii=False)}

        [작성 지침]
        1. Markdown 표 형식으로 작성: | 연도 | 부처 | 과제명 | 유사도 | 핵심 요약(30자) |
        2. 종합 의견 3줄 작성.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"[오류] {str(e)}"


# ============================================================================
# [기능 4] 대본 생성 (Step 4용 - 기존 유지)
# ============================================================================
def generate_script_and_qna(ppt_text: str) -> dict:
    if not api_key: return None
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        prompt = f"""
        R&D 과제 발표를 위한 대본과 Q&A를 JSON으로 생성해.
        [JSON 구조] {{ "slides": [{{ "page": 1, "script": "..." }}], "qna": [...] }}
        [PPT 내용] {ppt_text}
        """
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"): text = text.split("```json")[1].split("```")[0].strip()
        elif text.startswith("json"): text = text.replace("json", "", 1).strip()
        return json.loads(text)
    except Exception as e:
        logger.error(f"[오류] 대본 생성 실패: {e}")
        return None