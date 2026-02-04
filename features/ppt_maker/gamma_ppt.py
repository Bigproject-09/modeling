# """
# R&D 제안서 PPT 자동 생성 (수정 완료)
# - exportAs 파라미터 추가
# - 표지 배경 이미지 (오른쪽 절반)
# - 페이지 수 조정
# """
# import os
# import sys
# import json
# import time
# import requests
# from pathlib import Path
# from typing import Dict, List, Optional, Tuple
# import mysql.connector
# from dotenv import load_dotenv

# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
# from utils.document_parsing import extract_text_from_pdf
# from utils.section import SectionSplitter

# load_dotenv()

# class Config:
#     # 절대 경로 유지 (수정 금지)
#     BASE_DIR = Path(__file__).parent.parent.parent
    
#     INPUT_PDF_DIR = BASE_DIR / "data" / "ppt_input"
#     OUTPUT_PPTX_DIR = BASE_DIR / "data" / "pptx"
#     PARSING_DIR = BASE_DIR / "data" / "parsing"
#     SECTION_DIR = BASE_DIR / "data" / "sections"
#     TEMP_DIR = BASE_DIR / "data" / "temp"
    
#     GAMMA_API_KEY = os.getenv("GAMMA_API_KEY")
#     GAMMA_API_BASE = "https://public-api.gamma.app/v1.0"
#     PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
    
#     DB_CONFIG = {
#         "host": os.getenv("DB_HOST"),
#         "port": int(os.getenv("DB_PORT", "3306")),
#         "user": os.getenv("DB_USER"),
#         "password": os.getenv("DB_PASSWORD"),
#         "database": os.getenv("DB_NAME"),
#     }
    
#     ANNOUNCEMENT_TITLE = "고해상도 해양-빙권 결합모델 개발"
#     DEFAULT_COMPANY_ID = 1
    
#     SECTION_TITLE_MAPPING = {
#         "개요": ["연구개발의 개요"],
#         "연구필요성": ["연구개발 대상의 국내외 현황", "연구개발의 중요성"],
#         "연구목표": ["연구개발의 최종 목표", "연구개발과제의 단계별 목표"],
#         "연구내용": ["연구개발과제의 내용", "연구개발과제 수행일정 및 주요 결과물"],
#         "추진계획": ["연구개발 추진전략", "연구개발 수행방법", "연구개발 추진일정"],
#         "기대성과및활용방안": ["연구개발성과의 활용방안", "기대효과"]
#     }
    
#     SECTION_VISUAL_GUIDES = {
#         "개요": {
#             "image_source": "aiGenerated",
#             "instructions": "연구의 핵심 메커니즘과 구성 요소 간의 관계를 정의한 'System Framework Diagram'. 복잡한 배경 없이 보편적인 블록 구조와 화살표를 사용하여 연구의 전체적인 논리 흐름(Input-Process-Output)을 시각화. 깔끔하고 전문적인 설계도 느낌의 레이아웃."
#         },

#         "연구필요성": {
#             "image_source": "aiGenerated",
#             "instructions": "기존 기술의 한계(Pain Points)와 본 연구의 차별성을 보여주는 'Gap Analysis Infographic'. 막대/꺾은선 그래프를 활용해 기술적 격차를 강조하는 대비 구조의 시각화. 신뢰감을 주는 네이비/그레이 톤 활용."
#         },

#         "연구목표": {
#             "image_source": "aiGenerated",
#             "instructions": "최종 목표를 중심으로 한 'Target Dashboard'. 정량적 성능 지표(KPI)를 게이지 차트나 숫자 카드 형태로 시각화하고, 목표 달성 경로를 보여주는 선형 로드맵(Roadmap) 포함. 배경 이미지 없이 깔끔한 레이아웃."
#         },

