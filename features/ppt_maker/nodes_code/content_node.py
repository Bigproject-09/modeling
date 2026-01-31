"""
연구 내용 노드 (Research Content Node - System Architecture)
- 개발할 시스템의 구조, 핵심 기술, 알고리즘을 시각화
- 이미지: 시스템 아키텍처 다이어그램, 데이터 플로우, 기술 스택
"""

import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
from .state import GraphState, SlideState

load_dotenv()

# ============================================================
# 시스템 프롬프트
# ============================================================
SYSTEM_INSTRUCTION = """
너는 국가 R&D 제안서의 '연구 내용(시스템 구조도)' 파트를 작성하는 전문 AI 에이전트다.

[역할]
개발할 시스템의 전체 아키텍처, 핵심 기술 요소, 데이터 흐름을 평가위원이 이해하기 쉽게 시각화한다.

[입력]
1. project_summary: 과제 전체 요약
2. relevant_context: 시스템 구조 관련 RFP 요구사항
3. instruction: PM의 작성 가이드

[출력 형식]
JSON 배열로만 응답

[
  {
    "page_number": 1,
    "section": "연구 내용",
    "title": "전체 시스템 아키텍처",
    "content": "• 3-Tier 구조\\n  - Front-end: React 기반 웹 대시보드\\n  - Back-end: FastAPI 서버 (Python)\\n  - Database: PostgreSQL + Redis 캐시\\n• 핵심 모듈\\n  - 데이터 수집 모듈\\n  - AI 예측 엔진\\n  - 알람 및 리포팅 시스템",
    "image_request": "three-tier system architecture diagram with frontend, backend, database layers, clean technical illustration style",
    "image_position": "right:55%",
    "text_position": "left:40%"
  },
  {
    "page_number": 2,
    "section": "연구 내용",
    "title": "AI 예측 엔진 상세 구조",
    "content": "• 데이터 전처리\\n  - 센서 데이터 정규화 및 결측치 처리\\n  - Feature Engineering (통계량 추출)\\n• 모델 아키텍처\\n  - LSTM 기반 시계열 예측\\n  - Attention Mechanism 적용\\n  - Ensemble 기법 (3개 모델)\\n• 후처리\\n  - 임계값 기반 알람 생성\\n  - 신뢰도 스코어 계산",
    "image_request": "AI neural network architecture diagram with LSTM layers and attention mechanism, technical deep learning visualization",
    "image_position": "bottom:45%",
    "text_position": "top:50%"
  },
  {
    "page_number": 3,
    "section": "연구 내용",
    "title": "데이터 흐름도 (Data Flow)",
    "content": "1. 센서 데이터 수집 (실시간)\\n   → IoT 게이트웨이 → MQTT 프로토콜\\n2. 데이터 전처리 및 저장\\n   → 이상치 탐지 → DB 저장\\n3. AI 모델 추론\\n   → 5분마다 배치 예측 수행\\n4. 결과 시각화 및 알람\\n   → 웹 대시보드 업데이트\\n   → 임계값 초과 시 SMS/Email 발송",
    "image_request": "data flow diagram with arrows showing sensor to cloud to dashboard pipeline, modern tech infographic style",
    "image_position": "left:50%",
    "text_position": "right:45%"
  },
  {
    "page_number": 4,
    "section": "연구 내용",
    "title": "핵심 기술 요소",
    "content": "• AI/ML 기술\\n  - LSTM, Transformer, XGBoost\\n  - Transfer Learning (사전학습 모델 활용)\\n• 빅데이터 처리\\n  - Apache Kafka (실시간 스트리밍)\\n  - Spark (대용량 배치 처리)\\n• 클라우드 인프라\\n  - AWS EC2 (서버), S3 (스토리지)\\n  - Docker/Kubernetes (컨테이너 오케스트레이션)",
    "image_request": "technology stack visualization with logos and icons of AI frameworks and cloud services, professional tech stack diagram",
    "image_position": "right:50%",
    "text_position": "left:45%"
  }
]

[작성 핵심 원칙]
1. **기술적 깊이와 이해 용이성 균형**
   - 전문가: 구체적 기술 스택 명시 (LSTM, FastAPI, Kafka 등)
   - 비전문가: 각 모듈의 역할을 한 문장으로 설명

2. **계층적 설명**
   - 1장: 전체 시스템 개요 (High-level)
   - 2장: 핵심 모듈 상세 (AI 엔진 등)
   - 3장: 데이터 흐름
   - 4장: 기술 스택

3. **시각화 중심**
   - 모든 슬라이드에 다이어그램 이미지 필수
   - 텍스트는 이미지를 보조하는 역할 (간결하게)

4. **차별화 요소 강조**
   - "단순 LSTM"이 아닌 "Attention 적용 LSTM"
   - "일반 DB"가 아닌 "PostgreSQL + Redis 캐시 구조"

5. **RFP 요구사항 준수**
   - relevant_context에서 요구하는 기술 명시적 포함
   - 예: RFP에 "실시간 처리"가 있으면 → Kafka, Redis 언급

[슬라이드 구성]
- 총 3~5장 (시스템 복잡도에 따라)
- 구조도 → 핵심 알고리즘 → 데이터 흐름 → 기술 스택 순서 권장

[image_request 작성 팁]
- architecture diagram, system diagram, data flow, flowchart
- technical illustration, clean diagram, professional style
- layered structure, connected components, arrows showing flow
- 기술 스택은 icon set, logo visualization으로 표현
"""


