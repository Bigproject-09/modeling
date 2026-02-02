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
from io import BytesIO
from PIL import Image

load_dotenv()

# 색상 테마
COLOR_THEMES = {
    "ocean_polar": {
        "primary": RGBColor(6, 90, 130),
        "secondary": RGBColor(28, 114, 147),
        "accent": RGBColor(33, 41, 92),
        "text_main": RGBColor(30, 30, 30),
        "text_light": RGBColor(100, 100, 100),
        "text_inv": RGBColor(255, 255, 255),
        "bg_light": RGBColor(248, 249, 251),
        "card_bg": RGBColor(240, 245, 250)
    }
}

CURRENT_COLORS = COLOR_THEMES["ocean_polar"]
SLIDE_WIDTH, SLIDE_HEIGHT = 10, 7.5
MAX_Y = 7.0

def select_color_theme(title: str) -> str:
    title_lower = title.lower()
    if any(w in title_lower for w in ['해양','극지','기후']):
        return "ocean_polar"
    return "ocean_polar"

# LLM 디자인 가이드
def get_ppt_design_guide(project_title: str, slides_data: List[dict]) -> Dict:
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return get_fallback_design(slides_data)
            
        client = genai.Client(api_key=api_key)
        
        slides_summary = []
        for idx, slide in enumerate(slides_data, 1):
            items = slide.get("items", [])
            slides_summary.append({
                "index": idx,
                "title": slide.get("title", "")[:40],
                "item_count": len(items)
            })
        
        prompt = f"""전문 디자이너로서 PPT 디자인을 결정하세요.

**프로젝트:** {project_title}
**슬라이드:** {len(slides_data)}개
**구성:** {json.dumps(slides_summary, ensure_ascii=False)}

**결정사항:**
1. template.header_style: "minimal" (얇은 라인) | "bold" (배경 헤더)
2. template.spacing: "normal" | "spacious"
3. 각 슬라이드의 layout: "vertical_list" | "horizontal_cards" | "highlight_boxes"
4. 각 항목의 위치 (x, y, width, height in inches)

**제약조건:**
- 제목이 길면 2줄 가능 (y=0.3~1.1 영역)
- 내용 시작: y >= 1.4
- 최대: y + height <= 7.0
- 박스 내부 여백: 0.3인치
- 항목 간 간격: 최소 0.2인치

JSON:
{{
  "template": {{"header_style": "minimal", "spacing": "normal"}},
  "slides": [
    {{
      "index": 1,
      "layout": "vertical_list",
      "items": [
        {{"x": 1.0, "y": 1.5, "width": 8.0, "height": 1.0}},
        {{"x": 1.0, "y": 2.7, "width": 8.0, "height": 1.0}}
      ]
    }}
  ]
}}"""
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.3)
        )
        
        result = json.loads(response.text)
        result = validate_design(result, slides_data)
        
        print(f"\n  [LLM 디자인]")
        print(f"    템플릿: {result['template']['header_style']} | {result['template']['spacing']}")
        print(f"    슬라이드: {len(result['slides'])}개 설계")
        
        return result
        
    except Exception as e:
        print(f"\n  [LLM 실패] {e}")
        return get_fallback_design(slides_data)

def validate_design(design: Dict, slides_data: List[dict]) -> Dict:
    """디자인 유효성 검증"""
    if len(design.get('slides', [])) != len(slides_data):
        design['slides'] = []
        for idx, slide in enumerate(slides_data, 1):
            items = slide.get('items', [])
            design['slides'].append({
                "index": idx,
                "layout": "vertical_list",
                "items": [{"x": 1.0, "y": 1.5 + i*1.1, "width": 8.0, "height": 0.9} for i in range(min(len(items), 5))]
            })
    
    for slide_design in design['slides']:
        for item in slide_design.get('items', []):
            if item['y'] + item['height'] > MAX_Y:
                item['height'] = MAX_Y - item['y'] - 0.1
            item['height'] = max(0.4, min(item['height'], 2.0))
            item['width'] = max(3.0, min(item['width'], 9.0))
    
    return design

def get_fallback_design(slides_data: List[dict]) -> Dict:
    slides = []
    for idx, slide in enumerate(slides_data, 1):
        items = slide.get('items', [])
        slides.append({
            "index": idx,
            "layout": "vertical_list",
            "items": [{"x": 1.0, "y": 1.5 + i*1.1, "width": 8.0, "height": 0.9} for i in range(min(len(items), 5))]
        })
    
    return {
        "template": {"header_style": "minimal", "spacing": "normal"},
        "slides": slides
    }

