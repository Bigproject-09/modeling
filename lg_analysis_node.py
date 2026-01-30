import os
import json
import glob
from dotenv import load_dotenv
from google import genai
from google.genai import types

# ▼ [추가됨] 우리가 만든 State와 PDF 파싱 도구 가져오기
from state import GraphState
from document_parsing import extract_text_from_pdf 

load_dotenv()

# =========================================================
# [설정] 파일 경로
# =========================================================
RFP_INPUT_DIR = os.path.join("data", "lang_graph")

# =========================================================
# 시스템 프롬프트 (내용은 기존과 동일합니다)
# =========================================================
SYSTEM_INSTRUCTION_ROUTER = """
너는 국가 R&D 제안요청서(RFP)를 분석하여 총 8개의 제안서 작성 AI 에이전트들에게 업무를 정밀하게 배분하는 'PM(Project Manager) AI'다.
사용자가 제공하는 RFP 텍스트를 분석하여, 다음 JSON 구조로 응답해라.
반드시 JSON 포맷을 지키고, 마크다운이나 잡담은 포함하지 마라.

[작업 지침]
각 에이전트(task)에게 할당할 'relevant_context'는 요약하지 말고, RFP 원문에서 관련된 문장이나 단락을 **최대한 그대로 발췌**해서 넣어라. 에이전트들이 원문을 보고 판단해야 하기 때문이다.

[출력 JSON 구조]
{
  "project_summary": {
    "title": "공고명",
    "purpose": "과제 목표 요약 (1~2문장)",
    "period": "총 수행 기간",
    "budget": "정부지원금 규모",
    "keywords": ["키워드1", "키워드2", "키워드3"]
  },
  "tasks": {
    "agency_intro": {
        "role": "기관 소개 (1. 기관 소개)",
        "instruction": "신청 자격, 우대 사항, 가점 사항을 고려하여 기관의 역량을 강조하는 작성 지침",
        "relevant_context": "RFP 내 '신청자격', '우대사항', '가점요인', '주관기관 요건' 관련 텍스트 발췌"
    },
    "project_overview": {
        "role": "사업 개요 (2. 사업 개요)",
        "instruction": "과제의 정의, 비전, 최종 목표를 포괄적으로 요약하는 작성 지침",
        "relevant_context": "RFP 내 '사업목적', '지원분야', '과제 개요' 관련 텍스트 발췌"
    },
    "research_necessity": {
        "role": "연구 필요성 (3. 연구 필요성)",
        "instruction": "기술적/경제적/사회적 중요성과 현재의 문제점(Pain Point)을 부각하는 작성 지침",
        "relevant_context": "RFP 내 '추진배경', '필요성', '현황 및 문제점', '시장 동향' 관련 텍스트 발췌"
    },
    "research_goal": {
        "role": "연구 목표 (4. 연구 목표)",
        "instruction": "최종 목표와 연차별 목표, 정량적 성능지표(TP/KPI)를 명확히 제시하는 작성 지침",
        "relevant_context": "RFP 내 '최종목표', '성과지표', '평가항목', 'TRL(기술성숙도)' 관련 텍스트 발췌"
    },
    "research_content": {
        "role": "연구 내용 및 시스템 구조 (5. 연구 내용)",
        "instruction": "세부 개발 내용과 시스템 아키텍처(구조도)를 구체적으로 기술하는 작성 지침",
        "relevant_context": "RFP 내 '연구내용', '개발범위', '기능 요구사항', '시스템 구성도 요구사항' 관련 텍스트 발췌"
    },
    "promotion_plan": {
        "role": "추진 계획 (6. 추진 계획)",
        "instruction": "기술개발 추진 전략, 추진 체계, 일정, 리스크 관리 계획을 수립하는 작성 지침",
        "relevant_context": "RFP 내 '추진전략', '추진체계', '추진일정', '컨소시엄 구성' 관련 텍스트 발췌"
    },
    "expected_outcome": {
        "role": "기대 성과 (7. 기대 성과)",
        "instruction": "기술적 파급효과, 경제적 매출 증대 효과, 사회적 기여도를 작성하는 지침",
        "relevant_context": "RFP 내 '기대효과', '파급효과' 관련 텍스트 발췌"
    },
    "utilization_plan": {
        "role": "활용 계획 (8. 활용 계획)",
        "instruction": "개발된 기술의 사업화 방안, 판로 개척, 후속 연구 계획을 작성하는 지침",
        "relevant_context": "RFP 내 '활용방안', '사업화 계획', '시장 진입 전략' 관련 텍스트 발췌"
    }
  }
}
"""