#         "연구내용": {
#             "image_source": "aiGenerated",
#             "instructions": "시스템의 계층 구조를 보여주는 'Layered Architecture' 또는 'Detailed Module Block Diagram'. 기술적 처리 과정을 단계별로 보여주는 플로우차트. 텍스트 없이 선과 면 위주의 플랫하고 정교한 공학 설계도 스타일."
#         },

#         "추진계획": {
#             "image_source": "aiGenerated",
#             "instructions": "연구 일정을 체계적으로 보여주는 'Professional Gantt Chart'와 기관 간 협력 체계를 나타내는 'Governance Org-Chart'. 16:9 비율에 최적화된 마일스톤(Milestone) 표시와 연차별 구분선이 명확한 도식화."
#         },

#         "기대성과및활용방안": {
#             "image_source": "aiGenerated",
#             "instructions": "연구 결과가 실제 산업이나 사회로 확산되는 과정을 담은 'Value Chain Expansion Diagram'. 파급 효과를 보여주는 상승 곡선 그래프나 확산 경로 도식. 결과물의 활용처를 직관적으로 알 수 있는 범용적인 아이콘 활용."
#         },
#     }

#     def __init__(self):
#         for d in [self.OUTPUT_PPTX_DIR, self.PARSING_DIR, self.SECTION_DIR, self.TEMP_DIR]:
#             d.mkdir(parents=True, exist_ok=True)

# config = Config()

# def get_db_connection():
#     try:
#         return mysql.connector.connect(**Config.DB_CONFIG)
#     except Exception as e:
#         print(f"DB 연결 실패: {e}")
#         return None

# def fetch_company_info(company_id: int = Config.DEFAULT_COMPANY_ID) -> Dict:
#     conn = get_db_connection()
#     if not conn:
#         return {"company_name": "테스트 연구소", "business_report": {}}
    
#     cursor = conn.cursor(dictionary=True)
#     try:
#         query = "SELECT company_name, business_report_sections FROM companies WHERE company_id = %s"
#         cursor.execute(query, (company_id,))
#         result = cursor.fetchone()
        
#         if not result:
#             raise ValueError(f"Company ID {company_id} not found")
        
#         business_report = json.loads(result["business_report_sections"]) if result.get("business_report_sections") else {}
#         return {"company_name": result["company_name"], "business_report": business_report}
#     except Exception as e:
#         print(f"기관 정보 조회 실패: {e}")
#         return {"company_name": "테스트 연구소", "business_report": {}}
#     finally:
#         cursor.close()
#         conn.close()

# def parse_and_section_pdf(pdf_path: Path) -> str:
#     print(f"1단계: PDF 파싱 중...")
    
#     parsed_data = extract_text_from_pdf(str(pdf_path))
#     parsing_json_path = config.PARSING_DIR / f"{pdf_path.stem}_parsing.json"
#     with open(parsing_json_path, "w", encoding="utf-8") as f:
#         json.dump(parsed_data, f, ensure_ascii=False, indent=2)
#     print(f"  파싱 완료: {parsing_json_path}")
    
#     print(f"2단계: 섹션 분리 중...")
#     splitter = SectionSplitter(str(parsing_json_path))
#     section_json_path = config.SECTION_DIR / f"{pdf_path.stem}_sections.json"
#     sections = splitter.save_sections(str(section_json_path), format='json')
#     print(f"  섹션화 완료: {section_json_path}")
#     print(f"  총 {len(sections)}개 섹션")
    
#     return str(section_json_path)

# def find_section_content(section_json_path: str, target_titles: List[str]) -> str:
#     with open(section_json_path, 'r', encoding='utf-8') as f:
#         sections = json.load(f)
    
#     contents = []
#     for section in sections:
#         title = section.get("title", "").strip()
#         content_list = section.get("content", [])
        
#         if not content_list:
#             continue
        
#         for target in target_titles:
#             if target in title:
#                 content_text = "\n".join(content_list)
#                 if len(content_text.strip()) > 100:
#                     contents.append(content_text)
#                     print(f"  매칭: '{title}' ({len(content_text)}자)")
#                 break
    
