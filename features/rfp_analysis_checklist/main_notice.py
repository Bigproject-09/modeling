import os
import glob
import json
import sys
# ---------------------------------------------------------
# [경로 설정] 현재 파일 위치 기준으로 프로젝트 루트(MODELING) 찾기
# ---------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))  # .../rfp_analysis_checklist
parent_dir = os.path.dirname(current_dir)                 # .../features
project_root = os.path.dirname(parent_dir)                # .../MODELING (루트)

# 시스템 경로에 프로젝트 루트 추가 (그래야 document_parsing, section을 찾음)
sys.path.append(project_root)
from dotenv import load_dotenv
from utils.document_parsing import parse_docx_to_blocks, extract_text_from_pdf
from utils.section import SectionSplitter, verify_sections
from notice_llm import eligibility_checklist, deep_analysis

load_dotenv()

def classify_file(filename):
    """
    파일명을 보고 종류 분류
    
    Returns:
        str: 'notice' (공고), 'rfp', 'eligibility' (자격요건), 'unknown'
    """
    filename_lower = filename.lower()
    
    # 자격요건 키워드
    if any(keyword in filename_lower for keyword in ['자격요건', '자격', 'eligibility', '요건']):
        return 'eligibility'
    
    # RFP 키워드
    if any(keyword in filename_lower for keyword in ['rfp', '제안요청서', '제안서']):
        return 'rfp'
    
    # 공고 키워드
    if any(keyword in filename_lower for keyword in ['공고', 'notice', '공모', '모집']):
        return 'notice'
    
    # 기본값: 공고로 처리
    return 'notice'

