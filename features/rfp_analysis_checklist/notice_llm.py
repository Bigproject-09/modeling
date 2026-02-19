"""
공고문 분석 및 자격요건 자동 판정 시스템 (notice_llm)

DB에 저장된 사업보고서 섹션 JSON을 조회하여:
1. 공고문 자격요건 자동 판정 (가능/불가능/확인 필요) + 법령 조항 참조
2. 공고문 + RFP 심층 분석 (실무 기반 전략 리포트)
"""

import os
import json
import re
import platform
from urllib.parse import urlparse
from dotenv import load_dotenv
from google import genai
import mysql.connector
import chromadb
from sentence_transformers import SentenceTransformer

# .env 파일 로드
load_dotenv()

# =========================================================
# ChromaDB 설정
# =========================================================
CHROMA_DB_DIR = os.environ.get("LAW_CHROMA_DB_DIR", r"C:/chroma_law")
COLLECTION_NAME = os.environ.get("LAW_COLLECTION_NAME", "law_regulations")
EMBED_MODEL_NAME = os.environ.get("LAW_EMBED_MODEL_NAME", "intfloat/multilingual-e5-base")

# 전역 캐시
_chroma_client = None
_chroma_collection = None
_embed_model = None
# =========================================================
# ChromaDB 초기화
# =========================================================
def init_law_search():
    """ChromaDB 및 임베딩 모델 초기화 (전역 캐싱)"""
    global _chroma_client, _chroma_collection, _embed_model
    
    if _chroma_collection is not None and _embed_model is not None:
        return _chroma_collection, _embed_model
    
    print("ChromaDB 초기화 중...")
    
    # ChromaDB 클라이언트
    _chroma_client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    _chroma_collection = _chroma_client.get_collection(name=COLLECTION_NAME)
    
    # 임베딩 모델
    _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
    
    print(f"✓ ChromaDB 로드 완료 (문서 수: {_chroma_collection.count()}개)")
    
    return _chroma_collection, _embed_model

# =========================================================
# 텍스트에서 법령명 추출
# =========================================================
def extract_law_names(text: str) -> list[str]:
    """
    텍스트에서 법령명 추출
    
    예: "중소기업기본법 제2조" → ["중소기업기본법"]
    """
    pattern = r'([가-힣\s]+(?:법|조치법|특별법|기본법|촉진법|지원법))'
    matches = re.findall(pattern, text)
    
    # 중복 제거 및 정리
    law_names = []
    seen = set()
    
    for match in matches:
        clean_name = match.strip()
        if clean_name and clean_name not in seen and len(clean_name) > 2:
            law_names.append(clean_name)
            seen.add(clean_name)
    
    return law_names

# =========================================================
# 법령 조항 검색
# =========================================================
def search_law_regulations(
    query_text: str,
    top_k: int = 5,
    score_threshold: float = 0.5
) -> list[dict]:
    """
    ChromaDB에서 법령 조항 검색
    
    Args:
        query_text: 검색 쿼리
        top_k: 반환할 최대 결과 수
        score_threshold: 유사도 임계값 (0~1)
    
    Returns:
        [
            {
                "law_name": "중소기업기본법",
                "article_number": "2",
                "article_title": "중소기업자의 범위",
                "content": "...",
                "score": 0.85
            }
        ]
    """
    collection, model = init_law_search()
    
    # 쿼리 임베딩 생성
    query_embedding = model.encode([f"query: {query_text}"]).tolist()
    
    # ChromaDB 검색
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
        include=["metadatas", "documents", "distances"]
    )
    
    # 결과 정리
    law_results = []
    
    for i in range(len(results['ids'][0])):
        meta = results['metadatas'][0][i] or {}
        doc = results['documents'][0][i]
        distance = results['distances'][0][i]
        score = 1 - distance  # 거리를 유사도로 변환
        
        # 임계값 필터링
        if score < score_threshold:
            continue
        
        law_results.append({
            "law_name": meta.get('law_name', ''),
            "law_type": meta.get('law_type', ''),
            "regulation_type": meta.get('regulation_type', ''),
            "regulation_number": meta.get('regulation_number', ''),
            "article_number": meta.get('article_number', ''),
            "article_title": meta.get('article_title', ''),
            "full_reference": meta.get('full_reference', ''),
            "content": (doc or "").replace("passage: ", ""),
            "score": round(score * 100, 1)
        })
    
    return law_results

