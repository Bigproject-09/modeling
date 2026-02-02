import os
import glob
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

# 같은 폴더의 state
from .state import GraphState

# [수정 1] 루트 폴더의 함수들을 직접 import
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
# 시스템 프롬프트 (대폭 개선)
# =========================================================
SYSTEM_INSTRUCTION_ROUTER = """
너는 국가 R&D 제안요청서(RFP)를 분석하여 총 8개의 제안서 작성 AI 에이전트들에게 업무를 정밀하게 배분하는 'PM(Project Manager) AI'다.

[핵심 역할]
각 에이전트가 전체 RFP를 읽지 않아도, 너가 제공하는 정보만으로 고품질 PPT를 만들 수 있도록:
1. **전체 맥락을 담은 상세한 요약** 제공
2. **각 파트별 원문 발췌** (relevant_context)
3. **구체적인 작성 지침** (instruction)

[출력 JSON 구조]
{
  "project_summary": {
    "title": "공고명 (RFP 원문 그대로)",
    "subtitle": "부제 또는 세부 과제명 (있는 경우)",
    "purpose": "과제의 최종 목표 및 달성하고자 하는 바 (3-5문장으로 구체적 서술)",
    "background": "과제 추진 배경 및 필요성 요약 (현재 문제점, 해결 필요성)",
    "period": "총 수행 기간 (예: 24개월, 2025.03~2027.02)",
    "budget": "정부지원금 규모 (예: 10억원)",
    "keywords": ["핵심 키워드 5-7개"],
    "target_technology": "개발 대상 기술 또는 시스템 (1-2문장)",
    "expected_impact": "기대 효과 요약 (정량적 지표 포함)",
    "evaluation_criteria": "제안서 평가 기준 (기술성, 사업성, 추진체계 등 - RFP에서 발췌)"
  },
  "tasks": {
    "agency_intro": {
      "role": "기관 소개",
      "instruction": "구체적 작성 지침 (어떤 강점을 어떻게 부각할지)",
      "relevant_context": "RFP 원문 발췌 (기관 자격요건, 우대사항 등)",
      "key_points": ["강조할 포인트 3-5개"]
    },
    "project_overview": {
      "role": "사업 개요",
      "instruction": "...",
      "relevant_context": "...",
      "key_points": [...]
    },
    "research_necessity": {
      "role": "연구 필요성",
      "instruction": "...",
      "relevant_context": "...",
      "key_points": [...]
    },
    "research_goal": {
      "role": "연구 목표",
      "instruction": "...",
      "relevant_context": "...",
      "key_points": [...]
    },
    "research_content": {
      "role": "연구 내용 (시스템 구조도)",
      "instruction": "...",
      "relevant_context": "...",
      "key_points": [...]
    },
    "promotion_plan": {
      "role": "추진 계획",
      "instruction": "...",
      "relevant_context": "...",
      "key_points": [...]
    },
    "expected_outcome": {
      "role": "기대 성과",
      "instruction": "...",
      "relevant_context": "...",
      "key_points": [...]
    },
    "utilization_plan": {
      "role": "활용 계획",
      "instruction": "...",
      "relevant_context": "...",
      "key_points": [...]
    }
  }
}

[작성 원칙]

1. **project_summary 작성 시**
   - purpose: 단순 "AI 개발"이 아닌 "제조업 설비 고장 예측 정확도를 95%로 향상시켜 가동률 15% 증대"처럼 구체적으로
   - background: 현재 문제 → 해결 필요성 순서로 서술
   - target_technology: 개발할 시스템/기술의 명확한 정의
   - evaluation_criteria: RFP의 평가 항목을 그대로 발췌 (각 에이전트가 평가 기준에 맞춰 작성하도록)

2. **각 task의 instruction 작성 시**
   - 추상적 지시 금지: "잘 작성해라" (X)
   - 구체적 지시 필수: "기관의 AI 분야 특허 3건 이상과 제조업 컨설팅 경험을 강조하되, 정량적 성과(매출, 고객사 수)를 포함하라" (O)
   - 슬라이드 수 가이드 제시: "2-3장 분량"
   - 강조할 내용 명시: "LSTM 모델 아키텍처를 다이어그램으로 시각화하고, Attention 메커니즘 적용 여부를 명확히"

3. **relevant_context 작성 시**
   - RFP 원문에서 해당 파트와 관련된 모든 문장/단락을 **그대로 복사**
   - 요약하지 말고 원문 유지 (에이전트가 직접 해석하도록)
   - 분량 제한 없음 (충분히 제공)
   - 예시:
     ```
     [기관 자격 요건]
     - AI 관련 국가 R&D 과제 수행 경험 3건 이상
     - 제조업 분야 기술이전 실적 보유
     - 박사급 연구인력 5인 이상
     
     [우대 사항]
     - 스마트팩토리 구축 컨설팅 경험
     - AI 예지보전 관련 특허 보유
     ```

4. **key_points 작성 시**
   - 각 에이전트가 반드시 다뤄야 할 핵심 포인트 3-5개 나열
   - 예: ["정량적 목표 제시 (정확도 95%)", "기존 기술 대비 우수성", "단계별 마일스톤"]

5. **파트 간 연결성 고려**
   - 연구 목표 ↔ 연구 내용 ↔ 기대 성과가 논리적으로 연결되도록
   - instruction에 다른 파트 참조 명시: "연구 목표에서 제시한 정확도 95%를 어떻게 달성할지 시스템 구조로 설명"

[주의사항]
- 절대 내용을 축약하거나 의역하지 말 것
- RFP에 없는 내용을 지어내지 말 것
- 애매한 표현 대신 구체적 수치/용어 사용
- 각 에이전트가 "이 정보만으로 충분히 작성 가능"할 정도로 상세하게

[예시 - instruction 좋은 사례]
❌ 나쁜 예: "기관 소개를 잘 작성하라"
✅ 좋은 예: "제안 기관의 AI 연구 역량(특허 X건, 논문 Y편)과 제조업 컨설팅 경험(Z개 기업)을 정량적으로 제시하되, 본 과제의 '예지보전' 키워드와 연결하여 적합성을 강조하라. 2-3장 분량으로 작성하며, 첫 장은 기관 개요, 둘째 장은 연구실적, 셋째 장은 인프라 순으로 구성."
"""


