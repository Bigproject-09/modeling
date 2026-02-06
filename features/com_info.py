# """
# 사업보고서 파싱 및 DB 저장 시스템

# company_info 폴더의 사업보고서 PDF를:
# 1. document_parsing.py로 파싱
# 2. section.py로 섹션 분리
# 3. 섹션 JSON 전체를 DB에 저장 (항목별 파싱 X)
# """

# import os
# import sys
# import json
# from pathlib import Path
# from dotenv import load_dotenv
# import mysql.connector
# from datetime import datetime

# # ---------------------------------------------------------
# # [경로 설정] 현재 파일 위치 기준으로 프로젝트 루트(MODELING) 찾기
# # ---------------------------------------------------------
# current_dir = os.path.dirname(os.path.abspath(__file__))  # .../features
# project_root = os.path.dirname(current_dir)                # .../modeling (루트)
# sys.path.append(project_root)

# # 파싱 모듈 import
# from utils.document_parsing import extract_text_from_pdf
# from utils.section import SectionSplitter

# # .env 파일 로드
# load_dotenv()

# # =========================================================
# # DB 연결
# # =========================================================
# def get_db_conn():
#     """MySQL 커넥션 생성"""
#     return mysql.connector.connect(
#         host=os.environ["DB_HOST"],
#         port=int(os.environ.get("DB_PORT", "3306")),
#         user=os.environ["DB_USER"],
#         password=os.environ["DB_PASSWORD"],
#         database=os.environ["DB_NAME"],
#     )

# # =========================================================
# # 1단계: PDF 파싱
# # =========================================================
# def parse_pdf(pdf_path: str, output_dir: str) -> str:
#     """
#     PDF를 파싱하여 JSON 저장
    
#     Args:
#         pdf_path: 사업보고서 PDF 경로
#         output_dir: 출력 디렉토리 (parsing)
    
#     Returns:
#         str: 저장된 JSON 파일 경로
#     """
#     print("=" * 80)
#     print("1단계: PDF 파싱")
#     print("=" * 80)
    
#     os.makedirs(output_dir, exist_ok=True)
    
#     filename = Path(pdf_path).stem
#     output_path = os.path.join(output_dir, f"{filename}_parsing.json")
    
#     print(f"파일: {pdf_path}")
#     print("파싱 중...")
    
#     # document_parsing.py의 extract_text_from_pdf 사용
#     result = extract_text_from_pdf(pdf_path)
    
#     with open(output_path, "w", encoding="utf-8") as f:
#         json.dump(result, f, ensure_ascii=False, indent=2)
    
#     print(f"✓ 파싱 완료: {output_path}")
#     print(f"  - 총 페이지: {len(result)}")
    
#     return output_path

# # =========================================================
# # 2단계: 섹션 분리
# # =========================================================
# def split_sections(parsing_json_path: str, output_dir: str) -> str:
#     """
#     파싱된 JSON을 섹션별로 분리
    
#     Args:
#         parsing_json_path: 파싱 JSON 경로
#         output_dir: 출력 디렉토리 (sections)
    
#     Returns:
#         str: 저장된 섹션 JSON 파일 경로
#     """
#     print("\n" + "=" * 80)
#     print("2단계: 섹션 분리")
#     print("=" * 80)
    
#     filename = Path(parsing_json_path).stem.replace("_parsing", "")
#     output_path = os.path.join(output_dir, f"{filename}_sections.json")
    
#     print(f"입력: {parsing_json_path}")
#     print("섹션 분리 중...")
    
#     # section.py의 SectionSplitter 사용
#     splitter = SectionSplitter(parsing_json_path)
#     sections = splitter.save_sections(output_path, format='json')
    
#     print(f"✓ 섹션 분리 완료: {output_path}")
#     print(f"  - 총 섹션: {len(sections)}개")
    
#     return output_path

# # =========================================================
# # 3단계: 섹션 JSON 전체를 DB에 저장
# # =========================================================
# def save_sections_to_db(company_id: int, sections_json_path: str) -> bool:
#     """
#     섹션 JSON 파일 전체를 DB에 저장
    
#     Args:
#         company_id: 기업 ID
#         sections_json_path: 섹션 JSON 파일 경로
    
#     Returns:
#         bool: 저장 성공 여부
#     """
#     print("\n" + "=" * 80)
#     print("3단계: DB 저장")
#     print("=" * 80)
    
#     conn = get_db_conn()
#     cur = None
    
#     try:
#         # 섹션 JSON 로드
#         with open(sections_json_path, 'r', encoding='utf-8') as f:
#             sections_data = json.load(f)
        
#         # JSON을 문자열로 변환하여 저장
#         sections_json_str = json.dumps(sections_data, ensure_ascii=False)
        
#         cur = conn.cursor()
        
#         # UPDATE 쿼리 실행
#         # companies 테이블에 business_report_sections 컬럼이 있다고 가정
#         query = """
#             UPDATE companies 
#             SET business_report_sections = %s,
#                 updated_at = %s
#             WHERE company_id = %s
#         """
        
