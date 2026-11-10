"""11/04: 회원에게 '처음으로'는 '로그아웃'으로 보이고 한 번 묻는다. 혜택 화면에는 '메뉴로' 버튼."""
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


def leave_button(router, name):
    from PySide6.QtWidgets import QPushButton
    return router.screens[name].findChild(QPushButton, "leave_button")


def test_member_sees_logout_and_is_asked(window):
    router = window.router
    member = next(iter(router.session.vault.read("customers").values()))
    router.session.login(member)
    router.show_screen("menu")
    button = leave_button(router, "menu")
    assert button.text() == "로그아웃"
    button.click()
    box = router.away_box                                                 # 11/07: 10초 카운트다운 상자로 묻는다
    assert box.isVisible() and router.current_name == "menu"              # 바로 나가지 않고 묻는다
    assert "(10)" in box.yes_button.text()
    box.no_button.click()
    assert router.current_name == "menu" and router.session.is_member()   # 아니요 → 그대로
    button.click()
    box.yes_button.click()
    assert router.current_name == "idle" and not router.session.is_member()


def test_guest_without_items_goes_straight_back(window):
    router = window.router
    router.open_action("guest")
    button = leave_button(router, "menu")
    assert button.text() == "처음으로"
    button.click()
    assert router.current_name == "idle" and not router.popup.isVisible()


def test_benefit_screen_has_menu_button(window):
    from PySide6.QtWidgets import QPushButton
    router = window.router
    member = next(iter(router.session.vault.read("customers").values()))
    router.session.login(member)
    router.session.add("M001", None, 1)
    router.show_screen("benefit")
    names = [b.text() for b in router.screens["benefit"].findChildren(QPushButton)]
    assert "메뉴로" in names and leave_button(router, "benefit").text() == "로그아웃"
    next(b for b in router.screens["benefit"].findChildren(QPushButton) if b.text() == "메뉴로").click()
    assert router.current_name == "menu" and router.session.cart        # 담은 것은 그대로


def test_password_mode_puts_cursor_in_password_field(window):
    """11/04: 아이디를 넣고 '비밀번호로 로그인'을 누르면 비밀번호 칸에 바로 커서가 간다."""
    from PySide6.QtWidgets import QApplication
    router = window.router
    router.open_action("member")
    login = router.screens["login"]
    login.login_id.setText("bomin")
    login.password_mode_button.click()
    QApplication.processEvents()
    assert login.password.hasFocus() and login.keyboard.target is login.password


def test_use_all_points_never_more_than_amount_due(window):
    """11/04 회의: 포인트가 많아도 '전액 사용'은 결제 금액(카드 첫 주문 할인 · 쿠폰을 뺀 음료값)까지만."""
    from domain.member_cards import register_first_tap
    router = window.router
    session = router.session
    vault = session.vault
    customers = vault.read("customers")
    member = next(iter(customers.values()))
    member["extra"]["points"] = 50000
    vault.write("customers", customers)
    from domain.member_cards import purchase_card
    purchase_card(vault, member["id"], "new", "", 1000)
    register_first_tap(vault, member["id"], "CAFE9999")           # 다음 주문 10% 할인
    session.login(vault.read("customers")[member["id"]])
    session.add("M001", None, 1)
    router.show_screen("benefit")
    screen = router.screens["benefit"]
    screen.use_all_points()
    benefit = session.benefit()
    assert screen.message.text() == ""
    assert benefit["card_discount"] > 0 and session.use_points > 0
    assert session.use_points <= session.drink_total() - benefit["card_discount"]
