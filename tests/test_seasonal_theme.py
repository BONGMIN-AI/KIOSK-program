"""계절 전환은 지정된 메뉴·광고만 바꾸고 원본 및 주문 이력을 보존한다."""

from copy import deepcopy

from core.storage import MemoryVault
from domain import seed, seasonal_theme
from domain.kiosk_settings import all_slides, shown_slides
from gui.order import OrderSession


def test_switch_autumn_winter_none_preserves_originals():
    vault = MemoryVault()
    seed.run(vault)
    vault.write("settings", {})
    menu = vault.read("menu")
    menu["M900"] = {**menu["M001"], "id": "M900", "name": "관리자 추가 메뉴"}
    vault.write("menu", menu)
    originals = deepcopy(menu)
    slides = all_slides({}) + [{"file": "promo_upload_custom.png", "caption": "운영자 광고",
                               "fit": "contain", "on": True}]
    settings = vault.read("settings")
    settings["slides"] = slides
    vault.write("settings", settings)

    for choice, visible_ids, banner in (
        ("winter", 10, "promo_christmas_2026.png"),
        ("autumn", 5, "promo_autumn_2026.png"),
        ("none", 0, None),
        ("winter", 10, "promo_christmas_2026.png"),
    ):
        seasonal_theme.set_theme(vault, choice)
        current = vault.read("menu")
        assert all(current[menu_id] == item for menu_id, item in originals.items())
        assert len([i for i in current.values() if i.get("new_menu") and not i.get("hidden")]) == visible_ids
        assert len(OrderSession(vault).items_in("커피")) == 11 + (2 if choice == "winter" else 1 if choice == "autumn" else 0)
        active = all_slides(vault.read("settings"))
        assert [s for s in active if s["file"] not in seasonal_theme.SEASONAL_FILES] == slides
        assert len([s for s in active if s["file"] in seasonal_theme.SEASONAL_FILES]) == bool(banner)
        if banner:
            assert active[0]["file"] == banner and active[0]["caption"]
        else:
            assert current["XMAS01"]["hidden"] is True  # 주문 이력 참조용 기록은 남는다


def test_reselecting_theme_keeps_edited_seasonal_caption():
    vault = MemoryVault()
    seed.run(vault)
    vault.write("settings", {})
    seasonal_theme.set_theme(vault, "winter")
    settings = vault.read("settings")
    settings["slides"][0]["caption"] = "직접 수정한 문구"
    vault.write("settings", settings)
    seasonal_theme.set_theme(vault, "winter")
    assert shown_slides(vault.read("settings"))[0][1] == "직접 수정한 문구"
