"""07 현금 결제의 모든 상황: 넣기 · 빼기(반환) · 넣었다 빼기 · 딱 맞게 · 초과 · 0원 결제 · 결제 실패 · 시간 경고.

10/29: 반환 뒤에도 '충분해요'가 남던 문제(포인트 전액 결제 등)를 막으려고
'방금 일어난 일'(event 줄)과 '지금 상태'(status 줄)를 나눴다.
"""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from face import FakeFace
from gui.main import KioskWindow, demo_vault


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    result = KioskWindow(vault=demo_vault(), face_factory=lambda vault: FakeFace())
    result.show()
    app.processEvents()
    yield result
    result.close()
    result.deleteLater()
    app.processEvents()


def guest_cash(window, menu_id="M001"):
    """비회원 · 3,000원짜리 하나를 담고 07 화면."""
    router = window.router
    router.open_action("guest")
    router.session.add(menu_id, None, 1)
    router.show_screen("cash")
    return router.screens["cash"]


def member_cash(window, points=0, use_points=0):
    router = window.router
    router.open_action("member")
    vault = router.session.vault
    customers = vault.read("customers")
    member = next(iter(customers.values()))
    member["extra"]["points"] = points
    vault.write("customers", customers)
    router.start_member_order(member)
    router.session.add("M001", None, 1)
    if use_points:
        router.session.set_benefit(None, use_points)
    router.show_screen("cash")
    return router.screens["cash"]


def test_insert_then_refund_shows_start_state_not_enough(window):
    cash = guest_cash(window)
    assert cash.status.text() == "현금 3,000원을 넣어 주세요" and not cash.pay_button.isEnabled()
    cash.insert(5000)
    assert "충분해요" in cash.status.text() and cash.event.text() == "5,000원 받았어요"
    cash.refund()
    assert "5,000원을 돌려드렸어요" in cash.event.text()
    assert cash.status.text() == "현금 3,000원을 넣어 주세요"            # '충분해요'가 남지 않는다
    assert not cash.pay_button.isEnabled() and cash.cash_buttons[0].isEnabled()
    assert cash.remain_value.text() == "3,000원"
    cash.refund()
    assert cash.event.text() == "돌려드릴 현금이 없어요"


def test_partial_exact_and_too_much(window):
    cash = guest_cash(window)
    cash.insert(1000)
    assert cash.status.text() == "2,000원 더 넣어 주세요" and "1,000원 받았어요" in cash.change_text.text()
    cash.insert(1000)
    cash.insert(1000)
    assert cash.status.text().startswith("딱 맞아요") and cash.change_text.text() == "거스름돈 없음"
    assert cash.pay_button.isEnabled() and not any(b.isEnabled() for b in cash.cash_buttons)   # 투입구 닫힘
    cash.refund()
    cash.insert(10000)
    assert "거스름돈 7,000원" in cash.status.text()
    cash.insert(1000)                                   # 혹시 더 넣어도 받지 않는다
    assert window.router.session.inserted == 10000 and "받지 않았어요" in cash.event.text()


def test_done_screen_reminds_to_take_change(window):
    cash = guest_cash(window)
    cash.insert(5000)
    cash.finish()
    done = window.router.screens["done"]
    assert not done.change_notice.isHidden() and "2,000원" in done.change_notice.text()
    cash = guest_cash(window)
    cash.insert(1000), cash.insert(1000), cash.insert(1000)
    cash.finish()
    assert done.change_notice.isHidden()               # 딱 맞으면 안내 없음


def test_points_cover_everything(window):
    cash = member_cash(window, points=10000, use_points=3000)
    assert cash.status.text() == "쿠폰·포인트로 전액 할인됐어요"
    assert cash.pay_button.isEnabled() and cash.change_card.isHidden()
    cash.insert(1000)
    assert window.router.session.inserted == 0 and "필요 없어서" in cash.event.text()
    cash.finish()
    order = window.router.session.last_order
    assert window.router.current_name == "done" and order["final_total"] == 0 and order["cash"] == 0


def test_change_points_choice_resets_after_refund(window):
    cash = member_cash(window)
    cash.insert(5000)
    cash.change_check.setChecked(True)
    assert "포인트로 적립돼요" in cash.status.text()
    cash.refund()
    assert not window.router.session.change_to_points and not cash.change_check.isChecked()
    cash.insert(5000)
    assert "거스름돈 2,000원이 나와요" in cash.status.text()


def test_failed_payment_keeps_money_and_says_so(window, monkeypatch):
    cash = guest_cash(window)
    cash.insert(5000)

    def broken():
        raise ValueError("재고가 부족합니다")
    monkeypatch.setattr(window.router.session, "pay", broken)
    cash.finish()
    assert window.router.current_name == "cash"
    assert "결제하지 못했어요" in cash.event.text() and "5,000원은 그대로" in cash.event.text()


def test_warning_before_going_home(window):
    router = window.router
    cash = guest_cash(window)
    cash.insert(1000)
    router.warn_time_out()
    assert "15초 뒤" in router.notice.text() and "1,000원은 반환" in router.notice.text()
    router.restart_timer()                              # 손님이 화면을 누르면 경고가 사라진다
    assert router.notice.isHidden()
