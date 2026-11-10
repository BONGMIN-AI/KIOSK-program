"""크리스마스 시연 메뉴와 광고를 기존 금고에 한 번만 추가한다."""

from domain.seed import popularity

ITEMS = (
    ("XMAS01", "크리스마스 시나몬 라떼", "커피", 5200, ["우유", "기타 견과류(헤이즐넛·아몬드 등)"], 150),
    ("XMAS02", "홀리데이 모카", "커피", 5400, ["우유"], 160),
    ("XMAS03", "디카페인 시나몬 라떼", "디카페인", 5700, ["우유"], 0),
    ("XMAS04", "디카페인 홀리데이 모카", "디카페인", 5900, ["우유"], 0),
    ("XMAS05", "진저브레드 밀크", "논커피", 5200, ["우유", "밀", "알류(달걀 등)"], 0),
    ("XMAS06", "레드벨벳 초코", "논커피", 5400, ["우유", "밀", "알류(달걀 등)"], 10),
    ("XMAS07", "윈터 애플 시나몬 티", "차", 4800, [], 0),
    ("XMAS08", "크리스마스 베리 티", "차", 4800, [], 0),
    ("XMAS09", "크랜베리 스파클링", "에이드", 5200, [], 0),
    ("XMAS10", "루비 자몽 에이드", "에이드", 5200, [], 0),
)

BANNER = {"file": "promo_christmas_2026.png", "caption": "", "fit": "contain", "on": True}


def apply(vault):
    """재실행 시 중복 생성하지 않고, 관리자가 바꾼 메뉴는 보존한다."""
    from domain.kiosk_settings import all_slides

    settings = vault.read("settings", default={})
    if settings.get("christmas_2026_installed"):
        return
    menu = vault.read("menu", default={})
    changed = False
    for menu_id, name, category, price, allergens, caffeine in ITEMS:
        if menu_id in menu:
            continue
        menu[menu_id] = {
            "id": menu_id, "name": name, "category": category, "price": price,
            "allergens": allergens, "caffeine_mg": caffeine,
            "decaf": category == "디카페인", "stock": 20,
            "sold_count": 0, "sold_out": False, "new_menu": True,
            "season": "겨울", **popularity(name, category),
        }
        changed = True
    if changed:
        vault.write("menu", menu)

    slides = all_slides(settings)
    if not any(slide.get("file") == BANNER["file"] for slide in slides):
        settings["slides"] = slides + [dict(BANNER)]
    settings["christmas_2026_installed"] = True
    vault.write("settings", settings)