# =========================================================
# 자격요건별 법령 검색
# =========================================================
def search_for_eligibility(requirement_text: str) -> list[dict]:
    """
    자격요건 텍스트에서 법령 검색
    
    Args:
        requirement_text: 자격요건 텍스트
    
    Returns:
        관련 법령 조항 리스트
    """
    # 1. 텍스트에서 법령명 추출 시도
    law_names = extract_law_names(requirement_text)
    
    all_results = []
    
    # 2. 법령명이 있으면 법령별로 검색
    if law_names:
        for law_name in law_names[:5]:  # 최대 5개 법령
            # 법령명으로 검색
            results = search_law_regulations(
                query_text=law_name,
                top_k=2,  # 법령당 2개 조항
                score_threshold=0.6
            )
            all_results.extend(results)
    
    # 3. 법령명이 없으면 텍스트 전체로 검색
    if not all_results:
        all_results = search_law_regulations(
            query_text=requirement_text,
            top_k=5,
            score_threshold=0.5
        )
    
    return all_results

# =========================================================
# DB 연결
# =========================================================
def get_db_conn():
    """MySQL 커넥션 생성"""
    # DB_URL / DB_USERNAME / DB_PASSWORD 우선 지원
    db_url = (os.environ.get("DB_URL") or "").strip()
    db_user = (os.environ.get("DB_USERNAME") or os.environ.get("DB_USER") or "").strip()
    db_pw = os.environ.get("DB_PASSWORD") or ""
    if db_url.lower().startswith("jdbc:"):
        db_url = db_url[5:]
    if db_url:
        parsed = urlparse(db_url)
        if parsed.hostname:
            db_name = (parsed.path or "/").lstrip("/") or os.environ.get("DB_NAME") or ""
            return mysql.connector.connect(
                host=parsed.hostname,
                port=int(parsed.port or 3306),
                user=db_user or (parsed.username or ""),
                password=db_pw or (parsed.password or ""),
                database=db_name,
            )

    return mysql.connector.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
    )
# =========================================================
# DB에서 사업보고서 섹션 JSON 조회
# =========================================================
def load_business_report_from_db(company_id: int) -> dict:
    """
    DB에서 사업보고서 섹션 JSON 전체 조회
    
    Args:
        company_id: 기업 ID
    
    Returns:
        dict: 사업보고서 섹션 데이터
    """
    conn = get_db_conn()
    cur = None
    
    try:
        cur = conn.cursor()
        
        query = """
            SELECT business_report_sections
            FROM companies
            WHERE company_id = %s
        """
        
        cur.execute(query, (company_id,))
        result = cur.fetchone()
        
        if not result or result[0] is None:
            raise RuntimeError(f"company_id {company_id}에 해당하는 사업보고서를 찾을 수 없습니다.")
        
        # JSON 문자열을 파싱
        sections_data = json.loads(result[0])
        
        return sections_data
    
    finally:
        try:
            if cur:
                cur.close()
        finally:
            conn.close()

# =========================================================
# 개발/테스트용: 환경변수로 회사 고정
# =========================================================
def get_default_company_id() -> int | None:
    """DEFAULT_COMPANY_ID 환경변수 읽기"""
    v = os.environ.get("DEFAULT_COMPANY_ID")
    return int(v) if v else None

