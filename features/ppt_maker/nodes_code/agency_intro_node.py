"""
기관 소개 노드 (Agency Introduction Node)
- 제안 기관의 역량, 연구실적, 인프라를 PPT로 구성
- 이미지: 기관 로고, 조직도, 연구시설 사진 등
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
너는 국가 R&D 제안서의 '기관 소개' 파트를 작성하는 전문 AI 에이전트다.

[역할]
제안 기관의 강점을 부각시켜 평가위원에게 신뢰감을 주는 슬라이드를 만든다.

[입력]
1. project_summary: 전체 과제 요약 (맥락 파악용)
2. relevant_context: 기관 소개에 필요한 RFP 원문 발췌
3. instruction: PM이 제시한 작성 가이드

[출력 형식]
반드시 아래 JSON 배열 형태로만 응답해라. 마크다운이나 설명 금지.

[
  {
    "page_number": 1,
    "section": "기관 소개",
    "title": "제안 기관 개요",
    "content": "• 기관명: OO연구소\\n• 설립: 20XX년\\n• 주요 연구분야: AI, 빅데이터, IoT\\n• 보유 인력: 박사급 연구원 XX명",
    "image_request": "professional research institute building exterior with modern glass architecture, clean corporate style",
    "image_position": "right:50%",
    "text_position": "left:45%"
  },
  {
    "page_number": 2,
    "section": "기관 소개",
    "title": "주요 연구 실적",
    "content": "• 20XX년: △△△ 과제 수행 (예산 XX억)\\n• 20XX년: ○○○ 기술 개발 완료\\n• 특허 등록: XX건 (국내 XX, 해외 XX)\\n• 논문 발표: SCI급 XX편",
    "image_request": "abstract visualization of research achievements with graphs and award trophies, professional infographic style",
    "image_position": "bottom:40%",
    "text_position": "top:55%"
  },
  {
    "page_number": 3,
    "section": "기관 소개",
    "title": "연구 인프라",
    "content": "• 첨단 AI 연구실 (GPU 클러스터 XX대)\\n• 빅데이터 분석 센터 (XX TB 스토리지)\\n• IoT 테스트베드 (XX종 센서 보유)\\n• 협력 네트워크: XX개 대학/기업",
    "image_request": "modern research laboratory with high-tech equipment and computers, bright clean environment",
    "image_position": "left:50%",
    "text_position": "right:45%"
  }
]

[작성 원칙]
1. **구체적 수치 사용**: "다수의 연구원" (X) → "박사급 연구원 15명" (O)
2. **최근 실적 강조**: 3년 이내 성과를 우선 배치
3. **과제 연관성**: relevant_context에서 과제와 관련된 기관 역량만 선별
4. **이미지-텍스트 균형**: 
   - 이미지가 오른쪽이면 텍스트는 왼쪽 (image_position: "right:50%", text_position: "left:45%")
   - 이미지가 아래면 텍스트는 위 (image_position: "bottom:40%", text_position: "top:55%")
5. **슬라이드 수**: 2~4장 (내용 분량에 따라 조절, 너무 많으면 안됨)

[image_request 작성법]
- 영문으로 구체적 묘사 (예: "modern office interior with team collaboration")
- 스타일 키워드 포함 (professional, clean, corporate, bright 등)
- 저작권 안전한 일반적 이미지로 (특정 브랜드/인물 언급 금지)

[text_position / image_position 형식]
- "left:45%", "right:50%", "top:55%", "bottom:40%" 등
- PPT 레이아웃에서 해당 영역이 차지할 비율을 의미
"""


