"""회원카드 (11/03 바꿈): 장바구니에 담아 음료와 함께 결제 → '미사용' → 다음 주문 때 처음 대면 등록
→ 그 주문 10% 할인 · 카드 회원 3% 적립 · 스탬프 10개 = 음료 무료 · 카드 로그인 / 분실 신고(My Menu · 운영자) · 재발급 500원."""
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

from core.storage import MemoryVault
from domain import seed
from domain.cart import add_item
from domain.customers import find_by_card
from domain.member_cards import (
    card_status_text, check_can_buy, is_lost_card, register_first_tap, report_lost, requests_of, unregister_card,
    unused_card,
)
from domain.orders import complete_order


def make_vault():
    vault = MemoryVault()
    seed.run(vault)
    return vault


def customer(vault, customer_id="C0002"):
    return vault.read("customers")[customer_id]


def buy(vault, kind="new", customer_id="C0002"):
    cart = add_item({}, "M001", 1, None, vault.read("menu"))
    return complete_order(vault, cart, 10000, customer_id=customer_id, card_kind=kind)


def test_card_is_paid_with_drinks_and_stays_unused():
    vault = make_vault()
    order = buy(vault)
    drink = order["lines"][0]["subtotal"]
    assert order["card_total"] == 1000 and order["final_total"] == drink + 1000
    assert unused_card(vault, "C0002")["status"] == "unused"
    assert card_status_text(vault, customer(vault)) == "회원카드 등록 전"
    with pytest.raises(ValueError, match="아직 등록하지"):
        check_can_buy(vault, customer(vault), "new")
    with pytest.raises(ValueError, match="회원만"):
        complete_order(vault, {}, 1000, card_kind="new")


def test_first_tap_gives_10_percent_on_that_order_then_3_percent():
    vault = make_vault()
    buy(vault)
    record = register_first_tap(vault, "C0002", "A1B2C3D4")
    assert record["status"] == "issued" and record["card_tail"] == "C3D4"
    assert find_by_card(vault, "A1B2C3D4")["id"] == "C0002"
    assert card_status_text(vault, customer(vault)) == "회원카드 사용 중"
    with pytest.raises(ValueError, match="등록할 회원카드가 없어요"):
        register_first_tap(vault, "C0002", "A1B2C3D4")
    first = complete_order(vault, add_item({}, "M001", 2, None, vault.read("menu")), 10000, customer_id="C0002")
    assert first["card_discount"] == first["lines"][0]["subtotal"] // 10 // 10 * 10       # 카드 등록한 주문 10%
    assert first["earned_points"] == first["final_total"] * 3 // 100                      # 기본 1% 대신 3%
    second = buy(vault, kind=None)
    assert second["card_discount"] == 0                                                    # 할인은 한 번만
    buy(vault, customer_id="C0003")
    with pytest.raises(ValueError, match="다른 회원"):
        register_first_tap(vault, "C0003", "A1B2C3D4")


def test_stamps_give_free_drink_coupon_at_ten():
    vault = make_vault()
    buy(vault)
    register_first_tap(vault, "C0002", "STAMP001")
    for count in range(1, 10):
        order = buy(vault, kind=None)
        assert order["card_stamp"] == {"stamps": count, "goal": 10, "coupon": None}
    tenth = buy(vault, kind=None)
    assert tenth["card_stamp"] == {"stamps": 0, "goal": 10, "coupon": "음료 1잔 무료 (5,000원까지)"}
    assert any(c["name"] == "음료 1잔 무료 (5,000원까지)" for c in customer(vault)["extra"]["coupons"])
    assert buy(vault, kind=None, customer_id="C0003")["card_stamp"] is None             # 카드 없으면 스탬프 없음