# =========================================================
# 시스템 프롬프트 - 자격요건 자동 판정
# =========================================================
SYSTEM_INSTRUCTION_ELIGIBILITY = """
너는 R&D 공고문 자격요건 자동 판정 전문가다.
반드시 한국어로 답하고, JSON 형식으로 출력한다.

너의 역할:
1. 공고문에서 모든 자격요건을 추출한다
2. 제공된 법령 조항과 사업보고서 정보를 종합하여 각 자격요건을 비교한다
3. 각 요건에 대해 '가능'/'불가능'/'확인 필요'로 자동 판정한다
4. 판정 근거로 법령 조항 및 공고문 원문을 인용하고, 상세한 판단 이유를 제공한다

자동판정 규칙:
- 가능: 법령 조항 및 사업보고서 정보가 자격요건을 명확히 충족
- 불가능: 법령 조항 및 사업보고서 정보가 자격요건을 명확히 불충족
- 확인 필요: 제공된 정보만으로는 판단 불가능하거나, 사용자가 추가 확인 필요

법령 조항 활용:
- 제공된 법령 조항을 우선적으로 참고하여 판정
- 법령 조항이 자격요건의 근거가 되는 경우 반드시 인용
- 법령 조항과 사업보고서 정보를 종합하여 판단

재무 상태 판단 가이드:
- 자본잠식: 재무제표에서 자본총계가 0 이하이면 자본전액잠식
- 감사의견: 감사보고서에서 '의견거절', '부적정', '한정', '적정' 중 하나를 확인
- 채무불이행: 사업보고서에 명시된 경우에만 판정 가능
- 재무제표가 있으면 반드시 자본총계, 부채총계, 자산총계를 확인하여 판단

출력 형식 (JSON):
{
  "title": "자격요건 자동 판정 결과",
  "overall_eligibility": {
    "status": "가능|불가능|확인 필요",
    "summary": "전체 판정을 2-3문장으로 요약"
  },
  "judgments": [
    {
      "id": 1,
      "category": "신청주체 유형",
      "requirement_text": "공고문의 해당 자격요건 원문을 그대로 인용",
      "judgment": "가능|불가능|확인 필요",
      "reason": "판정 근거를 구체적이고 명확하게 설명. 법령 조항과 사업보고서의 어떤 부분을 보고 어떻게 판단했는지 상세히 기술",
      "related_law": "참고한 법령 조항 (예: 중소기업기본법 제2조)",
      "company_info_used": "판정에 사용된 사업보고서 정보",
      "quote_from_announcement": "판정 근거가 된 공고문 원문을 정확히 인용",
      "additional_action": "가능이면 null, 불가능이면 구체적인 사유, 확인 필요면 무엇을 어떻게 확인해야 하는지 안내"
    }
  ],
  "warning_items": [
    "특별히 주의해야 할 사항"
  ],
  "missing_info": [
    "판정에 필요하지만 사업보고서에서 찾을 수 없는 정보"
  ],
  "recommendations": [
    "신청 전 권장사항"
  ]
}

규칙:
- 모든 자격요건을 빠짐없이 판정한다
- 법령 조항이 제공된 경우 반드시 활용하여 판단한다
- 판정 근거는 반드시 법령 조항 및 공고문 원문을 인용한다
- 재무제표 정보가 있으면 반드시 활용하여 판단한다
- 애매한 경우 '확인 필요'로 판정하고, 무엇을 확인해야 하는지 구체적으로 안내한다
- 반드시 유효한 JSON만 출력한다 (코드 블록 없이)
""".strip()

