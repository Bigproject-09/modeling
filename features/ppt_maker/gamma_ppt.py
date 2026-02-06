
"""
R&D 제안서 PPT 자동 생성 (단일 API 호출 - 최종 버전)
- 섹션 순서 보장
- PPTX 생성 대기 로직 추가
- 토큰 길이 최적화
"""
import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional
import mysql.connector
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from utils.document_parsing import extract_text_from_pdf
from utils.section import SectionSplitter

load_dotenv()

class Config:
    BASE_DIR = Path(__file__).parent.parent.parent
    
    INPUT_PDF_DIR = BASE_DIR / "data" / "ppt_input"
    OUTPUT_PPTX_DIR = BASE_DIR / "data" / "pptx"
    PARSING_DIR = BASE_DIR / "data" / "parsing"
    SECTION_DIR = BASE_DIR / "data" / "sections"
    TEMP_DIR = BASE_DIR / "data" / "temp"
    
    GAMMA_API_KEY = os.getenv("GAMMA_API_KEY")
    GAMMA_API_BASE = "https://public-api.gamma.app/v1.0"
    
    DB_CONFIG = {
        "host": os.getenv("DB_HOST"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME"),
    }
    
    ANNOUNCEMENT_TITLE = "고해상도 해양-빙권 결합모델 개발"
    DEFAULT_COMPANY_ID = 1
    
    SECTION_TITLE_MAPPING = {
        "연구 개요": ["연구개발의 개요"],
        "연구 필요성": ["연구개발 대상의 국내외 현황", "연구개발의 중요성"],
        "연구 목표": ["연구개발의 최종 목표", "연구개발과제의 단계별 목표"],
        "연구 내용": ["연구개발과제의 내용", "연구개발과제 수행일정 및 주요 결과물"],
        "추진 계획": ["연구개발 추진전략", "연구개발 수행방법", "연구개발 추진일정"],
        "기대성과 및 활용방안": ["연구개발성과의 활용방안", "기대효과"]
    }
    
    # 섹션별 최대 글자 수 제한
    SECTION_MAX_CHARS = {
        "연구 개요": 3000,
        "연구 필요성": 5000,
        "연구 목표": 4000,
        "연구 내용": 10000,
        "추진 계획": 8000,
        "기대성과 및 활용방안": 5000
    }

    def __init__(self):
        for d in [self.OUTPUT_PPTX_DIR, self.PARSING_DIR, self.SECTION_DIR, self.TEMP_DIR]:
            d.mkdir(parents=True, exist_ok=True)

config = Config()

def get_db_connection():
    try:
        return mysql.connector.connect(**Config.DB_CONFIG)
    except Exception as e:
        print(f"DB 연결 실패: {e}")
        return None

def fetch_company_info(company_id: int = Config.DEFAULT_COMPANY_ID) -> Dict:
    conn = get_db_connection()
    if not conn:
        return {"company_name": "테스트 연구소", "business_report": {}}
    
    cursor = conn.cursor(dictionary=True)
    try:
        query = "SELECT company_name, business_report_sections FROM companies WHERE company_id = %s"
        cursor.execute(query, (company_id,))
        result = cursor.fetchone()
        
        if not result:
            raise ValueError(f"Company ID {company_id} not found")
        
        business_report = json.loads(result["business_report_sections"]) if result.get("business_report_sections") else {}
        return {"company_name": result["company_name"], "business_report": business_report}
    except Exception as e:
        print(f"기관 정보 조회 실패: {e}")
        return {"company_name": "테스트 연구소", "business_report": {}}
    finally:
        cursor.close()
        conn.close()

def parse_and_section_pdf(pdf_path: Path) -> str:
    print(f"1단계: PDF 파싱 중...")
    
    parsed_data = extract_text_from_pdf(str(pdf_path))
    parsing_json_path = config.PARSING_DIR / f"{pdf_path.stem}_parsing.json"
    with open(parsing_json_path, "w", encoding="utf-8") as f:
        json.dump(parsed_data, f, ensure_ascii=False, indent=2)
    print(f"  파싱 완료: {parsing_json_path}")
    
    print(f"2단계: 섹션 분리 중...")
    splitter = SectionSplitter(str(parsing_json_path))
    section_json_path = config.SECTION_DIR / f"{pdf_path.stem}_sections.json"
    sections = splitter.save_sections(str(section_json_path), format='json')
    print(f"  섹션화 완료: {section_json_path}")
    print(f"  총 {len(sections)}개 섹션")
    
    return str(section_json_path)

def find_section_content(section_json_path: str, target_titles: List[str]) -> str:
    with open(section_json_path, 'r', encoding='utf-8') as f:
        sections = json.load(f)
    
    contents = []
    for section in sections:
        title = section.get("title", "").strip()
        content_list = section.get("content", [])
        
        if not content_list:
            continue
        
        for target in target_titles:
            if target in title:
                content_text = "\n".join(content_list)
                if len(content_text.strip()) > 100:
                    contents.append(content_text)
                    print(f"  매칭: '{title}' ({len(content_text)}자)")
                break
    
    return "\n\n".join(contents)

def truncate_content(content: str, max_chars: int) -> str:
    """내용을 최대 글자 수로 자르기 (문장 단위로)"""
    if len(content) <= max_chars:
        return content
    
    # 문장 단위로 자르기
    sentences = content.split('.')
    truncated = ""
    for sentence in sentences:
        if len(truncated) + len(sentence) + 1 <= max_chars:
            truncated += sentence + "."
        else:
            break
    
    return truncated + "...(내용 계속)"

def build_unified_prompt(
    announcement_title: str,
    company_info: Dict,
    section_contents: Dict[str, str]
) -> tuple[str, str]:
    """
    모든 섹션을 하나의 통합 프롬프트로 구성 (순서 보장)
    """
    company_name = company_info["company_name"]
    business_report = company_info["business_report"]
    
    # 기관 정보 간소화
    report_summary = f"{company_name}의 주요 사업 분야 및 역량"
    
    if business_report:
        if isinstance(business_report, dict):
            report_summary += ": " + ", ".join(list(business_report.keys())[:5])
        elif isinstance(business_report, list):
            report_summary += ": " + ", ".join([str(item)[:50] for item in business_report[:3]])
        else:
            report_summary += ": " + str(business_report)[:200]
    
    # 입력 텍스트 구성 (섹션 구분자 추가로 순서 보장)
    input_text_parts = []
    
    # 1. 표지
    input_text_parts.append(f"# {announcement_title}\n\n연구개발 제안서")
    
    # 섹션 구분자
    input_text_parts.append("\n---\n")
    
    # 2. 기관 소개
    input_text_parts.append(f"# 수행 기관 소개\n\n## {company_name}\n\n{report_summary}")
    
    # 3. 각 섹션 내용 추가 (순서대로, 구분자로 분리)
    section_order = ["연구 개요", "연구 필요성", "연구 목표", "연구 내용", "추진 계획", "기대성과 및 활용방안"]
    
    for section_name in section_order:
        content = section_contents.get(section_name, "")
        if content:
            input_text_parts.append("\n---\n")
            max_chars = config.SECTION_MAX_CHARS.get(section_name, 5000)
            truncated_content = truncate_content(content, max_chars)
            input_text_parts.append(f"# {section_name}\n\n{truncated_content}")
    
    input_text = "".join(input_text_parts)
    
    # 간소화된 추가 지시사항
    additional_instructions = """프레젠테이션 규칙:
- 모든 슬라이드 16:9 비율
- 섹션 표지 없이 바로 내용 시작
- 각 섹션: 상단 왼쪽 작은 태그 박스(섹션명) + 아래 큰 대제목
- 슬라이드당 불릿 5개 이하, 간결하게
- 내용이 많으면 여러 슬라이드로 분할
- 명사 위주 개조식
- 전문적이고 깔끔한 레이아웃
- 이미지는 작은 다이어그램/차트/아이콘만 사용

섹션별 시각화:
- 연구 개요: 시스템 프레임워크 다이어그램
- 연구 필요성: Gap Analysis 인포그래픽
- 연구 목표: KPI 대시보드
- 연구 내용: 계층 구조 다이어그램
- 추진 계획: 조직도 (1개 총괄 + 4개 세부과제 박스, 연결선 표시)
- 기대성과: Value Chain 다이어그램

대상 독자: 연구비 심사위원
중요: 입력 텍스트의 섹션 순서를 그대로 유지할 것"""
    
    return input_text, additional_instructions

def _extract_pptx_url(result: Dict) -> Optional[str]:
    """
    다양한 위치에서 PPTX URL 추출
    """
    # 1. 직접 pptxUrl 필드
    if result.get("pptxUrl"):
        return result["pptxUrl"]
    
    # 2. exports 배열 안에서 찾기
    exports = result.get("exports", [])
    if isinstance(exports, list):
        for export in exports:
            if isinstance(export, dict):
                if export.get("format") == "pptx" and export.get("url"):
                    return export["url"]
    
    # 3. export 객체 안에서 찾기
    export_obj = result.get("export", {})
    if isinstance(export_obj, dict):
        if export_obj.get("pptx"):
            return export_obj["pptx"]
        if export_obj.get("pptxUrl"):
            return export_obj["pptxUrl"]
    
    return None

def call_gamma_unified_api(
    input_text: str,
    additional_instructions: str,
    estimated_cards: int = 23
) -> tuple[Optional[str], Optional[str]]:
    """
    단일 API 호출로 전체 PPT 생성
    """
    url = f"{config.GAMMA_API_BASE}/generations"
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": config.GAMMA_API_KEY
    }
    
    payload = {
        "inputText": input_text,
        "textMode": "condense",
        "format": "presentation",
        "numCards": estimated_cards,
        "cardSplit": "inputTextBreaks",  # 섹션 순서 보장
        "additionalInstructions": additional_instructions,
        "exportAs": "pptx",
        "textOptions": {
            "amount": "medium",
            "tone": "professional, clear, concise",
            "audience": "연구비 심사위원, 과학기술 전문가",
            "language": "ko"
        },
        "imageOptions": {
            "source": "aiGenerated",
            "style": "professional diagrams, infographics, technical charts, clean design, 16:9 aspect ratio"
        },
        "cardOptions": {
            "dimensions": "16x9"
        }
    }
    
    try:
        print(f"  API 호출 중... (예상 슬라이드: {estimated_cards}장)")
        print(f"  입력 텍스트 길이: {len(input_text):,}자")
        print(f"  추가 지시사항 길이: {len(additional_instructions):,}자")
        print(f"  섹션 순서: cardSplit=inputTextBreaks (구분자 기준)")
        
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        if response.status_code not in [200, 201]:
            return None, f"HTTP {response.status_code}: {response.text}"
        
        result = response.json()
        generation_id = result.get("generationId")
        
        if generation_id:
            print(f"  Generation ID: {generation_id}")
            return generation_id, None
        else:
            return None, "generationId not found"
        
    except Exception as e:
        return None, str(e)

