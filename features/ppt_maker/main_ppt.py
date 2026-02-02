# main_ppt.py
import os
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

# State 정의
from features.ppt_maker.nodes_code.state import GraphState

# 노드들 import
from features.ppt_maker.nodes_code.lg_analysis_node import analyze_node
from features.ppt_maker.nodes_code.overview_node import overview_node
from features.ppt_maker.nodes_code.necessity_node import necessity_node
# from features.ppt_maker.nodes_code.goal_node import goal_node
# from features.ppt_maker.nodes_code.content_node import content_node
# from features.ppt_maker.nodes_code.promotion_node import promotion_node
from features.ppt_maker.nodes_code.outcome_node import outcome_node
from features.ppt_maker.nodes_code.utilization_node import utilization_node
# from features.ppt_maker.nodes_code.agency_intro_node import agency_intro_node
# from features.ppt_maker.nodes_code.image_generation_node import image_generation_node
from features.ppt_maker.nodes_code.sort_node import sort_node
from features.ppt_maker.nodes_code.ppt_generation_node import ppt_generation_node

load_dotenv()

def build_graph():
    """LangGraph 워크플로우 구성"""
    
    # 1. StateGraph 생성
    workflow = StateGraph(GraphState)
    
    # 2. 노드 등록
    # Phase 1: RFP 분석 (1개 노드)
    workflow.add_node("analyze", analyze_node)
    
    # Phase 2: 슬라이드 생성 (8개 노드 - 병렬 실행)
    # workflow.add_node("overview", overview_node)
    workflow.add_node("necessity", necessity_node)
    # workflow.add_node("goal", goal_node)
    # workflow.add_node("content", content_node)
    # workflow.add_node("promotion", promotion_node)
    workflow.add_node("outcome", outcome_node)
    workflow.add_node("utilization", utilization_node)
    # workflow.add_node("agency_intro", agency_intro_node)
    
    # Phase 3: 이미지 생성 (1개 노드)
    # workflow.add_node("image_gen", image_generation_node)
    
    # Phase 4: 슬라이드 정렬 (1개 노드)
    workflow.add_node("sort", sort_node)
    
    # Phase 5: PPT 파일 생성 (1개 노드)
    workflow.add_node("generate_ppt", ppt_generation_node)
    
    # 3. 엣지(Edge) 설정
    # 시작 -> analyze
    workflow.set_entry_point("analyze")
    
    # analyze -> 8개 슬라이드 생성 노드로 분기 (병렬)
    workflow.add_edge("analyze", "overview")
    workflow.add_edge("analyze", "necessity")
    # workflow.add_edge("analyze", "goal")
    # workflow.add_edge("analyze", "content")
    # workflow.add_edge("analyze", "promotion")
    workflow.add_edge("analyze", "outcome")
    workflow.add_edge("analyze", "utilization")
    # workflow.add_edge("analyze", "agency_intro")
    
    # 모든 슬라이드 생성 완료 -> 이미지 생성
    # workflow.add_edge("overview", "image_gen")
    # workflow.add_edge("necessity", "image_gen")
    # workflow.add_edge("goal", "image_gen")
    # workflow.add_edge("content", "image_gen")
    # workflow.add_edge("promotion", "image_gen")
    # workflow.add_edge("outcome", "image_gen")
    # workflow.add_edge("utilization", "image_gen")
    # workflow.add_edge("agency_intro", "image_gen")
    
    # 이미지 생성 -> 정렬
    # workflow.add_edge("image_gen", "sort")
    
    # 정렬 -> PPT 생성
    workflow.add_edge("sort", "generate_ppt")
    
    # PPT 생성 -> 종료
    workflow.add_edge("generate_ppt", END)
    
    # 4. 그래프 컴파일
    app = workflow.compile()
    return app


def run_ppt_generation(rfp_text: str = ""):
    """
    PPT 생성 전체 프로세스 실행
    
    Args:
        rfp_text: RFP 텍스트 (비어있으면 자동으로 파일 로드)
    
    Returns:
        최종 State
    """
    print("=" * 80)
    print("PPT 자동 생성 시작")
    print("=" * 80)
    
    # 1. 그래프 빌드
    app = build_graph()
    
    # 2. 초기 State 설정
    initial_state = {
        "rfp_text": rfp_text,
        "analyzed_json": {},
        "slides": [],
        "final_ppt_path": ""
    }
    
    # 3. 실행
    try:
        print("\n[Phase 1] RFP 분석 중...")
        final_state = app.invoke(initial_state)
        
        print("\n" + "=" * 80)
        print("PPT 생성 완료!")
        print("=" * 80)
        
        # 결과 출력
        print(f"\n생성된 슬라이드 수: {len(final_state.get('slides', []))}")
        
        if final_state.get('final_ppt_path'):
            print(f"저장 경로: {final_state['final_ppt_path']}")
        
        # 각 슬라이드 정보 출력
        for i, slide in enumerate(final_state.get('slides', []), 1):
            print(f"\n  [{i}] {slide['section']} - {slide['title']}")
            if slide.get('image_request'):
                print(f"이미지: {slide['image_request'][:50]}...")
        
        return final_state
        
    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """메인 실행 함수"""
    
    # 환경변수 확인
    required_keys = ["GEMINI_API_KEY", "ANTHROPIC_API_KEY"]
    missing = [k for k in required_keys if not os.environ.get(k)]
    
    if missing:
        print(f"환경변수 누락: {', '.join(missing)}")
        print("   .env 파일에 API 키를 설정해주세요.")
        return
    
    # PPT 생성 실행
    result = run_ppt_generation()
    
    if result:
        print("\n작업 완료!")
    else:
        print("\n작업 실패")


if __name__ == "__main__":
    main()