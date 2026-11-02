"""11/02 B9 스마일 할인: 운영자 행사(긴 기간) · 웃음 확인 · 결제 금액에서 빼기."""
import os
from datetime import datetime

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

from core.storage import MemoryVault
from domain import seed
from domain.benefits import apply_benefits
from domain.orders import complete_order
from domain.policy import banner_message, describe_event, load_policy, smile_amount, upsert_event, validate_event


def smile_vault(amount=500):
    vault = MemoryVault()
    seed.run(vault)
    policy, _ = upsert_event(load_policy({}), {"name": "스마일", "start": "2026-11-01", "end": "2027-02-28",
                                               "smile_discount": amount})
    vault.write("settings", {"point_policy": policy})
    return vault


def test_smile_event_rules():
    event = validate_event({"name": "스마일", "start": "2026-11-01", "end": "2027-02-28", "smile_discount": "500"})
    assert event["smile_discount"] == 500 and "스마일 −500원" in describe_event(event)
    assert banner_message(event).startswith("카메라 보고 웃으면 500원 할인")
    with pytest.raises(ValueError, match="0~5,000원"):
        validate_event({"name": "x", "start": "2026-11-01", "end": "2026-11-02", "smile_discount": 9000})
    with pytest.raises(ValueError, match="중 하나는"):
        validate_event({"name": "x", "start": "2026-11-01", "end": "2026-11-02"})
    policy, _ = upsert_event(load_policy({}), event)
    assert smile_amount(policy, datetime(2026, 12, 1)) == 500
    assert smile_amount(policy, datetime(2027, 3, 1)) == 0


def test_smile_discount_for_guest_and_member():
    assert apply_benefits(4500, None, smile=500)["final_total"] == 4000
    vault = smile_vault()
    customer = vault.read("customers")["C0002"]
    assert apply_benefits(4500, customer, smile=500)["smile_discount"] == 500
    cart = {"M001": {"menu_id": "M001", "quantity": 1, "options": {}}}
    order = complete_order(vault, cart, 10000, smiled=True, now=datetime(2026, 11, 2, 12))
    assert order["smile_discount"] == 500 and order["final_total"] == order["total"] - 500
    late = complete_order(vault, cart, 10000, smiled=True, now=datetime(2027, 3, 2, 12))
    assert late["smile_discount"] == 0          # 행사가 끝나면 웃어도 할인 없음


def test_cart_smile_button(monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from face import FakeFace
    from gui.main import KioskWindow, demo_vault
    app = QApplication.instance() or QApplication([])
    window = KioskWindow(vault=demo_vault(), face_factory=lambda vault: FakeFace())
    window.show()
    router = window.router
    session = router.session
    session.add(next(iter(session.menu())), {})
    router.show_screen("cart")
    cart = router.screens["cart"]
    if not session.smile_offer():
        pytest.skip("오늘 진행 중인 스마일 행사가 없음")
    assert cart.smile_button.isVisible() and cart.smile_button.isEnabled()
    before = session.final_total()
    cart.try_smile()
    assert session.smiled and not cart.smile_button.isEnabled()
    assert session.final_total() == before - session.smile_offer()
    window.close()
    window.deleteLater()
    app.processEvents()
