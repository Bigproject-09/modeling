import os
import glob
from document_parsing import UniversalParser
from section import SectionSplitter, verify_sections

def main():
    # ---------------------------------------------------------
    # 아래 부분을 맞게 수정
    # ---------------------------------------------------------
    # 파싱할 파일들이 있는 입력 폴더
    INPUT_FOLDER = "data/input" 
    
    # 결과물을 저장할 출력 폴더
    OUTPUT_FOLDER = "data/output"
    # 섹션 분리 결과 저장 폴더
    SECTIONS_FOLDER = "data/sections"
    
    # ---------------------------------------------------------
    # [준비] 폴더 생성 및 파서 초기화
    # ---------------------------------------------------------
    if not os.path.exists(INPUT_FOLDER):
        print(f"[알림] 입력 폴더 '{INPUT_FOLDER}'가 없습니다. 폴더를 생성해 주세요.")
        os.makedirs(INPUT_FOLDER, exist_ok=True)
        return

    # 섹션 폴더 생성
    os.makedirs(SECTIONS_FOLDER, exist_ok=True)
    
    # 파서 객체 생성
    parser = UniversalParser(output_dir=OUTPUT_FOLDER)

    # 처리할 파일 목록 가져오기 (PDF, DOCX)
    files_to_process = []
    for ext in ['*.pdf', '*.docx']:
        files_to_process.extend(glob.glob(os.path.join(INPUT_FOLDER, ext)))

    if not files_to_process:
        print(f"[정보] '{INPUT_FOLDER}' 폴더에 처리할 PDF나 DOCX 파일이 없습니다.")
        return

    print(f"[*] 총 {len(files_to_process)}개의 파일을 발견했습니다. 작업을 시작합니다.")

    # ---------------------------------------------------------
    # [실행] 반복문을 돌며 파일 처리
    # ---------------------------------------------------------
    for file_path in files_to_process:
        try:
            # parser_utils의 기능을 호출합니다.
            result_path = parser.process_file(file_path)
            if result_path:
                print(f"  [성공] {os.path.basename(file_path)} -> {os.path.basename(result_path)}")
                # 파싱된 JSON을 섹션별로 분리
                # 섹션 결과 파일명: 원본파일명 기반으로 생성
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                sections_output_path = os.path.join(SECTIONS_FOLDER, f"{base_name}_sections.json")

                splitter = SectionSplitter(result_path)
                sections = splitter.save_sections(sections_output_path, format='json')

                # (선택) 검증 출력
                # verify_sections(sections, verbose=True)
        except Exception as e:
            print(f"  [실패] {os.path.basename(file_path)}: {str(e)}")

    print("-" * 50)
    print(f"[*] 모든 작업이 완료되었습니다. 결과물: {OUTPUT_FOLDER}")

if __name__ == "__main__":
    main()