# 표지
def render_cover(slide, title: str, researcher: str):
    """간단하고 깔끔한 표지"""
    # 배경
    bg = slide.shapes.add_shape(1, 0, 0, Inches(SLIDE_WIDTH), Inches(SLIDE_HEIGHT))
    bg.fill.solid()
    bg.fill.fore_color.rgb = CURRENT_COLORS["primary"]
    bg.line.fill.background()
    bg.shadow.inherit = False
    
    # 좌측 바
    bar = slide.shapes.add_shape(1, 0, 0, Inches(0.12), Inches(SLIDE_HEIGHT))
    bar.fill.solid()
    bar.fill.fore_color.rgb = CURRENT_COLORS["accent"]
    bar.line.fill.background()
    bar.shadow.inherit = False
    
    # 제목
    title_box = slide.shapes.add_textbox(Inches(1.0), Inches(2.8), Inches(8.0), Inches(2.2))
    tf = title_box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = 1
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(36)
    p.font.bold = True
    p.font.color.rgb = CURRENT_COLORS["text_inv"]
    p.alignment = PP_ALIGN.LEFT
    p.line_spacing = 1.25
    
    # 연구자
    researcher_box = slide.shapes.add_textbox(Inches(1.0), Inches(5.3), Inches(8.0), Inches(0.4))
    rf = researcher_box.text_frame
    rp = rf.paragraphs[0]
    rp.text = f"{researcher}  |  연구책임자"
    rp.font.size = Pt(15)
    rp.font.color.rgb = CURRENT_COLORS["text_inv"]
    rp.alignment = PP_ALIGN.LEFT

# 헤더
def render_header(slide, title: str, header_style: str):
    """제목 길이 자동 조정"""
    title_length = len(title)
    font_size = 20 if title_length > 45 else (23 if title_length > 30 else 26)
    
    if header_style == "bold":
        header_bg = slide.shapes.add_shape(1, 0, 0, Inches(SLIDE_WIDTH), Inches(1.0))
        header_bg.fill.solid()
        header_bg.fill.fore_color.rgb = CURRENT_COLORS["bg_light"]
        header_bg.line.fill.background()
        header_bg.shadow.inherit = False
        
        title_box = slide.shapes.add_textbox(Inches(0.4), Inches(0.25), Inches(9.2), Inches(0.65))
    else:
        title_box = slide.shapes.add_textbox(Inches(0.4), Inches(0.25), Inches(9.2), Inches(0.75))
    
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(font_size)
    p.font.bold = True
    p.font.color.rgb = CURRENT_COLORS["primary"]
    p.line_spacing = 1.15
    
    if header_style != "bold":
        line = slide.shapes.add_shape(1, Inches(0.4), Inches(1.08), Inches(9.2), Inches(0.015))
        line.fill.solid()
        line.fill.fore_color.rgb = CURRENT_COLORS["primary"]
        line.line.fill.background()
        line.shadow.inherit = False

