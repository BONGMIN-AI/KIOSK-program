"""11/01 회원카드: 신청 → 운영자 허용 → 빈 카드 할당 · 첫 주문 10% · 적립 +1%p · 분실 재발급 / 흐르는 초시계."""
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

from core.storage import MemoryVault
from domain import seed
from domain.cart import add_item
from domain.customers import find_by_card
from domain.member_cards import (
    approve_request, card_status_text, is_lost_card, issue_card, open_request, reject_request, request_card,
)
from domain.orders import complete_order


def make_vault():
    vault = MemoryVault()
    seed.run(vault)
    return vault


def customer(vault, customer_id="C0002"):
    return vault.read("customers")[customer_id]


def test_request_approve_issue_and_status():
    vault = make_vault()
    request = request_card(vault, "C0002")
    assert request["status"] == "waiting" and request["fee"] == 0
    assert card_status_text(vault, customer(vault)) == "회원카드 승인 대기 중"
    with pytest.raises(ValueError, match="이미 신청"):
        request_card(vault, "C0002")
    with pytest.raises(ValueError):                         # 허용 전에는 카드를 할당할 수 없다
        issue_card(vault, request["id"], "A1B2C3D4", "admin")
    approve_request(vault, request["id"], "admin")
    assert "카운터" in card_status_text(vault, customer(vault))
    issued = issue_card(vault, request["id"], "A1B2C3D4", "admin")
    assert issued["status"] == "issued" and issued["card_tail"] == "C3D4"
    assert find_by_card(vault, "A1B2C3D4")["id"] == "C0002"
    assert card_status_text(vault, customer(vault)) == "회원카드 사용 중" and open_request(vault, "C0002") is None
    with pytest.raises(ValueError, match="이미 회원카드"):
        request_card(vault, "C0002")


def test_card_already_used_by_other_member_is_refused():
    vault = make_vault()
    for member_id, uid in (("C0002", "11112222"), ("C0003", None)):
        request = request_card(vault, member_id)
        approve_request(vault, request["id"], "admin")
        if uid:
            issue_card(vault, request["id"], uid, "admin")
    with pytest.raises(ValueError, match="다른 회원"):
        issue_card(vault, open_request(vault, "C0003")["id"], "11112222", "admin")


def test_first_order_discount_once_and_bonus_points():
    vault = make_vault()
    request = request_card(vault, "C0002")
    approve_request(vault, request["id"], "admin")
    issue_card(vault, request["id"], "55556666", "admin")
    menu = vault.read("menu")
    cart = add_item({}, "M001", 2, None, menu)               # 6,000원
    first = complete_order(vault, cart, 10000, customer_id="C0002")
    assert first["card_discount"] == 600 and first["final_total"] == 5400
    assert first["earned_points"] == 108                     # 5,400 × (1% + 카드 1%p)
    second = complete_order(vault, add_item({}, "M001", 2, None, menu), 10000, customer_id="C0002")
    assert second["card_discount"] == 0 and second["earned_points"] == 120   # 할인은 한 번만, 적립 2%는 계속


def test_lost_card_reissue_blocks_old_card_and_charges_fee():
    vault = make_vault()
    request = request_card(vault, "C0002")
    approve_request(vault, request["id"], "admin")
    issue_card(vault, request["id"], "OLD11111", "admin")
    complete_order(vault, add_item({}, "M001", 1, None, vault.read("menu")), 5000, customer_id="C0002")   # 첫 주문 할인 씀
    reissue = request_card(vault, "C0002", "reissue")
    assert reissue["fee"] == 1000
    assert find_by_card(vault, "OLD11111") is None and is_lost_card(vault, "OLD11111")
    approve_request(vault, reissue["id"], "admin")
    with pytest.raises(ValueError, match="분실"):
        issue_card(vault, reissue["id"], "OLD11111", "admin")
    issue_card(vault, reissue["id"], "NEW22222", "admin")
    assert find_by_card(vault, "NEW22222")["id"] == "C0002"
    assert not customer(vault)["extra"].get("card_first_discount")   # 재발급으로 첫 주문 할인이 다시 생기지 않는다


def test_reject_and_reissue_without_card():
    vault = make_vault()
    with pytest.raises(ValueError, match="발급받은"):
        request_card(vault, "C0002", "reissue")
    request = request_card(vault, "C0002")
    reject_request(vault, request["id"], "admin")
    assert open_request(vault, "C0002") is None
    request_card(vault, "C0002")                             # 거절 뒤에는 다시 신청할 수 있다


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


def test_countdown_text_goes_down(window):
    """11/01: '15초 뒤 …'가 멈춰 있지 않고 1초마다 줄어든다."""
    router = window.router
    router.show_screen("home")
    router.warn_time_out()
    assert router.notice.text().startswith("15초 뒤")
    router.notice.count_down()
    assert router.notice.text().startswith("14초 뒤")
    router.restart_timer()                                   # 화면을 누르면 띠가 내려간다
    assert not router.notice.isVisible()


def test_signup_with_card_request_goes_to_admin(window):
    router = window.router
    router.open_action("signup")
    signup = router.screens["signup"]
    for field, text in ((signup.name, "카드손님"), (signup.login_id, "cardguest"), (signup.password, "1234"),
                        (signup.password_again, "1234"), (signup.phone, "01077778888")):
        field.setText(text)
    signup.privacy.setChecked(True)
    signup.card_request.setChecked(True)
    signup.submit()
    assert router.current_name == "menu" and "승인 대기" in router.screens["menu"].member_detail.text()
    router.admin_id = "admin"
    router.show_screen("admin", tab="cards")
    admin = router.screens["admin"]
    assert admin.card_table.rowCount() == 1 and "회원카드 발급 (1)" in [b.text() for b in admin.tab_group.buttons()]


def test_serial_reader_explains_refused_and_misread_cards(window):
    from gui.serial_card import SerialCardReader
    router = window.router
    reader = SerialCardReader(router.card_active)
    reader.scanned.connect(router.card_scanned)
    reader.notice.connect(router.card_refused)
    router.open_action("guest")                              # 메뉴 화면: 카드를 받지 않는다
    reader.deliver("84E3D273")
    assert router.notice.isVisible() and "처음 화면" in router.notice.text()
    reader.relay.misread.emit()
    assert "읽지 못했어요" in router.notice.text()
