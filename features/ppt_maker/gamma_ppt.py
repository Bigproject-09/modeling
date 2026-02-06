"""
R&D 제안서 PPT 자동 생성 (최종 완성)
- 테마 적용 (4udxbbuzsx7exr6)
- DALL-E 3로 표지 이미지 생성
- 대상 독자: 연구비 심사위원
- PPTX 자동 다운로드
"""
import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import mysql.connector
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from utils.document_parsing import extract_text_from_pdf
from utils.section import SectionSplitter

load_dotenv()

class Config:
    BASE_DIR = Path(__file__).parent.parent.parent
    
    INPUT_PDF_DIR = BASE_DIR / "data" / "ppt_input"
    OUTPUT_PPTX_DIR = BASE_DIR / "data" / "pptx"
    PARSING_DIR = BASE_DIR / "data" / "parsing"
    SECTION_DIR = BASE_DIR / "data" / "sections"
    TEMP_DIR = BASE_DIR / "data" / "temp"
    
    GAMMA_API_KEY = os.getenv("GAMMA_API_KEY")
    GAMMA_API_BASE = "https://public-api.gamma.app/v1.0"
    GAMMA_THEME_ID = "4udxbbuzsx7exr6"  # 사용자 테마
    SINGLE_GENERATION = os.getenv("GAMMA_SINGLE_GENERATION", "1") == "1"
    SINGLE_IMAGE_SOURCE = os.getenv("GAMMA_SINGLE_IMAGE_SOURCE", "aiGenerated")
    MAX_IMAGE_SLIDES_PER_SECTION = int(os.getenv("GAMMA_MAX_IMAGE_SLIDES_PER_SECTION", "1"))
    MAX_IMAGE_SLIDES_TOTAL = int(os.getenv("GAMMA_MAX_IMAGE_SLIDES_TOTAL", "6"))
    
    DB_CONFIG = {
        "host": os.getenv("DB_HOST"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME"),
    }
    
    ANNOUNCEMENT_TITLE = "고해상도 해양-빙권 결합모델 개발"
    DEFAULT_COMPANY_ID = 1
    
    SECTION_TITLE_MAPPING = {
        "연구 개요": ["연구개발의 개요"],
        "연구 필요성": ["연구개발 대상의 국내외 현황", "연구개발의 중요성"],
        "연구 목표": ["연구개발의 최종 목표", "연구개발과제의 단계별 목표"],
        "연구 내용": ["연구개발과제의 내용", "연구개발과제 수행일정 및 주요 결과물"],
        "추진 계획": ["연구개발 추진전략", "연구개발 수행방법", "연구개발 추진일정"],
        "기대성과 및 활용방안": ["연구개발성과의 활용방안", "기대효과"]
    }
    
    # 섹션별 시각화 가이드 (절대 변경 금지!)
    SECTION_VISUAL_GUIDES = {
        "연구 개요": {
            "image_source": "aiGenerated",
            "image_model": "recraft-v3-svg",
            "instructions": "연구의 핵심 메커니즘과 구성 요소 간의 관계를 정의한 'System Framework Diagram'. 복잡한 배경 없이 보편적인 블록 구조와 화살표를 사용하여 연구의 전체적인 논리 흐름(Input-Process-Output)을 시각화. 깔끔하고 전문적인 설계도 느낌의 레이아웃. 16:9 가로 비율 엄수.",
            "image_style": "technical diagram, clean blocks and arrows, system architecture, professional engineering design, minimal background, 16:9 aspect ratio"
        },
        "연구 필요성": {
            "image_source": "aiGenerated",
            "image_model": "recraft-v3-svg",
            "instructions": "기존 기술의 한계(Pain Points)와 본 연구의 차별성을 보여주는 'Gap Analysis Infographic'. 막대/꺾은선 그래프를 활용해 기술적 격차를 강조하는 대비 구조의 시각화. 신뢰감을 주는 네이비/그레이 톤 활용. 16:9 가로 비율 엄수.",
            "image_style": "bar chart, line graph, gap analysis visualization, navy and gray tones, professional infographic, data comparison, 16:9 aspect ratio"
        },
        "연구 목표": {
            "image_source": "aiGenerated",
            "image_model": "recraft-v3-svg",
            "instructions": "최종 목표를 중심으로 한 'Target Dashboard'. 정량적 성능 지표(KPI)를 게이지 차트나 숫자 카드 형태로 시각화하고, 목표 달성 경로를 보여주는 선형 로드맵(Roadmap) 포함. 배경 이미지 없이 깔끔한 레이아웃. 16:9 가로 비율 엄수.",
            "image_style": "KPI dashboard, gauge charts, numeric indicators, linear roadmap, milestone markers, clean layout, professional metrics display, 16:9 aspect ratio"
        },
        "연구 내용": {
            "image_source": "aiGenerated",
            "image_model": "recraft-v3-svg",
            "instructions": "2D 평면(정면/상단) 설계도 스타일의 블록 다이어그램 또는 데이터 흐름도. 3D/아이소메트릭/원근감 금지. 텍스트/라벨 절대 금지. 16:9 가로 비율 엄수.",
            "image_style": "2D flat blueprint, orthographic top-down, block diagram, thin lines, grid background, no 3D, no isometric, no perspective, no text, no labels, 16:9 aspect ratio"
        },
        "추진 계획": {
            "image_source": "aiGenerated",
            "image_model": "recraft-v3-svg",
            "instructions": "연구 일정을 체계적으로 보여주는 'Professional Gantt Chart'와 기관 간 협력 체계를 나타내는 'Governance Org-Chart'. 16:9 비율에 최적화된 마일스톤(Milestone) 표시와 연차별 구분선이 명확한 도식화. 16:9 가로 비율 엄수.",
            "image_style": "gantt chart, organizational chart, timeline with milestones, phase separators, governance structure, professional project management visual, 16:9 aspect ratio"
        },
        "기대성과 및 활용방안": {
            "image_source": "aiGenerated",
            "image_model": "recraft-v3-svg",
            "instructions": "연구 결과가 실제 산업이나 사회로 확산되는 과정을 담은 'Value Chain Expansion Diagram'. 파급 효과를 보여주는 상승 곡선 그래프나 확산 경로 도식. 결과물의 활용처를 직관적으로 알 수 있는 범용적인 아이콘 활용. 16:9 가로 비율 엄수. 모든 슬라이드에서 배경 이미지 및 마지막 슬라이드 큰 이미지 절대 금지 (도식/아이콘만 사용). 섹션 표지 생성 금지.",
            "image_style": "value chain diagram, expansion visualization, growth curve, impact ripple effect, application icons, professional infographic, 16:9 aspect ratio, no background image"
        }
    }

    def __init__(self):
        for d in [self.OUTPUT_PPTX_DIR, self.PARSING_DIR, self.SECTION_DIR, self.TEMP_DIR]:
            d.mkdir(parents=True, exist_ok=True)

config = Config()

# 슬라이드 유형별 이미지 스타일 (AI 생성용)
SLIDE_TYPE_STYLES = {
    "시스템 아키텍처": (
        "2D flat blueprint, orthographic top-down, clean block diagram, thin lines, grid background, "
        "no 3D, no isometric, no perspective, no text, no labels"
    ),
    "기술 구현도": (
        "2D flat technical diagram, orthographic top-down, modular blocks, thin lines, "
        "no 3D, no isometric, no perspective, no text, no labels"
    ),
    "데이터 흐름": (
        "2D flat data flow diagram, orthographic top-down, arrows between blocks, thin lines, "
        "no 3D, no isometric, no perspective, no text, no labels"
    ),
    "해수면 상승": "Watercolor",
    "협력 구조도": "Infographic",
    "연구 로드맵": "Infographic",
    "일반인 설명용": "Pen drawing",
}

# 섹션별 슬라이드 유형 순서 (필요 시 확장)
SECTION_SLIDE_TYPES = {
    "연구 내용": ["시스템 아키텍처", "기술 구현도", "데이터 흐름"],
    "연구 필요성": ["해수면 상승"],
    "추진 계획": ["협력 구조도", "연구 로드맵"],
    "기대성과 및 활용방안": ["일반인 설명용"],
}

def get_db_connection():
    try:
        return mysql.connector.connect(**Config.DB_CONFIG)
    except Exception as e:
        print(f"DB 연결 실패: {e}")
        return None

def fetch_company_info(company_id: int = Config.DEFAULT_COMPANY_ID) -> Dict:
    conn = get_db_connection()
    if not conn:
        return {"company_name": "테스트 연구소", "business_report": {}}
    
    cursor = conn.cursor(dictionary=True)
    try:
        query = "SELECT company_name, business_report_sections FROM companies WHERE company_id = %s"
        cursor.execute(query, (company_id,))
        result = cursor.fetchone()
        
        if not result:
            raise ValueError(f"Company ID {company_id} not found")
        
        business_report = json.loads(result["business_report_sections"]) if result.get("business_report_sections") else {}
        return {"company_name": result["company_name"], "business_report": business_report}
    except Exception as e:
        print(f"기관 정보 조회 실패: {e}")
        return {"company_name": "테스트 연구소", "business_report": {}}
    finally:
        cursor.close()
        conn.close()

def parse_and_section_pdf(pdf_path: Path) -> str:
    print(f"1단계: PDF 파싱 중...")
    
    parsed_data = extract_text_from_pdf(str(pdf_path))
    parsing_json_path = config.PARSING_DIR / f"{pdf_path.stem}_parsing.json"
    with open(parsing_json_path, "w", encoding="utf-8") as f:
        json.dump(parsed_data, f, ensure_ascii=False, indent=2)
    print(f"  파싱 완료: {parsing_json_path}")
    
    print(f"2단계: 섹션 분리 중...")
    splitter = SectionSplitter(str(parsing_json_path))
    section_json_path = config.SECTION_DIR / f"{pdf_path.stem}_sections.json"
    sections = splitter.save_sections(str(section_json_path), format='json')
    print(f"  섹션화 완료: {section_json_path}")
    print(f"  총 {len(sections)}개 섹션")
    
    return str(section_json_path)

def find_section_content(section_json_path: str, target_titles: List[str]) -> str:
    with open(section_json_path, 'r', encoding='utf-8') as f:
        sections = json.load(f)
    
    contents = []
    for section in sections:
        title = section.get("title", "").strip()
        content_list = section.get("content", [])
        
        if not content_list:
            continue
        
        for target in target_titles:
            if target in title:
                content_text = "\n".join(content_list)
                if len(content_text.strip()) > 100:
                    contents.append(content_text)
                    print(f"  매칭: '{title}' ({len(content_text)}자)")
                break
    
    return "\n\n".join(contents)

def call_gamma_generate_api(
    input_text: str,
    text_mode: str = "condense",
    num_cards: Optional[int] = 3,
    additional_instructions: str = "",
    image_source: str = "placeholder",
    image_model: str = "recraft-v3-svg",
    image_style: str = "",
    format: str = "presentation",
    export_as: str = "pptx",
    card_split: Optional[str] = None
) -> Tuple[Optional[str], Optional[str]]:
    """
    감마 API 호출
    - 테마 적용
    - 대상 독자 설정
    - DALL-E 3 이미지 생성
    """
    url = f"{config.GAMMA_API_BASE}/generations"
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": config.GAMMA_API_KEY
    }
    
    payload = {
        "inputText": input_text,
        "textMode": text_mode,
        "format": "presentation",
        "themeId": config.GAMMA_THEME_ID,  # 사용자 테마
        "additionalInstructions": additional_instructions,
        "exportAs": export_as,
        "textOptions": {
            "amount": "medium",
            "tone": "professional, clear, concise",
            "audience": "연구비 심사위원, 과학기술 전문가",
            "language": "ko"
        },
        "imageOptions": {
            "source": image_source
        },
        "cardOptions": {
            "dimensions": "16x9"
        }
    }
    
    if num_cards is not None:
        payload["numCards"] = num_cards
    if card_split:
        payload["cardSplit"] = card_split
    
    # AI 이미지 생성 옵션
    if image_source == "aiGenerated":
        payload["imageOptions"]["model"] = image_model
        if image_style:
            payload["imageOptions"]["style"] = image_style
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        if response.status_code not in [200, 201]:
            return None, f"HTTP {response.status_code}: {response.text}"
        
        result = response.json()
        generation_id = result.get("generationId")
        
        if generation_id:
            print(f"  Generation ID: {generation_id}")
            return generation_id, None
        else:
            return None, "generationId not found"
        
    except Exception as e:
        return None, str(e)