def get_latest_rfp_content() -> str:
    """data/lang 폴더에서 최신 파일을 찾아 텍스트 반환"""
    os.makedirs(RFP_INPUT_DIR, exist_ok=True)
    files = glob.glob(os.path.join(RFP_INPUT_DIR, "*"))
    
    if not files:
        raise FileNotFoundError(f"오류: '{RFP_INPUT_DIR}' 폴더가 비어있습니다.")

    latest_file = max(files, key=os.path.getmtime)
    ext = os.path.splitext(latest_file)[1].lower()
    print(f"[PM 노드] 파일 로드: {os.path.basename(latest_file)}")

    try:
        if ext == '.pdf':
            pdf_data_list = extract_text_from_pdf(latest_file)
            full_text = ""
            for page in pdf_data_list:
                full_text += f"\n--- Page {page['page_index'] + 1} ---\n" + "\n".join(page['texts']) + "\n"
            return full_text
        elif ext == '.json':
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return json.dumps(data, ensure_ascii=False) if not isinstance(data, list) else str(data)
        else:
            with open(latest_file, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception as e:
        return f"파일 읽기 오류: {str(e)}"

# ▼ [핵심 변경] State를 받아서 State 형식을 반환하도록 수정
def analyze_node(state: GraphState) -> dict:
    """
    [Node 1] RFP 분석 노드
    입력: State (비어있거나 rfp_text가 없을 수 있음)
    출력: State 업데이트 (rfp_text 채움, analyzed_json 채움)
    """
    # 1. 텍스트 가져오기 (이미 state에 있으면 그거 쓰고, 없으면 파일에서 읽기)
    rfp_text = state.get("rfp_text")
    if not rfp_text:
        rfp_text = get_latest_rfp_content()
    
    # 2. Gemini 호출
    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    
    print("[PM 노드] 분석 시작...")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"다음 제안요청서(RFP)를 분석해라:\n\n{rfp_text[:70000]}",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION_ROUTER,
            response_mime_type="application/json", 
            temperature=0.1, 
        ),
    )

    try:
        result_json = json.loads(response.text)
        print("[PM 노드] 분석 완료. State 업데이트함.")
        
        # ★ 중요: 전체 State를 다 리턴하는 게 아니라, "바뀐 부분"만 리턴하면 됩니다.
        return {
            "rfp_text": rfp_text,       # 텍스트 원본 저장
            "analyzed_json": result_json # 분석 결과 저장
        }
        
    except Exception as e:
        print(f"[오류] {e}")
        return {"analyzed_json": {"error": str(e)}}

# ▼ [테스트 코드 변경] 혼자 실행할 때도 '가짜 State'를 만들어서 테스트
if __name__ == "__main__":
    try:
        print("--- [TEST MODE] analyze_node 실행 ---")
        
        # 1. 가짜 빈 State 생성
        dummy_state = {"rfp_text": ""} 
        
        # 2. 노드 실행 (State가 업데이트되어 돌아옴)
        result_update = analyze_node(dummy_state)
        
        # 3. 결과 확인
        if "analyzed_json" in result_update:
            summary = result_update['analyzed_json'].get('project_summary', {})
            print("\n[성공] 분석 결과가 나왔습니다!")
            print(f"📌 과제명: {summary.get('title')}")
            print(f"📌 키워드: {summary.get('keywords')}")
            
            # 파일로도 한번 저장해볼까요? (확인용)
            with open("debug_analysis_result.json", "w", encoding="utf-8") as f:
                json.dump(result_update['analyzed_json'], f, indent=2, ensure_ascii=False)
            print(" -> 상세 내용은 'debug_analysis_result.json'에 저장됨.")
        else:
            print("[실패] 결과가 비어있습니다.")
            
    except Exception as e:
        print(f"[에러] {e}")