#     return "\n\n".join(contents)

# def search_pexels_image(query: str) -> Optional[str]:
#     if not config.PEXELS_API_KEY:
#         return None
    
#     url = "https://api.pexels.com/v1/search"
#     headers = {"Authorization": config.PEXELS_API_KEY}
#     params = {"query": query, "per_page": 1, "orientation": "landscape"}
    
#     try:
#         response = requests.get(url, headers=headers, params=params, timeout=10)
#         if response.status_code == 200:
#             data = response.json()
#             if data.get("photos"):
#                 return data["photos"][0]["src"]["large"]
#     except Exception as e:
#         print(f"  Pexels 오류: {e}")
#     return None

# def call_gamma_generate_api(
#     input_text: str,
#     text_mode: str = "condense",
#     num_cards: int = 3,
#     additional_instructions: str = "",
#     image_source: str = "placeholder",
#     export_as: str = "pptx"  # PPTX Export 추가!
# ) -> Tuple[Optional[str], Optional[str]]:
#     url = f"{config.GAMMA_API_BASE}/generations"
#     headers = {
#         "Content-Type": "application/json",
#         "X-API-KEY": config.GAMMA_API_KEY
#     }
    
#     payload = {
#         "inputText": input_text,
#         "textMode": text_mode,
#         "format": "presentation",
#         "numCards": num_cards,
#         "additionalInstructions": additional_instructions,
#         "exportAs": export_as,  # 이게 빠져있었음!
#         "textOptions": {
#             "amount": "detailed" if num_cards >= 3 else "medium",
#             "tone": "professional, clear, concise",
#             "language": "ko"
#         },
#         "imageOptions": {
#             "source": image_source
#         },
#         "cardOptions": {
#             "dimensions": "16x9"
#         }
#     }
    
#     if image_source == "aiGenerated":
#         payload["imageOptions"]["model"] = "flux-1-pro"
#         payload["imageOptions"]["style"] = "flat icon, minimal, simple diagram, technical, no text"
    
#     try:
#         response = requests.post(url, headers=headers, json=payload, timeout=60)
        
#         if response.status_code not in [200, 201]:
#             return None, f"HTTP {response.status_code}: {response.text}"
        
#         result = response.json()
#         generation_id = result.get("generationId")
        
#         if generation_id:
#             print(f"  Generation ID: {generation_id}")
#             return generation_id, None
#         else:
#             return None, "generationId not found"
        
#     except Exception as e:
#         return None, str(e)

# def poll_gamma_status(generation_id: str, max_wait: int = 300) -> Optional[Dict]:
#     url = f"{config.GAMMA_API_BASE}/generations/{generation_id}"
#     headers = {"X-API-KEY": config.GAMMA_API_KEY}
    
#     start_time = time.time()
#     print(f"  생성 대기", end="", flush=True)
    
#     while time.time() - start_time < max_wait:
#         try:
#             response = requests.get(url, headers=headers, timeout=30)
#             result = response.json()
#             status = result.get("status")
            
#             if status == "completed":
#                 print(f" 완료")
#                 gamma_url = result.get("gammaUrl")
#                 gamma_id = result.get("gammaId")
#                 pptx_url = result.get("pptxUrl")  # exportAs로 생성됨
                
#                 return {
#                     "status": "completed",
#                     "gammaUrl": gamma_url,
#                     "gammaId": gamma_id,
#                     "pptxUrl": pptx_url
#                 }
#             elif status == "failed":
#                 print(f" 실패")
#                 return {"status": "failed"}
            
#             print(".", end="", flush=True)
#             time.sleep(5)
#         except:
#             pass
    
#     print(f" 타임아웃")
#     return None

# def generate_cover_slide(announcement_title: str) -> Optional[Dict]:
#     """
#     표지 생성 (오른쪽 절반 배경 이미지)
#     1페이지 고정
#     """
#     print("\n[1/8] 표지")
    