def _extract_pptx_url(result: Dict) -> Optional[str]:
    # 1차: 최상위 키
    for key in ("pptxUrl", "pptx_url", "pptxURL", "exportUrl", "export_url", "exportURL"):
        value = result.get(key)
        if value:
            return value
    
    # 2차: 중첩 키 (API 응답 형식 변동 대비)
    for container_key in ("fileUrls", "file_urls", "exportUrls", "export_urls", "exports"):
        container = result.get(container_key)
        if isinstance(container, dict):
            for key in ("pptxUrl", "pptx_url", "pptxURL", "pptx"):
                value = container.get(key)
                if value:
                    return value
    return None

def poll_gamma_status(generation_id: str, max_wait: int = 300) -> Optional[Dict]:
    url = f"{config.GAMMA_API_BASE}/generations/{generation_id}"
    headers = {"X-API-KEY": config.GAMMA_API_KEY}
    
    start_time = time.time()
    print(f"  생성 대기", end="", flush=True)
    export_wait_started = False
    last_completed = None
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(url, headers=headers, timeout=30)
            result = None
            try:
                result = response.json()
            except Exception:
                result = {}
            status = result.get("status")
            
            if status == "completed":
                gamma_url = result.get("gammaUrl")
                gamma_id = result.get("gammaId")
                pptx_url = _extract_pptx_url(result)
                
                if pptx_url:
                    print(f" 완료")
                    return {
                        "status": "completed",
                        "gammaUrl": gamma_url,
                        "gammaId": gamma_id,
                        "pptxUrl": pptx_url
                    }
                
                # 완료는 되었지만 PPTX 링크가 아직 준비되지 않은 경우 재시도
                last_completed = {
                    "status": "completed",
                    "gammaUrl": gamma_url,
                    "gammaId": gamma_id,
                    "pptxUrl": None
                }
                if not export_wait_started:
                    print(" 완료(내보내기 대기)", end="", flush=True)
                    export_wait_started = True
                else:
                    print(".", end="", flush=True)
                time.sleep(5)
                continue
            elif status == "failed":
                print(f" 실패")
                return {"status": "failed"}
            
            print(".", end="", flush=True)
            time.sleep(5)
        except:
            pass
    
    print(f" 타임아웃")
    return last_completed

