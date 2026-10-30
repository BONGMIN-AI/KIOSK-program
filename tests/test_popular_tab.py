"""10/31: 인기 탭 — 좋아요순 · 판매순 · 계절 인기순 (시연용 가상 기록 + 실제 기록)."""
import os
from datetime import date

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

from domain.popular import ranking, season_of
from domain.seed import make_menu

MENU = {"M001": {"id": "M001", "name": "아메리카노", "demo_likes": 5, "sold_count": 100,
                 "demo_season": {"가을": 30, "여름": 10}},
        "M002": {"id": "M002", "name": "카페라떼", "demo_likes": 5, "sold_count": 200,
                 "demo_season": {"가을": 10, "여름": 50}},
        "M003": {"id": "M003", "name": "숨긴 메뉴", "demo_likes": 99, "sold_count": 999, "hidden": True}}


def test_likes_add_member_hearts_to_demo_counts():
    customers = {"C1": {"extra": {"likes": ["M002"]}}, "C2": {"extra": {"likes": ["M002", "M404"]}}}
    rows = ranking("좋아요순", MENU, customers, {})
    assert [(row["item"]["id"], row["value"], row["text"]) for row in rows] == [
        ("M002", 7, "♥ 7"), ("M001", 5, "♥ 5")]


def test_sales_and_season_orders():
    assert [row["item"]["id"] for row in ranking("판매순", MENU, {}, {})] == ["M002", "M001"]
    orders = {"o": {"created_at": "2025-10-03T10:00:00", "lines": [{"menu_id": "M002", "quantity": 25}]},
              "x": {"created_at": "2026-07-01T10:00:00", "lines": [{"menu_id": "M002", "quantity": 99}]}}
    autumn = ranking("계절 인기순", MENU, {}, orders, today=date(2026, 10, 31))
    assert [(row["item"]["id"], row["text"]) for row in autumn] == [("M002", "가을 35잔"), ("M001", "가을 30잔")]
    assert season_of(date(2026, 1, 5)) == "겨울"
    with pytest.raises(ValueError):
        ranking("가격순", MENU, {}, {})


def test_seed_menu_has_demo_popularity():
    rows = ranking("좋아요순", make_menu(), {}, {})
    assert len(rows) == 9 and rows[0]["item"]["name"] == "딸기라떼"
    assert ranking("판매순", make_menu(), {}, {})[0]["item"]["name"] == "아메리카노"


@pytest.fixture
def window():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from face import FakeFace
    from gui.main import KioskWindow, demo_vault
    app = QApplication.instance() or QApplication([])
    result = KioskWindow(vault=demo_vault(), face_factory=lambda vault: FakeFace())
    result.show()
    app.processEvents()
    yield result
    result.close()
    result.deleteLater()
    app.processEvents()


def badges(menu):
    from PySide6.QtWidgets import QLabel
    return [tag.text() for tag in menu.grid_area.widget().findChildren(QLabel) if "위 · " in tag.text()]


def test_popular_tab_for_guest_and_sort_switch(window):
    from PySide6.QtTest import QTest
    router = window.router
    router.open_action("guest")
    menu = router.screens["menu"]
    assert "인기" in router.session.categories()
    menu.show_category("인기")
    assert badges(menu)[0] == "1위 · ♥ 58"
    menu.sort_buttons["판매순"].click()
    QTest.qWait(50)
    assert badges(menu)[0] == "1위 · 누적 1,250잔"
    assert menu.sort_buttons["판매순"].isChecked()


def test_popular_tab_for_member(window):
    router = window.router
    member = next(iter(router.session.vault.read("customers").values()))
    router.start_member_order(member)
    assert router.session.categories()[:2] == ["My Menu", "인기"]
