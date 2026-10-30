"""회원·회원가입·운영자 화면 흐름 (플로차트 v2.1). 카메라 대신 FakeFace를 쓴다."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QPushButton, QRadioButton

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


def login_with_password(router, login_id="bomin", password="1234"):
    router.open_action("member")
    login = router.screens["login"]
    login.login_id.setText(login_id)
    login.set_mode("password")
    login.password.setText(password)
    login.password_login()
    return login


def test_face_failure_then_password(window):
    router = window.router
    router.open_action("member")
    login = router.screens["login"]
    login.login_id.setText("bomin")
    login.face_login()                              # 얼굴 등록 전 → 실패 안내
    assert router.current_name == "login"
    assert not login.fail_box.isHidden()
    assert "얼굴 정보가 없습니다" in login.fail_text.text()
    login.set_mode("password")
    login.password.setText("0000")
    login.password_login()                          # 비밀번호 실패 → 회원 ID 다시 입력
    assert login.mode == "face" and login.login_id.text() == ""
    assert "확인해 주세요" in login.message.text()
    login_with_password(router)
    assert router.current_name == "menu"
    menu = router.screens["menu"]
    assert menu.category == "My Menu"                # 회원은 My Menu가 먼저
    assert "MVP보민" in menu.member_name.text()


def test_member_order_with_allergy_coupon_points_and_change(window):
    router = window.router
    login_with_password(router)
    menu = router.screens["menu"]
    menu.show_category("커피")
    menu.open_option("M002")                         # 카페라떼: bomin은 우유 알레르기
    popup = menu.popup
    popup.change_quantity(2)                         # 3잔 = 12,000원
    popup.add_to_cart()
    assert not popup.warning.isHidden()              # 04-A 경고
    assert router.session.cart == {}
    popup.add_to_cart(confirmed=True)                # 그래도 담기
    assert router.session.total() == 12000

    menu.check_button.click()
    router.screens["cart"].pay_button.click()
    assert router.current_name == "benefit"          # 회원은 06 쿠폰·포인트
    benefit = router.screens["benefit"]
    coupon = [r for r in benefit.findChildren(QRadioButton) if r.property("coupon_id") == "WELCOME1"][0]
    coupon.setChecked(True)
    benefit.set_points(500)
    assert router.session.final_total() == 10500
    benefit.go_cash()
    assert router.current_name == "cash"

    cash = router.screens["cash"]
    assert cash.change_card.isHidden()               # 현금이 모자랄 때는 잔돈 카드 없음
    cash.findChild(QPushButton, "cash_10000").click()
    cash.findChild(QPushButton, "cash_1000").click()
    assert not cash.change_card.isHidden()           # 거스름돈 500원이 정해지면 회원에게만
    before = router.session.customer["extra"]["points"]
    cash.change_check.setChecked(True)
    assert "포인트로 적립" in cash.status.text()
    cash.pay_button.click()
    assert router.current_name == "done"
    order = router.session.last_order
    assert order["change"] == 0 and order["change_points"] == 500
    assert router.screens["done"].waiting.text() == "대기자: [새내기] MVP보민"
    after = router.session.customer["extra"]["points"]
    assert after == before - 500 + order["earned_points"] + 500


def test_quick_order_and_like(window):
    router = window.router
    login_with_password(router, "member1")
    session = router.session
    session.add("M001", {"temperature": "ICE"}, 2)
    session.add("M014", {"temperature": "HOT"}, 1)
    session.insert(20000)
    session.pay()                                    # 여러 잔 주문 기록 만들기
    router.start_member_order(session.customer)
    menu = router.screens["menu"]
    assert menu.quick_button is not None
    menu.quick_button.click()                        # 최근 주문 그대로 다시 담기 → 장바구니에서 확인
    assert router.current_name == "cart"
    # 10/31: 예전 Quick Order는 첫 잔만 담겼다 → 이제 지난 주문이 통째로
    assert sorted((line["name"], line["quantity"]) for line in session.lines()) == [("말차라떼", 1), ("아메리카노", 2)]
    session.cart = {}

    router.start_member_order(session.customer)
    menu.show_category("논커피")
    menu.open_option("M014")                         # 말차라떼
    menu.popup.toggle_like()
    assert menu.popup.like_button.text() == "♥ 좋아요"
    menu.popup.hide()
    menu.show_category("My Menu")
    assert [item["name"] for item in session.likes()] == ["말차라떼"]


def test_signup_with_face_then_face_login(window):
    router = window.router
    router.open_action("signup")
    signup = router.screens["signup"]
    signup.name.setText("새회원")
    signup.login_id.setText("newbie")
    signup.password.setText("abcd")
    signup.password_again.setText("abcd")
    signup.phone.setText("010-2222-3333")
    signup.submit()
    assert "필수 개인정보" in signup.message.text()   # 필수 동의 없이는 가입 안 됨
    signup.privacy.setChecked(True)
    signup.toggle_allergy("땅콩", True)
    signup.face_consent.setChecked(True)
    signup.submit()
    assert router.current_name == "enroll"           # 얼굴 동의 ○ → 10-B
    enroll = router.screens["enroll"]
    enroll.enroll()
    assert router.session.customer["extra"]["face_enrolled"]
    enroll.go_order()
    assert router.current_name == "menu"
    assert router.screens["menu"].category == "My Menu"

    router.show_screen("idle")
    router.open_action("member")
    login = router.screens["login"]
    login.login_id.setText("newbie")
    login.face_login()                               # FakeFace: 등록된 회원은 얼굴 로그인 성공
    assert router.current_name == "menu"


def test_signup_without_face_goes_to_my_menu(window):
    router = window.router
    router.open_action("signup")
    signup = router.screens["signup"]
    for field, text in ((signup.name, "가입이"), (signup.login_id, "plain"), (signup.password, "1111"),
                        (signup.password_again, "1111"), (signup.phone, "010-4444-5555")):
        field.setText(text)
    signup.privacy.setChecked(True)
    signup.submit()
    assert router.current_name == "menu"             # 얼굴 동의 × → 03 My Menu


def test_admin_flow(window):
    router = window.router
    router.open_action("admin")
    login = router.screens["admin_login"]
    login.password.setText("wrong")
    login.password_login()
    assert router.current_name == "admin_login"
    assert "운영자 계정을 확인해 주세요" in login.message.text()
    login.password.setText("demo")
    login.password_login()
    assert router.current_name == "admin" and router.admin_id == "admin"
    admin = router.screens["admin"]

    admin.menu_table.selectRow(0)                    # 09-B 품절 전환
    admin.toggle_sold_out()
    assert router.session.vault.read("menu")["M001"]["sold_out"]

    admin.show_tab("events")                         # 09-D 이벤트 + 테마
    admin.new_event()
    admin.ev_name.setText("주말 축제")
    admin.ev_start.setText("2026-10-01")
    admin.ev_end.setText("2026-12-31")
    admin.ev_bonus.setText("100")
    admin.set_theme("festival")
    admin.save_event()
    events = router.session.policy()["events"]
    assert events[-1]["name"] == "주말 축제" and events[-1]["theme"] == "festival"

    admin.show_tab("points")                         # 09-E 포인트 조정 (사유 필수)
    admin.point_table.selectRow(1)
    admin.adjust_delta.setText("+500")
    admin.save_adjust()
    assert "사유" in admin.message.text()
    admin.adjust_reason.setText("시연 보상")
    admin.save_adjust()
    assert router.session.vault.read("customers")["C0002"]["extra"]["points"] == 1400

    admin.show_tab("members")                        # 09-C 회원은 전화번호를 가려서
    assert "****" in admin.member_table.item(0, 3).text()

    admin.logout()
    assert router.current_name == "home" and router.admin_id is None    # 플로차트: 로그아웃 → 고객 HOME
    actions = [entry["action"] for entry in router.audit_memory]
    assert actions == ["admin_login", "menu_sold_out", "event_save", "points_adjust", "admin_logout"]