def generate_cover_slide(announcement_title: str) -> Optional[Dict]:
    """
    표지 생성 - DALL-E 3로 AI 배경 이미지 생성
    1페이지 고정
    """
    print("\n[1/8] 표지")
    
    input_text = f"# {announcement_title}\n\n연구개발 제안서"
    
    # 표지 이미지 스타일: 해양-빙권 연구
    cover_image_style = """Professional scientific visualization of ocean-ice interaction research.
High-resolution satellite view showing ocean currents meeting ice sheets.
Deep blue ocean tones transitioning to pristine white glacial ice.
Modern, technical, clean aesthetic. Data visualization style.
16:9 landscape format. No text overlays."""
    
    instructions = """표지 슬라이드. 
제목: 상단 또는 중앙에 가로로 넓고 시원하게 배치 (가로 너비 충분히 확보)
부제목: '연구개발 제안서'를 제목 아래 작게
배경: AI 생성 이미지는 배경으로 넓게 깔거나, 텍스트와 겹치지 않게 조화롭게 배치
디자인: 전문적, 미니멀, 깔끔
중요: 제목 글자가 가로로 좁게 압축되지 않도록 레이아웃 구성.
섹션 표지 스타일 사용 금지"""
    
    gen_id, error = call_gamma_generate_api(
        input_text=input_text,
        text_mode="preserve",
        format="presentation",
        num_cards=1,
        additional_instructions=instructions,
        image_source="aiGenerated",
        image_model="recraft-v3-svg",
        image_style=cover_image_style
    )
    
    if gen_id:
        return poll_gamma_status(gen_id)
    return None