def main():
    INPUT_FOLDER = os.path.join(project_root, "data", "notice_input")
    OUTPUT_FOLDER = os.path.join(project_root, "data", "parsing")
    SECTIONS_FOLDER = os.path.join(project_root, "data", "sections")
    ANALYSIS_FOLDER = os.path.join(project_root, "data", "analysis")
    
    if not os.path.exists(INPUT_FOLDER):
        print(f"[알림] 입력 폴더 '{INPUT_FOLDER}'가 없습니다.")
        os.makedirs(INPUT_FOLDER, exist_ok=True)
        return

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    os.makedirs(SECTIONS_FOLDER, exist_ok=True)
    os.makedirs(ANALYSIS_FOLDER, exist_ok=True)
    
    files_to_process = []
    for ext in ['*.pdf', '*.docx']:
        files_to_process.extend(glob.glob(os.path.join(INPUT_FOLDER, ext)))

    if not files_to_process:
        print(f"[알림] 처리할 파일이 없습니다.")
        return

    print(f"[*] 총 {len(files_to_process)}개의 파일을 발견했습니다.")
    print("=" * 60)

    # 파일 종류별로 청크 분류
    notice_chunks = []      # 공고
    rfp_chunks = []         # RFP
    eligibility_chunks = [] # 자격요건
    
    file_classification = {
        'notice': [],
        'rfp': [],
        'eligibility': []
    }

    # 1-2단계: 모든 파일 파싱 및 섹션 분리
    for file_path in files_to_process:
        try:
            filename = os.path.basename(file_path)
            name_only, ext = os.path.splitext(filename)
            ext = ext.lower()
            
            print(f"\n처리 중: {filename}")
            
            # 파일 종류 분류
            file_type = classify_file(filename)
            print(f"  파일 종류: {file_type}")
            print("-" * 60)
            
            # 1단계: 파싱
            result_path = os.path.join(OUTPUT_FOLDER, f"{name_only}_parsing.json")
            
            if ext == ".docx":
                result = parse_docx_to_blocks(file_path, OUTPUT_FOLDER)
            elif ext == ".pdf":
                result = extract_text_from_pdf(file_path)
            else:
                continue
            
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            if os.path.exists(result_path):
                print(f"[1단계] 파싱 완료 -> {os.path.basename(result_path)}")
                
                # 2단계: 섹션 분리
                sections_output_path = os.path.join(SECTIONS_FOLDER, f"{name_only}_sections.json")
                splitter = SectionSplitter(result_path)
                sections = splitter.save_sections(sections_output_path, format='json')
                print(f"[2단계] 섹션 분리 완료 -> {os.path.basename(sections_output_path)}")
                
                # 섹션 데이터 로드 및 청크로 변환
                with open(sections_output_path, 'r', encoding='utf-8') as f:
                    sections_data = json.load(f)
                
                if isinstance(sections_data, list):
                    file_chunks = []
                    for i, item in enumerate(sections_data):
                        section_num = item.get("section_number", f"Section_{i}")
                        content = item.get("content", [])
                        text = "\n".join(content) if isinstance(content, list) else str(content)
                        
                        chunk = {
                            "chunk_id": f"{name_only}_{section_num}",
                            "text": text
                        }
                        file_chunks.append(chunk)
                    
                    # 파일 종류에 따라 분류
                    if file_type == 'notice':
                        notice_chunks.extend(file_chunks)
                        file_classification['notice'].append(filename)
                    elif file_type == 'rfp':
                        rfp_chunks.extend(file_chunks)
                        file_classification['rfp'].append(filename)
                    elif file_type == 'eligibility':
                        eligibility_chunks.extend(file_chunks)
                        file_classification['eligibility'].append(filename)
                    
                    print(f"  섹션 {len(file_chunks)}개를 '{file_type}' 그룹에 추가")
                else:
                    print("  섹션 데이터 형식이 올바르지 않습니다.")

        except Exception as e:
            print(f"[실패] {os.path.basename(file_path)}: {str(e)}")
            import traceback
            traceback.print_exc()

    # 분류 결과 출력
    print("\n" + "=" * 60)
    print("[파일 분류 결과]")
    print("=" * 60)
    print(f"공고: {len(file_classification['notice'])}개 - {file_classification['notice']}")
    print(f"RFP: {len(file_classification['rfp'])}개 - {file_classification['rfp']}")
    print(f"자격요건: {len(file_classification['eligibility'])}개 - {file_classification['eligibility']}")

    # 3단계: 체크리스트 생성 (공고 + 자격요건)
    checklist_chunks = notice_chunks + eligibility_chunks

    if checklist_chunks:
        print("\n" + "=" * 60)
        print(f"[3단계] 자격요건 체크리스트 생성")
        print(f"  사용 파일: {file_classification['notice'] + file_classification['eligibility']}")
        print(f"  총 섹션: {len(checklist_chunks)}개")
        print("=" * 60)
        
        try:
            # JSON으로 받기
            checklist_result = eligibility_checklist(
                chunks=checklist_chunks,
                source=", ".join(file_classification['notice'] + file_classification['eligibility']),
            )
            
            # JSON 파일로 저장
            checklist_path = os.path.join(ANALYSIS_FOLDER, "checklist.json")
            with open(checklist_path, 'w', encoding='utf-8') as f:
                json.dump(checklist_result, f, ensure_ascii=False, indent=2)
            print(f"[3단계] 체크리스트 생성 완료 -> {os.path.basename(checklist_path)}")
            
        except Exception as e:
            print(f"[3단계] 체크리스트 생성 실패: {str(e)}")
            import traceback
            traceback.print_exc()
    else:
        print("\n[알림] 체크리스트 생성을 위한 파일이 없습니다.")

    # 4단계: 심층 분석 생성 (공고 + RFP)
    analysis_chunks = notice_chunks + rfp_chunks
    
    if analysis_chunks:
        print("\n" + "=" * 60)
        print(f"[4단계] 심층 전략 분석 생성")
        print(f"  사용 파일: {file_classification['notice'] + file_classification['rfp']}")
        print(f"  총 섹션: {len(analysis_chunks)}개")
        print("=" * 60)
        
        try:
            # JSON으로 받기
            analysis_result = deep_analysis(
                chunks=analysis_chunks,
                source=", ".join(file_classification['notice'] + file_classification['rfp']),
            )
            
            # JSON 파일로 저장
            analysis_path = os.path.join(ANALYSIS_FOLDER, "analysis.json")
            with open(analysis_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_result, f, ensure_ascii=False, indent=2)
            print(f"[4단계] 심층분석 완료 -> {os.path.basename(analysis_path)}")
            
        except Exception as e:
            print(f"[4단계] 심층분석 실패: {str(e)}")
            import traceback
            traceback.print_exc()
    else:
        print("\n[알림] 심층분석 생성을 위한 파일이 없습니다.")

    print("\n" + "=" * 60)
    print(f"모든 작업이 완료되었습니다!")
    print(f"\n결과 확인:")
    print(f"  - 파싱 결과: {OUTPUT_FOLDER}/")
    print(f"  - 섹션 분리: {SECTIONS_FOLDER}/")
    print(f"  - 분석 결과: {ANALYSIS_FOLDER}/")
    if checklist_chunks:
        print(f"    · checklist.json (공고 + 자격요건)")
    if analysis_chunks:
        print(f"    · analysis.json (공고 + RFP)")
    print("=" * 60)

if __name__ == "__main__":
    main()