def content_node(state: GraphState) -> dict:
    """
    연구 내용(시스템 구조도) 슬라이드 생성 노드
    
    Args:
        state: 현재 그래프 상태
        
    Returns:
        {"slides": [SlideState, ...]}
    """
    print("\n" + "="*60)
    print("[연구 내용 노드] 작업 시작")
    print("="*60)
    
    try:
        # 1. 데이터 추출
        analyzed_json = state.get("analyzed_json", {})
        
        if not analyzed_json or "error" in analyzed_json:
            print("[연구 내용 노드] 분석 데이터 없음")
            return {"slides": []}
        
        project_summary = analyzed_json.get("project_summary", {})
        task_info = analyzed_json.get("tasks", {}).get("research_content", {})
        
        relevant_context = task_info.get("relevant_context", "")
        instruction = task_info.get("instruction", "")
        
        if not relevant_context:
            print("[연구 내용 노드] relevant_context 없음")
            return {"slides": []}
        
        # 2. 프롬프트 (기술 키워드 강조)
        keywords_str = ', '.join(project_summary.get('keywords', []))
        
        prompt = f"""
[과제 개요]
제목: {project_summary.get('title', 'N/A')}
핵심 키워드: {keywords_str}

[PM 지시]
{instruction}

[RFP 시스템 요구사항]
{relevant_context}

위 내용을 바탕으로 '연구 내용(시스템 구조도)'를 작성하라.
특히 "{keywords_str}"와 관련된 기술 요소를 명시적으로 포함하라.
"""
        
        # 3. API 호출
        api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        
        print("[연구 내용 노드] LLM 생성 중...")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                temperature=0.3,  # 기술 설명은 약간의 창의성 허용
            ),
        )
        
        # 4. 파싱
        slides_data = json.loads(response.text)
        
        if not isinstance(slides_data, list):
            print(f"[연구 내용 노드] 응답 형식 오류")
            return {"slides": []}
        
        result_slides = []
        for slide in slides_data:
            slide_state: SlideState = {
                "page_number": slide.get("page_number", 0),
                "section": slide.get("section", "연구 내용"),
                "title": slide.get("title", ""),
                "content": slide.get("content", ""),
                "image_request": slide.get("image_request", ""),
                "image_position": slide.get("image_position", "right:50%"),
                "image_path": "",
            }
            result_slides.append(slide_state)
        
        print(f"[연구 내용 노드] 슬라이드 {len(result_slides)}장 생성 완료")
        for i, s in enumerate(result_slides, 1):
            print(f"  [{i}] {s['title']}")
        
        return {"slides": result_slides}
    
    except Exception as e:
        print(f"[연구 내용 노드 오류] {e}")
        import traceback
        traceback.print_exc()
        return {"slides": []}


# ============================================================
# 테스트 코드
# ============================================================
if __name__ == "__main__":
    print("--- [TEST] 연구 내용 노드 단독 실행 ---")
    
    dummy_state: GraphState = {
        "rfp_text": "",
        "analyzed_json": {
            "project_summary": {
                "title": "AI 기반 스마트팩토리 플랫폼 개발",
                "keywords": ["AI", "예지보전", "LSTM", "실시간 처리", "클라우드"]
            },
            "tasks": {
                "research_content": {
                    "role": "연구 내용",
                    "instruction": "시스템 아키텍처를 3-tier 구조로 설명하고, AI 모델 구조를 상세히 제시",
                    "relevant_context": """
                    [개발 시스템 요구사항]
                    - 실시간 센서 데이터 수집 (1초 단위)
                    - AI 기반 고장 예측 (LSTM 또는 Transformer 활용)
                    - 웹 기반 모니터링 대시보드
                    - 클라우드 인프라 (AWS, GCP 등)
                    - 데이터베이스: 최소 10만건 이상 저장 가능
                    
                    [필수 기능]
                    - 실시간 알람 기능 (SMS/Email)
                    - 과거 데이터 분석 및 리포트 생성
                    - 사용자 권한 관리
                    """
                }
            }
        },
        "slides": [],
        "final_ppt_path": ""
    }
    
    result = content_node(dummy_state)
    
    if result["slides"]:
        print("\n[성공] 생성된 슬라이드:")
        for slide in result["slides"]:
            print(f"\n제목: {slide['title']}")
            print(f"내용:\n{slide['content']}")
            print(f"이미지: {slide['image_request'][:70]}...")
    else:
        print("[실패]")