def generate_company_intro_slide(company_info: Dict) -> Optional[Dict]:
    """기관 소개 - 1페이지 고정"""
    print("\n[2/8] 기관 소개")
    
    company_name = company_info["company_name"]
    business_report = company_info["business_report"]
    report_text = json.dumps(business_report, ensure_ascii=False, indent=2)
    
    input_text = f"# 수행 기관 소개\n\n## {company_name}\n\n{report_text}"
    instructions = f"""기관 소개 슬라이드.
1. 레이아웃 구조 (절대 엄수):
   - 16:9 와이드 가로 비율 고정.
   - 슬라이드 상단 왼쪽 (박스 형태): 섹션명 '수행 기관 소개'를 태그(Tag/Overline) 스타일의 작은 네모 박스 안에 배치.
   - 섹션명 아래 (큰 폰트): '{company_name} 주요 역량 및 사업 현황'을 대제목(H1)으로 크게 배치.
   - 모든 콘텐츠는 한 화면에 들어와야 함. 세로 스크롤/확장 절대 금지.
2. 형식 및 분량:
   - 명사 위주 개조식, 불릿 포인트, 텍스트 중심.
   - 가독성을 위해 핵심 역량 위주로 요약 배치.
3. 시각화: 이미지 없이 깔끔한 레이아웃."""
    
    gen_id, error = call_gamma_generate_api(
        input_text=input_text,
        text_mode="condense",
        format="presentation",
        num_cards=1,  # 1페이지 고정
        additional_instructions=instructions,
        image_source="noImages"
    )
    
    if gen_id:
        return poll_gamma_status(gen_id)
    return None

