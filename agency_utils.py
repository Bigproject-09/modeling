# modeling/agency_utils.py

_ALIAS_GROUPS = [
    {"과기정통부", "과학기술정보통신부", "미래창조과학부"},
    {"산업부", "산업통상부", "산업통상자원부", "지식경제부"},
    {"해수부", "해양수산부"},
    {"복지부", "보건복지부"},
    {"행안부", "행정안전부", "안전행정부"},
    {"중기부", "중소벤처기업부", "중소기업청"},
    {"농식품부", "농림축산식품부"},
    {"식약처", "식품의약품안전처"},
    {"국토부", "국토교통부"},
    {"환경부"},
    {"교육부"},
    {"방사청", "방위사업청"},
]

def get_ministry_variants(name: str) -> list:
    if not name:
        return []
    name = name.strip()
    variants = {name}
    for group in _ALIAS_GROUPS:
        if name in group:
            variants.update(group)
            break
    return list(variants)