def poll_gamma_status(generation_id: str, max_wait: int = 600) -> Optional[Dict]:
    """
    상태 폴링 (PPTX 생성 대기 로직 포함)
    """
    url = f"{config.GAMMA_API_BASE}/generations/{generation_id}"
    headers = {"X-API-KEY": config.GAMMA_API_KEY}
    
    start_time = time.time()
    print(f"  생성 대기", end="", flush=True)
    
    pptx_wait_count = 0
    max_pptx_wait = 60  # PPTX 생성을 위한 추가 대기 시간 (초)
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(url, headers=headers, timeout=30)
            result = response.json()
            status = result.get("status")
            
            if status == "completed":
                # 완료되었지만 PPTX URL이 없으면 추가 대기
                pptx_url = _extract_pptx_url(result)
                
                if pptx_url:
                    print(f" 완료 (PPTX 생성됨)")
                    return {
                        "status": "completed",
                        "gammaUrl": result.get("gammaUrl"),
                        "gammaId": result.get("gammaId"),
                        "pptxUrl": pptx_url
                    }
                else:
                    # PPTX가 아직 없으면 추가 대기
                    if pptx_wait_count < max_pptx_wait:
                        print("P", end="", flush=True)  # P = PPTX 대기 중
                        pptx_wait_count += 1
                        time.sleep(1)
                        continue
                    else:
                        # 최대 대기 시간 초과
                        print(f" 완료 (PPTX 생성 시간 초과)")
                        return {
                            "status": "completed",
                            "gammaUrl": result.get("gammaUrl"),
                            "gammaId": result.get("gammaId"),
                            "pptxUrl": None,
                            "warning": "PPTX URL을 찾을 수 없음"
                        }
            
            elif status == "failed":
                print(f" 실패")
                return {"status": "failed", "error": result.get("error")}
            
            print(".", end="", flush=True)
            time.sleep(5)
            
        except Exception as e:
            print(f"\n  폴링 오류: {e}")
            time.sleep(5)
    
    print(f" 타임아웃")
    return None

