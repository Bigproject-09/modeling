import os
import glob
import json
# 기존에 작성한 파싱 함수들이 들어있는 파일명을 import 하세요 (예: parser_utils.py)
from document_parsing import parse_docx_to_blocks, extract_text_from_pdf

from section import SectionSplitter, verify_sections

def main():
    # ---------------------------------------------------------
    # 경로 설정
    # ---------------------------------------------------------
    INPUT_FOLDER = "data/input" 
    OUTPUT_FOLDER = "data/parsing"
    SECTIONS_FOLDER = "data/sections"
    
    if not os.path.exists(INPUT_FOLDER):
        print(f"[알림] 입력 폴더 '{INPUT_FOLDER}'가 없습니다.")
        os.makedirs(INPUT_FOLDER, exist_ok=True)
        return

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    os.makedirs(SECTIONS_FOLDER, exist_ok=True)
    
    # 처리할 파일 목록
    files_to_process = []
    for ext in ['*.pdf', '*.docx']:
        files_to_process.extend(glob.glob(os.path.join(INPUT_FOLDER, ext)))

    if not files_to_process:
        print(f"[정보] 처리할 파일이 없습니다.")
        return

    print(f"[*] 총 {len(files_to_process)}개의 파일을 발견했습니다.")

    # ---------------------------------------------------------
    # [실행] 반복문을 돌며 파일 처리
    # ---------------------------------------------------------
    for file_path in files_to_process:
        try:
            filename = os.path.basename(file_path)
            name_only, ext = os.path.splitext(filename)
            ext = ext.lower()
            
            # 저장될 JSON 경로 설정 (기존 규칙: 파일명_parsing.json)
            result_path = os.path.join(OUTPUT_FOLDER, f"{name_only}_parsing.json")
            
            # --- [수정 포인트] 확장자에 따라 기존 함수 호출 ---
            if ext == ".docx":
                result = parse_docx_to_blocks(file_path, OUTPUT_FOLDER)
            elif ext == ".pdf":
                result = extract_text_from_pdf(file_path)
            else:
                continue
            
            # JSON 저장 (결과를 파일로 기록)
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            # ----------------------------------------------

            if os.path.exists(result_path):
                print(f"  [성공] {filename} -> {os.path.basename(result_path)}")
                
                # 섹션 분리 실행
                sections_output_path = os.path.join(SECTIONS_FOLDER, f"{name_only}_sections.json")
                splitter = SectionSplitter(result_path)
                sections = splitter.save_sections(sections_output_path, format='json')

        except Exception as e:
            print(f"  [실패] {os.path.basename(file_path)}: {str(e)}")

    print("-" * 50)
    print(f"[*] 모든 작업이 완료되었습니다.")

if __name__ == "__main__":
    main()