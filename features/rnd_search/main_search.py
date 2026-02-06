#main_search.py
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

def main(notice_id=None, notice_text=None):
    """
    유관 RFP 검색 메인 함수
    
    Args:
        notice_id: 공고 ID (부처명 보정용, 선택적)
        notice_text: 파싱된 공고문 텍스트 (필수)
    """
    print("=" * 60)
    print(f"[Step 2] 유관 RFP 검색 (ID: {notice_id})")
    
    # 1. 공고 정보 준비
    notice_title = "업로드된 공고문"
    notice_ministry = ""
    query_text = ""
    
    # (A) notice_text가 전달된 경우 (파일 업로드)
    if notice_text:
        print(f"  📄 파일에서 파싱한 텍스트 사용")
        query_text = notice_text[:2000]  # 처음 2000자 사용
        
        # notice_id가 있으면 MySQL에서 부처명만 조회 (보정용)
        if notice_id:
            info = get_notice_info_by_id(notice_id)
            if info:
                notice_ministry = info.get('author', "")
                notice_title = info.get('title', notice_title)
                print(f"  ✅ MySQL에서 부처명 조회: {notice_ministry}")
        else:
            print(f"  ⚠️ notice_id 없음 - 부처명 필터링 없이 검색")
    
    # (B) notice_text가 없는 경우 (기존 방식 - DB에서 전부 조회)
    else:
        print(f"  📋 MySQL에서 공고 정보 조회")
        if notice_id:
            info = get_notice_info_by_id(notice_id)
            if info:
                notice_title = info.get('title', notice_title)
                notice_ministry = info.get('author', "")
                notice_summary = info.get('title', "")
                query_text = f"{notice_title} {notice_summary}"
                print(f"  ✅ 제목: {notice_title[:40]}...")
                print(f"  ✅ 부처: {notice_ministry}")
            else:
                print(f"  ❌ 공고 정보 조회 실패")
                return {"error": "공고 정보를 찾을 수 없습니다."}
        else:
            print(f"  ❌ notice_id 없음")
            return {"error": "notice_id 또는 notice_text가 필요합니다."}
    
    print(f"  🔍 검색 쿼리: {query_text[:50]}...")
    print(f"  🏛️ 소관 부처: {notice_ministry if notice_ministry else '없음 (전체 검색)'}")

    # 2. 벡터 DB 검색
    try:
        search_results = search_two_tracks(
            notice_text=query_text,
            ministry_name=notice_ministry,
            top_k_a=10,
            top_k_b=10,
            score_threshold=72.9
        )
        
        track_a = search_results['track_a']
        track_b = search_results['track_b']
        
        print(f"  ✅ 검색 완료: Track A {len(track_a)}건, Track B {len(track_b)}건")
        
    except Exception as e:
        print(f"  ❌ [오류] 벡터 DB 검색 실패: {e}")
        track_a = []
        track_b = []

    # 3. LLM 분석
    print("  🤖 [AI] 전략계획서 본문 기반 심층 분석 중...")
    report_json = summarize_report(
        new_project_info={
            "project_name": notice_title, 
            "summary": query_text[:500]  # 요약은 500자만
        },
        track_a=track_a,
        track_b=track_b
    )

    # 4. 저장
    try:
        with open(REPORT_FILE, 'w', encoding='utf-8') as f:
            json.dump(report_json, f, ensure_ascii=False, indent=2)
        print(f"  💾 리포트 저장 완료: {REPORT_FILE}")
    except Exception as e:
        print(f"  ⚠️ 리포트 저장 실패: {e}")
    
    return report_json

if __name__ == "__main__":
    # 테스트용
    main(notice_id=1)