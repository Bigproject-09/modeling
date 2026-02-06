"""
4개 노드 테스트용 메인 파일
- 분석 노드 → 4개 슬라이드 노드 실행
- 최종 결과 검증
"""
import sys
import os
import json
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
# ==========================================
# [경로 긴급 수정] 시스템 경로에 프로젝트 루트 추가
# ==========================================
# 1. 현재 파일(test_4_nodes.py)의 절대 경로를 구합니다.
current_file_path = os.path.abspath(__file__)

# 2. 부모 폴더들을 거슬러 올라가서 프로젝트 루트(MODELING 폴더)를 찾습니다.
nodes_code_dir = os.path.dirname(current_file_path) # .../nodes_code
ppt_maker_dir = os.path.dirname(nodes_code_dir)     # .../ppt_maker
features_dir = os.path.dirname(ppt_maker_dir)       # .../features
project_root = os.path.dirname(features_dir)        # .../modeling (여기가 루트!)

# 3. 파이썬이 이 경로를 알 수 있게 sys.path에 추가합니다.
sys.path.append(project_root)

# ------------------------------------------
# 이제 'features' 패키지를 찾을 수 있습니다.
# ------------------------------------------
# State 정의 (subtitle 추가된 버전 사용)
from features.ppt_maker.nodes_code.state import GraphState, validate_analyzed_json, validate_slide

# 노드들 import
from features.ppt_maker.nodes_code.lg_analysis_node import analyze_node
from features.ppt_maker.nodes_code.agency_intro_node import agency_intro_node
from features.ppt_maker.nodes_code.goal_node import goal_node
from features.ppt_maker.nodes_code.promotion_node import promotion_node
from features.ppt_maker.nodes_code.content_node import content_node

load_dotenv()


def build_test_graph():
    """
    4개 노드만 테스트하는 그래프 구성
    
    워크플로우:
    analyze → (agency_intro, goal, promotion, content) → END
    """
    
    workflow = StateGraph(GraphState)
    
    # 1. 노드 등록
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("agency_intro", agency_intro_node)
    workflow.add_node("goal", goal_node)
    workflow.add_node("promotion", promotion_node)
    workflow.add_node("content", content_node)
    
    # 2. 엣지 설정
    workflow.set_entry_point("analyze")
    
    # analyze → 4개 노드로 병렬 분기
    workflow.add_edge("analyze", "agency_intro")
    workflow.add_edge("analyze", "goal")
    workflow.add_edge("analyze", "promotion")
    workflow.add_edge("analyze", "content")
    
    # 4개 노드 → END
    workflow.add_edge("agency_intro", END)
    workflow.add_edge("goal", END)
    workflow.add_edge("promotion", END)
    workflow.add_edge("content", END)
    
    return workflow.compile()


def print_slide_summary(slides: list):
    """슬라이드 요약 출력"""
    
    if not slides:
        print("  ⚠️  생성된 슬라이드 없음")
        return
    
    # 섹션별로 그룹화
    sections = {}
    for slide in slides:
        section = slide.get("section", "Unknown")
        if section not in sections:
            sections[section] = []
        sections[section].append(slide)
    
    print(f"\n{'='*80}")
    print(f"총 {len(slides)}장의 슬라이드 생성")
    print(f"{'='*80}\n")
    
    for section, section_slides in sections.items():
        print(f"[{section}] ({len(section_slides)}장)")
        for i, slide in enumerate(section_slides, 1):
            print(f"  {i}. {slide.get('title', 'N/A')}")
            if slide.get('subtitle'):
                print(f"     부제: {slide['subtitle']}")
            
            # 내용 미리보기 (첫 줄만)
            content = slide.get('content', '')
            first_line = content.split('\n')[0] if content else ''
            if len(first_line) > 60:
                first_line = first_line[:60] + "..."
            print(f"     내용: {first_line}")
            
            # 이미지 요청 여부
            if slide.get('image_request'):
                img_preview = slide['image_request'][:50] + "..." if len(slide['image_request']) > 50 else slide['image_request']
                print(f"     이미지: {img_preview}")
            
            # 유효성 검사
            is_valid = validate_slide(slide)
            status = "✓" if is_valid else "✗"
            print(f"     상태: {status}")
            print()