#     # Pexels 이미지 다운로드 (Python-pptx용)
#     pexels_url = None
#     cover_img_path = None
#     if config.PEXELS_API_KEY:
#         keywords = " ".join(announcement_title.split()[:3])
#         pexels_url = search_pexels_image(keywords)
#         if pexels_url:
#             print(f"  Pexels: {pexels_url}")
#             cover_img_path = config.TEMP_DIR / "cover_image.jpg"
#             try:
#                 response = requests.get(pexels_url, timeout=30)
#                 with open(cover_img_path, "wb") as f:
#                     f.write(response.content)
#                 print(f"  이미지 저장: {cover_img_path}")
#             except Exception as e:
#                 print(f"  이미지 다운로드 실패: {e}")
#                 cover_img_path = None
    
#     input_text = f"# {announcement_title}\n\n연구개발 제안서"
#     instructions = """표지 슬라이드. 
# 제목: 왼쪽에 크게 배치
# 부제목: '연구개발 제안서'를 제목 아래 작게
# 레이아웃: 왼쪽 절반에 텍스트, 오른쪽 절반은 비워둠 (배경 이미지용)
# 디자인: 미니멀, 깔끔"""
    
#     gen_id, error = call_gamma_generate_api(
#         input_text=input_text,
#         text_mode="preserve",
#         num_cards=1,  # 1페이지 고정
#         additional_instructions=instructions,
#         image_source="noImages"  # 이미지 없이 생성, 나중에 merge_pptx.py에서 Pexels 이미지 추가
#     )
    
#     if gen_id:
#         result = poll_gamma_status(gen_id)
#         if result:
#             result["pexels_image"] = pexels_url
#             result["pexels_image_path"] = str(cover_img_path) if cover_img_path else None
#         return result
#     return None

# def generate_company_intro_slide(company_info: Dict) -> Optional[Dict]:
#     """기관 소개 - 1페이지 고정"""
#     print("\n[2/8] 기관 소개")
#     
#     company_name = company_info["company_name"]
#     business_report = company_info["business_report"]
#     report_text = json.dumps(business_report, ensure_ascii=False, indent=2)
#     
#     input_text = f"# 수행 기관 소개\n\n## {company_name}\n\n{report_text}"
#     instructions = f"""기관 소개 슬라이드.
# 1. 레이아웃 구조 (절대 엄수):
#    - 16:9 와이드 가로 비율 고정.
#    - 슬라이드 상단 왼쪽 (박스 형태): 섹션명 '수행 기관 소개'를 태그(Tag/Overline) 스타일의 작은 네모 박스 안에 배치.
#    - 섹션명 아래 (큰 폰트): '{company_name} 주요 역량 및 사업 현황'을 대제목(H1)으로 크게 배치.
#    - 모든 콘텐츠는 한 화면에 들어와야 함. 세로 스크롤/확장 절대 금지.
# 2. 형식 및 분량:
#    - 명사 위주 개조식, 불릿 포인트, 텍스트 중심.
#    - 가독성을 위해 핵심 역량 위주로 요약 배치.
# 3. 시각화: 이미지 없이 깔끔한 레이아웃."""
#     
#     gen_id, error = call_gamma_generate_api(
#         input_text=input_text,
#         text_mode="generate",
#         num_cards=1,  # 1페이지 고정
#         additional_instructions=instructions,
#         image_source="noImages"
#     )
#     
#     if gen_id:
#         return poll_gamma_status(gen_id)
#     return None

# def generate_section_slide(section_name: str, content: str, num_cards: int) -> Optional[Dict]:
#     print(f"\n[{section_name}]")
    
#     visual_guide = config.SECTION_VISUAL_GUIDES.get(section_name, {})
#     image_source = visual_guide.get("image_source", "placeholder")
#     visual_instructions = visual_guide.get("instructions", "")
    
