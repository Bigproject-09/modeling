import os
import json
import sys

# 경로 설정
current_dir = os.path.dirname(os.path.abspath(__file__))
features_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(features_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from utils.db_lookup import get_notice_info_by_id

# [변경] utils.vector_db 파일에서 search_two_tracks 함수 import
from utils.vector_db import search_two_tracks 
from .search_llm import summarize_report

# 저장 경로
DATA_DIR = os.path.join(root_dir, "data")
REPORT_FILE = os.path.join(DATA_DIR, "report", "combined_report.json")
os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)

def main(notice_id=None):
    print("=" * 60)
    print(f"[Step 2] 전략계획서(RAG) 기반 정밀 분석 (ID: {notice_id})")
    
    # 1. 공고 정보 가져오기
    notice_title = "신규 기획 과제"
    notice_ministry = ""
    notice_summary = ""

    if notice_id:
        info = get_notice_info_by_id(notice_id)
        if info:
            notice_title = info.get('title', notice_title)
            notice_ministry = info.get('author', "") # author가 부처명
            notice_summary = info.get('title', "")
    
    query_text = f"{notice_title} {notice_summary}"
    print(f" 검색 쿼리: {query_text[:40]}...")
    print(f" 소관 부처: {notice_ministry}")

    # 2. 벡터 DB 검색
    try:
        #  여기서 search_two_tracks 호출
        search_results = search_two_tracks(
            notice_text=query_text,
            ministry_name=notice_ministry,
            top_k_a=10,
            top_k_b=10,
            score_threshold=72.9
        )
        
        track_a = search_results['track_a']
        track_b = search_results['track_b']
        
        print(f" 검색 완료: Track A {len(track_a)}건, Track B {len(track_b)}건")
        
    except Exception as e:
        print(f"[오류] 벡터 DB 검색 실패: {e}")
        track_a = []
        track_b = []

    # 3. LLM 분석
    print(" [AI] 전략계획서 본문 기반 심층 분석 중...")
    report_json = summarize_report(
        new_project_info={"project_name": notice_title, "summary": query_text},
        track_a=track_a,
        track_b=track_b
    )

    # 4. 저장
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        json.dump(report_json, f, ensure_ascii=False, indent=2)
    
    print(f" 리포트 저장 완료: {REPORT_FILE}")
    return report_json

if __name__ == "__main__":
    main(notice_id=1)
