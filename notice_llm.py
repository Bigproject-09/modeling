import os
import json
from dotenv import load_dotenv
from google import genai

# .env 파일 로드
load_dotenv()

# =========================================================
# 회원가입에서 받는 정보
# =========================================================
USER_ENTITY_TYPE = "영리"

# =========================================================
# 시스템 프롬프트 - 자격요건 체크리스트
# =========================================================
SYSTEM_INSTRUCTION_CHECKLIST = """
    너는 R&D 공고문 자격요건 분석 전문가다.
    반드시 한국어로 답하고, 마크다운 형식으로 출력한다.

    너의 역할:
    1. 공고문의 자격요건을 추출한다
    2. 사용자의 회원가입 정보(영리/비영리, 기업규모)와 비교한다
    3. 각 자격요건에 대해 PASS/FAIL/UNKNOWN을 자동 판정한다
    4. 사용자가 최종 확인할 수 있도록 체크리스트 형식으로 제공한다

    자동판정 규칙:
    - PASS: 사용자 정보가 자격요건을 명확히 충족함
    - FAIL: 사용자 정보가 자격요건을 명확히 불충족함
    - UNKNOWN: 추가 정보가 필요하거나 판단이 애매한 경우

    출력 형식 (마크다운):

    # 자격요건 체크리스트

    ## 자동 판정 결과
    - **신청주체 유형**: [PASS/FAIL] - [판정근거]
    - **기업 규모**: [PASS/FAIL/UNKNOWN] - [판정근거]

    ## 전체 자격요건 (사용자 확인 필요)

    ### 1. [자격요건 항목명]
    - [ ] **요구사항**: [공고문 원문]
    - **자동판정**: [PASS/FAIL/UNKNOWN]
    - **판정근거**: [구체적 근거 + chunk_id]
    - **확인사항**: [사용자가 추가로 확인해야 할 내용]
    
    ## 추가 안내사항
    - 자동판정이 PASS여도 반드시 원문을 확인하세요
    - 체크리스트를 항목을 모두 확인한 후 신청하시기 바랍니다

    규칙:
    - 모든 자격요건을 빠짐없이 나열한다
    - 근거는 공고문 원문을 그대로 인용한다
    - chunk_id를 명시하여 추적 가능하게 한다
    - 마크다운 문법을 정확히 지킨다
    """.strip()

# =========================================================
# 시스템 프롬프트 - 심층 분석 (마크다운)
# =========================================================
SYSTEM_INSTRUCTION_ANALYSIS = """
    당신은 대한민국 최고의 국가 R&D 제안 전략 컨설턴트입니다.
    반드시 한국어로 답하고, 마크다운 형식으로 출력합니다.

    제공된 공고문을 정밀 분석하여 '수주 전략 리포트'를 작성하세요.

    출력 형식 (마크다운):

    # 공고문 심층 분석 리포트

    ## 사업 배경 및 목적

    [사업이 추진되는 근본적인 배경과 정부가 해결하고자 하는 사회적/기술적 이슈를 3-4문장으로 요약]

    **핵심 이슈:**
    - 이슈 1
    - 이슈 2
    - 이슈 3

    ---

    ## 1. 핵심 평가항목 분석

    ### [평가항목명] (배점: XX점)

    **평가 요지:**
    [이 항목에서 평가하는 핵심 내용]

    **만점 전략:**
    - 전략 1: 구체적인 작성 방법
    - 전략 2: 강조해야 할 포인트
    - 전략 3: 차별화 요소

    **주의사항:**
    [이 항목에서 흔히 실수하는 부분이나 주의할 점]

    ---

    ## 2. 경쟁력 강화 전략

    ### 전략 1: [전략명]
    [기술적 우위, 사업화 가능성, 인력/인프라 강점 등을 구체적으로 설명]

    **실행 방안:**
    - 세부 실행 1
    - 세부 실행 2

    ---

    ### 전략 2: [전략명]
    [차별화 포인트를 구체적으로 설명]

    **실행 방안:**
    - 세부 실행 1
    - 세부 실행 2

    ---

    ### 전략 3: [전략명]
    [경쟁사 대비 우위를 확보할 수 있는 방안]

    **실행 방안:**
    - 세부 실행 1
    - 세부 실행 2

    ---

    ## 3. 제안서 작성 체크리스트

    - [ ] 사업 배경/목적이 공고문의 정책 방향과 일치하는가?
    - [ ] 핵심 평가항목별 배점 전략이 수립되었는가?
    - [ ] 차별화된 기술적 우위가 명확히 드러나는가?
    - [ ] 사업화 계획이 구체적이고 실현 가능한가?
    - [ ] 연구진 구성이 과제 수행에 최적화되어 있는가?

    규칙:
    - 구체적이고 실행 가능한 전략을 제시한다
    - 공고문의 원문을 근거로 분석한다
    - 마크다운 문법을 정확히 지킨다
    - 불필요한 일반론은 배제하고 실질적인 조언을 제공한다
    """.strip()