#     input_text = f"# {section_name}\n\n{content}"
#     instructions = f"{section_name} 슬라이드. 섹션 표지 슬라이드 없이 바로 내용 시작. 명사 위주 개조식, 불릿 포인트, 깔끔한 레이아웃.\n시각화: {visual_instructions}\n중요: 왼쪽/오른쪽 큰 배경 이미지 절대 금지. 작은 아이콘, 다이어그램, 그래프만 사용."
    
#     gen_id, error = call_gamma_generate_api(
#         input_text=input_text,
#         text_mode="condense",
#         num_cards=num_cards,
#         additional_instructions=instructions,
#         image_source=image_source
#     )
    
#     if gen_id:
#         return poll_gamma_status(gen_id)
#     return None

# def download_pptx_file(url: str, filename: str) -> bool:
#     save_path = config.TEMP_DIR / filename
#     try:
#         print(f"  다운로드: {filename}...", end="")
#         response = requests.get(url, timeout=120)
#         with open(save_path, "wb") as f:
#             f.write(response.content)
#         print(" OK")
#         return True
#     except Exception as e:
#         print(f" 실패: {e}")
#         return False

# def main():
#     print("=" * 80)
#     print("R&D 제안서 PPT 자동 생성")
#     print("=" * 80)
    
#     # 1. PDF 찾기
#     pdf_files = list(config.INPUT_PDF_DIR.glob("*.pdf"))
#     if not pdf_files:
#         print(f"PDF 파일 없음: {config.INPUT_PDF_DIR}")
#         return
    
#     pdf_path = pdf_files[0]
#     print(f"\n대상: {pdf_path.name}")
    
#     # 2. 파싱 & 섹션화
#     section_json_path = parse_and_section_pdf(pdf_path)
    
#     # 3. 기관 정보
#     print(f"\n3단계: 기관 정보 조회")
#     company_info = fetch_company_info(config.DEFAULT_COMPANY_ID)
#     print(f"  기관명: {company_info['company_name']}")
    
#     # 4. PPT 생성
#     print(f"\n4단계: PPT 생성")
#     results = {}
    
#     # 표지 (1페이지)
#     results["1_표지"] = generate_cover_slide(config.ANNOUNCEMENT_TITLE)
#     time.sleep(3)
    
#     # 기관 소개는 주석 처리 (요청사항)
#     # results["2_기관소개"] = generate_company_intro_slide(company_info)
#     # time.sleep(3)
    
#     # 섹션별 페이지 설정
#     section_configs = {
#         "2_개요": {"titles": config.SECTION_TITLE_MAPPING["개요"], "num_cards": 1},
#         "3_연구필요성": {"titles": config.SECTION_TITLE_MAPPING["연구필요성"], "num_cards": 2},
#         "4_연구목표": {"titles": config.SECTION_TITLE_MAPPING["연구목표"], "num_cards": 2},
#         "5_연구내용": {"titles": config.SECTION_TITLE_MAPPING["연구내용"], "num_cards": 4},
#         "6_추진계획": {"titles": config.SECTION_TITLE_MAPPING["추진계획"], "num_cards": 2},
#         "7_기대성과및활용방안": {"titles": config.SECTION_TITLE_MAPPING["기대성과및활용방안"], "num_cards": 3},
#     }
    
#     for key, cfg in section_configs.items():
#         section_name = key.split("_")[1]
#         content = find_section_content(section_json_path, cfg["titles"])
        
#         if not content or len(content.strip()) < 200:
#             print(f"\n[{section_name}] 건너뜀 ({len(content)}자)")
#             results[key] = None
#             continue
        
#         results[key] = generate_section_slide(section_name, content, cfg["num_cards"])
#         time.sleep(3)
    
#     # 5. 결과 정리
#     print("\n" + "=" * 80)
#     print("결과")
#     print("=" * 80)
    
#     gamma_urls = {}
#     pptx_urls = {}
#     pexels_data = {}
    
