"""11/03 맨 앞 분기: 매장 / 포장 고르기 → 주문 · 완료 화면 · 영수증에 남는다. 대기 화면에서 카드를 대도 여기를 먼저."""
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest


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


def test_takeout_goes_through_order_and_done_screen(window):
    from PySide6.QtWidgets import QLabel
    router = window.router
    session = router.session
    router.show_screen("dine")
    router.screens["dine"].choose(True)
    assert router.current_name == "home" and session.takeout is True
    router.open_action("guest")
    session.add("M001", None, 1)
    router.show_screen("cart")
    assert router.screens["cart"].summary_title.text() == "주문 합계 · 포장"
    session.insert(10000)
    order = session.pay()
    assert order["takeout"] is True
    router.show_screen("done")
    texts = [w.text() for w in router.screens["done"].findChildren(QLabel) if w.isVisibleTo(window)]
    assert "대기 번호 · 포장" in texts and "영수증 · 포장" in texts
    router.show_screen("idle")
    assert session.takeout is None                    # 다음 손님은 다시 고른다


def test_card_tag_on_idle_asks_dine_first_then_logs_in(window):
    from domain.member_cards import purchase_card, register_first_tap
    router = window.router
    vault = router.session.vault
    purchase_card(vault, "C0001", "new", "", 1000)
    register_first_tap(vault, "C0001", "CAFE1234")
    router.show_screen("idle")
    router.card_scanned("CAFE1234")
    assert router.choosing_dine() and router.current_name == "idle"   # 대기 화면 위에 매장 / 포장 버튼
    router.choose_dine(False)
    assert router.current_name == "login" and router.screens["login"].login_id.text() == "bomin"
    assert router.session.takeout is False