def generate_section_slide(section_name: str, content: str, num_cards: int) -> Optional[Dict]:
    """
    섹션 슬라이드 생성
    - 섹션별 맞춤 시각화 (절대 변경 금지)
    - 섹션 표지 없음
    - 대제목으로 섹션명 표시
    """
    print(f"\n[{section_name}]")
    
    visual_guide = config.SECTION_VISUAL_GUIDES.get(section_name, {})
    image_source = visual_guide.get("image_source", "placeholder")
    image_model = visual_guide.get("image_model", "recraft-v3-svg")
    visual_instructions = visual_guide.get("instructions", "")
    image_style = visual_guide.get("image_style", "")
    
    input_text = f"# {section_name}\n\n{content}"
    
    instructions = f"""{section_name} 슬라이드.
1. 레이아웃 구조 (절대 엄수):
   - 16:9 와이드 가로 비율 고정.
   - 슬라이드 상단 왼쪽 (박스 형태): 섹션명 '{section_name}'을 태그(Tag/Overline) 스타일의 작은 네모 박스 안에 배치.
   - 섹션명 아래 (큰 폰트): 슬라이드 내용을 구체적으로 핵심 요약한 제목을 대제목(H1)으로 크게 배치. (예: '연구 내용'은 박스로, '전지구 해양-해빙 모델 구축'은 대제목으로)
   - 16:9 가로 비율 엄수. 내용이 많아 화면을 벗어날 경우, 다음 슬라이드로 과감히 분할하여 배치할 것.
   - 모든 콘텐츠는 한 화면에 들어와야 함. 세로 스크롤/확장 절대 금지. 하나의 페이지에 빽빽하게 채우는 것보다 여러 슬라이드로 나누는 것이 가독성에 좋음.
2. 형식 및 분량:
   - 슬라이드당 불릿 포인트는 최대 5개로 제한 (간결성 유지).
   - 텍스트가 화면 하단을 벗어나지 않도록 내용을 요약하여 배치.
   - 섹션 표지 생성 절대 금지 (첫 페이지부터 내용 바로 시작).
   - 명사 위주 개조식, 깔끔한 레이아웃.
3. 시각화 (절대 변경 금지): {visual_instructions}
4. 중요: 왼쪽/오른쪽 큰 배경 이미지 및 전체 배경 이미지 절대 금지. 아이콘, 작은 다이어그램, 차트, 그래프만 사용. 섹션 표지 스타일 절대 금지. 슬라이드 여백을 충분히 확보할 것.
"""
    
    gen_id, error = call_gamma_generate_api(
        input_text=input_text,
        text_mode="condense",
        num_cards=num_cards,
        format="presentation",
        additional_instructions=instructions,
        image_source=image_source,
        image_model=image_model,
        image_style=image_style
    )
    
    if gen_id:
        return poll_gamma_status(gen_id)
    return None

