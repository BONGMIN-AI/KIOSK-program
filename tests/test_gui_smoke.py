"""외부 장치와 데이터 없이 화면 연결만 확인한다."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from gui import theme
from gui.main import KioskWindow, demo_vault


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    result = KioskWindow(vault=demo_vault())
    result.show()
    app.processEvents()
    yield result
    result.close()
    result.deleteLater()
    app.processEvents()


def test_initial_window(window):
    assert window.windowTitle() == "COFFEE & SPOON KIOSK"
    assert (window.width(), window.height()) == (1200, 800)
    assert not window.windowIcon().isNull()
    assert window.router.current_name == "idle"


def test_idle_home_back(window):
    router = window.router
    QTest.mouseClick(router.screens["idle"], Qt.MouseButton.LeftButton, pos=QPoint(600, 400))
    assert router.current_name == "home"
    QTest.mouseClick(router.screens["home"].back_button, Qt.MouseButton.LeftButton)
    assert router.current_name == "idle"


def test_theme_colors():
    assert [theme.BROWN, theme.CARAMEL, theme.CARAMEL_LIGHT, theme.BG,
            theme.CARD, theme.TEXT2, theme.LINE] == [
        "#3C1B03", "#B66B2E", "#F1DFCB", "#F7EEE3", "#FFFFFF", "#7A6252", "#E6D6C4"]
    assert theme.EVENT_THEMES == {
        "basic": ("#F1DFCB", "#3C1B03"),
        "season": ("#FBE3D0", "#B5561B"),
        "festival": ("#FFF0B3", "#B4236B"),
    }


def test_no_event_hides_banner(app):
    window = KioskWindow(event=None, vault=demo_vault())
    window.show()
    app.processEvents()
    banner = window.router.screens["idle"].banner
    assert banner.isHidden()
    banner.set_event(theme.EXAMPLE_EVENT)
    assert banner.isVisible()
    banner.set_event(None)
    assert banner.isHidden()
    window.close()
    window.deleteLater()


def test_language_does_not_navigate(window):
    idle = window.router.screens["idle"]
    english = idle.languages.buttons()[1]
    QTest.mouseClick(english, Qt.MouseButton.LeftButton)
    assert english.isChecked()
    assert not idle.languages.buttons()[0].isChecked()
    assert window.router.current_name == "idle"


def test_language_changes_start_text(window):
    idle = window.router.screens["idle"]
    assert idle.start_text() == "화면을 터치하여 주문을 시작하세요"
    QTest.mouseClick(idle.languages.buttons()[1], Qt.MouseButton.LeftButton)
    assert idle.start_text() == "Touch the screen to start your order"


def test_idle_uses_clean_background_and_hides_approach_hint(window):
    idle = window.router.screens["idle"]
    assert not idle.background.isNull()
    assert not idle.logo.isNull()
    assert idle.show_approach_hint is False   # D10 접근 감지 연결 전


def test_banner_alternates_event_and_approach_hint(window):
    idle = window.router.screens["idle"]
    banner = idle.banner
    assert len(banner.messages) == 1 and banner.is_scrolling()
    idle.set_approach_hint(True)
    assert len(banner.messages) == 2
    first = banner.current_text()
    assert first.startswith("가을 더블 포인트") and banner.is_scrolling()
    banner.show_next(animated=False)
    assert banner.current_text() == "가까이 오시면 자동으로 시작할 수 있어요"
    assert not banner.is_scrolling() and banner.switch_timer.isActive()   # 가운데 5초
    banner.show_next(animated=False)
    assert banner.current_text() == first
    QTest.mouseClick(idle.languages.buttons()[1], Qt.MouseButton.LeftButton)
    assert banner.messages[1][0] == "Come closer and it starts by itself"
    idle.set_approach_hint(False)
    assert len(banner.messages) == 1 and not banner.switch_timer.isActive()


def test_event_text_scrolls_right_to_left(window):
    banner = window.router.screens["idle"].banner
    assert banner.frame_timer.isActive()            # 대기 화면에 보이는 동안 움직인다
    banner.start_message()
    start = banner.offset
    assert start == banner.width()                  # 오른쪽 끝에서 시작
    banner.step()
    assert banner.offset < start                    # 왼쪽으로 이동
    banner.offset = -banner.text_width() - 1        # 다 지나가면 (문구가 하나뿐이면) 다시 오른쪽에서
    banner.step()
    assert banner.offset > banner.width() - 10
    window.router.show_screen("home")
    assert not banner.frame_timer.isActive()        # 다른 화면에서는 멈춘다


def test_scroll_end_switches_to_hint(window):
    idle = window.router.screens["idle"]
    banner = idle.banner
    idle.set_approach_hint(True)
    banner.offset = -banner.text_width() - 1
    banner.step()                                   # 다 지나가면 접근 안내로 넘어가기 시작
    hint = "가까이 오시면 자동으로 시작할 수 있어요"
    for _ in range(50):                             # 최대 5초 기다린다 (흐려졌다 나타나는 0.8초)
        if banner.current_text() == hint:
            break
        QTest.qWait(100)
    assert banner.current_text() == hint


def test_banner_shows_hint_alone_without_event(app):
    window = KioskWindow(event=None, vault=demo_vault())
    idle = window.router.screens["idle"]
    idle.set_approach_hint(True)
    assert not idle.banner.isHidden()
    assert idle.banner.current_text() == "가까이 오시면 자동으로 시작할 수 있어요"
    assert not idle.banner.switch_timer.isActive()
    window.close()
    window.deleteLater()


def test_buttons_take_no_keyboard_focus(window):
    home = window.router.screens["home"]
    for item in home.findChildren(QPushButton):
        assert item.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_home_buttons_follow_flowchart(window):
    """01 시작: 회원 → 02 로그인, 회원가입 → 10, 운영자 메뉴 → 09-A, 비회원 → 03 메뉴."""
    router = window.router
    for action, screen in (("member", "login"), ("signup", "signup"), ("admin", "admin_login"),
                           ("guest", "menu")):
        router.show_screen("home")
        router.open_action(action)
        assert router.current_name == screen
    router.show_screen("idle")
    assert router.pending_action is None


def test_inactivity_returns_to_idle(window):
    router = window.router
    assert router.timer.interval() == 60_000
    router.show_screen("home")
    QTest.qWait(50)                      # 시작 화면 첫 그림(사진·페이드)이 느려도 시간에 걸리지 않게 먼저 그린다
    router.timer.setInterval(400)
    router.timer.start()
    QTest.qWait(200)
    QTest.keyClick(router.screens["home"], Qt.Key.Key_Space)
    QTest.qWait(250)
    assert router.current_name == "home"
    QTest.qWait(400)
    assert router.current_name == "idle"
    assert not router.timer.isActive()


def test_starts_with_unlock_without_vault(app):
    window = KioskWindow()
    assert window.router.current_name == "unlock"
    window.close()
    window.deleteLater()


def test_guest_order_flow(window):
    """비회원: 메뉴 → 옵션 → 장바구니 → 현금(부족→충분) → 완료 → 처음 화면."""
    router = window.router
    router.show_screen("home")
    QTest.mouseClick(router.screens["home"].findChild(QPushButton, "guest_button"),
                     Qt.MouseButton.LeftButton)
    assert router.current_name == "menu"
    menu = router.screens["menu"]
    assert not menu.check_button.isEnabled()

    menu.open_option("M003")                       # 바닐라라떼
    popup = menu.popup
    assert popup.isVisible()
    assert popup.allergy_label.text() == "알레르기: 우유"
    hot = [b for b in popup.temperature_group.buttons() if b.property("value") == "HOT"][0]
    hot.click()
    large = [b for b in popup.size_group.buttons() if b.property("value") == "L"][0]
    large.click()
    popup.change_quantity(1)                       # 2잔
    assert popup.add_button.text().endswith("11,000원")   # (4,500 + 1,000) × 2
    popup.add_to_cart()
    assert not popup.isVisible()
    assert router.session.total() == 11000
    assert menu.check_button.isEnabled()

    menu.check_button.click()
    assert router.current_name == "cart"
    router.screens["cart"].pay_button.click()
    assert router.current_name == "cash"
    cash = router.screens["cash"]
    assert not cash.pay_button.isEnabled()
    cash.findChild(QPushButton, "cash_10000").click()
    assert "1,000원 더 넣어 주세요" in cash.status.text()
    cash.findChild(QPushButton, "cash_5000").click()
    assert "거스름돈 4,000원" in cash.status.text()
    cash.pay_button.click()
    assert router.current_name == "done"
    done = router.screens["done"]
    assert done.number.text() == "001"
    assert router.session.vault.read("menu")["M003"]["stock"] == 18
    router.show_screen("idle")
    assert router.session.cart == {} and router.session.last_order is None


def test_dessert_has_no_options_and_cash_refund(window):
    router = window.router
    router.open_action("guest")
    menu = router.screens["menu"]
    menu.show_category("디저트")
    menu.open_option("M041")                       # 크루아상
    assert menu.popup.temperature_group.buttons() == []
    menu.popup.add_to_cart()
    router.show_screen("cash")
    cash = router.screens["cash"]
    cash.findChild(QPushButton, "cash_1000").click()
    cash.refund()
    assert router.session.inserted == 0
    assert "1,000원을 돌려드렸어요" in cash.event.text()
    assert "현금" in cash.status.text() and "넣어 주세요" in cash.status.text()   # 반환 뒤 상태 줄은 다시 처음 상태


def test_sold_out_card_cannot_open(window):
    router = window.router
    menu_data = router.session.vault.read("menu")
    menu_data["M001"]["sold_out"] = True
    router.session.vault.write("menu", menu_data)
    router.open_action("guest")
    cards = router.screens["menu"].grid_area.widget().findChildren(QWidget)
    first = [c for c in cards if getattr(c, "item", {}).get("id") == "M001"][0]
    assert first.sold_out and not first.plus.isEnabled()


def test_banners_follow_operator_policy(app):
    vault = demo_vault()
    window = KioskWindow(vault=vault)          # 이벤트를 운영자 정책에서 읽는다
    idle = window.router.screens["idle"]
    shown = window.router.session.current_event()
    if shown is None:                           # 시연 이벤트 기간(10/20~11/11)이 지난 날 실행
        assert idle.banner.isHidden()
    else:
        assert idle.banner.current_text().startswith(shown["name"])
        window.router.open_action("guest")
        assert shown["name"] in window.router.screens["menu"].banner.text()
    settings = vault.read("settings")
    settings["point_policy"]["events"] = []     # 운영자가 이벤트를 모두 끄면
    vault.write("settings", settings)
    window.router.show_screen("idle")
    assert idle.banner.isHidden()
    window.router.open_action("guest")
    assert window.router.screens["menu"].banner.isHidden()
    window.close()
    window.deleteLater()