#     for key, result in results.items():
#         section_name = key.split("_", 1)[1]
#         if result and result.get("status") == "completed":
#             gamma_url = result.get("gammaUrl")
#             pptx_url = result.get("pptxUrl")
#             gamma_urls[section_name] = gamma_url
#             pptx_urls[section_name] = pptx_url
            
#             # Pexels 정보 저장
#             if result.get("pexels_image"):
#                 pexels_data[section_name] = {
#                     "url": result.get("pexels_image"),
#                     "path": result.get("pexels_image_path")
#                 }
            
#             print(f"{section_name:12s}: {gamma_url}")
            
#             # PPTX 다운로드
#             if pptx_url:
#                 download_pptx_file(pptx_url, f"{key}.pptx")
#         else:
#             gamma_urls[section_name] = None
#             pptx_urls[section_name] = None
#             print(f"{section_name:12s}: 실패")
    
#     # 6. URL 저장
#     output_json = config.OUTPUT_PPTX_DIR / "gamma_urls.json"
#     with open(output_json, "w", encoding="utf-8") as f:
#         json.dump({
#             "gamma_urls": gamma_urls,
#             "pptx_urls": pptx_urls,
#             "pexels_data": pexels_data
#         }, f, ensure_ascii=False, indent=2)
    
#     print(f"\nURL 저장: {output_json}")
#     print(f"PPTX 저장: {config.TEMP_DIR}")
    
#     # 7. Python-pptx로 표지 배경 추가 안내
#     if pexels_data:
#         print("\n" + "=" * 80)
#         print("다음 단계: Python-pptx로 표지 배경 이미지 추가")
#         print("=" * 80)
#         for section, data in pexels_data.items():
#             print(f"{section}: {data['path']}")
#         print("merge_pptx.py 스크립트 실행하여 배경 이미지 추가 및 병합")

# if __name__ == "__main__":
#     main()

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
            "image_model": "dall-e-3",
            "instructions": "연구의 핵심 메커니즘과 구성 요소 간의 관계를 정의한 'System Framework Diagram'. 복잡한 배경 없이 보편적인 블록 구조와 화살표를 사용하여 연구의 전체적인 논리 흐름(Input-Process-Output)을 시각화. 깔끔하고 전문적인 설계도 느낌의 레이아웃. 16:9 가로 비율 엄수.",
            "image_style": "technical diagram, clean blocks and arrows, system architecture, professional engineering design, minimal background, 16:9 aspect ratio"
        },
        "연구 필요성": {
            "image_source": "aiGenerated",
            "image_model": "dall-e-3",
            "instructions": "기존 기술의 한계(Pain Points)와 본 연구의 차별성을 보여주는 'Gap Analysis Infographic'. 막대/꺾은선 그래프를 활용해 기술적 격차를 강조하는 대비 구조의 시각화. 신뢰감을 주는 네이비/그레이 톤 활용. 16:9 가로 비율 엄수.",
            "image_style": "bar chart, line graph, gap analysis visualization, navy and gray tones, professional infographic, data comparison, 16:9 aspect ratio"
        },
        "연구 목표": {
            "image_source": "aiGenerated",
            "image_model": "dall-e-3",
            "instructions": "최종 목표를 중심으로 한 'Target Dashboard'. 정량적 성능 지표(KPI)를 게이지 차트나 숫자 카드 형태로 시각화하고, 목표 달성 경로를 보여주는 선형 로드맵(Roadmap) 포함. 배경 이미지 없이 깔끔한 레이아웃. 16:9 가로 비율 엄수.",
            "image_style": "KPI dashboard, gauge charts, numeric indicators, linear roadmap, milestone markers, clean layout, professional metrics display, 16:9 aspect ratio"
        },
        "연구 내용": {
            "image_source": "aiGenerated",
            "image_model": "dall-e-3",
            "instructions": "시스템의 계층 구조를 보여주는 'Layered Architecture' 또는 'Detailed Module Block Diagram'. 기술적 처리 과정을 단계별로 보여주는 플로우차트. 텍스트 없이 선과 면 위주의 플랫하고 정교한 공학 설계도 스타일. 16:9 가로 비율 엄수.",
            "image_style": "layered architecture diagram, module blocks, technical flowchart, engineering blueprint style, flat design, lines and shapes, no text, 16:9 aspect ratio"
        },
        "추진 계획": {
            "image_source": "aiGenerated",
            "image_model": "dall-e-3",
            "instructions": "연구 일정을 체계적으로 보여주는 'Professional Gantt Chart'와 기관 간 협력 체계를 나타내는 'Governance Org-Chart'. 16:9 비율에 최적화된 마일스톤(Milestone) 표시와 연차별 구분선이 명확한 도식화. 16:9 가로 비율 엄수.",
            "image_style": "gantt chart, organizational chart, timeline with milestones, phase separators, governance structure, professional project management visual, 16:9 aspect ratio"
        },
        "기대성과 및 활용방안": {
            "image_source": "aiGenerated",
            "image_model": "dall-e-3",
            "instructions": "연구 결과가 실제 산업이나 사회로 확산되는 과정을 담은 'Value Chain Expansion Diagram'. 파급 효과를 보여주는 상승 곡선 그래프나 확산 경로 도식. 결과물의 활용처를 직관적으로 알 수 있는 범용적인 아이콘 활용. 16:9 가로 비율 엄수. 모든 슬라이드에서 배경 이미지 및 마지막 슬라이드 큰 이미지 절대 금지 (도식/아이콘만 사용). 섹션 표지 생성 금지.",
            "image_style": "value chain diagram, expansion visualization, growth curve, impact ripple effect, application icons, professional infographic, 16:9 aspect ratio, no background image"
        }
    }

    def __init__(self):
        for d in [self.OUTPUT_PPTX_DIR, self.PARSING_DIR, self.SECTION_DIR, self.TEMP_DIR]:
            d.mkdir(parents=True, exist_ok=True)

