"""
사업보고서 파싱 및 DB 저장 시스템

company_info 폴더의 사업보고서 PDF를:
1. document_parsing.py로 파싱
2. section.py로 섹션 분리
3. LLM으로 항목 추출
4. MySQL DB에 저장
"""

import os
import sys
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from google import genai
import mysql.connector
from datetime import datetime

# ---------------------------------------------------------
# [경로 설정] 현재 파일 위치 기준으로 프로젝트 루트(MODELING) 찾기
# ---------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))  # .../features
project_root = os.path.dirname(current_dir)                # .../modeling (루트)
sys.path.append(project_root)

# 파싱 모듈 import
from utils.document_parsing import extract_text_from_pdf
from utils.section import SectionSplitter

# .env 파일 로드
load_dotenv()

# =========================================================
# DB 연결
# =========================================================
def get_db_conn():
    """MySQL 커넥션 생성"""
    return mysql.connector.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
    )

# =========================================================
# LLM 시스템 프롬프트 - 사업보고서 정보 추출
# =========================================================
SYSTEM_INSTRUCTION_EXTRACT = """
    너는 사업보고서 분석 전문가다.
    제공된 사업보고서 섹션들을 읽고, 기업 정보를 정확하게 추출한다.
    반드시 한국어로 답하고, JSON 형식으로 출력한다.

    추출해야 할 항목:
    1. company_name: 회사명 (예: "주식회사 내츄럴엔도텍")
    2. business_number: 사업자등록번호 (예: "123-45-67890", 없으면 null)
    3. established_date: 설립일 (YYYY-MM-DD 형식, 예: "2001-05-24")
    4. company_size: 기업 규모 (중소기업/중견기업/대기업, 정확히 이 중 하나)
    5. certifications: 보유 인증 (쉼표로 구분, 예: "벤처기업,이노비즈", 없으면 null)
    6. capital: 자본금 (숫자만, 단위는 원, 예: "15877450000", 없으면 null)
    7. annual_revenue: 연매출 (당기 매출액, 숫자만, 단위는 원, 예: "22263243100", 없으면 null)
    8. employee_count: 종업원 수 (숫자만, 예: "50", 없으면 null)
    9. has_research_center: 기업부설연구소 보유 여부 (true/false)
    10. rd_expense: 연구개발비 (당기, 숫자만, 단위는 원, 예: "2349683000", 없으면 null)
    11. rd_personnel: 연구개발 인력 (숫자만, 예: "13", 없으면 null)
    12. industry: 업종 (예: "물리화학 및 생물학 연구개발", 없으면 null)

    출력 형식 (JSON):
    {
      "company_name": "회사명",
      "business_number": "123-45-67890",
      "established_date": "2001-05-24",
      "company_size": "중소기업",
      "certifications": "벤처기업,이노비즈",
      "capital": "15877450000",
      "annual_revenue": "22263243100",
      "employee_count": "50",
      "has_research_center": true,
      "rd_expense": "2349683000",
      "rd_personnel": "13",
      "industry": "물리화학 및 생물학 연구개발"
    }

    규칙:
    1. 숫자 필드는 쉼표(,)를 제거하고 순수 숫자만 출력
    2. 날짜는 반드시 YYYY-MM-DD 형식
    3. company_size는 "중소기업", "중견기업", "대기업" 중 정확히 하나
    4. has_research_center는 boolean (true/false)
    5. 값이 없으면 null
    6. 반드시 유효한 JSON만 출력 (코드 블록 없이)
    """.strip()

# =========================================================
# 1단계: PDF 파싱
# =========================================================
def parse_pdf(pdf_path: str, output_dir: str) -> str:
    """
    PDF를 파싱하여 JSON 저장
    
    Args:
        pdf_path: 사업보고서 PDF 경로
        output_dir: 출력 디렉토리 (parsing)
    
    Returns:
        str: 저장된 JSON 파일 경로
    """
    print("=" * 80)
    print("1단계: PDF 파싱")
    print("=" * 80)
    
    os.makedirs(output_dir, exist_ok=True)
    
    filename = Path(pdf_path).stem
    output_path = os.path.join(output_dir, f"{filename}_parsing.json")
    
    print(f"파일: {pdf_path}")
    print("파싱 중...")
    
    # document_parsing.py의 extract_text_from_pdf 사용
    result = extract_text_from_pdf(pdf_path)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"파싱 완료: {output_path}")
    print(f"  - 총 페이지: {len(result)}")
    
    return output_path