# 콘텐츠 렌더링
def render_content(slide, items: List[dict], layout_design: Dict, layout_type: str):
    """LLM 배치대로 렌더링 + 이미지 지원 (position: left/right/top/bottom)"""
    items_positions = layout_design.get('items', [])
    
    for idx, (item, pos) in enumerate(zip(items, items_positions)):
        if idx >= len(items_positions):
            break
            
        subtitle = item.get("subtitle", "")
        content = item.get("content", "")
        image_path = item.get("image_path", None)  # 앞 노드에서 전달
        image_position = item.get("image_position", "right")  # left/right/top/bottom
        
        x = pos.get('x', 1.0)
        y = pos.get('y', 1.5)
        width = pos.get('width', 8.0)
        height = pos.get('height', 1.0)
        
        if y + height > MAX_Y:
            height = MAX_Y - y - 0.1
            if height < 0.3:
                break
        
        if layout_type == "highlight_boxes":
            # 강조 박스
            color_bar = slide.shapes.add_shape(1, Inches(x - 0.15), Inches(y), Inches(0.06), Inches(height))
            color_bar.fill.solid()
            color_bar.fill.fore_color.rgb = CURRENT_COLORS["primary"]
            color_bar.line.fill.background()
            color_bar.shadow.inherit = False
            
            bg_box = slide.shapes.add_shape(1, Inches(x), Inches(y), Inches(width), Inches(height))
            bg_box.fill.solid()
            bg_box.fill.fore_color.rgb = CURRENT_COLORS["card_bg"]
            bg_box.line.fill.background()
            bg_box.shadow.inherit = False
            
            # 텍스트 영역 (내부 여백 확보)
            text_x = x + 0.25
            text_y = y + 0.15
            text_w = width - 0.5
            text_h = height - 0.3
            
            # 이미지가 있으면 위치에 따라 배치
            if image_path and os.path.exists(image_path):
                img_gap = 0.2  # 이미지-텍스트 간격
                
                if image_position == "right":
                    # 이미지 우측
                    img_w = text_w * 0.35
                    img_h = text_h
                    slide.shapes.add_picture(
                        image_path, 
                        Inches(text_x + text_w - img_w), 
                        Inches(text_y), 
                        width=Inches(img_w), 
                        height=Inches(img_h)
                    )
                    text_w = text_w * 0.60  # 텍스트 영역 축소
                
                elif image_position == "left":
                    # 이미지 좌측
                    img_w = text_w * 0.35
                    img_h = text_h
                    slide.shapes.add_picture(
                        image_path, 
                        Inches(text_x), 
                        Inches(text_y), 
                        width=Inches(img_w), 
                        height=Inches(img_h)
                    )
                    text_x = text_x + img_w + img_gap
                    text_w = text_w * 0.60
                
                elif image_position == "top":
                    # 이미지 상단
                    img_h = text_h * 0.4
                    img_w = text_w
                    slide.shapes.add_picture(
                        image_path, 
                        Inches(text_x), 
                        Inches(text_y), 
                        width=Inches(img_w), 
                        height=Inches(img_h)
                    )
                    text_y = text_y + img_h + img_gap
                    text_h = text_h * 0.55
                
                elif image_position == "bottom":
                    # 이미지 하단
                    img_h = text_h * 0.4
                    img_w = text_w
                    slide.shapes.add_picture(
                        image_path, 
                        Inches(text_x), 
                        Inches(text_y + text_h - img_h), 
                        width=Inches(img_w), 
                        height=Inches(img_h)
                    )
                    text_h = text_h * 0.55
            
            text_box = slide.shapes.add_textbox(Inches(text_x), Inches(text_y), Inches(text_w), Inches(text_h))
            tf = text_box.text_frame
            tf.word_wrap = True
            
            if subtitle:
                p = tf.paragraphs[0]
                p.text = subtitle
                p.font.size = Pt(18)
                p.font.bold = True
                p.font.color.rgb = CURRENT_COLORS["primary"]
                p.space_after = Pt(4)
            
            if content:
                cp = tf.add_paragraph()
                text = content.split('\n')[0].strip().lstrip('•-·')[:100]
                cp.text = text
                cp.font.size = Pt(14)
                cp.font.color.rgb = CURRENT_COLORS["text_light"]
        
        else:  # vertical_list
            # 리스트
            if subtitle:
                dot = slide.shapes.add_shape(2, Inches(x - 0.25), Inches(y + 0.05), Inches(0.1), Inches(0.1))
                dot.fill.solid()
                dot.fill.fore_color.rgb = CURRENT_COLORS["primary"]
                dot.line.fill.background()
                dot.shadow.inherit = False
                
                st = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(width), Inches(0.3))
                st.text_frame.word_wrap = True
                st.text_frame.paragraphs[0].text = subtitle
                st.text_frame.paragraphs[0].font.size = Pt(17)
                st.text_frame.paragraphs[0].font.bold = True
                st.text_frame.paragraphs[0].font.color.rgb = CURRENT_COLORS["text_main"]
            
            if content:
                ct_y = y + 0.35 if subtitle else y
                ct_h = height - 0.35 if subtitle else height
                
                ct = slide.shapes.add_textbox(Inches(x), Inches(ct_y), Inches(width), Inches(ct_h))
                ct.text_frame.word_wrap = True
                
                lines = [l.strip().lstrip('•-·') for l in content.split('\n') if l.strip()]
                for line in lines[:2]:
                    p = ct.text_frame.add_paragraph() if ct.text_frame.text else ct.text_frame.paragraphs[0]
                    p.text = line[:90]
                    p.font.size = Pt(14)
                    p.font.color.rgb = CURRENT_COLORS["text_light"]

