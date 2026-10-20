"""알레르기 유발 물질 목록.

국내 '식품 등의 표시기준'(식약처)의 표시 대상 알레르기 유발 식품을 기준으로 하고,
카페 메뉴에 자주 쓰이지만 법정 목록에 없는 2가지(기타 견과류, 참깨)를 덧붙였다.
조개류는 굴·전복·홍합을 포함한다(이를 따로 세어 '22종'이라고도 부른다).
"""

OFFICIAL = [
    "알류(달걀 등)", "우유", "메밀", "땅콩", "대두", "밀", "고등어", "게", "새우",
    "돼지고기", "복숭아", "토마토", "아황산류", "호두", "닭고기", "쇠고기", "오징어",
    "조개류(굴·전복·홍합 포함)", "잣",
]
CAFE_EXTRA = ["기타 견과류(헤이즐넛·아몬드 등)", "참깨"]
ALLERGENS = OFFICIAL + CAFE_EXTRA

# 예전 데이터나 줄임말을 표준 이름으로 맞춘다.
ALIASES = {
    "달걀": "알류(달걀 등)", "계란": "알류(달걀 등)", "난류": "알류(달걀 등)", "알류": "알류(달걀 등)",
    "견과류": "기타 견과류(헤이즐넛·아몬드 등)", "헤이즐넛": "기타 견과류(헤이즐넛·아몬드 등)",
    "아몬드": "기타 견과류(헤이즐넛·아몬드 등)", "깨": "참깨", "흑임자": "참깨",
    "조개류": "조개류(굴·전복·홍합 포함)", "굴": "조개류(굴·전복·홍합 포함)",
    "전복": "조개류(굴·전복·홍합 포함)", "홍합": "조개류(굴·전복·홍합 포함)",
    "콩": "대두",
}


def normalize(name: str) -> str:
    name = (name or "").strip()
    return ALIASES.get(name, name)


def normalize_all(names) -> list[str]:
    result = []
    for name in names or []:
        canonical = normalize(name)
        if canonical and canonical not in result:
            result.append(canonical)
    return result


def search(keyword: str, names=None) -> list[str]:
    """검색어가 들어간 항목만 돌려준다. 별칭으로도 찾는다(예: '달걀' → 알류)."""
    names = names or ALLERGENS
    keyword = (keyword or "").strip()
    if not keyword:
        return list(names)
    hit = {normalize(alias) for alias in ALIASES if keyword in alias}
    return [n for n in names if keyword in n or n in hit]