# =========================================================
# 2단계: 섹션 분리
# =========================================================
def split_sections(parsing_json_path: str, output_dir: str) -> str:
    """
    파싱된 JSON을 섹션별로 분리
    
    Args:
        parsing_json_path: 파싱 JSON 경로
        output_dir: 출력 디렉토리 (parsing)
    
    Returns:
        str: 저장된 섹션 JSON 파일 경로
    """
    print("\n" + "=" * 80)
    print("2단계: 섹션 분리")
    print("=" * 80)
    
    filename = Path(parsing_json_path).stem.replace("_parsing", "")
    output_path = os.path.join(output_dir, f"{filename}_sections.json")
    
    print(f"입력: {parsing_json_path}")
    print("섹션 분리 중...")
    
    # section.py의 SectionSplitter 사용
    splitter = SectionSplitter(parsing_json_path)
    sections = splitter.save_sections(output_path, format='json')
    
    print(f"섹션 분리 완료: {output_path}")
    print(f"  - 총 섹션: {len(sections)}개")
    
    return output_path

# =========================================================
# 3단계: LLM으로 정보 추출
# =========================================================
def extract_company_info_with_llm(sections_json_path: str) -> dict:
    """
    LLM을 사용하여 섹션에서 기업 정보 추출
    
    Args:
        sections_json_path: 섹션 JSON 경로
    
    Returns:
        dict: 추출된 기업 정보
    """
    print("\n" + "=" * 80)
    print("3단계: LLM 정보 추출")
    print("=" * 80)
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("환경변수 GEMINI_API_KEY가 설정되어 있지 않습니다.")
    
    # 섹션 로드
    with open(sections_json_path, 'r', encoding='utf-8') as f:
        sections = json.load(f)
    
    print(f"섹션 수: {len(sections)}개")
    print("LLM 분석 중...")
    
    # 섹션을 텍스트로 변환
    sections_text = ""
    for section in sections:
        sections_text += f"\n## 섹션 {section['section_number']}: {section['title']}\n"
        sections_text += f"페이지: {section['start_page']+1} ~ {section['end_page']+1}\n"
        sections_text += "\n".join(section['content'][:100])  # 너무 길면 앞부분만
        sections_text += "\n" + "="*80 + "\n"
    
    # 프롬프트 생성
    prompt = f"""
    아래는 사업보고서를 섹션별로 나눈 내용입니다.
    이 내용을 읽고 기업 정보를 추출하여 JSON 형식으로 출력하세요.
    
    {sections_text}
    
    주의: JSON 응답만 출력하고, ```json 같은 코드 블록은 사용하지 마세요.
    """.strip()
    
    # LLM 호출
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION_EXTRACT,
            temperature=0.1,
        ),
    )
    
    text = response.text
    if not text:
        raise RuntimeError("LLM 응답이 비어 있습니다.")
    
    # JSON 파싱
    clean_text = text.strip()
    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]
    if clean_text.startswith("```"):
        clean_text = clean_text[3:]
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]
    
    try:
        company_info = json.loads(clean_text.strip())
        
        print("LLM 추출 완료")
        print("\n추출된 정보:")
        for key, value in company_info.items():
            if value is not None:
                print(f"  {key}: {value}")
        
        return company_info
    
    except json.JSONDecodeError as e:
        raise RuntimeError(f"JSON 파싱 실패: {e}\n응답 내용:\n{text}")