#         print(f"DB 업데이트 중... (company_id: {company_id})")
#         print(f"  - 섹션 수: {len(sections_data)}개")
#         print(f"  - JSON 크기: {len(sections_json_str):,} 글자")
        
#         cur.execute(query, (sections_json_str, datetime.now(), company_id))
#         conn.commit()
        
#         print(f"✓ DB 저장 완료")
        
#         return True
    
#     except Exception as e:
#         print(f"✗ DB 저장 실패: {e}")
#         conn.rollback()
#         return False
    
#     finally:
#         try:
#             if cur:
#                 cur.close()
#         finally:
#             conn.close()

# # =========================================================
# # 메인 실행 함수
# # =========================================================
# def process_business_report(pdf_path: str, company_id: int) -> dict:
#     """
#     사업보고서 전체 처리 파이프라인
    
#     Args:
#         pdf_path: 사업보고서 PDF 경로
#         company_id: 기업 ID
    
#     Returns:
#         dict: 처리 결과 정보
#     """
#     print("\n" + "="*80)
#     print("사업보고서 처리 시작")
#     print("="*80)
#     print(f"파일: {pdf_path}")
#     print(f"기업 ID: {company_id}")

#     # 디렉토리 설정 (절대 경로)
#     parsing_dir = os.path.join(project_root, "data", "parsing")
#     sections_dir = os.path.join(project_root, "data", "sections")
    
#     print(f"파싱 출력 디렉토리: {parsing_dir}")
#     print(f"섹션 출력 디렉토리: {sections_dir}")
    
#     # 1단계: PDF 파싱
#     parsing_json_path = parse_pdf(pdf_path, parsing_dir)
    
#     # 2단계: 섹션 분리
#     sections_json_path = split_sections(parsing_json_path, sections_dir)
    
#     # 3단계: 섹션 JSON 전체를 DB에 저장
#     success = save_sections_to_db(company_id, sections_json_path)
    
#     result = {
#         "pdf_path": pdf_path,
#         "parsing_json": parsing_json_path,
#         "sections_json": sections_json_path,
#         "db_saved": success
#     }
    
#     if success:
#         print("\n" + "="*80)
#         print("사업보고서 처리 완료!")
#         print("="*80)
#     else:
#         print("\n" + "="*80)
#         print("DB 저장 실패")
#         print("="*80)
    
#     return result

# # =========================================================
# # 실행 코드
# # =========================================================
# if __name__ == "__main__":
#     # 경로 설정
#     COMPANY_INFO_DIR = os.path.join(project_root, "data", "com_input")
    
#     # company_id 설정 (환경변수 또는 직접 지정)
#     COMPANY_ID = int(os.environ.get("DEFAULT_COMPANY_ID", "1"))
    
#     # company_info 폴더의 모든 PDF 파일 처리
#     if not os.path.exists(COMPANY_INFO_DIR):
#         print(f"오류: {COMPANY_INFO_DIR} 폴더가 없습니다.")
#         os.makedirs(COMPANY_INFO_DIR, exist_ok=True)
#         print(f"폴더를 생성했습니다. PDF 파일을 넣고 다시 실행하세요.")
#         sys.exit(1)
    
#     pdf_files = [f for f in os.listdir(COMPANY_INFO_DIR) if f.lower().endswith('.pdf')]
    
#     if not pdf_files:
#         print(f"{COMPANY_INFO_DIR} 폴더에 PDF 파일이 없습니다.")
#         sys.exit(1)
    
#     print(f"발견된 PDF 파일: {len(pdf_files)}개")
#     print("="*80)
    
#     results = []
    
#     for pdf_file in pdf_files:
#         pdf_path = os.path.join(COMPANY_INFO_DIR, pdf_file)
        
#         try:
#             result = process_business_report(
#                 pdf_path=pdf_path,
#                 company_id=COMPANY_ID
#             )
#             results.append(result)
            
#         except Exception as e:
#             print(f"\n오류 발생 ({pdf_file}): {e}")
#             import traceback
#             traceback.print_exc()
    
#     print("\n" + "="*80)
#     print("전체 처리 요약")
#     print("="*80)
#     print(f"총 파일: {len(pdf_files)}개")
#     print(f"성공: {sum(1 for r in results if r.get('db_saved'))}개")
#     print(f"실패: {sum(1 for r in results if not r.get('db_saved'))}개")
#     print("="*80)