# =========================================================
# 시스템 프롬프트 - 심층 분석
# =========================================================
SYSTEM_INSTRUCTION_ANALYSIS = """
당신은 대한민국 최고의 국가 R&D 제안 전략 컨설턴트입니다.
반드시 한국어로 답하고, JSON 형식으로 출력합니다.

제공된 공고문과 RFP 양식을 정밀 분석하여 '실무 기반 전략 리포트'를 작성하세요.

분석 근거:
- 「국가연구개발혁신법」 제11조: 평가 기준 명시
- 과기정통부 「국가연구개발사업 운영·관리 지침」
- 한국산업기술진흥원(KIAT) 「R&D 제안서 작성 실무 가이드」(2023)
- 중소벤처기업부 「기술개발사업 신청 길라잡이」(2024)
- 학술 연구: 「국가 R&D 과제 선정 평가요인 분석」(한국기술혁신학회지, 2022)

실무 연구 결과:
- 성공적인 제안서의 공통점: 공고문의 '사업 목적'과 제안 내용의 정렬도 높음
- 평가위원 인터뷰: "공고문에 명시된 정량 목표 달성 가능성을 가장 중시"
- 배점 30점 이상 평가항목 = 핵심 차별화 포인트

출력 형식 (JSON):
{
  "title": "공고문 실무 분석 리포트",
  "research_intent": {
    "policy_background": "정부가 이 사업을 추진하는 정책적 배경과 의도를 3-4문장으로 설명",
    "target_issues": [
      "해결하고자 하는 핵심 이슈 1",
      "해결하고자 하는 핵심 이슈 2"
    ]
  },
  "evaluation_weight_analysis": {
    "summary": "평가표 배점 구조 분석 요약",
    "high_weight_items": [
      {
        "item": "평가항목명",
        "points": 30,
        "strategy": "이 항목에서 만점을 받기 위한 핵심 전략"
      }
    ]
  },
  "mandatory_vs_optional": {
    "mandatory": [
      "필수 요건 1",
      "필수 요건 2"
    ],
    "optional_bonus": [
      "가점 요건 1",
      "가점 요건 2"
    ]
  },
  "critical_focus_areas": [
    {
      "area": "중점 분석 영역 (예: 기술 완성도, 사업화 계획)",
      "why_important": "왜 이 영역이 중요한지",
      "action_items": [
        "구체적으로 해야 할 일 1",
        "구체적으로 해야 할 일 2"
      ]
    }
  ],
  "quantitative_targets": {
    "research_goals": [
      "연구개발 목표 1: 정량 지표 포함",
      "연구개발 목표 2: 정량 지표 포함"
    ],
    "performance_indicators": [
      "성능지표 1 (예: TRL 7단계 달성)",
      "성능지표 2 (예: 처리속도 50% 향상)"
    ],
    "deliverables": [
      "최종 성과물 1 (예: 시제품 1대)",
      "최종 성과물 2 (예: SCI 논문 2편, 특허 3건)"
    ],
    "commercialization": [
      "사업화 요구사항 1 (예: 3년 내 매출 10억 달성)",
      "사업화 요구사항 2 (예: 시장 점유율 5% 확보)"
    ],
    "mandatory_requirements": [
      "필수 참여 요건 1 (예: 중소기업 또는 벤처기업)",
      "필수 참여 요건 2 (예: 박사급 연구원 1명 이상)"
    ]
  }
}

규칙:
- 공고문에 명시된 정량 목표를 빠짐없이 추출한다
- 배점이 높은 평가항목을 우선 분석한다
- 필수 요건과 가점 요건을 명확히 구분한다
- 구체적이고 실행 가능한 전략을 제시한다
- 반드시 유효한 JSON만 출력한다 (코드 블록 없이)
""".strip()