def save_results(final_state: dict, output_dir: str = "test_outputs"):
    """테스트 결과 저장"""
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. analyzed_json 저장
    analyzed_path = os.path.join(output_dir, "analyzed_json.json")
    with open(analyzed_path, "w", encoding="utf-8") as f:
        json.dump(final_state.get("analyzed_json", {}), f, indent=2, ensure_ascii=False)
    print(f"[저장] {analyzed_path}")
    
    # 2. slides 저장
    slides_path = os.path.join(output_dir, "slides.json")
    with open(slides_path, "w", encoding="utf-8") as f:
        json.dump(final_state.get("slides", []), f, indent=2, ensure_ascii=False)
    print(f"[저장] {slides_path}")
    
    # 3. 요약 보고서 저장
    report_path = os.path.join(output_dir, "test_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("4개 노드 테스트 보고서\n")
        f.write("=" * 80 + "\n\n")
        
        # analyzed_json 요약
        analyzed = final_state.get("analyzed_json", {})
        if analyzed and "error" not in analyzed:
            summary = analyzed.get("project_summary", {})
            f.write("[과제 정보]\n")
            f.write(f"제목: {summary.get('title', 'N/A')}\n")
            f.write(f"부제: {summary.get('subtitle', 'N/A')}\n")
            f.write(f"수행기간: {summary.get('period', 'N/A')}\n")
            f.write(f"예산: {summary.get('budget', 'N/A')}\n")
            f.write(f"키워드: {', '.join(summary.get('keywords', []))}\n\n")
        
        # 슬라이드 통계
        slides = final_state.get("slides", [])
        f.write(f"[생성 슬라이드]\n")
        f.write(f"총 {len(slides)}장\n\n")
        
        sections = {}
        for slide in slides:
            section = slide.get("section", "Unknown")
            sections[section] = sections.get(section, 0) + 1
        
        for section, count in sections.items():
            f.write(f"  {section}: {count}장\n")
        
        f.write("\n[슬라이드 상세]\n")
        for i, slide in enumerate(slides, 1):
            f.write(f"\n{i}. [{slide.get('section')}] {slide.get('title')}\n")
            if slide.get('subtitle'):
                f.write(f"   부제: {slide['subtitle']}\n")
            f.write(f"   내용:\n")
            for line in slide.get('content', '').split('\n'):
                if line.strip():
                    f.write(f"     {line}\n")
            if slide.get('image_request'):
                f.write(f"   이미지 프롬프트: {slide['image_request']}\n")
    
    print(f"[저장] {report_path}")


def run_test(rfp_text: str = ""):
    """
    4개 노드 테스트 실행
    
    Args:
        rfp_text: RFP 텍스트 (비어있으면 자동 로드)
    """
    
    print("\n" + "=" * 80)
    print("4개 노드 테스트 시작")
    print("=" * 80 + "\n")
    
    # 1. 그래프 빌드
    print("[1단계] 그래프 빌드 중...")
    app = build_test_graph()
    print("  ✓ 그래프 빌드 완료\n")
    
    # 2. 초기 State
    initial_state = {
        "rfp_text": rfp_text,
        "analyzed_json": {},
        "slides": [],
        "final_ppt_path": ""
    }
    
    # 3. 실행
    try:
        print("[2단계] 분석 노드 실행 중...")
        print("-" * 80)
        
        final_state = app.invoke(initial_state)
        
        print("\n" + "=" * 80)
        print("테스트 완료!")
        print("=" * 80)
        
        # 4. 결과 검증
        print("\n[3단계] 결과 검증")
        print("-" * 80)
        
        # analyzed_json 검증
        analyzed_json = final_state.get("analyzed_json", {})
        is_valid, message = validate_analyzed_json(analyzed_json)
        
        print(f"\n✓ analyzed_json 검증: {message}")
        
        if not is_valid:
            print("  ⚠️  경고: 분석 결과에 문제가 있습니다.")
            return final_state
        
        # 슬라이드 검증
        slides = final_state.get("slides", [])
        print(f"✓ 생성된 슬라이드: {len(slides)}장")
        
        invalid_slides = [s for s in slides if not validate_slide(s)]
        if invalid_slides:
            print(f"  ⚠️  경고: {len(invalid_slides)}장의 슬라이드가 유효하지 않음")
        
        # 5. 요약 출력
        print_slide_summary(slides)
        
        # 6. 결과 저장
        print("[4단계] 결과 저장")
        print("-" * 80)
        save_results(final_state)
        
        print("\n" + "=" * 80)
        print("✅ 모든 테스트 완료!")
        print("=" * 80)
        
        return final_state
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """메인 실행 함수"""
    
    # 환경변수 확인
    required_keys = ["GEMINI_API_KEY"]
    missing = [k for k in required_keys if not os.environ.get(k)]
    
    if missing:
        print(f"❌ 환경변수 누락: {', '.join(missing)}")
        print("   .env 파일에 API 키를 설정해주세요.")
        return
    
    print("=" * 80)
    print("환경변수 확인 완료")
    print("=" * 80)
    
    # 테스트 실행
    result = run_test()
    
    if result:
        print("\n✅ 테스트 성공!")
        print("\n다음 단계:")
        print("  1. test_outputs/ 폴더의 결과 파일 확인")
        print("  2. analyzed_json.json 에서 PM의 분석 품질 검토")
        print("  3. slides.json 에서 각 노드의 슬라이드 품질 검토")
        print("  4. 문제가 있다면 프롬프트 개선 후 재실행")
    else:
        print("\n❌ 테스트 실패")


if __name__ == "__main__":
    main()