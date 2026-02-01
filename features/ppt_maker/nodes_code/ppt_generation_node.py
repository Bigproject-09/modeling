import os
import json
from typing import List, Dict
from datetime import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor

load_dotenv()

# =========================================================
# 1. 고도화된 디자인 테마
# =========================================================
COLOR_THEMES = {
    "navy_gold": {
        "primary": RGBColor(0, 32, 96),
        "secondary": RGBColor(230, 235, 245),
        "accent": RGBColor(255, 192, 0),
        "text_main": RGBColor(30, 30, 30),
        "text_inv": RGBColor(255, 255, 255),
        "bg_light": RGBColor(248, 249, 251)
    }
}
CURRENT_COLORS = COLOR_THEMES["navy_gold"]
SLIDE_WIDTH, SLIDE_HEIGHT = 10, 7.5

# =========================================================
# 2. 디자인 및 레이아웃 분석 (Gemini 2.5-flash)
# =========================================================
def analyze_slide_layout(title: str, items: List[dict]) -> Dict:
    """LLM이 레이아웃 스타일을 결정"""
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return {"theme_key": "navy_gold", "layout_type": "Standard"}
            
        client = genai.Client(api_key=api_key)
        summary = " ".join([i.get('subtitle', '') for i in items])
        
        prompt = f"R&D 제안서 디자인 분석:\n제목: {title}\n내용요약: {summary}\nStandard/TwoColumn/Highlight 중 하나를 layout_type으로 정해 JSON으로 응답해줘."
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[AI Analysis Error] {e}")
        return {"theme_key": "navy_gold", "layout_type": "Standard"}

# =========================================================
# 3. PPT 디자인 엔진 함수 (이름 유지)
# =========================================================
def _draw_pdf_header(slide, title: str):
    """상단 헤더 디자인"""
    rect = slide.shapes.add_shape(1, 0, 0, Inches(SLIDE_WIDTH), Inches(0.85))
    rect.fill.solid()
    rect.fill.fore_color.rgb = CURRENT_COLORS["primary"]
    rect.line.fill.background()
    
    title_box = slide.shapes.add_textbox(Inches(0.4), Inches(0.15), Inches(9.2), Inches(0.6))
    p = title_box.text_frame.paragraphs[0]
    p.text = title
    p.font.size, p.font.bold = Pt(26), True
    p.font.color.rgb = CURRENT_COLORS["text_inv"]

def _add_content_items(slide, items: List[dict], left, top, width, height):
    """아이템 리스트 배치"""
    content_box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = content_box.text_frame
    tf.word_wrap = True
    
    for item in items:
        sub = item.get("subtitle", "")
        con = item.get("content", "")
        if sub:
            p = tf.add_paragraph()
            p.text = f"■ {sub}"
            p.font.size, p.font.bold = Pt(18), True
            p.font.color.rgb = CURRENT_COLORS["primary"]
            p.space_before = Pt(12)
        if con:
            for line in con.split('\n'):
                p = tf.add_paragraph()
                p.text = line.strip().lstrip('•-·')
                p.level, p.font.size = 1, Pt(14)
                p.font.color.rgb = RGBColor(60, 60, 60)

def _add_slide_without_image(slide, title: str, items: List[dict]) -> None:
    _draw_pdf_header(slide, title)
    # 배경 카드
    card = slide.shapes.add_shape(1, Inches(0.3), Inches(1.0), Inches(9.4), Inches(6.2))
    card.fill.solid()
    card.fill.fore_color.rgb = CURRENT_COLORS["bg_light"]
    card.line.color.rgb = CURRENT_COLORS["primary"]
    _add_content_items(slide, items, 0.6, 1.2, 8.8, 5.8)

# =========================================================
# 4. 메인 실행 노드
# =========================================================
def generate_ppt_node(state: Dict) -> dict:
    """입력받은 state를 바탕으로 PPTX 파일 생성"""
    try:
        prs = Presentation()
        prs.slide_width, prs.slide_height = Inches(SLIDE_WIDTH), Inches(SLIDE_HEIGHT)
        
        slides_data = state.get("slides", [])
        project_title = state.get("analyzed_json", {}).get("project_summary", {}).get("title", "R&D 제안서")
        
        # 1. 표지
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        bg = slide.shapes.add_shape(1, 0, 0, Inches(SLIDE_WIDTH), Inches(SLIDE_HEIGHT))
        bg.fill.solid()
        bg.fill.fore_color.rgb = CURRENT_COLORS["primary"]
        title_box = slide.shapes.add_textbox(Inches(1), Inches(3), Inches(8), Inches(1.5))
        p = title_box.text_frame.paragraphs[0]
        p.text = project_title
        p.font.size, p.font.bold, p.font.color.rgb = Pt(44), True, CURRENT_COLORS["text_inv"]
        p.alignment = PP_ALIGN.CENTER

        # 2. 내용 슬라이드
        for s_data in slides_data:
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            _add_slide_without_image(slide, s_data["title"], s_data["items"])

        # 3. 저장 (절대 경로로 파일 유실 방지)
        filename = f"Proposal_{datetime.now().strftime('%H%M%S')}.pptx"
        output_path = os.path.join(os.getcwd(), filename)
        prs.save(output_path)
        
        print(f"\n[성공] PPT 파일이 생성되었습니다: {output_path}")
        return {"ppt_path": output_path}
    except Exception as e:
        print(f"\n[실패] PPT 생성 중 에러 발생: {e}")
        return {"ppt_path": ""}

# =========================================================
# 5. 테스트 실행 함수
# =========================================================
def test_generate_ppt_node():
    test_slides = [
        {
            "page_number": 1,
            "section": "사업 개요",
            "title": "사업 개요 및 추진 방향",
            "items": [
                {"subtitle": "과제명", "content": "• 차세대 AI 기반 스마트 헬스케어 시스템 개발"},
                {"subtitle": "사업 목적", "content": "• 고령화 사회 대비 예방적 건강관리 시스템 구축\n• AI 기술을 활용한 개인 맞춤형 건강관리 서비스 제공"}
            ]
        },
        {
            "page_number": 2,
            "section": "연구 필요성",
            "title": "연구개발의 필요성",
            "items": [
                {"subtitle": "국내외 환경변화", "content": "• 고령 인구 증가로 인한 의료비 급증\n• 예방적 건강관리의 중요성 대두"},
                {"subtitle": "기술 현황", "content": "• 국내 기술 수준: 70%\n• 해외 기술 수준: 100% (미국, 일본)"}
            ]
        }
    ]
    
    test_state = {
        "slides": test_slides,
        "analyzed_json": {
            "project_summary": {"title": "차세대 AI 스마트 헬스케어"}
        }
    }
    
    result = generate_ppt_node(test_state)
    print(f"최종 경로 확인: {result['ppt_path']}")

if __name__ == "__main__":
    test_generate_ppt_node()