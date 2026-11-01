"""11/02 B-17: 온도를 고르면 사진이 바뀐다 (ICE 22장 + 연유라떼 HOT 1장)."""
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from domain.options import available_options
from domain.seed import make_menu
from face import FakeFace
from gui.main import KioskWindow, demo_vault
from gui.widgets import TEMPERATURE_PHOTOS, menu_photo_path


def test_every_hot_and_ice_drink_has_its_other_photo():
    menu = make_menu()
    for item in menu.values():
        temps = available_options(item)["temperatures"]
        if temps != ["HOT", "ICE"] or item["category"] == "디카페인":
            continue
        base = menu_photo_path(item)
        ice, hot = menu_photo_path(item, "ICE"), menu_photo_path(item, "HOT")
        assert base is not None, item["name"]
        assert ice != hot, f"{item['name']}: HOT·ICE 사진이 같다"
    assert len(list(TEMPERATURE_PHOTOS.glob("*.png"))) == 23


def test_photo_rules_for_special_cases():
    menu = {item["name"]: item for item in make_menu().values()}
    assert menu_photo_path(menu["아메리카노"], "ICE").name == "M001_ICE.png"
    assert menu_photo_path(menu["아메리카노"], "HOT") == menu_photo_path(menu["아메리카노"])      # 기본 = HOT
    assert menu_photo_path(menu["연유라떼"], "HOT").name == "M008_HOT.png"                       # 기본이 아이스
    assert menu_photo_path(menu["연유라떼"], "ICE") == menu_photo_path(menu["연유라떼"])
    assert menu_photo_path(menu["디카페인 카페라떼"], "ICE").name == "M002_ICE.png"              # 디카페인은 일반 메뉴 사진
    assert menu_photo_path(menu["딸기라떼"], "ICE") == menu_photo_path(menu["딸기라떼"])         # ICE만 되는 메뉴


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    result = KioskWindow(vault=demo_vault(), face_factory=lambda vault: FakeFace())
    result.show()
    app.processEvents()
    yield result
    result.close()
    result.deleteLater()
    app.processEvents()


def test_option_photo_follows_temperature(window):
    router = window.router
    router.open_action("guest")
    menu = router.screens["menu"]
    menu.show_category("커피")
    menu.open_option("M001")
    popup = menu.popup
    first = popup.photo_widget.pixmap().cacheKey()            # 기본 선택은 ICE
    hot = next(b for b in popup.temperature_group.buttons() if b.property("value") == "HOT")
    hot.click()
    assert popup.photo_widget.pixmap().cacheKey() != first
    assert popup.photo_layout.count() == 1                    # 사진은 한 장만 (바꿀 때 예전 사진을 뗀다)
