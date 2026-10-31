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


def wait_until(condition, timeout_ms):
    """condition()이 참이 될 때까지 화면 일을 처리하며 기다린다 (PySide6에는 qWaitFor가 없다)."""
    from PySide6.QtTest import QTest
    waited = 0
    while not condition():
        if waited >= timeout_ms:
            return False
        QTest.qWait(20)
        waited += 20
    return True


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


def test_find_screen_issues_temp_password_then_asks_new_one(window):
    """11/01: 본인 확인 → 임시 비밀번호(한 번만 보임) → 그걸로 로그인 → 새 비밀번호 → 주문 화면."""
    router = window.router
    member = first_member(router)
    login_id = member["extra"]["login_id"]
    router.open_action("member")
    router.screens["login"].login_id.setText(login_id)
    router.screens["login"].find_account()
    find = router.screens["find"]
    assert router.current_name == "find" and find.mode == "password"
    find.phone.setText(member["phone"])
    find.verify_phone()
    temp = find.temp_label.text()
    assert len(temp) == 6 and find.temp_box.isVisible() and not find.save_button.isVisible()
    find.save_password()                              # 발급 단계에서는 저장이 안 된다 → 로그인으로
    login = router.screens["login"]
    assert router.current_name == "login" and login.mode == "password"
    assert login.login_id.text() == login_id and find.temp_label.text() == ""
    login.password.setText("1234")                    # 예전 비밀번호는 이제 안 된다
    login.password_login()
    assert router.current_name == "login"
    login.login_id.setText(login_id)
    login.set_mode("password")
    login.password.setText(temp)
    login.password_login()
    assert router.current_name == "find" and find.mode == "change" and find.new_password.isVisible()
    find.new_password.setText("night123")
    find.confirm.setText("night123")
    find.save_password()
    assert router.current_name == "menu" and router.session.customer["id"] == member["id"]
    assert not router.session.customer["extra"].get("must_change_password")
    assert [e["action"] for e in router.audit_memory][-3:] == [
        "member_identity_checked", "member_temp_password", "member_password_reset"]


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


def issue_card_through_admin(router, number):
    """운영자 '회원카드 발급': 맨 위 신청을 허용하고 빈 카드를 찍는다."""
    router.admin_id = "admin"
    router.show_screen("admin", tab="cards")
    admin = router.screens["admin"]
    admin.card_table.selectRow(0)
    admin.allow_card()
    assert router.card_wait is not None, admin.message.text()
    router.card_scanned(number)
    return admin


def test_card_request_admin_issue_then_tag_starts_face_login(window, app):
    """11/01: 손님 신청 → 운영자 허용 → 빈 카드 찍어 할당 → 카드만 대면 로그인."""
    router = window.router
    member = first_member(router)
    set_face_enrolled(router.session.vault, member["id"])
    router.open_action("member")
    login = router.screens["login"]
    login.set_mode("password")
    login.login_id.setText(member["extra"]["login_id"])
    login.password.setText("1234")                    # 시연 데이터 회원 비밀번호
    login.password_then_card()
    assert "신청했어요" in login.message.text() and router.session.customer is None
    admin = issue_card_through_admin(router, "0099887766")
    assert "발급 완료" in admin.message.text() and "7766" in admin.message.text()
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
    """10/30: 카드를 기다리는 중 큰 글자로 바꾸면 지워진 화면에 글을 써서 오류가 났다 (11/01: 운영자 발급 화면)."""
    from domain.member_cards import request_card
    router = window.router
    member = first_member(router)
    request_card(router.session.vault, member["id"])
    router.admin_id = "admin"
    router.show_screen("admin", tab="cards")
    admin = router.screens["admin"]
    admin.card_table.selectRow(0)
    admin.allow_card()
    assert router.card_wait is not None and router.notice.isVisible() and "20초" in router.notice.text()
    router.set_display(large=True)                    # 화면을 새로 만든다 (옛 운영자 화면은 지워짐)
    assert router.current_name == "admin"
    router.show_screen("home")                        # 운영자 화면을 떠나면 기다리기도 끝
    assert router.card_wait is None
    app.processEvents()


def test_phone_number_takes_shape_while_typing(window):
    """10/31: 전화번호는 숫자만 쳐도 010-0000-0000 모양으로 바뀐다 (가입 · 아이디 찾기)."""
    from core.validators import format_phone_typing
    assert format_phone_typing("010") == "010"
    assert format_phone_typing("0101234") == "010-1234"
    assert format_phone_typing("01012345678") == "010-1234-5678"
    assert format_phone_typing("010-1234-56789") == "010-1234-5678"     # 11자리까지만
    router = window.router
    router.open_action("signup")
    phone = router.screens["signup"].phone
    for digit in "01098765432":
        phone.insert(digit)                           # 한 글자씩 (키보드처럼)
    assert phone.text() == "010-9876-5432"
    phone.backspace()
    assert phone.text() == "010-9876-543"
    router.show_screen("find", mode="id")
    find_phone = router.screens["find"].phone
    find_phone.insert("01011112222")
    assert find_phone.text() == "010-1111-2222"


def test_start_screen_slideshow_turns_and_fades_in(window, app):
    """10/31: 01 시작 화면 — 위 로고, 왼쪽 돌아가는 광고·사진, 오른쪽 회원/비회원 버튼, 들어올 때 페이드 인."""
    from PySide6.QtTest import QTest
    router = window.router
    router.show_screen("home")
    home = router.screens["home"]
    assert home.content.graphicsEffect() is not None          # 흐릿하게 시작
    # 시간 대신 결과를 기다린다 (전체 시험을 돌리면 PC가 바빠 늦어질 수 있다)
    assert wait_until(lambda: home.content.graphicsEffect() is None, 5000)   # 다 보이면 효과를 뗀다
    show = home.slideshow
    assert show.timer.isActive() and len(show.slides) >= 2
    assert all(not picture.isNull() for picture, _caption, _fit in show.slides)   # 그림 파일이 다 있다
    show.timer.stop()                                         # 자동 넘김과 겹치지 않게
    start = show.index
    show.next_slide()
    assert wait_until(lambda: show.index == (start + 1) % len(show.slides), 5000)
    show.timer.start()
    router.show_screen("idle")
    assert not show.timer.isActive()                          # 안 보일 때는 멈춘다


def test_enroll_face_shows_inside_screen(window):
    """10/31: 10-B 얼굴 등록도 창 전체를 덮지 않고 왼쪽 칸에 얼굴 기호, 오른쪽에 '지금 할 일'."""
    import numpy as np
    from face import FaceError
    router = window.router
    seen = []

    class InlineFace:
        def __init__(self):
            self.viewer = None
            self.on_step = None

        def enroll_face(self, customer_id, on_status=print):
            enroll = router.screens["enroll"]
            self.on_step("정면을 보고 잠시 멈춰 주세요")
            for _ in range(3):
                seen.append((enroll.face_panel.isVisible(), router.camera_view.isVisible(), enroll.now_text.text()))
                if self.viewer(np.zeros((720, 1280, 3), np.uint8), 1):
                    raise FaceError("사용자가 얼굴 인증을 취소했습니다")
            return True

    router.face_factory = lambda vault: InlineFace()
    member = first_member(router)
    router.session.login(member)
    router.show_screen("enroll", customer=member)
    enroll = router.screens["enroll"]
    enroll.enroll()
    assert seen and all(panel and not cover for panel, cover, _text in seen)
    assert seen[0][2] == "정면을 보고 잠시 멈춰 주세요"
    assert not enroll.face_panel.isVisible() and "등록 완료" in enroll.steps.text()