# =========================================================
# 4단계: DB 저장
# =========================================================
def save_to_db(company_id: int, company_info: dict) -> bool:
    """
    추출된 기업 정보를 DB에 저장
    
    Args:
        company_id: 기업 ID
        company_info: 추출된 기업 정보
    
    Returns:
        bool: 저장 성공 여부
    """
    print("\n" + "=" * 80)
    print("4단계: DB 저장")
    print("=" * 80)
    
    conn = get_db_conn()
    cur = None
    
    try:
        cur = conn.cursor()
        
        # UPDATE 쿼리 생성
        update_fields = []
        update_values = []
        
        # 각 필드 처리
        field_mapping = {
            'company_name': 'company_name',
            'business_number': 'business_number',
            'established_date': 'established_date',
            'company_size': 'company_size',
            'certifications': 'certifications',
            'capital': 'capital',
            'annual_revenue': 'annual_revenue',
            'employee_count': 'employee_count',
            'has_research_center': 'has_research_center',
            'rd_expense': 'rd_expense',
            'rd_personnel': 'rd_personnel',
            'industry': 'industry',
        }
        
        for key, db_column in field_mapping.items():
            if key in company_info and company_info[key] is not None:
                update_fields.append(f"{db_column} = %s")
                update_values.append(company_info[key])
        
        # 업데이트 시간 추가
        update_fields.append("updated_at = %s")
        update_values.append(datetime.now())
        
        # company_id 추가
        update_values.append(company_id)
        
        # 쿼리 실행
        query = f"""
            UPDATE companies 
            SET {', '.join(update_fields)}
            WHERE company_id = %s
        """
        
        print(f"DB 업데이트 중... (company_id: {company_id})")
        cur.execute(query, update_values)
        conn.commit()
        
        print(f"DB 저장 완료")
        print(f"  - 업데이트된 필드: {len(update_fields)}개")
        
        return True
    
    except Exception as e:
        print(f"DB 저장 실패: {e}")
        conn.rollback()
        return False
    
    finally:
        try:
            if cur:
                cur.close()
        finally:
            conn.close()

# =========================================================
# 메인 실행 함수
# =========================================================
def process_business_report(pdf_path: str, company_id: int, output_dir: str = "parsing") -> dict:
    """
    사업보고서 전체 처리 파이프라인
    
    Args:
        pdf_path: 사업보고서 PDF 경로
        company_id: 기업 ID
        output_dir: 중간 파일 저장 디렉토리
    
    Returns:
        dict: 추출된 기업 정보
    """
    print("\n" + "="*80)
    print("사업보고서 처리 시작")
    print("="*80)
    print(f"파일: {pdf_path}")
    print(f"기업 ID: {company_id}")
    print(f"출력 디렉토리: {output_dir}")
    
    # 1단계: PDF 파싱
    parsing_json_path = parse_pdf(pdf_path, output_dir)
    
    # 2단계: 섹션 분리
    sections_json_path = split_sections(parsing_json_path, output_dir)
    
    # 3단계: LLM 정보 추출
    company_info = extract_company_info_with_llm(sections_json_path)
    
    # 4단계: DB 저장
    success = save_to_db(company_id, company_info)
    
    if success:
        print("\n" + "="*80)
        print("사업보고서 처리 완료!")
        print("="*80)
    else:
        print("\n" + "="*80)
        print("DB 저장 실패")
        print("="*80)
    
    return company_info

# =========================================================
# 실행 코드
# =========================================================
if __name__ == "__main__":
    # 경로 설정
    COMPANY_INFO_DIR = "./data/com_input"
    OUTPUT_DIR = "./data/com_info"
    
    # company_id 설정 (환경변수 또는 직접 지정)
    COMPANY_ID = int(os.environ.get("DEFAULT_COMPANY_ID", "1"))
    
    # company_info 폴더의 모든 PDF 파일 처리
    if not os.path.exists(COMPANY_INFO_DIR):
        print(f"오류: {COMPANY_INFO_DIR} 폴더가 없습니다.")
        sys.exit(1)
    
    pdf_files = [f for f in os.listdir(COMPANY_INFO_DIR) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print(f"{COMPANY_INFO_DIR} 폴더에 PDF 파일이 없습니다.")
        sys.exit(1)
    
    print(f"발견된 PDF 파일: {len(pdf_files)}개")
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(COMPANY_INFO_DIR, pdf_file)
        
        try:
            result = process_business_report(
                pdf_path=pdf_path,
                company_id=COMPANY_ID,
                output_dir=OUTPUT_DIR
            )
            
            # 결과 저장
            result_path = os.path.join(OUTPUT_DIR, f"{Path(pdf_file).stem}_extracted.json")
            with open(result_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            print(f"\n추출 결과 저장: {result_path}")
            
        except Exception as e:
            print(f"\n오류 발생 ({pdf_file}): {e}")
            import traceback
            traceback.print_exc()
    
    print("\n모든 작업 완료")