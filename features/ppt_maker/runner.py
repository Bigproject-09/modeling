import os
import sys
import json
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

# ---------------------------------------------------------
# [경로 설정] 핵심!
# runner.py 위치: .../features/ppt_maker/runner.py
# 우리가 필요한 루트: .../MODELING
# ---------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))  # ppt_maker
parent_dir = os.path.dirname(current_dir)                 # features
project_root = os.path.dirname(parent_dir)                # MODELING (루트)

# 1. 루트 경로 추가 (하위 노드들이 document_parsing 등을 찾을 수 있게 함)
sys.path.append(project_root)

# 2. 현재 폴더 경로 명시 (nodes_code를 잘 찾게 함)
sys.path.append(current_dir)
# [수정됨] 폴더 이름이 'nodes_code'로 바뀌었으므로 여기를 수정합니다.
from nodes_code.state import GraphState
from nodes_code.lg_analysis_node import analyze_node
from nodes_code.lg_writer_node import writer_node

load_dotenv()

# ====================================================
# 2. 노드 래퍼(Wrapper) 정의
# ====================================================
# writer_node 함수는 하나지만, 8명의 직원이 필요하므로
# 각자의 '이름표(section)'를 달아주는 중간 함수를 만듭니다.

def node_agency_intro(state):
    return writer_node(state, "agency_intro", 1)

def node_project_overview(state):
    return writer_node(state, "project_overview", 2)

def node_research_necessity(state):
    return writer_node(state, "research_necessity", 3)

def node_research_goal(state):
    return writer_node(state, "research_goal", 4)

def node_research_content(state):
    return writer_node(state, "research_content", 5)

def node_promotion_plan(state):
    return writer_node(state, "promotion_plan", 6)

def node_expected_outcome(state):
    return writer_node(state, "expected_outcome", 7)

def node_utilization_plan(state):
    return writer_node(state, "utilization_plan", 8)

# ====================================================
# 3. 그래프(Workflow) 조립하기
# ====================================================
print("[시스템] 랭그래프 조립을 시작합니다...")

# (1) 그래프 뼈대 만들기 (State 모양 정의)
workflow = StateGraph(GraphState)

# (2) 노드 등록 (직원 채용 및 배치)
workflow.add_node("PM_Analysis", analyze_node)

workflow.add_node("Writer_1_Intro", node_agency_intro)
workflow.add_node("Writer_2_Overview", node_project_overview)
workflow.add_node("Writer_3_Necessity", node_research_necessity)
workflow.add_node("Writer_4_Goal", node_research_goal)
workflow.add_node("Writer_5_Content", node_research_content)
workflow.add_node("Writer_6_Promotion", node_promotion_plan)
workflow.add_node("Writer_7_Outcome", node_expected_outcome)
workflow.add_node("Writer_8_Utilization", node_utilization_plan)

# (3) 엣지 연결 (업무 순서 정하기)
# 시작점 설정: 무조건 PM부터 시작
workflow.set_entry_point("PM_Analysis")

# PM이 끝나면 -> 8명의 작가에게 동시에 업무 지시 (Fan-Out)
# 리스트로 나열하면 병렬(Parallel) 실행됩니다.
writers = [
    "Writer_1_Intro", "Writer_2_Overview", "Writer_3_Necessity",
    "Writer_4_Goal", "Writer_5_Content", "Writer_6_Promotion",
    "Writer_7_Outcome", "Writer_8_Utilization"
]

for writer in writers:
    # PM -> 작가 연결
    workflow.add_edge("PM_Analysis", writer)
    # 작가 -> 끝(END) 연결
    # (나중에 여기에 'PPT 생성 노드'를 연결할 예정입니다)
    workflow.add_edge(writer, END)

# (4) 컴파일 (기계 조립 완료)
app = workflow.compile()

print("[시스템] 조립 완료! 실행 준비 끝.")

# ====================================================
# 4. 실제 실행 (Run) 및 저장
# ====================================================
if __name__ == "__main__":
    
    initial_state = {"rfp_text": ""}  # 파일 자동 로드
    final_slides = [] # 결과 모음집
    project_title = "Unknown_Project"

    print("\n🚀 [LangGraph] 제안서 작성 프로젝트 시작!")
    
    # stream을 돌면서 나오는 결과들을 하나씩 주워 담습니다.
    for event in app.stream(initial_state):
        for key, value in event.items():
            print(f"\n✅ [완료된 작업]: {key}")
            
            # 1. PM 분석 결과 저장
            if key == "PM_Analysis":
                if 'analyzed_json' in value and 'project_summary' in value['analyzed_json']:
                    project_title = value['analyzed_json']['project_summary'].get('title', '제목 없음')
                    print(f"   ▶ 과제명: {project_title}")

            # 2. 슬라이드 결과 저장 (리스트에 추가)
            if "slides" in value:
                slide = value['slides'][0]
                final_slides.append(slide) # 결과 수집
                print(f"   📘 [슬라이드 생성 완료] {slide.get('section')} (Page {slide.get('page_number')})")
                print(f"      제목: {slide.get('title')}")
    
    # -------------------------------------------------------
    # [결과 저장] JSON 파일로 예쁘게 떨구기
    # -------------------------------------------------------
    print("\n💾 결과를 파일로 저장하는 중...")
    
    # 페이지 번호 순서대로 정렬 (1페이지 -> 8페이지)
    final_slides.sort(key=lambda x: x['page_number'])
    
    output_data = {
        "project_title": project_title,
        "total_slides": len(final_slides),
        "slides": final_slides
    }
    
    # 파일명: ppt_result.json
    output_path = os.path.join(current_dir, "ppt_result.json")
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
        
    print(f"🎉 저장 완료! 아래 파일을 열어서 내용을 확인해보세요:\n   -> {output_path}")