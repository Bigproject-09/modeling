import os
import glob
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

# 같은 폴더의 state
from .state import GraphState

# [수정 1] 루트 폴더의 함수들을 직접 import 해야 밑에서 에러가 안 납니다.
from document_parsing import parse_docx_to_blocks, extract_text_from_pdf

load_dotenv()

# =========================================================
# [경로 설정] 파일 경로를 '절대 경로'로 확실하게 잡아줍니다.
# =========================================================
current_file_path = os.path.abspath(__file__)
nodes_code_dir = os.path.dirname(current_file_path) # .../nodes_code
ppt_maker_dir = os.path.dirname(nodes_code_dir)     # .../ppt_maker
features_dir = os.path.dirname(ppt_maker_dir)       # .../features
project_root = os.path.dirname(features_dir)        # .../MODELING (루트)

# 실제 데이터 폴더 위치: .../MODELING/data/ppt_input
RFP_INPUT_DIR = os.path.join(project_root, "data", "ppt_input")

print(f"[System] RFP 검색 경로: {RFP_INPUT_DIR}")

# =========================================================
# 시스템 프롬프트
# =========================================================
SYSTEM_INSTRUCTION_ROUTER = """
너는 국가 R&D 제안요청서(RFP)를 분석하여 총 8개의 제안서 작성 AI 에이전트들에게 업무를 정밀하게 배분하는 'PM(Project Manager) AI'다.
사용자가 제공하는 RFP 텍스트를 분석하여, 다음 JSON 구조로 응답해라.
반드시 JSON 포맷을 지키고, 마크다운이나 잡담은 포함하지 마라.

[작업 지침]
각 에이전트(task)에게 할당할 'relevant_context'는 요약하지 말고, RFP 원문에서 관련된 문장이나 단락을 **최대한 그대로 발췌**해서 넣어라.

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
    "agency_intro": { "role": "기관 소개", "instruction": "...", "relevant_context": "..." },
    "project_overview": { "role": "사업 개요", "instruction": "...", "relevant_context": "..." },
    "research_necessity": { "role": "연구 필요성", "instruction": "...", "relevant_context": "..." },
    "research_goal": { "role": "연구 목표", "instruction": "...", "relevant_context": "..." },
    "research_content": { "role": "연구 내용", "instruction": "...", "relevant_context": "..." },
    "promotion_plan": { "role": "추진 계획", "instruction": "...", "relevant_context": "..." },
    "expected_outcome": { "role": "기대 성과", "instruction": "...", "relevant_context": "..." },
    "utilization_plan": { "role": "활용 계획", "instruction": "...", "relevant_context": "..." }
  }
}
"""

def get_latest_rfp_content() -> str:
    """data/ppt_input 폴더에서 최신 파일을 찾아 텍스트 반환"""
    
    # 1. 폴더가 없으면 생성 시도 (혹시 모르니)
    os.makedirs(RFP_INPUT_DIR, exist_ok=True)
    
    # 2. 파일 검색
    files = glob.glob(os.path.join(RFP_INPUT_DIR, "*"))
    target_files = [f for f in files if f.lower().endswith(('.pdf', '.docx', '.txt', '.json'))]

    if not target_files:
        raise FileNotFoundError(f"오류: '{RFP_INPUT_DIR}' 폴더에 지원하는 파일(pdf, docx)이 없습니다.")

    # 3. 최신 파일 선택
    latest_file = max(target_files, key=os.path.getmtime)
    ext = os.path.splitext(latest_file)[1].lower()
    print(f"[PM 노드] 파일 로드: {os.path.basename(latest_file)}")

    try:
        # [수정 2] 파일 타입별 처리 (docx 추가)
        if ext == '.pdf':
            pdf_data_list = extract_text_from_pdf(latest_file)
            full_text = ""
            for page in pdf_data_list:
                full_text += f"\n--- Page {page['page_index'] + 1} ---\n" + "\n".join(page['texts']) + "\n"
            return full_text
            
        elif ext == '.docx':
            blocks = parse_docx_to_blocks(latest_file)
            return "\n".join([b['text'] for b in blocks if b['text']])
            
        elif ext == '.json':
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return json.dumps(data, ensure_ascii=False) if not isinstance(data, list) else str(data)
        
        else: # txt 등
            with open(latest_file, 'r', encoding='utf-8') as f:
                return f.read()
                
    except Exception as e:
        # 에러 나면 그냥 빈 문자열 리턴하지 말고 에러 메시지를 던지는 게 낫습니다.
        raise RuntimeError(f"파일 읽기 실패 ({os.path.basename(latest_file)}): {str(e)}")


def analyze_node(state: GraphState) -> dict:
    """
    [Node 1] RFP 분석 노드
    """
    try:
        # 1. 텍스트 가져오기
        rfp_text = state.get("rfp_text")
        if not rfp_text:
            rfp_text = get_latest_rfp_content()
        
        if not rfp_text:
             return {"analyzed_json": {"error": "RFP 텍스트를 읽을 수 없습니다."}}

        # 2. Gemini 호출
        api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        
        print("[PM 노드] 분석 시작 (Gemini-2.5)...")
        response = client.models.generate_content(
            model="gemini-2.5 flash",
            contents=f"다음 제안요청서(RFP)를 분석해라:\n\n{rfp_text[:70000]}", # 길이 제한 안전장치
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION_ROUTER,
                response_mime_type="application/json", 
                temperature=0.1, 
            ),
        )

        result_json = json.loads(response.text)
        print("[PM 노드] 분석 완료. State 업데이트함.")
        
        return {
            "rfp_text": rfp_text,       
            "analyzed_json": result_json
        }
        
    except Exception as e:
        print(f"[PM 노드 에러] {e}")
        # 에러 발생 시에도 멈추지 않도록 에러 정보를 담아 보냄
        return {"analyzed_json": {"error": str(e)}}

# [테스트 코드]
if __name__ == "__main__":
    # 테스트 할 때도 루트 경로가 sys.path에 있어야 document_parsing을 찾을 수 있습니다.
    import sys
    sys.path.append(project_root) # 이 파일만 단독 실행할 때를 대비해 경로 추가
    
    try:
        print("--- [TEST MODE] analyze_node 실행 ---")
        dummy_state = {"rfp_text": ""} 
        result_update = analyze_node(dummy_state)
        
        if "analyzed_json" in result_update:
            summary = result_update['analyzed_json'].get('project_summary', {})
            print("\n[성공] 분석 결과가 나왔습니다!")
            print(f"과제명: {summary.get('title')}")
            
            with open("debug_analysis_result.json", "w", encoding="utf-8") as f:
                json.dump(result_update['analyzed_json'], f, indent=2, ensure_ascii=False)
            print(" -> debug_analysis_result.json 저장 완료")
        else:
            print("[실패] 결과 없음")
            
    except Exception as e:
        print(f"[테스트 에러] {e}")