# =========================================================
# 프롬프트 생성 - 자격요건 자동 판정
# =========================================================
def eligibility_prompt(
    announcement_chunks: list[dict],
    business_report_sections: list[dict],
    law_articles: list[dict],
    source: str | None = None
) -> str:
    """자격요건 자동 판정용 프롬프트 생성"""
    header = f"**공고 출처**: {source}\n\n" if source else ""

    # 법령 조항 텍스트 생성
    law_text = ""
    if law_articles:
        law_text = "## 관련 법령 조항\n\n"
        for article in law_articles:
            law_text += f"### {article['law_name']} ({article['law_type']})\n"
            law_text += f"- 규정: {article['regulation_type']} {article['regulation_number']}\n"
            law_text += f"- 조항: {article['full_reference']} {article['article_title']}\n"
            law_text += f"- 유사도: {article['score']}%\n\n"
            law_text += f"```\n{article['content'][:500]}\n```\n\n"
        law_text += "---\n\n"

    # 사업보고서 섹션을 텍스트로 변환
    business_report_text = "## 사업보고서 정보\n\n"
    
    # 중요 키워드가 있는 섹션 우선 포함
    priority_keywords = [
        '재무', '감사', '자본', '부채', '매출', '손익',
        '중소기업', '벤처', '연구', '인증', '설립'
    ]
    
    priority_sections = []
    other_sections = []
    
    for section in business_report_sections:
        section_num = section.get('section_number', 'Unknown')
        title = section.get('title', 'Untitled')
        content = section.get('content', [])
        
        # 우선순위 섹션 판별
        is_priority = any(keyword in title for keyword in priority_keywords)
        
        section_text = f"### 섹션 {section_num}: {title}\n"
        
        # 내용이 리스트면 합치기
        if isinstance(content, list):
            if is_priority:
                text_content = "\n".join(content)
            else:
                text_content = "\n".join(content[:30])
        else:
            text_content = str(content)[:2000] if is_priority else str(content)[:500]
        
        section_text += f"{text_content}\n\n"
        
        if is_priority:
            priority_sections.append(section_text)
        else:
            other_sections.append(section_text)
    
    # 우선순위 섹션 먼저, 그 다음 일반 섹션
    business_report_text += "".join(priority_sections)
    business_report_text += "".join(other_sections[:30])

    # 공고문 청크
    announcement_body = "\n\n".join(
        f"### Chunk {c['chunk_id']}\n```\n{c['text']}\n```"
        for c in announcement_chunks
    )

    return f"""
{header}
{law_text}
{business_report_text}

아래 공고문의 모든 자격요건을 추출하고, 위에 제공된 법령 조항과 사업보고서 정보를 종합하여
각 요건에 대해 '가능'/'불가능'/'확인 필요'를 자동 판정하라.

판정 시 반드시 다음을 포함하라:
1. 법령 조항이 제공된 경우 우선 참고하여 판정
2. 판정 근거가 된 법령 조항 및 공고문의 원문을 그대로 인용
3. 해당 요건을 어떻게 해석했고, 법령 및 사업보고서의 어느 부분과 비교했는지 상세 설명
4. 불가능하다면 구체적으로 어떤 부분이 불충족인지 명확히 제시
5. 확인이 필요하다면 무엇을 어떻게 확인해야 하는지 안내

## 공고문 내용
{announcement_body}

주의: JSON 응답만 출력하고, ```json 같은 코드 블록은 사용하지 마라.
""".strip()

# =========================================================
# 프롬프트 생성 - 심층 분석
# =========================================================
def analysis_prompt(
    announcement_chunks: list[dict],
    rfp_chunks: list[dict] | None = None,
    source: str | None = None
) -> str:
    """심층 분석용 프롬프트 생성"""
    header = f"**공고 출처**: {source}\n\n" if source else ""
    
    announcement_body = "\n\n".join(
        f"### 공고문 Chunk {c['chunk_id']}\n```\n{c['text']}\n```"
        for c in announcement_chunks
    )
    
    rfp_body = ""
    if rfp_chunks:
        rfp_body = "\n\n## RFP 양식 내용\n\n" + "\n\n".join(
            f"### RFP Chunk {c['chunk_id']}\n```\n{c['text']}\n```"
            for c in rfp_chunks
        )

    return f"""
{header}

아래 공고문과 RFP 양식을 정밀 분석하여 실무 기반 전략 리포트를 JSON 형식으로 작성하라.

분석 요구사항:
1. 사업의 정책적 배경 및 정부가 해결하고자 하는 핵심 이슈 파악
2. 평가표 배점 분석: 30점 이상 고배점 항목을 핵심 차별화 포인트로 선정
3. 필수 요건과 가점 요건을 명확히 구분
4. 공고문에 명시된 모든 정량 목표를 빠짐없이 추출
   - 연구개발 목표 및 성능지표
   - 최종 성과물 형태 (시제품, 논문, 특허 등)
   - 사업화 요구사항 (매출 목표, 시장 진출 계획)
   - 필수 참여 요건 (기업 형태, 연구진 구성)

## 공고문 내용
{announcement_body}

{rfp_body}

주의: JSON 응답만 출력하고, ```json 같은 코드 블록은 사용하지 마라.
""".strip()