def test_lost_card_blocks_old_and_reissue_costs_500_without_discount():
    vault = make_vault()
    buy(vault)
    register_first_tap(vault, "C0002", "OLD11111")
    report_lost(vault, "C0002")
    assert is_lost_card(vault, "OLD11111") and find_by_card(vault, "OLD11111") is None
    with pytest.raises(ValueError, match="재발급"):
        check_can_buy(vault, customer(vault), "new")
    order = buy(vault, "reissue")
    assert order["card_total"] == 500
    with pytest.raises(ValueError, match="분실 신고된"):
        register_first_tap(vault, "C0002", "OLD11111")
    register_first_tap(vault, "C0002", "NEW22222")
    assert find_by_card(vault, "NEW22222")["id"] == "C0002"
    assert not customer(vault)["extra"].get("card_first_discount")       # 재발급은 첫 주문 할인 없음
    with pytest.raises(ValueError, match="없어요"):
        check_can_buy(vault, customer(vault, "C0003"), "reissue")


def test_admin_unregister_stops_card():
    vault = make_vault()
    buy(vault)
    record = register_first_tap(vault, "C0002", "55556666")
    unregister_card(vault, record["id"], "admin")
    assert find_by_card(vault, "55556666") is None
    assert requests_of(vault)[record["id"]]["status"] == "revoked"
    with pytest.raises(ValueError, match="미사용 · 사용 중"):
        unregister_card(vault, record["id"], "admin")


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


def test_signup_card_goes_to_cart_then_pay_then_first_tap(window):
    router = window.router
    session = router.session
    router.open_action("signup")
    signup = router.screens["signup"]
    for field, text in ((signup.name, "카드손님"), (signup.login_id, "cardguest"), (signup.password, "1234"),
                        (signup.password_again, "1234"), (signup.phone, "01077778888")):
        field.setText(text)
    signup.privacy.setChecked(True)
    signup.card_request.setChecked(True)
    signup.submit()
    assert router.current_name == "menu" and session.card_kind == "new"
    assert "장바구니에 담았어요" in router.notice.text()
    session.add("M001", None, 1)
    router.show_screen("cart")
    assert session.total() == session.drink_total() + 1000
    router.show_screen("cash")
    session.insert(10000)
    order = session.pay()
    assert order["card_kind"] == "new" and session.card_kind is None
    router.show_screen("done")
    from PySide6.QtWidgets import QLabel
    receipt = " ".join(w.text() for w in router.screens["done"].findChildren(QLabel) if w.isVisibleTo(window))
    assert "음료와 함께 받아" in receipt and "회원카드 (신규)" in receipt
    cid = session.customer["id"]
    router.start_member_order(session.vault.read("customers")[cid])        # 다음 주문
    assert "리더기에 대면 등록" in router.notice.text()
    assert router.card_active()                                              # 메뉴 화면에서도 카드를 받는다
    router.card_scanned("ABCD1234")
    shown = router.popup.title.text() + router.popup.text.text()
    assert "등록 완료" in shown and "10% 할인" in shown and "3% 적립" in shown
    assert session.card_status() == "회원카드 사용 중"
    router.show_screen("idle")
    router.card_scanned("ABCD1234")                                          # 다음부터 카드만 대면 로그인
    assert router.choosing_dine() and router.current_name == "idle"   # 대기 화면 위에 매장 / 포장 버튼
    router.choose_dine(False)
    assert router.current_name == "login" and router.screens["login"].login_id.text() == "cardguest"


def test_unknown_card_while_logged_out_says_log_in_first(window):
    router = window.router
    router.show_screen("idle")
    router.card_scanned("5555555555")
    assert router.current_name == "idle" and "로그인한 뒤" in router.notice.text()


def test_serial_reader_explains_refused_and_misread_cards(window):
    from gui.serial_card import SerialCardReader
    router = window.router
    reader = SerialCardReader(router.card_active)
    reader.scanned.connect(router.card_scanned)
    reader.notice.connect(router.card_refused)
    router.open_action("guest")                              # 비회원 메뉴 화면: 카드를 받지 않는다
    reader.deliver("84E3D273")
    assert router.notice.isVisible() and "처음 화면" in router.notice.text()
    reader.relay.misread.emit()
    assert "읽지 못했어요" in router.notice.text()