# 메인
def generate_ppt_node(state: Dict, output_dir: str, project_title: str = None, researcher_name: str = "박OO 교수") -> dict:
    try:
        prs = Presentation()
        prs.slide_width = Inches(SLIDE_WIDTH)
        prs.slide_height = Inches(SLIDE_HEIGHT)
        
        slides_data = state.get("slides", [])
        
        if project_title is None:
            project_title = state.get("analyzed_json", {}).get("project_summary", {}).get("title", "연구 제안서")
        
        print(f"\n[PPT 생성]")
        print(f"  제목: {project_title}")
        print(f"  슬라이드: {len(slides_data)}개")
        
        theme_key = select_color_theme(project_title)
        global CURRENT_COLORS
        CURRENT_COLORS = COLOR_THEMES[theme_key]
        
        design_guide = get_ppt_design_guide(project_title, slides_data)
        
        # 표지
        cover = prs.slides.add_slide(prs.slide_layouts[6])
        render_cover(cover, project_title, researcher_name)
        print(f"\n  ✓ 표지")
        
        # 내용
        template = design_guide['template']
        slides_designs = design_guide['slides']
        
        for idx, s_data in enumerate(slides_data, 1):
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            title = s_data.get("title", "")
            items = s_data.get("items", [])
            
            print(f"  [{idx}] {title[:30]}...")
            
            render_header(slide, title, template['header_style'])
            
            layout_design = slides_designs[idx - 1] if idx <= len(slides_designs) else slides_designs[0]
            layout_type = layout_design.get('layout', 'vertical_list')
            
            render_content(slide, items, layout_design, layout_type)
        
        os.makedirs(output_dir, exist_ok=True)
        filename = f"PPT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pptx"
        output_path = os.path.join(output_dir, filename)
        prs.save(output_path)
        
        print(f"\n[완료] {output_path}\n")
        return {"ppt_path": output_path}
        
    except Exception as e:
        print(f"\n[실패] {e}\n")
        import traceback
        traceback.print_exc()
        return {"ppt_path": ""}

# 테스트
def test_generate_ppt_node():
    """이미지 포함 테스트 - state에서 image_path와 position 받아옴"""
    
    # ========================================
    # 테스트용 이미지 저장 위치 안내
    # ========================================
    # 실제 사용 시: 이미지 생성 노드에서 이미지를 생성하고
    # 경로를 C:\big_project\modeling\data\images\ 에 저장
    # 예: C:\big_project\modeling\data\images\slide1_image.png
    
    # 테스트용으로는 업로드된 이미지 사용
    test_image_path = ".data/images/test-image.png"
    
    # 실제 구조 시뮬레이션
    test_slides = [
        {
            "page_number": 1,
            "title": "연구개발 목표 및 핵심 기술",
            "items": [
                {
                    "subtitle": "연구 목표", 
                    "content": "세계 3위권 예측 정확도 확보를 통한 국제 경쟁력 강화\n계절~10년 규모 장기 예측 기술 확보"
                },
                {
                    "subtitle": "초고해상도 모델링", 
                    "content": "해상도 혁신: 기존 1도(100km) → 1/10도(10km)로 10배 향상\n중규모 에디(Mesoscale Eddy) 명시적 계산 가능",
                    "image_path": test_image_path,  # 앞 노드에서 전달
                    "image_position": "right"       # 앞 노드에서 전달 (left/right/top/bottom)
                },
                {
                    "subtitle": "AI 기반 오차 보정", 
                    "content": "딥러닝 기반 편향 보정(Bias Correction) 시스템\n모델 체계적 오차를 AI가 학습하여 실시간 보정",
                    "image_path": test_image_path,  
                    "image_position": "left"        # 다른 위치 테스트
                },
                {
                    "subtitle": "통합 결합 모델", 
                    "content": "해양(MOM6) + 빙권(CICE6) + 생태계(NPZD) 완전 결합\n물리-생태계 양방향 피드백 구현"
                }
            ]
        }
    ]
    
    test_state = {
        "slides": test_slides,
        "analyzed_json": {
            "project_summary": {
                "title": "차세대 해양·극지 환경 기후예측시스템 개발"
            }
        }
    }
    
    result = generate_ppt_node(
        test_state, 
        r"C:\big_project\modeling\data\pptx", 
        "차세대 해양·극지 환경 및 생태계 기후예측시스템 개발",
        "박철수 교수"
    )
    
    print(f"\n{'='*60}")
    if result['ppt_path']:
        print(f"테스트 성공!")
        print(f"파일: {result['ppt_path']}")
        print(f"\n이미지 배치 테스트:")
        print(f"  - 항목 2: '초고해상도 모델링' (이미지 우측)")
        print(f"  - 항목 3: 'AI 기반 오차 보정' (이미지 좌측)")
        print(f"\n실제 사용 시:")
        print(f"  이미지 저장 경로: C:\\big_project\\modeling\\data\\images\\")
        print(f"  예시: slide1_image.png, slide2_diagram.png 등")
    else:
        print(f"테스트 실패")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    test_generate_ppt_node()