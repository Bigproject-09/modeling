# main_search.py
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
from utils.vector_db import search_two_tracks
from .search_llm import summarize_report

# 저장 경로
DATA_DIR = os.path.join(root_dir, "data")
REPORT_FILE = os.path.join(DATA_DIR, "report", "combined_report.json")
os.makedirs(os.path.dirname(REPORT_FILE), exist_ok=True)


def main(notice_id=None, notice_text=None, ministry_name=None):
    """
    유관 RFP 검색 메인 함수

    Args:
        notice_id: 공고 ID (부처명/제목 보정용, 선택적)
        notice_text: 파싱된 공고문 텍스트 (선택적이지만 있으면 우선)
        ministry_name: Spring이 이미 알고 있는 소관 부처명(선택적)
    """
    print("=" * 60)
    print(f"[Step 2] 유관 RFP 검색 (ID: {notice_id})")

    # 1) 기본값
    notice_title = "업로드된 공고문"
    notice_ministry = (ministry_name or "").strip()
    query_text = ""

    # 2) notice_text 우선으로 검색 쿼리 구성 (ministry_name 여부랑 무관하게)
    if notice_text and str(notice_text).strip():
        print("  📄 파일에서 파싱한 텍스트 사용")
        query_text = str(notice_text).strip()[:2000]

        # notice_id 있으면 제목만이라도 보정 (있으면 더 좋음)
        if notice_id:
            info = get_notice_info_by_id(notice_id)
            if info:
                notice_title = info.get("title", notice_title)

                # ministry_name이 비어있을 때만 DB로 보정
                if not notice_ministry:
                    notice_ministry = info.get("author", "") or ""
                    print(f"  ✅ MySQL에서 부처명 조회: {notice_ministry}")

    # 3) notice_text가 없으면 기존 DB 방식 fallback
    else:
        print("  📋 MySQL에서 공고 정보 조회(텍스트 없음 fallback)")
        if not notice_id:
            print("  ❌ notice_id 없음")
            return {"error": "notice_id 또는 notice_text가 필요합니다."}

        info = get_notice_info_by_id(notice_id)
        if not info:
            print("  ❌ 공고 정보 조회 실패")
            return {"error": "공고 정보를 찾을 수 없습니다."}

        notice_title = info.get("title", notice_title)
        if not notice_ministry:
            notice_ministry = info.get("author", "") or ""

        notice_summary = info.get("title", "")
        query_text = f"{notice_title} {notice_summary}".strip()[:2000]

        print(f"  ✅ 제목: {notice_title[:40]}...")
        print(f"  ✅ 부처: {notice_ministry}")

    if not query_text.strip():
        # 이 케이스가 나오면 upstream에서 notice_text를 못 만들었다는 뜻
        return {"error": "검색용 query_text가 비어있습니다. notice_text 생성/파싱을 확인하세요."}

    print(f"  🔍 검색 쿼리: {query_text[:50]}...")
    print(f"  🏛️ 소관 부처: {notice_ministry if notice_ministry else '없음 (전체 검색)'}")

    # 4) 벡터 DB 검색
    try:
        search_results = search_two_tracks(
            notice_text=query_text,
            ministry_name=notice_ministry,
            top_k_a=10,
            top_k_b=10,
            score_threshold=72.9
        )

        track_a = search_results.get("track_a", [])
        track_b = search_results.get("track_b", [])

        print(f"  ✅ 검색 완료: Track A {len(track_a)}건, Track B {len(track_b)}건")

    except Exception as e:
        print(f"  ❌ [오류] 벡터 DB 검색 실패: {e}")
        track_a = []
        track_b = []

    # 5) LLM 분석
    print("  🤖 [AI] 전략계획서 본문 기반 심층 분석 중...")
    report_json = summarize_report(
        new_project_info={
            "project_name": notice_title,
            "summary": query_text[:500]
        },
        track_a=track_a,
        track_b=track_b
    )

    # 6) 저장
    try:
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(report_json, f, ensure_ascii=False, indent=2)
        print(f"  💾 리포트 저장 완료: {REPORT_FILE}")
    except Exception as e:
        print(f"  ⚠️ 리포트 저장 실패: {e}")

    return report_json


if __name__ == "__main__":
    main(notice_id=1)