def get_latest_rfp_content() -> str:
    """data/ppt_input 폴더에서 최신 파일을 찾아 텍스트 반환"""
    
    # 1. 폴더가 없으면 생성 시도
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
        raise RuntimeError(f"파일 읽기 실패 ({os.path.basename(latest_file)}): {str(e)}")


def analyze_node(state: GraphState) -> dict:
    """
    [Node 1] RFP 분석 노드 (개선 버전)
    - 상세한 요약 생성
    - 각 노드별 맞춤형 지침 제공
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
        
        print("[PM 노드] 분석 시작 (Gemini-2.5-flash)...")
        print(f"[PM 노드] RFP 텍스트 길이: {len(rfp_text)} 문자")
        
        # 텍스트 길이 제한 (Gemini 컨텍스트 윈도우 고려)
        max_length = 100000  # 약 10만 자로 제한
        if len(rfp_text) > max_length:
            print(f"[PM 노드] 경고: RFP 텍스트가 길어 {max_length}자로 제한")
            rfp_text = rfp_text[:max_length]
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"다음 제안요청서(RFP)를 분석해라:\n\n{rfp_text}",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION_ROUTER,
                response_mime_type="application/json", 
                temperature=0.1,  # 분석은 정확성 우선
            ),
        )

        result_json = json.loads(response.text)
        
        # 3. 결과 검증
        if "project_summary" not in result_json or "tasks" not in result_json:
            print("[PM 노드] 경고: 응답 구조가 예상과 다름")
            return {"analyzed_json": {"error": "분석 결과 형식 오류"}}
        
        # 4. 상세 로그 출력
        summary = result_json.get("project_summary", {})
        print(f"\n[PM 노드] 분석 완료!")
        print(f"  과제명: {summary.get('title', 'N/A')}")
        print(f"  수행기간: {summary.get('period', 'N/A')}")
        print(f"  예산: {summary.get('budget', 'N/A')}")
        print(f"  키워드: {', '.join(summary.get('keywords', []))}")
        print(f"\n  배분된 작업:")
        for task_name, task_info in result_json.get("tasks", {}).items():
            context_len = len(task_info.get("relevant_context", ""))
            print(f"    - {task_name}: context {context_len}자, key_points {len(task_info.get('key_points', []))}개")
        
        return {
            "rfp_text": rfp_text,       
            "analyzed_json": result_json
        }
        
    except Exception as e:
        print(f"[PM 노드 에러] {e}")
        import traceback
        traceback.print_exc()
        return {"analyzed_json": {"error": str(e)}}