def download_pptx_file(url: str, filename: str) -> bool:
    save_path = config.OUTPUT_PPTX_DIR / filename
    try:
        print(f"  다운로드: {filename}...", end="")
        response = requests.get(url, timeout=120)
        with open(save_path, "wb") as f:
            f.write(response.content)
        print(" OK")
        print(f"  저장 위치: {save_path}")
        return True
    except Exception as e:
        print(f" 실패: {e}")
        return False

def main():
    print("=" * 80)
    print("R&D 제안서 PPT 자동 생성 (섹션 순서 보장 + PPTX 대기)")
    print("=" * 80)
    
    # 1. PDF 찾기
    pdf_files = list(config.INPUT_PDF_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"PDF 파일 없음: {config.INPUT_PDF_DIR}")
        return
    
    pdf_path = pdf_files[0]
    print(f"\n대상: {pdf_path.name}")
    
    # 2. 파싱 & 섹션화
    section_json_path = parse_and_section_pdf(pdf_path)
    
    # 3. 기관 정보
    print(f"\n3단계: 기관 정보 조회")
    company_info = fetch_company_info(config.DEFAULT_COMPANY_ID)
    print(f"  기관명: {company_info['company_name']}")
    
    # 4. 섹션 내용 추출
    print(f"\n4단계: 섹션 내용 추출 및 길이 제한")
    section_contents = {}
    total_chars = 0
    
    for section_name, target_titles in config.SECTION_TITLE_MAPPING.items():
        content = find_section_content(section_json_path, target_titles)
        if content and len(content.strip()) > 100:
            max_chars = config.SECTION_MAX_CHARS.get(section_name, 5000)
            truncated = truncate_content(content, max_chars)
            section_contents[section_name] = truncated
            total_chars += len(truncated)
            print(f"  {section_name}: {len(content):,}자 → {len(truncated):,}자")
        else:
            print(f"  {section_name}: 건너뜀")
    
    print(f"\n  총 내용 길이: {total_chars:,}자")
    
    # 5. 통합 프롬프트 생성
    print(f"\n5단계: 통합 프롬프트 생성")
    input_text, additional_instructions = build_unified_prompt(
        config.ANNOUNCEMENT_TITLE,
        company_info,
        section_contents
    )
    
    estimated_cards = 23
    
    print(f"  최종 입력 텍스트: {len(input_text):,}자")
    print(f"  추가 지시사항: {len(additional_instructions):,}자")
    print(f"  예상 슬라이드: {estimated_cards}장")
    print(f"  섹션 구분자 개수: {input_text.count('---')}개")
    
    # 6. 단일 API 호출
    print(f"\n6단계: PPT 생성")
    print(f"  테마: 기본 테마")
    
    gen_id, error = call_gamma_unified_api(
        input_text=input_text,
        additional_instructions=additional_instructions,
        estimated_cards=estimated_cards
    )
    
    if not gen_id:
        print(f"  생성 실패: {error}")
        return
    
    # 7. 상태 확인
    result = poll_gamma_status(gen_id, max_wait=600)
    
    if not result or result.get("status") != "completed":
        print("  PPT 생성 실패")
        if result:
            print(f"  오류: {result.get('error', '알 수 없는 오류')}")
        return
    
    # 8. 결과 저장
    print("\n" + "=" * 80)
    print("결과")
    print("=" * 80)
    
    gamma_url = result.get("gammaUrl")
    pptx_url = result.get("pptxUrl")
    
    print(f"Gamma URL: {gamma_url}")
    print(f"PPTX URL: {pptx_url if pptx_url else '생성되지 않음'}")
    
    if result.get("warning"):
        print(f"경고: {result['warning']}")
    
    # PPTX 다운로드
    if pptx_url:
        download_pptx_file(pptx_url, f"{pdf_path.stem}_complete.pptx")
    else:
        print("  PPTX 파일을 다운로드할 수 없습니다. Gamma 웹사이트에서 수동으로 다운로드하세요.")
    
    # 9. URL 저장
    output_json = config.OUTPUT_PPTX_DIR / "gamma_urls.json"
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump({
            "announcement_title": config.ANNOUNCEMENT_TITLE,
            "gamma_url": gamma_url,
            "pptx_url": pptx_url,
            "generation_id": gen_id,
            "estimated_cards": estimated_cards,
            "input_text_length": len(input_text),
            "section_breaks": input_text.count('---')
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\nURL 저장: {output_json}")
    print("\n완료!")

if __name__ == "__main__":
    main()
    
    
# """
# R&D 제안서 PPT 자동 생성 (단일 API 호출 - 최종 버전)
# - 섹션 순서 보장
# - PPTX 생성 대기 로직 추가
# - 토큰 길이 최적화
# """
# import os
# import sys
# import json
# import time
# import requests
# from pathlib import Path
# from typing import Dict, List, Optional
# import mysql.connector
# from dotenv import load_dotenv

# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
# from utils.document_parsing import extract_text_from_pdf
# from utils.section import SectionSplitter

# load_dotenv()

# class Config:
#     BASE_DIR = Path(__file__).parent.parent.parent
    
#     INPUT_PDF_DIR = BASE_DIR / "data" / "ppt_input"
#     OUTPUT_PPTX_DIR = BASE_DIR / "data" / "pptx"
#     PARSING_DIR = BASE_DIR / "data" / "parsing"
#     SECTION_DIR = BASE_DIR / "data" / "sections"
#     TEMP_DIR = BASE_DIR / "data" / "temp"
    
#     GAMMA_API_KEY = os.getenv("GAMMA_API_KEY")
#     GAMMA_API_BASE = "https://public-api.gamma.app/v1.0"
    
#     DB_CONFIG = {
#         "host": os.getenv("DB_HOST"),
#         "port": int(os.getenv("DB_PORT", "3306")),
#         "user": os.getenv("DB_USER"),
#         "password": os.getenv("DB_PASSWORD"),
#         "database": os.getenv("DB_NAME"),
#     }
    
#     ANNOUNCEMENT_TITLE = "고해상도 해양-빙권 결합모델 개발"
#     DEFAULT_COMPANY_ID = 1
    
#     SECTION_TITLE_MAPPING = {
#         "연구 개요": ["연구개발의 개요"],
#         "연구 필요성": ["연구개발 대상의 국내외 현황", "연구개발의 중요성"],
#         "연구 목표": ["연구개발의 최종 목표", "연구개발과제의 단계별 목표"],
#         "연구 내용": ["연구개발과제의 내용", "연구개발과제 수행일정 및 주요 결과물"],
#         "추진 계획": ["연구개발 추진전략", "연구개발 수행방법", "연구개발 추진일정"],
#         "기대성과 및 활용방안": ["연구개발성과의 활용방안", "기대효과"]
#     }
    
#     # 섹션별 최대 글자 수 제한
#     SECTION_MAX_CHARS = {
#         "연구 개요": 3000,
#         "연구 필요성": 5000,
#         "연구 목표": 4000,
#         "연구 내용": 10000,
#         "추진 계획": 8000,
#         "기대성과 및 활용방안": 5000
#     }

#     def __init__(self):
#         for d in [self.OUTPUT_PPTX_DIR, self.PARSING_DIR, self.SECTION_DIR, self.TEMP_DIR]:
#             d.mkdir(parents=True, exist_ok=True)

# config = Config()

# def get_db_connection():
#     try:
#         return mysql.connector.connect(**Config.DB_CONFIG)
#     except Exception as e:
#         print(f"DB 연결 실패: {e}")
#         return None

# def fetch_company_info(company_id: int = Config.DEFAULT_COMPANY_ID) -> Dict:
#     conn = get_db_connection()
#     if not conn:
#         return {"company_name": "테스트 연구소", "business_report": {}}
    
#     cursor = conn.cursor(dictionary=True)
#     try:
#         query = "SELECT company_name, business_report_sections FROM companies WHERE company_id = %s"
#         cursor.execute(query, (company_id,))
#         result = cursor.fetchone()
        
#         if not result:
#             raise ValueError(f"Company ID {company_id} not found")
        
#         business_report = json.loads(result["business_report_sections"]) if result.get("business_report_sections") else {}
#         return {"company_name": result["company_name"], "business_report": business_report}
#     except Exception as e:
#         print(f"기관 정보 조회 실패: {e}")
#         return {"company_name": "테스트 연구소", "business_report": {}}
#     finally:
#         cursor.close()
#         conn.close()

# def parse_and_section_pdf(pdf_path: Path) -> str:
#     print(f"1단계: PDF 파싱 중...")
    
#     parsed_data = extract_text_from_pdf(str(pdf_path))
#     parsing_json_path = config.PARSING_DIR / f"{pdf_path.stem}_parsing.json"
#     with open(parsing_json_path, "w", encoding="utf-8") as f:
#         json.dump(parsed_data, f, ensure_ascii=False, indent=2)
#     print(f"  파싱 완료: {parsing_json_path}")
    
#     print(f"2단계: 섹션 분리 중...")
#     splitter = SectionSplitter(str(parsing_json_path))
#     section_json_path = config.SECTION_DIR / f"{pdf_path.stem}_sections.json"
#     sections = splitter.save_sections(str(section_json_path), format='json')
#     print(f"  섹션화 완료: {section_json_path}")
#     print(f"  총 {len(sections)}개 섹션")
    
#     return str(section_json_path)

# def find_section_content(section_json_path: str, target_titles: List[str]) -> str:
#     with open(section_json_path, 'r', encoding='utf-8') as f:
#         sections = json.load(f)
    
#     contents = []
#     for section in sections:
#         title = section.get("title", "").strip()
#         content_list = section.get("content", [])
        
#         if not content_list:
#             continue
        
#         for target in target_titles:
#             if target in title:
#                 content_text = "\n".join(content_list)
#                 if len(content_text.strip()) > 100:
#                     contents.append(content_text)
#                     print(f"  매칭: '{title}' ({len(content_text)}자)")
#                 break
    
#     return "\n\n".join(contents)

# def truncate_content(content: str, max_chars: int) -> str:
#     """내용을 최대 글자 수로 자르기 (문장 단위로)"""
#     if len(content) <= max_chars:
#         return content
    
#     # 문장 단위로 자르기
#     sentences = content.split('.')
#     truncated = ""
#     for sentence in sentences:
#         if len(truncated) + len(sentence) + 1 <= max_chars:
#             truncated += sentence + "."
#         else:
#             break
    
#     return truncated + "...(내용 계속)"

# def build_unified_prompt(
#     announcement_title: str,
#     company_info: Dict,
#     section_contents: Dict[str, str]
# ) -> tuple[str, str]:
#     """
#     모든 섹션을 하나의 통합 프롬프트로 구성 (순서 보장)
#     """
#     company_name = company_info["company_name"]
#     business_report = company_info["business_report"]
    
#     # 기관 정보 간소화
#     report_summary = f"{company_name}의 주요 사업 분야 및 역량"
    
#     if business_report:
#         if isinstance(business_report, dict):
#             report_summary += ": " + ", ".join(list(business_report.keys())[:5])
#         elif isinstance(business_report, list):
#             report_summary += ": " + ", ".join([str(item)[:50] for item in business_report[:3]])
#         else:
#             report_summary += ": " + str(business_report)[:200]
    
#     # 입력 텍스트 구성 (섹션 구분자 추가로 순서 보장)
#     input_text_parts = []
    
#     # 1. 표지
#     input_text_parts.append(f"# {announcement_title}\n\n연구개발 제안서")
    
#     # 섹션 구분자
#     input_text_parts.append("\n---\n")
    
#     # 2. 기관 소개
#     input_text_parts.append(f"# 수행 기관 소개\n\n## {company_name}\n\n{report_summary}")
    
#     # 3. 각 섹션 내용 추가 (순서대로, 구분자로 분리)
#     section_order = ["연구 개요", 
#                     #  "연구 필요성", "연구 목표", "연구 내용", "추진 계획", "기대성과 및 활용방안"
#                      ]
    
#     for section_name in section_order:
#         content = section_contents.get(section_name, "")
#         if content:
#             input_text_parts.append("\n---\n")
#             max_chars = config.SECTION_MAX_CHARS.get(section_name, 5000)
#             truncated_content = truncate_content(content, max_chars)
#             input_text_parts.append(f"# {section_name}\n\n{truncated_content}")
    
#     input_text = "".join(input_text_parts)
    
#     # 간소화된 추가 지시사항
#     additional_instructions = """프레젠테이션 규칙:
# - 모든 슬라이드 16:9 비율
# - 섹션 표지 없이 바로 내용 시작 (중요)
# - 각 섹션: 상단 왼쪽 작은 태그 박스(섹션명) + 아래 큰 대제목
# - 슬라이드당 불릿 5개 이하, 간결하게
# - 내용이 많으면 여러 슬라이드로 분할
# - 명사 위주 개조식
# - 전문적이고 깔끔한 레이아웃
# - 이미지는 작은 다이어그램/차트/아이콘만 사용 (절대 큰 이미지를 사용하지 않는다.)

# 섹션별 시각화 (필수적으로 들어가야 함):
# - 연구 개요: 시스템 프레임워크 다이어그램
# - 연구 필요성: Gap Analysis 인포그래픽
# - 연구 목표: KPI 대시보드
# - 연구 내용: 계층 구조 다이어그램
# - 추진 계획: 조직도 (1개 총괄 + 4개 세부과제 박스, 연결선 표시), 간트자트
# - 기대성과: Value Chain 다이어그램

# 대상 독자: 연구비 심사위원
# 중요: 입력 텍스트의 섹션 순서를 그대로 유지할 것"""
    
#     return input_text, additional_instructions

# def _extract_pptx_url(result: Dict) -> Optional[str]:
#     if result.get("pptxUrl"):
#         return result["pptxUrl"]

#     exports = result.get("exports", [])
#     if isinstance(exports, list):
#         for export in exports:
#             if export.get("format") == "pptx" and export.get("url"):
#                 return export["url"]

#     export_obj = result.get("export", {})
#     if isinstance(export_obj, dict):
#         return export_obj.get("pptx") or export_obj.get("pptxUrl")

#     return None

# def call_gamma_unified_api(
#     input_text: str,
#     additional_instructions: str,
#     estimated_cards: int = 23
# ) -> tuple[Optional[str], Optional[str]]:
#     """
#     단일 API 호출로 전체 PPT 생성
#     """
#     url = f"{config.GAMMA_API_BASE}/generations"
#     headers = {
#         "Content-Type": "application/json",
#         "X-API-KEY": config.GAMMA_API_KEY
#     }
    
#     payload = {
#         "inputText": input_text,
#         "textMode": "condense",
#         "format": "presentation",
#         "numCards": estimated_cards,
#         "cardSplit": "inputTextBreaks",  # 섹션 순서 보장
#         "additionalInstructions": additional_instructions,
#         "exportAs": "pptx",
#         "textOptions": {
#             "amount": "medium",
#             "tone": "professional, clear, concise",
#             "audience": "연구비 심사위원, 과학기술 전문가",
#             "language": "ko"
#         },
#         "imageOptions": {
#             "source": "aiGenerated",
#             "style": "professional diagrams, infographics, technical charts, clean design, 16:9 aspect ratio"
#         },
#         "cardOptions": {
#             "dimensions": "16x9"
#         }
#     }
    
#     try:
#         print(f"  API 호출 중... (예상 슬라이드: {estimated_cards}장)")
#         print(f"  입력 텍스트 길이: {len(input_text):,}자")
#         print(f"  추가 지시사항 길이: {len(additional_instructions):,}자")
#         print(f"  섹션 순서: cardSplit=inputTextBreaks (구분자 기준)")
        
#         response = requests.post(url, headers=headers, json=payload, timeout=60)
        
#         if response.status_code not in [200, 201]:
#             return None, f"HTTP {response.status_code}: {response.text}"
        
#         result = response.json()
#         generation_id = result.get("generationId")
        
#         if generation_id:
#             print(f"  Generation ID: {generation_id}")
#             return generation_id, None
#         else:
#             return None, "generationId not found"
        
#     except Exception as e:
#         return None, str(e)

# def poll_gamma_status(generation_id: str, max_wait: int = 600) -> Optional[Dict]:
#     url = f"{config.GAMMA_API_BASE}/generations/{generation_id}"
#     headers = {"X-API-KEY": config.GAMMA_API_KEY}

#     start_time = time.time()
#     print("  생성 대기", end="", flush=True)

#     last_completed = None

#     while time.time() - start_time < max_wait:
#         try:
#             response = requests.get(url, headers=headers, timeout=30)
#             result = response.json()
#             status = result.get("status")

#             if status == "completed":
#                 pptx_url = _extract_pptx_url(result)

#                 if pptx_url:
#                     print(" 완료 (PPTX 확인)")
#                     return {
#                         "status": "completed",
#                         "gammaUrl": result.get("gammaUrl"),
#                         "gammaId": result.get("gammaId"),
#                         "pptxUrl": pptx_url
#                     }

#                 # completed 되었지만 export 아직 안 됨 → 계속 대기
#                 last_completed = {
#                     "status": "completed",
#                     "gammaUrl": result.get("gammaUrl"),
#                     "gammaId": result.get("gammaId"),
#                     "pptxUrl": None
#                 }
#                 print("P", end="", flush=True)
#                 time.sleep(5)
#                 continue

#             elif status == "failed":
#                 print(" 실패")
#                 return {"status": "failed", "error": result.get("error")}

#             print(".", end="", flush=True)
#             time.sleep(5)

#         except Exception as e:
#             print(f"\n  폴링 오류: {e}")
#             time.sleep(5)

#     print(" 타임아웃")
#     return last_completed

# def download_pptx_file(url: str, filename: str) -> bool:
#     save_path = config.OUTPUT_PPTX_DIR / filename
#     try:
#         print(f"  다운로드: {filename}...", end="")
#         response = requests.get(url, timeout=120)
#         with open(save_path, "wb") as f:
#             f.write(response.content)
#         print(" OK")
#         print(f"  저장 위치: {save_path}")
#         return True
#     except Exception as e:
#         print(f" 실패: {e}")
#         return False

# def main():
#     print("=" * 80)
#     print("R&D 제안서 PPT 생성 중")
#     print("=" * 80)
    
#     # 1. PDF 찾기
#     pdf_files = list(config.INPUT_PDF_DIR.glob("*.pdf"))
#     if not pdf_files:
#         print(f"PDF 파일 없음: {config.INPUT_PDF_DIR}")
#         return
    
#     pdf_path = pdf_files[0]
#     print(f"\n대상: {pdf_path.name}")
    
#     # 2. 파싱 & 섹션화
#     section_json_path = parse_and_section_pdf(pdf_path)
    
#     # 3. 기관 정보
#     print(f"\n3단계: 기관 정보 조회")
#     company_info = fetch_company_info(config.DEFAULT_COMPANY_ID)
#     print(f"  기관명: {company_info['company_name']}")
    
#     # 4. 섹션 내용 추출
#     print(f"\n4단계: 섹션 내용 추출 및 길이 제한")
#     section_contents = {}
#     total_chars = 0
    
#     # for section_name, target_titles in config.SECTION_TITLE_MAPPING.items():
#     #     content = find_section_content(section_json_path, target_titles)
#     #     if content and len(content.strip()) > 100:
#     #         max_chars = config.SECTION_MAX_CHARS.get(section_name, 5000)
#     #         truncated = truncate_content(content, max_chars)
#     #         section_contents[section_name] = truncated
#     #         total_chars += len(truncated)
#     #         print(f"  {section_name}: {len(content):,}자 → {len(truncated):,}자")
#     #     else:
#     #         print(f"  {section_name}: 건너뜀")
#     # ===== 테스트용: 회사소개 + 연구 개요만 =====

#     TEST_SECTION_MAPPING = {
#         "연구 개요": config.SECTION_TITLE_MAPPING["연구 개요"]
#         # "연구 필요성": config.SECTION_TITLE_MAPPING["연구 필요성"],
#         # "연구 목표": config.SECTION_TITLE_MAPPING["연구 목표"],
#         # "연구 내용": config.SECTION_TITLE_MAPPING["연구 내용"],
#         # "추진 계획": config.SECTION_TITLE_MAPPING["추진 계획"],
#         # "기대성과 및 활용방안": config.SECTION_TITLE_MAPPING["기대성과 및 활용방안"],
#     }

#     for section_name, target_titles in TEST_SECTION_MAPPING.items():
#         content = find_section_content(section_json_path, target_titles)
#         if content and len(content.strip()) > 100:
#             max_chars = config.SECTION_MAX_CHARS.get(section_name, 3000)
#             truncated = truncate_content(content, max_chars)
#             section_contents[section_name] = truncated
#             total_chars += len(truncated)
#             print(f"  {section_name}: {len(content):,}자 → {len(truncated):,}자")
#         else:
#             print(f"  {section_name}: 건너뜀")

# # ==========================================

#     print(f"\n  총 내용 길이: {total_chars:,}자")
    
#     # 5. 통합 프롬프트 생성
#     print(f"\n5단계: 통합 프롬프트 생성")
#     input_text, additional_instructions = build_unified_prompt(
#         config.ANNOUNCEMENT_TITLE,
#         company_info,
#         section_contents
#     )
    
#     estimated_cards = 3
    
#     print(f"  최종 입력 텍스트: {len(input_text):,}자")
#     print(f"  추가 지시사항: {len(additional_instructions):,}자")
#     print(f"  예상 슬라이드: {estimated_cards}장")
#     print(f"  섹션 구분자 개수: {input_text.count('---')}개")
    
#     # 6. 단일 API 호출
#     print(f"\n6단계: PPT 생성")
#     print(f"  테마: 기본 테마")
    
#     gen_id, error = call_gamma_unified_api(
#         input_text=input_text,
#         additional_instructions=additional_instructions,
#         estimated_cards=estimated_cards
#     )
    
#     if not gen_id:
#         print(f"  생성 실패: {error}")
#         return
    
#     # 7. 상태 확인
#     result = poll_gamma_status(gen_id, max_wait=600)
    
#     if not result or result.get("status") != "completed":
#         print("  PPT 생성 실패")
#         if result:
#             print(f"  오류: {result.get('error', '알 수 없는 오류')}")
#         return
    
#     # 8. 결과 저장
#     print("\n" + "=" * 80)
#     print("결과")
#     print("=" * 80)
    
#     gamma_url = result.get("gammaUrl")
#     pptx_url = result.get("pptxUrl")
    
#     print(f"Gamma URL: {gamma_url}")
#     print(f"PPTX URL: {pptx_url if pptx_url else '생성되지 않음'}")
    
#     if result.get("warning"):
#         print(f"경고: {result['warning']}")
    
#     # PPTX 다운로드
#     if pptx_url:
#         download_pptx_file(pptx_url, f"{pdf_path.stem}_complete.pptx")
#     else:
#         print("  PPTX 파일을 다운로드할 수 없습니다. Gamma 웹사이트에서 수동으로 다운로드하세요.")
    
#     # 9. URL 저장
#     output_json = config.OUTPUT_PPTX_DIR / "gamma_urls.json"
#     with open(output_json, "w", encoding="utf-8") as f:
#         json.dump({
#             "announcement_title": config.ANNOUNCEMENT_TITLE,
#             "gamma_url": gamma_url,
#             "pptx_url": pptx_url,
#             "generation_id": gen_id,
#             "estimated_cards": estimated_cards,
#             "input_text_length": len(input_text),
#             "section_breaks": input_text.count('---')
#         }, f, ensure_ascii=False, indent=2)
    
#     print(f"\nURL 저장: {output_json}")
#     print("\n완료!")

# if __name__ == "__main__":
#     main()