"""
사업보고서 파싱 및 DB 저장 시스템

company_info 폴더의 사업보고서 PDF를:
1. document_parsing.py로 파싱
2. section.py로 섹션 분리
3. 섹션 JSON 전체를 DB에 저장 (항목별 파싱 X)
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
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
    
    print(f"✓ 파싱 완료: {output_path}")
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
        output_dir: 출력 디렉토리 (sections)
    
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
    
    print(f"✓ 섹션 분리 완료: {output_path}")
    print(f"  - 총 섹션: {len(sections)}개")
    
    return output_path

# =========================================================
# 3단계: 섹션 JSON 전체를 DB에 저장
# =========================================================
def save_sections_to_db(company_id: int, sections_json_path: str) -> bool:
    """
    섹션 JSON 파일 전체를 DB에 저장
    
    Args:
        company_id: 기업 ID
        sections_json_path: 섹션 JSON 파일 경로
    
    Returns:
        bool: 저장 성공 여부
    """
    print("\n" + "=" * 80)
    print("3단계: DB 저장")
    print("=" * 80)
    
    conn = get_db_conn()
    cur = None
    
    try:
        # 섹션 JSON 로드
        with open(sections_json_path, 'r', encoding='utf-8') as f:
            sections_data = json.load(f)
        
        # JSON을 문자열로 변환하여 저장
        sections_json_str = json.dumps(sections_data, ensure_ascii=False)
        
        cur = conn.cursor()
        
        # UPDATE 쿼리 실행
        # companies 테이블에 business_report_sections 컬럼이 있다고 가정
        query = """
            UPDATE companies 
            SET business_report_sections = %s,
                updated_at = %s
            WHERE company_id = %s
        """
        
        print(f"DB 업데이트 중... (company_id: {company_id})")
        print(f"  - 섹션 수: {len(sections_data)}개")
        print(f"  - JSON 크기: {len(sections_json_str):,} 글자")
        
        cur.execute(query, (sections_json_str, datetime.now(), company_id))
        conn.commit()
        
        print(f"✓ DB 저장 완료")
        
        return True
    
    except Exception as e:
        print(f"✗ DB 저장 실패: {e}")
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
def process_business_report(pdf_path: str, company_id: int) -> dict:
    """
    사업보고서 전체 처리 파이프라인
    
    Args:
        pdf_path: 사업보고서 PDF 경로
        company_id: 기업 ID
    
    Returns:
        dict: 처리 결과 정보
    """
    print("\n" + "="*80)
    print("사업보고서 처리 시작")
    print("="*80)
    print(f"파일: {pdf_path}")
    print(f"기업 ID: {company_id}")

    # 디렉토리 설정 (절대 경로)
    parsing_dir = os.path.join(project_root, "data", "parsing")
    sections_dir = os.path.join(project_root, "data", "sections")
    
    print(f"파싱 출력 디렉토리: {parsing_dir}")
    print(f"섹션 출력 디렉토리: {sections_dir}")
    
    # 1단계: PDF 파싱
    parsing_json_path = parse_pdf(pdf_path, parsing_dir)
    
    # 2단계: 섹션 분리
    sections_json_path = split_sections(parsing_json_path, sections_dir)
    
    # 3단계: 섹션 JSON 전체를 DB에 저장
    success = save_sections_to_db(company_id, sections_json_path)
    
    result = {
        "pdf_path": pdf_path,
        "parsing_json": parsing_json_path,
        "sections_json": sections_json_path,
        "db_saved": success
    }
    
    if success:
        print("\n" + "="*80)
        print("사업보고서 처리 완료!")
        print("="*80)
    else:
        print("\n" + "="*80)
        print("DB 저장 실패")
        print("="*80)
    
    return result

# =========================================================
# 실행 코드
# =========================================================
if __name__ == "__main__":
    # 경로 설정
    COMPANY_INFO_DIR = os.path.join(project_root, "data", "com_input")
    
    # company_id 설정 (환경변수 또는 직접 지정)
    COMPANY_ID = int(os.environ.get("DEFAULT_COMPANY_ID", "1"))
    
    # company_info 폴더의 모든 PDF 파일 처리
    if not os.path.exists(COMPANY_INFO_DIR):
        print(f"오류: {COMPANY_INFO_DIR} 폴더가 없습니다.")
        os.makedirs(COMPANY_INFO_DIR, exist_ok=True)
        print(f"폴더를 생성했습니다. PDF 파일을 넣고 다시 실행하세요.")
        sys.exit(1)
    
    pdf_files = [f for f in os.listdir(COMPANY_INFO_DIR) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print(f"{COMPANY_INFO_DIR} 폴더에 PDF 파일이 없습니다.")
        sys.exit(1)
    
    print(f"발견된 PDF 파일: {len(pdf_files)}개")
    print("="*80)
    
    results = []
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(COMPANY_INFO_DIR, pdf_file)
        
        try:
            result = process_business_report(
                pdf_path=pdf_path,
                company_id=COMPANY_ID
            )
            results.append(result)
            
        except Exception as e:
            print(f"\n오류 발생 ({pdf_file}): {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*80)
    print("전체 처리 요약")
    print("="*80)
    print(f"총 파일: {len(pdf_files)}개")
    print(f"성공: {sum(1 for r in results if r.get('db_saved'))}개")
    print(f"실패: {sum(1 for r in results if not r.get('db_saved'))}개")
    print("="*80)