# =========================================================
# Gemini 호출 - 자격요건 자동 판정
# =========================================================
def eligibility_judgment(
    announcement_chunks: list[dict],
    source: str | None = None,
    model: str = "gemini-2.5-flash",
    temperature: float = 0.2,
    company_id: int | None = None,
) -> dict:
    """
    공고문 자격요건을 분석하여 자동 판정 결과 반환
    
    Args:
        announcement_chunks: 공고문 텍스트 청크 리스트
        source: 공고 출처 (선택)
        model: Gemini 모델명
        temperature: 생성 온도
        company_id: 기업 ID
    
    Returns:
        dict: JSON 형식의 자격요건 자동 판정 결과
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("환경변수 GEMINI_API_KEY가 설정되어 있지 않습니다.")

    # company_id 설정
    if company_id is None:
        company_id = get_default_company_id()
        if company_id is None:
            raise RuntimeError("company_id를 찾을 수 없습니다.")

    # DB에서 사업보고서 섹션 JSON 조회
    print(f"DB에서 사업보고서 조회 중... (company_id: {company_id})")
    business_report_sections = load_business_report_from_db(company_id)
    print(f"✓ 사업보고서 로드 완료 (섹션 수: {len(business_report_sections)}개)")

    # ChromaDB에서 관련 법령 조항 검색
    print("관련 법령 조항 검색 중...")
    
    # 모든 공고문 청크를 합쳐서 법령 검색
    full_announcement_text = "\n".join([chunk['text'] for chunk in announcement_chunks])
    
    # 법령명 추출
    law_names = extract_law_names(full_announcement_text)
    print(f"✓ 추출된 법령명: {law_names}")
    
    # 법령 조항 검색
    law_articles = []
    if law_names:
        for law_name in law_names[:5]:  # 최대 5개 법령
            results = search_law_regulations(law_name, top_k=2, score_threshold=0.6)
            law_articles.extend(results)
        print(f"✓ 검색된 법령 조항: {len(law_articles)}개")
    else:
        print("  법령명을 찾을 수 없어 법령 검색을 건너뜁니다.")

    # 프롬프트 생성
    client = genai.Client(api_key=api_key)
    prompt = eligibility_prompt(
        announcement_chunks,
        business_report_sections,
        law_articles,
        source
    )

    print("\n자격요건 자동 판정 중...")
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION_ELIGIBILITY,
            temperature=temperature,
        ),
    )

    text = response.text
    if not text:
        raise RuntimeError("모델 응답이 비어 있습니다.")

    # JSON 파싱
    clean_text = text.strip()
    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]
    if clean_text.startswith("```"):
        clean_text = clean_text[3:]
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]
    
    try:
        result = json.loads(clean_text.strip())
        print("✓ 자격요건 판정 완료\n")
        return result
    except json.JSONDecodeError as e:
        raise RuntimeError(f"JSON 파싱 실패: {e}\n응답 내용:\n{text}")

# =========================================================
# Gemini 호출 - 심층 분석
# =========================================================
def deep_analysis(
    announcement_chunks: list[dict],
    rfp_chunks: list[dict] | None = None,
    source: str | None = None,
    model: str = "gemini-2.5-flash",
    temperature: float = 0.5,
) -> dict:
    """
    공고문과 RFP 양식을 심층 분석하여 전략 리포트 반환
    
    Args:
        announcement_chunks: 공고문 텍스트 청크 리스트
        rfp_chunks: RFP 양식 텍스트 청크 리스트 (선택)
        source: 공고 출처 (선택)
        model: Gemini 모델명
        temperature: 생성 온도
    
    Returns:
        dict: JSON 형식의 심층 분석 리포트
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("환경변수 GEMINI_API_KEY가 설정되어 있지 않습니다.")
    
    client = genai.Client(api_key=api_key)
    prompt = analysis_prompt(announcement_chunks, rfp_chunks, source)
    
    print("공고문 심층 분석 중...")
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION_ANALYSIS,
            temperature=temperature,
        ),
    )
    
    text = response.text
    if not text:
        raise RuntimeError("모델 응답이 비어 있습니다.")
    
    # JSON 파싱
    clean_text = text.strip()
    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]
    if clean_text.startswith("```"):
        clean_text = clean_text[3:]
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]
    
    try:
        result = json.loads(clean_text.strip())
        print("✓ 심층 분석 완료\n")
        return result
    except json.JSONDecodeError as e:
        raise RuntimeError(f"JSON 파싱 실패: {e}\n응답 내용:\n{text}")

