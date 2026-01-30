import os
import json
import time  # [추가] 시간을 세기 위해 필요
from google import genai
from google.genai import types
from dotenv import load_dotenv

# 같은 폴더(. = nodes_code)에 있는 state
from .state import GraphState, SlideState

load_dotenv()

def writer_node(state: GraphState, section_name: str, page_number: int):
    """
    특정 섹션의 PPT 슬라이드 내용을 작성하는 노드
    """
    print(f"   ✍️ [{section_name}] 작가: 집필 준비 중... (Page {page_number})")
    
    # ------------------------------------------------------------------
    # [Rate Limit 방지] 
    # 8명이 동시에 요청하면 429 에러가 뜨므로, 페이지 번호에 따라 대기 시간을 줍니다.
    # 예: 1번 작가=0초, 2번 작가=5초, 3번 작가=10초 ... 뒤로 갈수록 늦게 시작
    # ------------------------------------------------------------------
    delay_time = (page_number - 1) * 5  # 5초 간격으로 실행
    if delay_time > 0:
        print(f"      ...[{section_name}] API 과부하 방지를 위해 {delay_time}초 대기합니다.")
        time.sleep(delay_time)

    try:
        # 1. PM이 분석한 결과 가져오기
        analyzed_data = state['analyzed_json']
        rfp_summary = analyzed_data.get('project_summary', {})
        
        # 2. 클라이언트 설정
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

        # 3. 프롬프트 작성 (기존과 동일)
        prompt = f"""
        당신은 국가 R&D 제안서 작성 전문가입니다.
        아래 [RFP 요약] 정보를 바탕으로, 제안서의 '{section_name}' 파트에 들어갈
        PPT 슬라이드 1장 분량의 내용을 구체적으로 작성해주세요.

        [RFP 요약 정보]
        - 과제명: {rfp_summary.get('title', '미정')}
        - 목적: {rfp_summary.get('purpose', '미정')}
        - 주요 키워드: {rfp_summary.get('keywords', [])}

        [작성 조건]
        1. JSON 형식으로 출력할 것.
        2. 키(key) 구성: "title" (슬라이드 제목), "content" (본문 내용, 개조식), "image_desc" (추천 이미지 묘사)
        3. 내용은 전문적이고 설득력 있게 작성할 것.
        """

        # 4. LLM 호출
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7
            ),
        )

        # 5. 결과 파싱
        slide_content = json.loads(response.text)
        
        # 6. 결과 정리
        result_slide = SlideState(
            section=section_name,
            page_number=page_number,
            title=slide_content.get("title", section_name),
            content=slide_content.get("content", ""),
            image_desc=slide_content.get("image_desc", "")
        )

        return {"slides": [result_slide]}

    except Exception as e:
        print(f"   ❌ [{section_name}] 에러 발생: {str(e)}")
        # 에러 나도 멈추지 않고 빈 슬라이드 반환 (전체 프로세스 보호)
        return {"slides": [SlideState(section=section_name, page_number=page_number, title="에러 발생", content=str(e), image_desc="")]}