"""원본 메뉴·광고·대기 배경을 보존하며 계절 콘텐츠를 전환한다."""

from core.storage import write_together
from domain.christmas_menu import ITEMS as WINTER_ITEMS
from domain.seed import popularity
from domain.kiosk_settings import all_slides

AUTUMN_ITEMS = (
    ("FALL01", "밤 크림 라떼", "커피", 5300, ["우유", "기타 견과류(헤이즐넛·아몬드 등)"], 150),
    ("FALL02", "디카페인 메이플 라떼", "디카페인", 5600, ["우유"], 0),
    ("FALL03", "군고구마 브륄레", "논커피", 5200, ["우유"], 0),
    ("FALL04", "사과 계피 루이보스", "차", 4700, [], 0),
    ("FALL05", "석류 유자 에이드", "에이드", 5100, [], 0),
)

THEMES = {
    "autumn": ("가을", AUTUMN_ITEMS, {"file": "promo_autumn_2026.png",
                                   "caption": "가을 한정 신메뉴를 만나보세요", "fit": "contain", "on": True}),
    "winter": ("겨울", WINTER_ITEMS, {"file": "promo_christmas_2026.png",
                                   "caption": "크리스마스 한정 신메뉴를 만나보세요", "fit": "contain", "on": True}),
}
SEASONAL_IDS = {row[0] for _name, items, _slide in THEMES.values() for row in items}
SEASONAL_FILES = {slide["file"] for _name, _items, slide in THEMES.values()}
IDLE_BACKGROUNDS = {
    "none": ("idle_bg_clean.png", "idle_bg_choice.png"),
    "autumn": ("seasonal/autumn/idle_bg_autumn.png", "seasonal/autumn/idle_bg_autumn_choice.png"),
    "winter": ("seasonal/winter/idle_bg_winter.png", "seasonal/winter/idle_bg_winter_choice.png"),
}


def current_theme(settings):
    return (settings or {}).get("season_theme", "none")


def idle_backgrounds(settings):
    """대기 및 매장·포장 선택 단계의 배경 파일. 해제하면 원본 두 장."""
    return IDLE_BACKGROUNDS.get(current_theme(settings), IDLE_BACKGROUNDS["none"])


def set_theme(vault, choice):
    """기존 M 메뉴와 일반 배너를 수정하지 않는다. 같은 선택은 중복 추가하지 않는다."""
    if choice not in ("none", *THEMES):
        raise ValueError("계절 테마를 다시 선택해 주세요")
    original_menu = vault.read("menu", default={})
    original_settings = vault.read("settings", default={})
    menu = {menu_id: dict(item) for menu_id, item in original_menu.items()}
    for menu_id in SEASONAL_IDS:
        if menu_id in menu:
            menu[menu_id]["hidden"] = True  # 주문 이력은 이름·가격을 계속 참조하므로 기록은 남긴다
    slides = [slide for slide in all_slides(original_settings)
              if slide["file"] not in SEASONAL_FILES]
    settings = dict(original_settings)
    if choice != "none":
        name, items, banner = THEMES[choice]
        for menu_id, title, category, price, allergens, caffeine in items:
            previous = original_menu.get(menu_id, {})
            menu[menu_id] = {"id": menu_id, "name": title, "category": category,
                             "price": price, "allergens": allergens, "caffeine_mg": caffeine,
                             "decaf": category == "디카페인", "stock": 20,
                             "sold_count": 0, "sold_out": False, "new_menu": True,
                             "season": name, **popularity(title, category), **previous,
                             "hidden": False}
        previous_banner = next((s for s in all_slides(original_settings)
                                if s["file"] == banner["file"]), None)
        selected_banner = dict(previous_banner or banner)
        if current_theme(original_settings) != choice and not selected_banner.get("caption"):
            selected_banner["caption"] = banner["caption"]
        slides.insert(0, selected_banner)
    settings["slides"] = slides
    settings["season_theme"] = choice
    if menu != original_menu or settings != original_settings:
        write_together(vault, {"menu": menu, "settings": settings})
    return choice


def initialize(vault):
    """기존 크리스마스 설치 데이터를 겨울 선택으로 승계한다."""
    settings = vault.read("settings", default={})
    if "season_theme" not in settings:
        set_theme(vault, "winter")