# =========================================================
# 기관소개 전용 추출 (DB JSON -> LLM 요약)
# =========================================================
SYSTEM_INSTRUCTION_ORG_PROFILE = """
너는 발표자료 기관소개 슬라이드 요약 전문가다.
입력으로 전달된 company 메타정보와 business_report_sections JSON에서
기관소개에 필요한 정보만 추출해 JSON으로 출력한다.

출력 JSON 스키마:
{
  "company_name": "회사명",
  "company_type": "기관 유형",
  "employees": "인력 정보(없으면 빈 문자열)",
  "one_line_intro": "한 줄 소개",
  "core_competency": ["핵심역량1", "핵심역량2", "핵심역량3"],
  "key_achievements": ["주요 실적1", "주요 실적2"],
  "evidence": ["근거1", "근거2"]
}

규칙:
- 추측 금지, 근거 없으면 빈 문자열/빈 배열
- 문장 짧게 (발표용)
- JSON 외 텍스트 출력 금지
""".strip()


def load_company_profile_from_db(company_id: int) -> dict:
    """companies 테이블에서 기관소개용 필드와 sections JSON 조회"""
    conn = get_db_conn()
    cur = None
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT
                company_id,
                company_name,
                user_entity_type,
                employees,
                history,
                core_competency,
                business_report_sections
            FROM companies
            WHERE company_id = %s
            LIMIT 1
            """,
            (company_id,),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"company_id {company_id}에 해당하는 회사 정보를 찾을 수 없습니다.")

        sections = row.get("business_report_sections")
        if isinstance(sections, str):
            try:
                sections = json.loads(sections)
            except Exception:
                sections = []
        if sections is None:
            sections = []

        return {
            "company_id": row.get("company_id"),
            "company_name": row.get("company_name") or "",
            "company_type": row.get("user_entity_type") or "",
            "employees": row.get("employees"),
            "history": row.get("history") or "",
            "core_competency": row.get("core_competency") or "",
            "business_report_sections": sections,
        }
    finally:
        try:
            if cur:
                cur.close()
        finally:
            conn.close()


def org_profile_prompt(company_profile: dict) -> str:
    """기관소개 요약용 프롬프트 생성 (JSON only)"""
    sections = company_profile.get("business_report_sections") or []
    if not isinstance(sections, list):
        sections = []
    sections = sections[:30]

    return (
        "다음 business_report_sections JSON만 보고 기관소개 슬라이드용 요약 JSON을 작성하라.\n\n"
        "[BUSINESS_REPORT_SECTIONS]\n"
        + json.dumps(sections, ensure_ascii=False)
    )


def extract_org_profile(company_id: int, model: str = "gemini-2.5-flash", temperature: float = 0.1) -> dict:
    """DB JSON을 읽어 기관소개 슬라이드용 요약 JSON 반환"""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY 또는 GOOGLE_API_KEY가 설정되어 있지 않습니다.")

    company_profile = load_company_profile_from_db(company_id)
    prompt = org_profile_prompt(company_profile)

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION_ORG_PROFILE,
            temperature=temperature,
        ),
    )

    text = (response.text or "").strip()
    if not text:
        raise RuntimeError("기관소개 추출 응답이 비어있습니다.")

    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as e:
        raise RuntimeError(f"기관소개 JSON 파싱 실패: {e}\n응답 내용:\n{response.text}")
