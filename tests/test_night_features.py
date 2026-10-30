"""10/29 밤 추가: 08 '더 주문하시겠어요?' · 02-C 아이디 찾기/비밀번호 재설정 · RFID 회원 카드 로그인."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from core.storage import MemoryVault
from domain.customers import (
    find_by_card, find_login_id, link_card, login_with_password, mask_login_id, register_customer,
    reset_member_password, set_face_enrolled, verify_identity,
)
from face import FakeFace
from gui.card_reader import CardReader
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


def first_member(router):
    return next(iter(router.session.vault.read("customers").values()))


def pay_as_member(router):
    member = first_member(router)
    router.open_action("member")
    router.start_member_order(member)
    router.session.add("M001", None, 1)
    router.show_screen("cash")
    cash = router.screens["cash"]
    cash.insert(5000)
    cash.finish()
    return member


# ---------------------------------------------------------------- 08 더 주문
def test_done_asks_to_order_more_and_keeps_login(window):
    router = window.router
    member = pay_as_member(router)
    done = router.screens["done"]
    assert router.current_name == "done" and "더 주문하시겠어요? (15)" == done.ask_label.text()
    done.tick()
    assert "(14)" in done.ask_label.text()
    done.order_more()
    assert router.current_name == "menu" and router.session.customer["id"] == member["id"]
    assert router.session.cart == {}


def test_done_no_or_timeout_logs_out(window):
    router = window.router
    pay_as_member(router)
    done = router.screens["done"]
    done.seconds_left = 1
    done.tick()                                       # 시간이 다 되면 '아니요'
    assert router.current_name == "idle" and router.session.customer is None
    pay_as_member(router)
    done.finish_visit()
    assert router.current_name == "idle" and not done.countdown.isActive()


# ---------------------------------------------------------------- 02-C
@pytest.fixture
def vault():
    vault = MemoryVault()
    register_customer(vault, "가나다", "", "010-1234-5678", "kbm000608", "pass1234", privacy_agreed=True)
    return vault


def test_find_id_masks(vault):
    assert find_login_id(vault, "01012345678") == "kbm****08"
    assert mask_login_id("abcd") == "ab**"
    with pytest.raises(ValueError):
        find_login_id(vault, "010-9999-9999")


def test_reset_needs_matching_phone_and_locks_after_five(vault):
    for _ in range(4):
        with pytest.raises(ValueError, match="번 더 틀리면"):
            verify_identity(vault, "kbm000608", "010-0000-0000")
    customer = verify_identity(vault, "kbm000608", "010-1234-5678")   # 4번 틀린 뒤 맞으면 초기화
    reset_member_password(vault, customer["id"], "newpass", "newpass")
    login_with_password(vault, "kbm000608", "newpass")
    for _ in range(5):
        with pytest.raises(ValueError):
            verify_identity(vault, "kbm000608", "010-0000-0000")
    with pytest.raises(ValueError, match="직원"):
        verify_identity(vault, "kbm000608", "010-1234-5678")


def test_find_screen_resets_password_and_returns_to_login(window):
    router = window.router
    member = first_member(router)
    router.open_action("member")
    router.screens["login"].login_id.setText(member["extra"]["login_id"])
    router.screens["login"].find_account()
    find = router.screens["find"]
    assert router.current_name == "find" and find.mode == "password"
    find.phone.setText(member["phone"])
    find.verify_phone()
    find.new_password.setText("night123")
    find.confirm.setText("night123")
    find.save_password()
    login = router.screens["login"]
    assert router.current_name == "login" and login.mode == "password"
    assert login.login_id.text() == member["extra"]["login_id"]
    assert router.audit_memory[-1]["action"] == "member_password_reset"


# ---------------------------------------------------------------- RFID
def test_card_reader_needs_fast_digits_and_enter():
    reader = CardReader()
    for i, digit in enumerate("0012345678"):
        assert reader.feed(digit, now=i * 0.01) is None
    assert reader.feed("\r", now=0.11) == "0012345678"
    for i, digit in enumerate("123456"):
        reader.feed(digit, now=10 + i * 0.5)          # 사람이 천천히 친 숫자
    assert reader.feed("\r", now=13.0) is None
    for i, digit in enumerate("123"):
        reader.feed(digit, now=20 + i * 0.01)
    assert reader.feed("\r", now=20.04) is None       # 너무 짧음


def test_card_link_rules(vault):
    customer = next(iter(vault.read("customers").values()))
    link_card(vault, customer["id"], "0012345678")
    assert find_by_card(vault, "0012345678")["id"] == customer["id"]
    assert "0012345678" not in str(vault.read("customers"))           # 번호는 해시로만
    other = register_customer(vault, "라마바", "", "010-2222-3333", "other1", "pass1234", privacy_agreed=True)
    with pytest.raises(ValueError, match="다른 회원"):
        link_card(vault, other["id"], "0012345678")


def test_link_card_then_tag_starts_face_login(window, app):
    router = window.router
    member = first_member(router)
    set_face_enrolled(router.session.vault, member["id"])
    router.open_action("member")
    login = router.screens["login"]
    login.set_mode("password")
    login.login_id.setText(member["extra"]["login_id"])
    login.password.setText("1234")                    # 시연 데이터 회원 비밀번호
    login.password_then_card()
    assert router.card_wait is not None, login.message.text()
    router.card_scanned("0099887766")                 # 카드 연결 → 주문으로
    assert router.current_name == "menu"
    router.show_screen("idle")
    handle = window.windowHandle()                    # 실제 키처럼 창으로 보낸다
    for digit in "0099887766":                        # 대기 화면에서 리더기가 번호 + Enter
        QTest.keyClick(handle, getattr(Qt.Key, f"Key_{digit}"), Qt.KeyboardModifier.NoModifier)
    QTest.keyClick(handle, Qt.Key.Key_Return)
    app.processEvents()
    assert router.current_name == "menu" and router.session.customer["id"] == member["id"]
    assert any(entry["action"] == "card_tag" for entry in router.audit_memory)


def test_unknown_card_tells_how_to_link(window):
    router = window.router
    router.show_screen("idle")
    router.card_scanned("5555555555")
    assert router.current_name == "idle" and "등록되지 않은 카드" in router.notice.text()


# ---------------------------------------------------------------- 상황별 점검에서 찾은 것
def test_shrinking_cart_after_points_does_not_crash(window):
    router = window.router
    session = router.session
    customers = session.vault.read("customers")
    member = next(iter(customers.values()))
    member["extra"]["points"] = 20000
    session.vault.write("customers", customers)
    router.start_member_order(member)
    session.add("M001", None, 3)
    router.show_screen("benefit")
    router.screens["benefit"].set_points(9000)
    session.change(session.lines()[0]["key"], 1)      # 장바구니를 줄이면 9000P는 너무 많다
    router.show_screen("cash")                        # 예전에는 여기서 오류 → 처음 화면
    cash = router.screens["cash"]
    assert router.current_name == "cash" and "선택을 풀었어요" in cash.event.text()
    assert session.use_points == 0 and cash.status.text() == "현금 3,000원을 넣어 주세요"


def test_quantity_limit_is_explained(window):
    router = window.router
    router.open_action("guest")
    router.session.add("M001", None, 10)
    key = router.session.lines()[0]["key"]
    router.screens["menu"].change_quantity(key, 11)
    assert "최대 10개" in router.notice.text()
    router.show_screen("cart")
    router.screens["cart"].change(key, 11)
    assert "최대 10개" in router.notice.text()


def test_number_keys_still_type_on_login(window, app):
    """10/29 아침: 카드 리더 때문에 로그인 칸에 숫자 키가 안 들어가던 문제."""
    router = window.router
    router.open_action("member")
    login = router.screens["login"]
    login.login_id.setFocus()
    app.processEvents()
    handle = window.windowHandle()
    for key in (Qt.Key.Key_K, Qt.Key.Key_B, Qt.Key.Key_0, Qt.Key.Key_6, Qt.Key.Key_0, Qt.Key.Key_8):
        QTest.keyClick(handle, key, Qt.KeyboardModifier.NoModifier)
    app.processEvents()
    assert login.login_id.text() == "kb0608"


def test_card_wait_is_cancelled_by_leaving_or_rebuilding(window, app):
    """10/30: 카드 연결을 기다리는 중 큰 글자로 바꾸면 지워진 화면에 글을 써서 오류가 났다."""
    router = window.router
    member = first_member(router)
    router.open_action("member")
    login = router.screens["login"]
    login.set_mode("password")
    login.login_id.setText(member["extra"]["login_id"])
    login.password.setText("1234")
    login.password_then_card()
    router.set_display(large=True)                    # 화면을 새로 만든다 (옛 로그인 화면은 지워짐)
    assert router.current_name == "login"
    router.show_screen("menu")                        # 로그인 화면을 떠나면 기다리기도 끝
    assert router.card_wait is None
    app.processEvents()