config = Config()

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
    num_cards: int = 3,
    additional_instructions: str = "",
    image_source: str = "placeholder",
    image_model: str = "dall-e-3",
    image_style: str = "",
    format: str = "presentation",
    export_as: str = "pptx"
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
        "numCards": num_cards,
        "additionalInstructions": additional_instructions,
        "exportAs": export_as,
        "textOptions": {
            "amount": "medium",
            "tone": "professional, clear, concise",
            "audience": "연구비 심사위원, 과학기술 전문가",
            "language": "ko"
        },
        "imageOptions": {
            "source": "aiGenerated",
            "model": "dall-e-3"
        },
        "cardOptions": {
            "dimensions": "16x9"
        }
    }
    
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

def poll_gamma_status(generation_id: str, max_wait: int = 300) -> Optional[Dict]:
    url = f"{config.GAMMA_API_BASE}/generations/{generation_id}"
    headers = {"X-API-KEY": config.GAMMA_API_KEY}
    
    start_time = time.time()
    print(f"  생성 대기", end="", flush=True)
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(url, headers=headers, timeout=30)
            result = response.json()
            status = result.get("status")
            
            if status == "completed":
                print(f" 완료")
                gamma_url = result.get("gammaUrl")
                gamma_id = result.get("gammaId")
                pptx_url = result.get("pptxUrl")
                
                return {
                    "status": "completed",
                    "gammaUrl": gamma_url,
                    "gammaId": gamma_id,
                    "pptxUrl": pptx_url
                }
            elif status == "failed":
                print(f" 실패")
                return {"status": "failed"}
            
            print(".", end="", flush=True)
            time.sleep(5)
        except:
            pass
    
    print(f" 타임아웃")
    return None

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
        image_model="dall-e-3",
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
    image_model = visual_guide.get("image_model", "dall-e-3")
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

def download_pptx_file(url: str, filename: str) -> bool:
    save_path = config.TEMP_DIR / filename
    try:
        print(f"  다운로드: {filename}...", end="")
        response = requests.get(url, timeout=120)
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
    results = {}
    
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