def split_text_into_chunks(text: str, count: int) -> List[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    count = max(1, min(count, len(lines)))
    total = len(lines)
    chunks = []
    for i in range(count):
        start = round(i * total / count)
        end = round((i + 1) * total / count)
        chunk = "\n".join(lines[start:end]).strip()
        if chunk:
            chunks.append(chunk)
    return chunks

def build_combined_input_text(
    section_json_path: str,
    company_info: Dict,
    section_configs: Dict
) -> Tuple[str, List[str], List[Tuple[str, str]]]:
    parts = []
    used_sections = []
    slide_style_map = []
    section_image_counts: Dict[str, int] = {}
    total_image_count = 0
    
    # 표지
    parts.append(f"# {config.ANNOUNCEMENT_TITLE}\n\n연구개발 제안서")
    used_sections.append("표지")
    
    # 기관 소개
    company_name = company_info["company_name"]
    business_report = company_info["business_report"]
    report_text = json.dumps(business_report, ensure_ascii=False, indent=2)
    parts.append(f"# 수행 기관 소개\n\n## {company_name}\n\n{report_text}")
    used_sections.append("수행 기관 소개")
    
    # 본문 섹션
    for key, cfg in section_configs.items():
        if cfg.get("type") != "content":
            continue
        section_name = key.split("_", 1)[1]
        content = find_section_content(section_json_path, cfg["titles"])
        
        if not content or len(content.strip()) < 200:
            print(f"\n[{section_name}] 건너뜀 ({len(content)}자)")
            continue
        
        num_cards = cfg.get("num_cards", 1)
        chunks = split_text_into_chunks(content, num_cards)
        slide_types = SECTION_SLIDE_TYPES.get(section_name, [])
        if not chunks:
            parts.append(f"# {section_name}\n\n{content}")
            used_sections.append(section_name)
            continue
        
        for idx, chunk in enumerate(chunks):
            slide_type = slide_types[idx] if idx < len(slide_types) else None
            slide_title = f"{section_name} - {slide_type}" if slide_type else section_name
            parts.append(f"# {slide_title}\n\n{chunk}")
            used_sections.append(section_name)
            
            style = None
            if slide_type:
                style = SLIDE_TYPE_STYLES.get(slide_type)
            if not style:
                guide = config.SECTION_VISUAL_GUIDES.get(section_name, {})
                style = guide.get("image_style") or guide.get("instructions")
            if style:
                section_count = section_image_counts.get(section_name, 0)
                if (
                    section_count < config.MAX_IMAGE_SLIDES_PER_SECTION
                    and total_image_count < config.MAX_IMAGE_SLIDES_TOTAL
                ):
                    slide_style_map.append((slide_title, style))
                    section_image_counts[section_name] = section_count + 1
                    total_image_count += 1
    
    return "\n---\n".join(parts), used_sections, slide_style_map

def build_combined_instructions(
    used_sections: List[str],
    company_name: str,
    slide_style_map: List[Tuple[str, str]]
) -> str:
    lines = [
        "카드는 inputText의 '---' 기준으로 분할.",
        "전체 16:9 가로 비율, 모든 콘텐츠는 한 화면에 들어오게 구성.",
        "섹션 표지 슬라이드 금지.",
        "첫 카드(표지): 제목 크게, 부제목 작게, 텍스트 압축 금지.",
    ]
    
    if "수행 기관 소개" in used_sections:
        lines.append(
            f"수행 기관 소개: '{company_name} 주요 역량 및 사업 현황'을 대제목으로, 텍스트 중심, 이미지 최소."
        )
    
    if slide_style_map:
        lines.append("이미지는 아래 슬라이드와 표지에만 배치하고, 나머지는 이미지 최소/없음.")
        lines.append("표지는 배경 이미지 1개 허용.")
        lines.append("기술 관련 이미지(시스템 아키텍처/기술 구현도/데이터 흐름)는 텍스트/라벨 절대 금지.")
        for title, style in slide_style_map:
            lines.append(f"슬라이드 '{title}': 이미지 스타일은 {style}")
    
    instructions = "\n".join(lines)
    if len(instructions) > 1900:
        instructions = instructions[:1900] + "\n(시각화 가이드 일부 생략)"
    return instructions

def download_pptx_file(url: str, filename: str) -> bool:
    save_path = config.TEMP_DIR / filename
    try:
        print(f"  다운로드: {filename}...", end="")
        response = requests.get(url, timeout=120)
        if response.status_code != 200:
            print(f" 실패: HTTP {response.status_code}")
            return False
        with open(save_path, "wb") as f:
            f.write(response.content)
        print(" OK")
        return True
    except Exception as e:
        print(f" 실패: {e}")
        return False

def main():
    print("=" * 80)
    print("R&D 제안서 PPT 자동 생성 (테마 적용)")
    print("=" * 80)
    
    # 1. PDF 찾기
    pdf_files = list(config.INPUT_PDF_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"PDF 파일 없음: {config.INPUT_PDF_DIR}")
        return
    
    pdf_path = pdf_files[0]
    print(f"\n대상: {pdf_path.name}")
    
    # 2. 파싱 & 섹션화
    section_json_path = parse_and_section_pdf(pdf_path)
    
    # 3. 기관 정보
    print(f"\n3단계: 기관 정보 조회")
    company_info = fetch_company_info(config.DEFAULT_COMPANY_ID)
    print(f"  기관명: {company_info['company_name']}")
    
    # 4. PPT 생성
    print(f"\n4단계: PPT 생성")
    print(f"  테마 ID: {config.GAMMA_THEME_ID}")
    print(f"  대상 독자: 연구비 심사위원")
    print(f"  표지 이미지: DALL-E 3")
    
    # 섹션별 페이지 설정 (16:9 비율 유지를 위해 넉넉하게 배정)
    # 1, 2번은 표지와 기관소개로 고정
    section_configs = {
        "1_표지": {"type": "cover", "num_cards": 1},
        "2_기관소개": {"type": "intro", "num_cards": 1},
        "3_연구 개요": {"type": "content", "titles": config.SECTION_TITLE_MAPPING["연구 개요"], "num_cards": 2},
        "4_연구 필요성": {"type": "content", "titles": config.SECTION_TITLE_MAPPING["연구 필요성"], "num_cards": 3},
        "5_연구 목표": {"type": "content", "titles": config.SECTION_TITLE_MAPPING["연구 목표"], "num_cards": 3},
        "6_연구 내용": {"type": "content", "titles": config.SECTION_TITLE_MAPPING["연구 내용"], "num_cards": 6},
        "7_추진 계획": {"type": "content", "titles": config.SECTION_TITLE_MAPPING["추진 계획"], "num_cards": 3},
        "8_기대성과 및 활용방안": {"type": "content", "titles": config.SECTION_TITLE_MAPPING["기대성과 및 활용방안"], "num_cards": 4},
    }
    
    if config.SINGLE_GENERATION:
        print("\n단일 생성 모드: 전체 PPT를 1번 호출로 생성합니다.")
        input_text, used_sections, slide_style_map = build_combined_input_text(
            section_json_path,
            company_info,
            section_configs
        )
        instructions = build_combined_instructions(
            used_sections,
            company_info["company_name"],
            slide_style_map
        )
        gen_id, error = call_gamma_generate_api(
            input_text=input_text,
            text_mode="condense",
            num_cards=None,
            additional_instructions=instructions,
            image_source=config.SINGLE_IMAGE_SOURCE,
            image_model="recraft-v3-svg",
            image_style="",
            format="presentation",
            export_as="pptx",
            card_split="inputTextBreaks"
        )
        if error:
            print(f"  생성 오류: {error}")
        
        result = poll_gamma_status(gen_id) if gen_id else None
        
        print("\n" + "=" * 80)
        print("결과")
        print("=" * 80)
        
        gamma_urls = {}
        pptx_urls = {}
        key = "전체"
        if result and result.get("status") == "completed":
            gamma_url = result.get("gammaUrl")
            pptx_url = result.get("pptxUrl")
            gamma_urls[key] = gamma_url
            pptx_urls[key] = pptx_url
            print(f"{key:25s}: {gamma_url}")
            print(f"{'':25s}  PPTX: {pptx_url if pptx_url else '(없음)'}")
            if pptx_url:
                download_pptx_file(pptx_url, "FULL_DECK.pptx")
        else:
            gamma_urls[key] = None
            pptx_urls[key] = None
            print(f"{key:25s}: 실패")
        
        output_json = config.OUTPUT_PPTX_DIR / "gamma_urls.json"
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump({
                "gamma_urls": gamma_urls,
                "pptx_urls": pptx_urls,
                "theme_id": config.GAMMA_THEME_ID
            }, f, ensure_ascii=False, indent=2)
        
        print(f"\nURL 저장: {output_json}")
        print(f"PPTX 저장: {config.TEMP_DIR}")
        print("\n완료!")
        return
    
    results = {}
    
    for key, cfg in section_configs.items():
        try:
            if cfg["type"] == "cover":
                results[key] = generate_cover_slide(config.ANNOUNCEMENT_TITLE)
            elif cfg["type"] == "intro":
                results[key] = generate_company_intro_slide(company_info)
            else:
                section_name = key.split("_", 1)[1]
                content = find_section_content(section_json_path, cfg["titles"])
                
                if not content or len(content.strip()) < 200:
                    print(f"\n[{section_name}] 건너뜀 ({len(content)}자)")
                    results[key] = None
                    continue
                
                results[key] = generate_section_slide(section_name, content, cfg["num_cards"])
            
            time.sleep(3)
        except Exception as e:
            print(f"\n[{key}] 오류 발생: {e}")
            results[key] = None
    
    # 5. 결과 정리
    print("\n" + "=" * 80)
    print("결과")
    print("=" * 80)
    
    gamma_urls = {}
    pptx_urls = {}
    
    for key, result in results.items():
        section_name = key.split("_", 1)[1]
        if result and result.get("status") == "completed":
            gamma_url = result.get("gammaUrl")
            pptx_url = result.get("pptxUrl")
            gamma_urls[section_name] = gamma_url
            pptx_urls[section_name] = pptx_url
            
            print(f"{section_name:25s}: {gamma_url}")
            print(f"{'':25s}  PPTX: {pptx_url if pptx_url else '(없음)'}")
            
            # PPTX 다운로드
            if pptx_url:
                download_pptx_file(pptx_url, f"{key}.pptx")
        else:
            gamma_urls[section_name] = None
            pptx_urls[section_name] = None
            print(f"{section_name:25s}: 실패")
    
    # 6. URL 저장
    output_json = config.OUTPUT_PPTX_DIR / "gamma_urls.json"
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump({
            "gamma_urls": gamma_urls,
            "pptx_urls": pptx_urls,
            "theme_id": config.GAMMA_THEME_ID
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\nURL 저장: {output_json}")
    print(f"PPTX 저장: {config.TEMP_DIR}")
    print("\n완료!")

if __name__ == "__main__":
    main()