# =========================================================
# 유저 프롬프트 생성 - 자격요건
# =========================================================
def checklist_prompts(chunks: list[dict], source: str | None = None) -> str:
    """
    Gemini에 전달할 프롬프트 생성 (자격요건 체크리스트용)
    
    Args:
        chunks: 섹션별 텍스트 리스트
        source: 공고 출처 (선택)
    
    Returns:
        str: 완성된 프롬프트
    """
    header = f"**공고 출처**: {source}\n\n" if source else ""

    user_profile = f"""
    ## 사용자 정보 (회원가입 데이터)

    | 항목 | 값 |
    |------|-----|
    | 신청주체 유형 | {USER_ENTITY_TYPE} |

    """.strip()

    body = "\n\n".join(
        f"### Chunk {c['chunk_id']}\n```\n{c['text']}\n```"
        for c in chunks
    )

    return f"""
    {header}
    {user_profile}

    아래 공고문에서 자격요건을 추출하고, 사용자 정보와 비교하여 
    마크다운 체크리스트를 작성하라.

    특히 다음 항목들을 중점적으로 확인하라:
    1. 영리/비영리 구분 제한
    2. 기타 모든 자격 요건

    ## 공고문 내용
    {body}
    """.strip()

# =========================================================
# 유저 프롬프트 생성 - 심층 분석
# =========================================================
def analysis_prompts(chunks: list[dict], source: str | None = None) -> str:
    """
    Gemini에 전달할 프롬프트 생성 (심층 분석용)
    
    Args:
        chunks: 섹션별 텍스트 리스트
        source: 공고 출처 (선택)
    
    Returns:
        str: 완성된 프롬프트
    """
    header = f"**공고 출처**: {source}\n\n" if source else ""
    
    body = "\n\n".join(
        f"### Chunk {c['chunk_id']}\n```\n{c['text']}\n```"
        for c in chunks
    )

    return f"""
    {header}

    아래 공고문을 정밀 분석하여 수주 전략 리포트를 마크다운으로 작성하라.

    분석 요구사항:
    1. 사업 배경과 정부가 해결하고자 하는 핵심 이슈 파악
    2. 배점이 높거나 까다로운 핵심 평가항목 Top 3 선정 및 만점 전략 수립
    3. 경쟁사 대비 차별화할 수 있는 필승 전략 3가지 제시

    ## 공고문 내용
    {body}
    """.strip()

# =========================================================
# Gemini 호출 - 자격요건 체크리스트 생성
# =========================================================
def eligibility_checklist(
    chunks: list[dict],
    source: str | None = None,
    model: str = "gemini-2.5-flash",
    temperature: float = 0.2,
) -> str:
    """
    공고문 자격요건을 분석하여 마크다운 체크리스트 반환
    
    Args:
        chunks: 섹션별 텍스트 리스트
        source: 공고 출처 (선택)
        model: Gemini 모델명
        temperature: 생성 온도 (0.0~1.0)
    
    Returns:
        str: 마크다운 형식의 자격요건 체크리스트
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("환경변수 GEMINI_API_KEY가 설정되어 있지 않습니다.")

    client = genai.Client(api_key=api_key)
    prompt = checklist_prompts(chunks, source)

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION_CHECKLIST,
            temperature=temperature,
        ),
    )

    text = response.text
    if not text:
        raise RuntimeError("모델 응답이 비어 있습니다.")

    return text.strip()

# =========================================================
# Gemini 호출 - 심층 분석 (마크다운)
# =========================================================
def deep_analysis(
    chunks: list[dict],
    source: str | None = None,
    model: str = "gemini-2.5-flash",
    temperature: float = 0.5,
) -> str:
    """
    공고문을 심층 분석하여 마크다운 전략 리포트 반환
    
    Args:
        chunks: 섹션별 텍스트 리스트
        source: 공고 출처 (선택)
        model: Gemini 모델명
        temperature: 생성 온도 (0.0~1.0)
    
    Returns:
        str: 마크다운 형식의 심층 분석 리포트
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("환경변수 GEMINI_API_KEY가 설정되어 있지 않습니다.")
    
    client = genai.Client(api_key=api_key)
    prompt = analysis_prompts(chunks, source)
    
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
    
    return text.strip()