def agency_intro_node(state: GraphState) -> dict:
    """
    기관 소개 슬라이드 생성 노드
    
    Args:
        state: 현재 그래프 상태
        
    Returns:
        {"slides": [SlideState, ...]} 형태로 반환
    """
    print("\n" + "="*60)
    print("[기관 소개 노드] 작업 시작")
    print("="*60)
    
    try:
        # 1. State에서 필요한 정보 추출
        analyzed_json = state.get("analyzed_json", {})
        
        if not analyzed_json or "error" in analyzed_json:
            print("[기관 소개 노드] 분석 데이터 없음 - 빈 슬라이드 반환")
            return {"slides": []}
        
        project_summary = analyzed_json.get("project_summary", {})
        task_info = analyzed_json.get("tasks", {}).get("agency_intro", {})
        
        relevant_context = task_info.get("relevant_context", "")
        instruction = task_info.get("instruction", "")
        
        if not relevant_context:
            print("[기관 소개 노드] relevant_context 없음 - 슬라이드 생성 불가")
            return {"slides": []}
        
        # 2. LLM 입력 구성
        prompt = f"""
[전체 과제 요약]
제목: {project_summary.get('title', 'N/A')}
목적: {project_summary.get('purpose', 'N/A')}
키워드: {', '.join(project_summary.get('keywords', []))}

[PM 지시사항]
{instruction}

[관련 RFP 원문]
{relevant_context}

위 정보를 바탕으로 '기관 소개' 슬라이드를 생성해라.
"""
        
        # 3. Gemini API 호출
        api_key = os.environ.get("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        
        print("[기관 소개 노드] LLM 생성 중...")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                temperature=0.3,  # 창의성 약간 허용
            ),
        )
        
        # 4. 응답 파싱
        slides_data = json.loads(response.text)
        
        if not isinstance(slides_data, list):
            print(f"[기관 소개 노드] 예상치 못한 응답 형식: {type(slides_data)}")
            return {"slides": []}
        
        # 5. SlideState로 변환
        result_slides = []
        for slide in slides_data:
            slide_state: SlideState = {
                "page_number": slide.get("page_number", 0),
                "section": slide.get("section", "기관 소개"),
                "title": slide.get("title", ""),
                "content": slide.get("content", ""),
                "image_request": slide.get("image_request", ""),
                "image_position": slide.get("image_position", "right:50%"),
                "image_path": "",  # 초기값 (이미지 생성 노드에서 채움)
            }
            result_slides.append(slide_state)
        
        print(f"[기관 소개 노드] 슬라이드 {len(result_slides)}장 생성 완료")
        for i, s in enumerate(result_slides, 1):
            print(f"  [{i}] {s['title']}")
        
        return {"slides": result_slides}
    
    except Exception as e:
        print(f"[기관 소개 노드 오류] {e}")
        import traceback
        traceback.print_exc()
        return {"slides": []}


# ============================================================
# 테스트 코드
# ============================================================
if __name__ == "__main__":
    print("--- [TEST] 기관 소개 노드 단독 실행 ---")
    
    # 더미 State 구성
    dummy_state: GraphState = {
        "rfp_text": "",
        "analyzed_json": {
            "project_summary": {
                "title": "AI 기반 스마트팩토리 플랫폼 개발",
                "purpose": "제조업 디지털 전환을 위한 AI 예지보전 시스템 구축",
                "keywords": ["AI", "예지보전", "스마트팩토리"]
            },
            "tasks": {
                "agency_intro": {
                    "role": "기관 소개",
                    "instruction": "제안 기관의 AI/제조 분야 역량과 관련 실적을 강조하라",
                    "relevant_context": """
                    [제안 기관 자격 요건]
                    - AI 관련 국가 R&D 과제 수행 경험 3건 이상
                    - 제조업 분야 기술이전 실적 보유
                    - 박사급 연구인력 5인 이상
                    
                    [우대 사항]
                    - 스마트팩토리 구축 컨설팅 경험
                    - AI 예지보전 관련 특허 보유
                    """
                }
            }
        },
        "slides": [],
        "final_ppt_path": ""
    }
    
    # 노드 실행
    result = agency_intro_node(dummy_state)
    
    # 결과 출력
    if result["slides"]:
        print("\n[성공] 생성된 슬라이드:")
        for slide in result["slides"]:
            print(f"\n제목: {slide['title']}")
            print(f"내용: {slide['content'][:100]}...")
            print(f"이미지 요청: {slide['image_request'][:80]}...")
    else:
        print("[실패] 슬라이드 생성되지 않음")