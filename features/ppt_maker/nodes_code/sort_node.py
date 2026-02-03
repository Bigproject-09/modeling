"""
슬라이드 정렬 노드 (Sort Node)

역할:
- 모든 노드에서 생성된 슬라이드를 수집
- 노드 순서와 page_number에 따라 정렬
- 최종 페이지 번호 재부여

입력: GraphState의 slides 리스트
출력: 정렬된 slides 리스트
"""

from typing import List
from state import GraphState, SlideState


def sort_node(state: GraphState) -> dict:
    """
    슬라이드 정렬 노드
    
    Args:
        state: GraphState - 현재 워크플로우 상태
        
    Returns:
        dict: {"slides": List[SlideState]} - 정렬된 슬라이드 리스트
    """
    try:
        print("\n" + "="*60)
        print("[Sort Node] 슬라이드 정렬 시작")
        print("="*60)
        
        # 1. State에서 모든 슬라이드 가져오기
        all_slides: List[SlideState] = state.get("slides", [])
        
        if not all_slides:
            print("[Sort Node] 정렬할 슬라이드가 없습니다.")
            return {"slides": []}
        
        print(f"[Sort Node] 수집된 슬라이드: {len(all_slides)}개")
        
        # 2. 섹션 순서 정의 (워크플로우 노드 순서와 일치)
        # 이 순서는 실제 워크플로우 실행 순서와 동일하게 설정
        section_order = {
            "기관 소개": 1,
            "사업 개요": 2,
            "연구 필요성": 3,
            "연구 목표": 4,
            "연구 내용": 5,
            "추진 전략": 6,
            "추진 방법": 6,  # 추진 전략과 동일 순서
            "기대 성과": 7,
            "활용 계획": 8,
            "활용성": 8,  # 활용 계획과 동일 순서
        }
        
        # 3. 슬라이드를 섹션별로 그룹화
        slides_by_section = {}
        for slide in all_slides:
            section = slide.get("section", "기타")
            if section not in slides_by_section:
                slides_by_section[section] = []
            slides_by_section[section].append(slide)
        
        print(f"\n[Sort Node] 📑 섹션별 슬라이드 분포:")
        for section in slides_by_section:
            count = len(slides_by_section[section])
            print(f"  • {section}: {count}개")
        
        # 4. 각 섹션 내에서 page_number로 정렬
        for section in slides_by_section:
            slides_by_section[section].sort(
                key=lambda s: s.get("page_number", 999)
            )
        
        # 5. 섹션 순서대로 슬라이드 재배열
        sorted_slides = []
        
        # 정의된 순서대로 먼저 추가
        for section_name in sorted(slides_by_section.keys(), 
                                   key=lambda s: section_order.get(s, 999)):
            sorted_slides.extend(slides_by_section[section_name])
        
        # 6. 최종 페이지 번호 재부여 (1부터 시작)
        for idx, slide in enumerate(sorted_slides, start=1):
            slide["page_number"] = idx
        
        print(f"\n[Sort Node] 정렬 완료: 총 {len(sorted_slides)}개 슬라이드")
        print(f"\n[Sort Node] 최종 슬라이드 순서:")
        print("-" * 60)
        
        for slide in sorted_slides:
            page_num = slide['page_number']
            section = slide['section']
            title = slide['title']
            has_image = "🖼️ " if slide.get('image_path') else ""
            print(f"  {page_num:2d}. [{section:12s}] {has_image}{title}")
        
        print("="*60 + "\n")
        
        # 7. State 업데이트
        return {"slides": sorted_slides}
        
    except Exception as e:
        print(f"\n[Sort Node] 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        
        # 에러 발생 시 원본 슬라이드 그대로 반환
        print("[Sort Node] 원본 슬라이드를 그대로 반환합니다.")
        return {"slides": state.get("slides", [])}