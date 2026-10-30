"""10/31: 카페인 리포트 줄임 · 주별/월별 그래프 · 카페인 알리미(이번 주 제한, 넘으면 묻기)."""
import os
from datetime import date, datetime

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

from domain.my_menu import caffeine_report, caffeine_trend, limit_warning, lines_caffeine

MENU = {"M001": {"id": "M001", "name": "아메리카노", "caffeine_mg": 150},
        "M051": {"id": "M051", "name": "디카페인 아메리카노", "caffeine_mg": 0, "decaf": True}}


def order(day, quantity, menu_id="M001", customer="C1"):
    return {"created_at": datetime(day.year, day.month, day.day, 10).isoformat(),
            "customer": {"id": customer}, "lines": [{"menu_id": menu_id, "quantity": quantity, "options": {}}]}


ORDERS = {"a": order(date(2026, 10, 26), 2), "b": order(date(2026, 10, 29), 1),
          "c": order(date(2026, 10, 20), 1), "d": order(date(2026, 9, 3), 4), "e": order(date(2026, 10, 27), 9, customer="C2")}
TODAY = date(2026, 10, 31)                       # 토요일, 이번 주 월요일 = 10/26


def test_report_names_the_biggest_day():
    report = caffeine_report(ORDERS, "C1", MENU, TODAY)
    assert report["total"] == 450 and report["message"] == "월요일에 가장 많은 카페인을 섭취했어요!"
    assert caffeine_report({}, "C1", MENU, TODAY)["message"] == "이번 주 카페인 기록이 아직 없어요"


def test_trend_by_week_and_month():
    week = caffeine_trend(ORDERS, "C1", MENU, "주별", TODAY)
    assert len(week["values"]) == 8 and week["labels"][-2:] == ["19", "26"] and week["labels"][0] == "9/7"
    assert week["values"][-2:] == [150, 450]
    month = caffeine_trend(ORDERS, "C1", MENU, "월별", TODAY)
    assert month["labels"] == ["5월", "6월", "7월", "8월", "9월", "10월"]
    assert month["values"][-2:] == [600, 600]
    assert caffeine_trend(ORDERS, "C1", MENU, "이번 주", TODAY)["values"][0] == 300


def test_limit_warning_by_cups_and_mg():
    adding = lines_caffeine([{"menu_id": "M001", "quantity": 2, "options": {}}], MENU)
    assert adding == {"mg": 300, "잔": 2}
    used = {"mg": 450, "잔": 3}
    assert "5잔" in limit_warning({"unit": "잔", "amount": 4}, used, adding)
    assert limit_warning({"unit": "잔", "amount": 5}, used, adding) is None
    assert "750mg" in limit_warning({"unit": "mg", "amount": 600}, used, adding)
    decaf = lines_caffeine([{"menu_id": "M051", "quantity": 3, "options": {}}], MENU)
    assert limit_warning({"unit": "잔", "amount": 1}, used, decaf) is None    # 디카페인은 묻지 않는다


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


def test_alert_asks_before_going_over(window):
    router = window.router
    member = next(iter(router.session.vault.read("customers").values()))
    router.start_member_order(member)
    menu = router.screens["menu"]
    assert menu.limit_amount.text() == "꺼짐"
    menu.change_limit(step=1)                    # 꺼진 상태에서 + → 주 3잔
    assert menu.limit_amount.text() == "주 3잔"
    menu.change_limit(step=-1)
    assert router.session.caffeine_limit() == {"unit": "잔", "amount": 2}
    menu.change_limit(unit="mg")
    assert menu.limit_amount.text() == "주 400mg"
    menu.change_limit(unit="잔")
    menu.change_limit(step=-1)                   # 3 → 2잔
    popup = menu.popup
    popup.open_for("M001")
    popup.quantity = 3
    popup.add_to_cart()
    assert popup.warning.isVisibleTo(popup) and "그래도 담을까요?" in popup.warning_text.text()
    assert router.session.lines() == []
    popup.warning_cancel.click()                 # 아니요 → 담지 않고 나간다
    assert not popup.isVisible() and router.session.lines() == []
    popup.open_for("M001")
    popup.quantity = 3
    popup.add_to_cart()
    popup.confirm_button.click()                 # 예 → 담긴다
    assert router.session.lines()[0]["quantity"] == 3


def test_reorder_asks_too_and_graph_views_switch(window):
    router = window.router
    session = router.session
    member = next(iter(session.vault.read("customers").values()))
    session.login(member)
    session.add("M001", None, 2)
    session.insert(50000)
    session.pay()
    router.start_member_order(session.customer)
    menu = router.screens["menu"]
    menu.change_limit(unit="잔")
    menu.change_limit(step=-1)                   # 주 2잔, 이미 2잔 마심
    menu.quick_button.click()
    assert menu.confirm_box.isVisible() and session.lines() == []
    menu.confirm_box.yes_button.click()
    assert router.current_name == "cart" and session.lines()[0]["quantity"] == 2
    router.start_member_order(session.customer)
    menu.trend_bars.mousePressEvent(None)
    assert menu.caffeine_view == "주별" and len(menu.trend_bars.values) == 8
    menu.view_buttons["월별"].click()
    assert len(menu.trend_bars.labels) == 6 and menu.view_buttons["월별"].isChecked()