def test_admin_cards_page_lists_and_unregisters(window):
    router = window.router
    vault = router.session.vault
    buy(vault)
    register_first_tap(vault, "C0002", "77778888")
    buy(vault, customer_id="C0003")
    router.admin_id = "admin"
    router.show_screen("admin", tab="cards")
    admin = router.screens["admin"]
    assert admin.card_table.rowCount() == 2 and "사용 중 1장 · 미사용 1장" == admin.card_count.text()
    assert not admin.card_unregister_button.isEnabled()
    statuses = [admin.card_table.item(r, 6).text() for r in range(2)]
    assert statuses == ["미사용", "사용 중"]
    from PySide6.QtCore import Qt
    admin.card_table.item(1, 0).setCheckState(Qt.CheckState.Checked)
    assert admin.card_unregister_button.isEnabled()
    admin.unregister_cards()
    assert find_by_card(vault, "77778888") is None


def test_admin_screen_has_no_idle_logout_and_perks_are_adjustable(window):
    """운영자 화면은 직접 로그아웃할 때만 · 회원카드 값 · 카드 회원 적립률은 운영자가 바꾸고 가입 화면에 바로 보인다."""
    router = window.router
    router.admin_id = "admin"
    router.show_screen("admin", tab="perks")
    assert not router.timer.isActive() and not router.warn_timer.isActive()
    admin = router.screens["admin"]
    assert admin.perk_fields["card_point_rate"].text() == "3"
    admin.perk_fields["card_price"].setText("2000")
    admin.perk_fields["card_first_discount"].setText("15")
    admin.perk_fields["card_point_rate"].setText("5")
    admin.perk_fields["card_stamp_goal"].setText("8")
    admin.save_perks()
    assert "저장" in admin.message.text()
    policy = router.session.policy()
    assert (policy["card_price"], policy["card_first_discount"], policy["card_point_rate"],
            policy["card_stamp_goal"], policy["card_reissue_fee"]) == (2000, 15, 5.0, 8, 500)
    admin.perk_fields["card_point_rate"].setText("90")           # 범위 밖 → 저장 안 됨
    admin.save_perks()
    assert router.session.policy()["card_point_rate"] == 5.0
    admin.logout()
    assert router.timer.isActive()
    router.open_action("signup")
    perks = router.screens["signup"].card_perks.text()
    assert "첫 주문 15% 할인" in perks and "매 주문 5% 적립" in perks and "스탬프 8개 = 음료 1잔 무료" in perks
    assert "카드값 2,000원" in router.screens["signup"].card_how.text()


def test_lost_card_from_my_menu_and_admin(window):
    """분실 신고는 My Menu(손님) 또는 운영자 화면 '분실 처리'. 재발급 카드는 장바구니로 (500원)."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QPushButton
    router = window.router
    vault = router.session.vault
    buy(vault)
    register_first_tap(vault, "C0002", "LOST0001")
    router.start_member_order(customer(vault))
    menu = router.screens["menu"]
    links = [b.text() for b in menu.findChildren(QPushButton) if b.isVisibleTo(window)]
    assert "회원카드를 잃어버렸어요" in links
    menu.ask_lost_card()
    assert menu.confirm_box.isVisible() and "500원" in menu.confirm_box.text.text()
    menu.confirm_box.yes()
    assert is_lost_card(vault, "LOST0001") and router.session.card_kind == "reissue"
    assert router.session.card_total() == 500
    # 운영자 분실 처리 → 손님은 My Menu에서 재발급을 담는다
    buy(vault, customer_id="C0003")
    register_first_tap(vault, "C0003", "LOST0002")
    router.show_screen("idle")
    router.admin_id = "admin"
    router.show_screen("admin", tab="cards")
    admin = router.screens["admin"]
    row = next(r for r in range(admin.card_table.rowCount()) if admin.card_table.item(r, 7).text() == "****0002")
    admin.card_table.item(row, 0).setCheckState(Qt.CheckState.Checked)
    assert admin.card_lost_button.isEnabled()
    admin.mark_cards_lost()
    assert is_lost_card(vault, "LOST0002") and "분실 처리" in admin.message.text()
    admin.logout()
    router.start_member_order(customer(vault, "C0003"))
    menu = router.screens["menu"]
    menu.add_reissue_card()
    assert router.session.card_kind == "reissue"
