# modeling/main_1.py

import os
import json
import glob
from dotenv import load_dotenv

# 사용자 정의 모듈 (같은 폴더에 있어야 함)
from utils.document_parsing import parse_docx_to_blocks, extract_text_from_pdf
from utils.vector_db import search_two_tracks
from utils.gemini_client import summarize_report
from utils.db_lookup import find_ministry_by_seq_author 

load_dotenv()

# =========================================================
# [설정] 분포 분석(calculate_threshold.py) 결과 적용
# =========================================================
SIMILARITY_THRESHOLD = 78.1
# =========================================================

def main():
    print("="*60)
    print(f"[시스템 시작] R&D 공고 유사 과제 분석 (임계값: {SIMILARITY_THRESHOLD}점)")
    print("="*60)
    
    # 1. 환경 변수 및 공고 정보 확인
    notice_seq = os.environ.get("NOTICE_SEQ", "20240101_TEST")
    notice_author = os.environ.get("NOTICE_AUTHOR", "")

    print(f"[*] 공고 번호: {notice_seq}")
    
    if not notice_author:
        print("[!] 부처명(NOTICE_AUTHOR) 누락. DB Lookup 시도...")
        try:
            notice_author = find_ministry_by_seq_author(notice_seq, notice_author)
            if notice_author:
                print(f"[*] DB 조회 성공: {notice_author}")
            else:
                print("[!] DB 조회 실패. 부처 필터링(Track A)이 건너뛰어질 수 있습니다.")
        except Exception as e:
            print(f"[!] DB 조회 중 오류: {e}")
    else:
        print(f"[*] 소관 부처: {notice_author}")

    # 2. 분석할 공고 파일 파싱
    input_folder = "data/notice_input"
    files = glob.glob(os.path.join(input_folder, "*.pdf")) + glob.glob(os.path.join(input_folder, "*.docx"))
    
    if not files:
        print(f"[!] 오류: '{input_folder}' 폴더에 분석할 공고 파일이 없습니다.")
        return

    target_file = files[0]
    print(f"[*] 분석 대상 파일: {os.path.basename(target_file)}")
    
    full_text = ""
    try:
        if target_file.endswith(".pdf"):
            parsed = extract_text_from_pdf(target_file)
            for page in parsed:
                full_text += " ".join(page.get("texts", [])) + "\n"
        elif target_file.endswith(".docx"):
            parsed = parse_docx_to_blocks(target_file, "data/parsing")
            full_text = str(parsed)
    except Exception as e:
        print(f"[오류] 파일 파싱 실패: {e}")
        return

    print(f"[*] 파싱 완료 (텍스트 길이: {len(full_text)}자)")

    # 3. 유사 과제 검색 (78.1점 이상만 통과)
    print(f"[*] 유사도 검색 시작 (Threshold: {SIMILARITY_THRESHOLD}점 이상만 통과)...")
    try:
        results = search_two_tracks(
            notice_text=full_text,
            ministry_name=notice_author,
            top_k_a=5,
            top_k_b=5,
            score_threshold=SIMILARITY_THRESHOLD # 필터링 적용
        )
    except Exception as e:
        print(f"[오류] 검색 엔진 구동 실패: {e}")
        return
    
    # 4. 결과 집계
    count_a = len(results.get('track_a', []))
    count_b = len(results.get('track_b', []))
    
    print("-" * 40)
    print(f" [검색 결과 요약]")
    print(f" - Track A (동일 부처): {count_a}건 매칭됨")
    print(f" - Track B (타  부처): {count_b}건 매칭됨")
    
    if count_a == 0 and count_b == 0:
        print(f"[!] 알림: 임계값({SIMILARITY_THRESHOLD}점)을 넘는 과제가 없습니다.")
        print("    (분석된 데이터 기준으로는 유사도가 낮은 과제들만 존재합니다.)")

    # 5. JSON 결과 저장
    output_path = "data/report/final_result.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    final_data = {
        "input_meta": {
            "seq": notice_seq, 
            "author": notice_author,
            "filename": os.path.basename(target_file),
            "threshold_used": SIMILARITY_THRESHOLD
        },
        "track_a_same_ministry": results.get('track_a', []),
        "track_b_diff_ministry": results.get('track_b', [])
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    print(f"[*] 결과 JSON 저장 완료: {output_path}")

    # 6. LLM 요약 리포트 생성
    if count_a > 0 or count_b > 0:
        print("[*] Gemini 요약 리포트 생성 중...")
        try:
            md_content = summarize_report(final_data)
            md_path = "data/report/combined_report.md"
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            print(f"[*] 리포트 생성 완료: {md_path}")
        except Exception as e:
            print(f"[오류] 리포트 생성 실패: {e}")
    else:
        print("[*] 매칭된 과제가 없어 리포트 생성을 생략합니다.")

    print("="*60)

if __name__ == "__main__":
    main()