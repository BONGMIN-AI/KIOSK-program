"""플로차트 v4의 모든 갈래를 처음부터 끝까지 자동으로 지나가 보며 단계마다 점검한다 (10/31 최종 점검).

check_layout.py가 '화면 한 장'을 여러 크기로 본다면, 이것은 '손님 한 명의 흐름'을 따라간다.
단계마다 확인하는 것:
  - 화면: 기대한 화면으로 넘어갔는지, 글자 잘림·눌림·칸 밖(check_layout과 같은 기준)
  - 코드: 처리 안 된 오류(예외), Qt 경고
  - 데이터: 주문·재고·포인트·좌석 등 결과가 맞는지
결과: 폴더에 단계별 화면 그림(화면/*.jpg) + 결과표(점검결과.md · 점검결과.html). 문제가 하나라도 있으면 끝 상태 코드 1.

사용: python tools/run_scenarios.py [결과 폴더]
      (기본: 저장소 밖 ../../08_최종점검/시나리오_점검)  카메라 없이 가짜 얼굴(FakeFace) · 메모리 시연 데이터
"""
import copy
from html import escape
import os
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KIOSK_CARD_PORT", "off")      # 꽂혀 있는 아두이노 카드 리더는 열지 않는다
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from PySide6.QtCore import Qt, QtMsgType, qInstallMessageHandler
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QRadioButton, QWidget

from check_layout import check as check_layout
from core.storage import MemoryVault
from face import FakeFace, FaceError
from gui.main import KioskWindow, demo_vault

DEFAULT_OUT = ROOT.parent.parent / "08_최종점검" / "시나리오_점검"
RUNS = [("기본 글자", (1440, 900), {}), ("큰 글자", (1200, 800), {"large": True})]


# ---------------------------------------------------------------- 얼굴 대역
class WrongFace(FakeFace):
    """다른 사람 얼굴로 판정되는 카메라 (얼굴 불일치 → 3번이면 잠금)."""

    def identify_face(self, claimed_customer_id, on_status=print):
        return "C9999"


class BrokenCamera(FakeFace):
    """카메라가 꺼지거나 뽑힌 상황."""

    def identify_face(self, claimed_customer_id, on_status=print):
        raise RuntimeError("camera unplugged")

    def enroll_face(self, customer_id, on_status=print):
        raise FaceError("카메라를 찾지 못했어요")


# ---------------------------------------------------------------- 실행기
class Problem(Exception):
    pass


class Run:
    """시나리오 하나를 창 하나에서 돌리며 단계마다 기록한다."""

    def __init__(self, monitor, number, name, path, size, display, shots):
        self.monitor, self.number, self.name, self.path = monitor, number, name, path
        self.face = FakeFace()
        self.window = KioskWindow(vault=monitor.fresh_vault(), face_factory=lambda vault: self.face)
        self.window.resize(*size)
        self.window.show()
        if display:
            self.router.apply_display({"contrast": False, **display})
        self.shots = shots
        self.steps = []
        self.size = size

    @property
    def router(self):
        return self.window.router

    @property
    def session(self):
        return self.router.session

    def screen(self, name=None):
        return self.router.screens[name or self.router.current_name]

    def step(self, label, expect=None, ok=None, why=""):
        """지금 화면을 점검하고 기록한다. expect: 있어야 할 화면 이름, ok(): 데이터 확인."""
        for _ in range(4):                          # 새로 보인 칸의 배치가 끝날 때까지
            QTest.qWait(30)
        problems = list(self.monitor.take_errors())
        current = self.router.current_name
        if expect and current != expect:
            problems.append(f"화면 이동 오류: '{expect}' 화면이어야 하는데 '{current}'")
        try:
            if ok is not None and not ok():
                problems.append(f"결과 확인 실패: {why or label}")
        except Exception as error:                  # 확인 코드 자체가 깨진 것도 문제로 남긴다
            problems.append(f"결과 확인 중 오류: {type(error).__name__}: {error}")
        where = f"{self.name} / {label}"
        for _where, kind, text, reason in check_layout(self.window, self.screen(), where):
            problems.append(f"화면 배치: {kind} '{text[:30]}' — {reason}")
        if self.window.height() > self.size[1] + 2:
            problems.append(f"창이 {self.size[1]} → {self.window.height()}로 커짐 (내용이 창보다 큼)")
        picture = ""
        if self.shots is not None:
            picture = f"{self.number:02d}_{len(self.steps) + 1:02d}.jpg"
            self.window.grab().scaledToWidth(960, Qt.TransformationMode.SmoothTransformation).save(
                str(self.shots / picture), "JPG", 80)
        self.steps.append({"label": label, "screen": current, "problems": problems, "picture": picture})

    def close(self):
        self.window.close()
        self.window.deleteLater()
        QApplication.processEvents()


class Monitor:
    def __init__(self, out):
        self.out = out
        self.errors = []
        self.template = demo_vault()
        qInstallMessageHandler(self.qt_message)
        sys.excepthook = self.exception

    def fresh_vault(self):
        vault = MemoryVault()
        vault._store = copy.deepcopy(self.template._store)
        return vault

    def qt_message(self, kind, context, text):
        if kind in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
            if "propagateSizeHints" in text or "Cannot find font directory" in text:
                return                              # offscreen·한글 경로에서만 나오는 무해한 알림
            self.errors.append(f"Qt 경고: {text}")

    def exception(self, kind, error, trace):
        last = traceback.extract_tb(trace)[-1] if trace else None
        place = f" ({Path(last.filename).name}:{last.lineno})" if last else ""
        self.errors.append(f"처리 안 된 오류: {kind.__name__}: {error}{place}")

    def take_errors(self):
        errors, self.errors = self.errors, []
        return errors


# ---------------------------------------------------------------- 공통 동작
def click(widget):
    QTest.mouseClick(widget, Qt.MouseButton.LeftButton)


def touch_idle(r):
    r.router.show_screen("idle")
    r.step("00 대기 화면", "idle")
    r.router.show_screen("home")
    r.step("01 시작 화면 (화면 터치)", "home")


def login_password(r, login_id="bomin", password="1234"):
    r.router.open_action("member")
    login = r.screen("login")
    login.login_id.setText(login_id)
    login.set_mode("password")
    login.password.setText(password)
    r.step("02-B 비밀번호 입력", "login")
    login.password_login()


def pay_cash(r, notes, change_points=False, label="07 현금 넣기"):
    cash = r.screen("cash")
    for note in notes:
        cash.findChild(QPushButton, f"cash_{note}").click()
    if change_points and not cash.change_card.isHidden():
        cash.change_check.setChecked(True)
    r.step(label, "cash", lambda: cash.pay_button.isEnabled(), "충분히 넣으면 결제 버튼이 켜져야 함")
    cash.pay_button.click()


def add_from_popup(r, menu_id, quantity=1, category="커피", confirm=False):
    menu = r.screen("menu")
    menu.show_category(category)
    menu.open_option(menu_id)
    popup = menu.popup
    for _ in range(quantity - 1):
        popup.change_quantity(1)
    r.step(f"04 옵션 ({r.session.menu()[menu_id]['name']})", "menu", lambda: popup.isVisible())
    popup.add_to_cart()
    if confirm and popup.warning.isVisible():
        r.step("04-A 확인 질문", "menu", lambda: popup.warning.isVisible())
        popup.confirm_button.click()


def stock(r, menu_id):
    return r.session.vault.read("menu")[menu_id]["stock"]


def member(r, login_id="bomin"):
    return next(c for c in r.session.vault.read("customers").values() if c["extra"]["login_id"] == login_id)


# ---------------------------------------------------------------- 시나리오 (플로차트 갈래)
def guest_basic(r):
    touch_idle(r)
    click(r.screen("home").findChild(QPushButton, "guest_button"))
    r.step("03 비회원 메뉴 (My Menu 없음)", "menu", lambda: "My Menu" not in r.session.categories())
    before = stock(r, "M003")
    add_from_popup(r, "M003", 2)
    r.step("03 장바구니에 담김", "menu", lambda: r.session.total() == 9000)
    r.screen("menu").check_button.click()
    r.step("05 장바구니 확인", "cart")
    r.screen("cart").pay_button.click()
    r.step("07 현금 (비회원은 쿠폰 단계 없음)", "cash")
    pay_cash(r, [10000])
    r.step("08 완료 · 거스름돈 1,000원", "done",
           lambda: r.session.last_order["change"] == 1000 and stock(r, "M003") == before - 2)
    r.screen("done").finish_visit()
    r.step("08 아니요 → 대기 화면", "idle", lambda: r.session.cart == {} and r.session.customer is None)


def guest_short_cash_refund(r):
    r.router.open_action("guest")
    add_from_popup(r, "M041", 1, "디저트")
    r.router.show_screen("cash")
    cash = r.screen("cash")
    cash.findChild(QPushButton, "cash_1000").click()
    r.step("07 돈이 모자람 (부족 금액 안내)", "cash", lambda: "더 넣어 주세요" in cash.status.text())
    cash.refund()
    r.step("07 반환 → 1,000원 돌려줌", "cash", lambda: r.session.inserted == 0 and "돌려드렸어요" in cash.event.text())


def cash_timeout(r):
    r.router.open_action("guest")
    add_from_popup(r, "M001")
    r.router.show_screen("cash")
    r.screen("cash").findChild(QPushButton, "cash_1000").click()
    r.router.warn_time_out()
    r.step("07 45초: 곧 처음으로 돌아간다는 경고", "cash", lambda: r.router.warning_shown)
    r.router.time_out()
    r.step("07 60초: 넣은 돈 반환하고 대기 화면", "idle",
           lambda: r.session.inserted == 0 and any(e["action"] == "cash_refund_timeout" for e in r.router.audit_memory))


def member_face_success(r):
    touch_idle(r)
    vault = r.session.vault
    customers = vault.read("customers")
    customers["C0001"]["extra"]["face_enrolled"] = True
    vault.write("customers", customers)
    r.router.open_action("member")
    login = r.screen("login")
    login.login_id.setText("bomin")
    r.step("02 회원 ID 입력", "login")
    login.face_login()
    r.step("02 얼굴 인증 성공 → My Menu", "menu", lambda: r.screen("menu").category == "My Menu")


def member_face_lock_then_password(r):
    vault = r.session.vault
    customers = vault.read("customers")
    customers["C0001"]["extra"]["face_enrolled"] = True
    vault.write("customers", customers)
    r.face = WrongFace()
    r.router.open_action("member")
    login = r.screen("login")
    for attempt in (1, 2, 3):
        login.login_id.setText("bomin")
        login.face_login()
        r.step(f"02 얼굴 불일치 {attempt}번째", "login", lambda: not login.fail_box.isHidden())
    login.face_login()
    r.step("02 3번 실패 → 얼굴 로그인 잠김 안내", "login", lambda: "잠겼어요" in login.fail_text.text())
    login.set_mode("password")
    login.password.setText("1234")
    login.password_login()
    r.step("02-B 비밀번호 성공 → My Menu (잠금 풀림)", "menu",
           lambda: not vault.read("face_failures", default={}).get("C0001"))


def member_password_fail(r):
    r.router.open_action("member")
    login = r.screen("login")
    login.login_id.setText("bomin")
    login.set_mode("password")
    login.password.setText("0000")
    login.password_login()
    r.step("02-B 비밀번호 틀림 → 회원 ID부터 다시", "login",
           lambda: login.mode == "face" and login.login_id.text() == "")
    login.login_id.setText("nobody")
    login.face_login()
    r.step("02 없는 회원 ID", "login", lambda: "없습니다" in login.fail_text.text())


def camera_broken(r):
    vault = r.session.vault
    customers = vault.read("customers")
    customers["C0001"]["extra"]["face_enrolled"] = True
    vault.write("customers", customers)
    r.face = BrokenCamera()
    r.router.open_action("member")
    login = r.screen("login")
    login.login_id.setText("bomin")
    login.face_login()
    r.step("02 카메라 고장 → 멈추지 않고 비밀번호 안내", "login", lambda: "카메라" in login.fail_text.text())


def find_account(r):
    r.router.open_action("member")
    r.router.show_screen("find", mode="id")
    find = r.screen("find")
    find.phone.setText("01010000001")
    find.find_id()
    r.step("02-C 아이디 찾기 (가려서 보여 줌)", "find", lambda: "**" in find.result_text.text())
    r.router.show_screen("find", mode="password", login_id="bomin")
    find.phone.setText("010-1000-0001")
    find.verify_phone()
    temp = find.temp_label.text()
    r.step("02-C 본인 확인 → 임시 비밀번호 발급", "find", lambda: len(temp) == 6 and find.temp_box.isVisible())
    find.to_login_button.click()
    r.step("로그인하러 가기 (아이디 채워짐)", "login", lambda: r.screen("login").login_id.text() == "bomin")
    login = r.screen("login")
    login.set_mode("password")
    login.password.setText(temp)
    login.password_login()
    r.step("임시 비밀번호로 로그인 → 새 비밀번호 정하기", "find", lambda: find.mode == "change")
    find.new_password.setText("new1234")
    find.confirm.setText("new1234")
    find.save_password()
    r.step("새 비밀번호 저장 → 바로 My Menu", "menu", lambda: r.session.customer is not None)
    r.router.show_screen("idle")
    login_password(r, "bomin", "new1234")
    r.step("02-B 새 비밀번호로 다시 로그인", "menu")


def card_login(r):
    r.router.open_action("member")
    login = r.screen("login")
    login.login_id.setText("bomin")
    login.password.setText("1234")
    login.password_then_card()
    r.step("02-B 카드 연결 대기", "login", lambda: r.router.card_active())
    r.router.card_scanned("0012345678")
    r.step("카드 연결됨", None, lambda: member(r)["extra"].get("card_id") or True)
    r.router.show_screen("home")
    r.router.card_scanned("0012345678")
    r.step("RFID 카드 태그 → 회원 확인 진행", None)
    r.router.show_screen("home")
    r.router.card_scanned("9999999999")
    r.step("등록 안 된 카드 → 연결 방법 안내", None)


def signup_errors_then_face(r):
    touch_idle(r)
    r.router.open_action("signup")
    signup = r.screen("signup")
    signup.submit()
    r.step("10 빈칸으로 가입 → 안내", "signup", lambda: signup.message.text() != "")
    for field, text in ((signup.name, "새회원"), (signup.login_id, "bomin"), (signup.password, "abcd"),
                        (signup.password_again, "abcd"), (signup.phone, "01022223333")):
        field.setText(text)
    signup.privacy.setChecked(True)
    signup.submit()
    r.step("10 이미 있는 아이디 → 안내", "signup", lambda: signup.message.text() != "")
    signup.login_id.setText("newbie")
    signup.password_again.setText("abce")
    signup.submit()
    r.step("10 비밀번호 확인 다름 → 안내", "signup", lambda: signup.message.text() != "")
    signup.password_again.setText("abcd")
    signup.toggle_allergy("땅콩", True)
    signup.face_consent.setChecked(True)
    signup.submit()
    r.step("10-B 얼굴 등록 화면", "enroll")
    enroll = r.screen("enroll")
    enroll.enroll()
    r.step("10-B 얼굴 등록 완료", "enroll", lambda: r.session.customer["extra"]["face_enrolled"])
    enroll.go_order()
    r.step("가입 → My Menu", "menu", lambda: r.screen("menu").category == "My Menu")


def signup_no_face(r):
    r.router.open_action("signup")
    signup = r.screen("signup")
    for field, text in ((signup.name, "가입이"), (signup.login_id, "plain"), (signup.password, "1111"),
                        (signup.password_again, "1111"), (signup.phone, "01044445555")):
        field.setText(text)
    signup.privacy.setChecked(True)
    signup.submit()
    r.step("10 얼굴 동의 안 함 → 바로 My Menu", "menu")


def enroll_camera_broken(r):
    r.face = BrokenCamera()
    r.router.show_screen("enroll", customer=member(r))
    r.screen("enroll").enroll()
    r.step("10-B 카메라 고장 → 멈추지 않고 안내", "enroll", lambda: not member(r)["extra"]["face_enrolled"])


def member_full_order(r):
    login_password(r)
    r.step("03 My Menu (회원 첫 화면)", "menu", lambda: r.screen("menu").category == "My Menu")
    menu = r.screen("menu")
    menu.show_category("커피")
    menu.open_option("M002")                         # 카페라떼: bomin 우유 알레르기
    menu.popup.change_quantity(2)
    menu.popup.add_to_cart()
    r.step("04-A 알레르기 경고", "menu", lambda: menu.popup.warning.isVisible() and r.session.cart == {})
    menu.popup.confirm_button.click()
    r.step("04-A 그래도 담기 → 12,000원", "menu", lambda: r.session.total() == 12000)
    menu.check_button.click()
    r.screen("cart").pay_button.click()
    r.step("06 쿠폰·포인트", "benefit")
    benefit = r.screen("benefit")
    coupon = [b for b in benefit.findChildren(QRadioButton) if b.property("coupon_id") == "WELCOME1"][0]
    coupon.setChecked(True)
    benefit.set_points(500)
    r.step("06 쿠폰 1,000원 + 포인트 500P", "benefit", lambda: r.session.final_total() == 10500)
    benefit.go_cash()
    before = member(r)["extra"]["points"]
    pay_cash(r, [10000, 1000], change_points=True, label="07 현금 + 잔돈 500원을 포인트로")
    order = r.session.last_order
    r.step("08 완료 (잔돈 → 포인트, 적립)", "done",
           lambda: order["change"] == 0 and order["change_points"] == 500
           and member(r)["extra"]["points"] == before - 500 + order["earned_points"] + 500)
    r.screen("done").order_more()
    r.step("08 더 주문 → 로그인 유지", "menu", lambda: r.session.customer is not None and r.session.cart == {})


def member_done_timeout(r):
    login_password(r)
    r.session.add("M001", None, 1)
    r.router.show_screen("cash")
    pay_cash(r, [5000])
    done = r.screen("done")
    done.seconds_left = 1
    done.tick()
    r.step("08 15초 지남 → 로그아웃 · 대기", "idle", lambda: r.session.customer is None)


def zero_won(r):
    customers = r.session.vault.read("customers")
    customers["C0001"]["extra"]["points"] = 10000
    r.session.vault.write("customers", customers)
    login_password(r)
    r.session.add("M001", None, 1)
    r.router.show_screen("benefit")
    r.screen("benefit").set_points(3000)
    r.step("06 포인트로 전액", "benefit", lambda: r.session.final_total() == 0)
    r.screen("benefit").go_cash()
    cash = r.screen("cash")
    r.step("07 0원 결제 (돈 없이 결제)", "cash", lambda: cash.pay_button.isEnabled())
    cash.pay_button.click()
    r.step("08 완료", "done")


def recent_reorder_and_caffeine(r):
    login_password(r)
    r.session.add("M001", {"temperature": "ICE", "size": "L"}, 2)
    r.session.add("M041", None, 1)
    r.router.show_screen("cash")
    pay_cash(r, [50000])
    r.screen("done").order_more()
    menu = r.screen("menu")
    r.step("03 My Menu 최근 주문 · 카페인 리포트", "menu", lambda: menu.quick_button is not None)
    menu.gear_button.click()
    r.step("카페인 알리미 설정 창 (톱니바퀴)", "menu", lambda: menu.caffeine_settings.isVisible())
    menu.change_limit(unit="잔")
    menu.change_limit(step=-1)
    menu.settings_done.click()
    r.step("알리미 주 2잔 → 리포트에 '넘었어요/남았어요'", "menu", lambda: "주 2잔" in menu.alert_title.text())
    menu.quick_button.click()
    r.step("다시 담기 → 제한 넘음 질문", "menu", lambda: menu.confirm_box.isVisible() and r.session.cart == {})
    menu.confirm_box.no_button.click()
    r.step("아니요 → 담지 않음", "menu", lambda: r.session.cart == {})
    menu.quick_button.click()
    menu.confirm_box.yes_button.click()
    r.step("예 → 지난 주문 통째로 장바구니", "cart", lambda: r.session.count() == 3)
    r.router.start_member_order(r.session.customer)
    menu.show_category("커피")
    menu.open_option("M001")
    menu.popup.add_to_cart()
    r.step("옵션 창에서도 제한 넘음 질문", "menu", lambda: menu.popup.warning.isVisible())
    menu.popup.warning_cancel.click()
    r.step("아니요 → 창 닫힘", "menu", lambda: not menu.popup.isVisible())
    menu.show_category("My Menu")
    for view in ("주별", "월별"):
        menu.view_buttons[view].click()
        r.step(f"카페인 그래프 {view}", "menu", lambda: menu.caffeine_view == view)


def batch1_habit_eco_coin(r):
    login_password(r)
    r.session.add("M001", {"temperature": "ICE", "size": "L", "extras": ["shot"]}, 1)
    r.session.insert(10000)
    r.session.pay()
    r.router.start_member_order(r.session.customer)
    menu = r.screen("menu")
    menu.show_category("커피")
    menu.open_option("M001")
    r.step("옵션 습관: 지난번 ICE·L·샷이 미리 골라짐", "menu",
           lambda: menu.popup.chosen_options()["size"] == "L" and menu.popup.habit_note.isVisible())
    menu.popup.add_to_cart()
    add_from_popup(r, "M047", 1, "디저트", confirm=True)     # 소금빵: bomin 우유 알레르기 → 그래도 담기
    menu.check_button.click()
    cart = r.screen("cart")
    r.step("장바구니: 개인 컵(에코 포인트) 체크", "cart", lambda: cart.eco_box.isVisible())
    cart.eco_check.setChecked(True)
    cart.pay_button.click()
    r.screen("benefit").go_cash()
    cash = r.screen("cash")
    r.step("현금: 동전 줄이기 팁 (700원)", "cash", lambda: "700원" in cash.coin_tip.text())
    pay_cash(r, [5000, 1000, 1000, 500, 100, 100])
    r.step("완료: 에코 포인트 +100P · 거스름돈 동전 없음", "done",
           lambda: r.session.last_order["eco_points"] == 100 and r.session.last_order["change"] == 0)


def popular_and_like(r):
    login_password(r)
    menu = r.screen("menu")
    menu.show_category("인기")
    for sort in ("좋아요순", "판매순", "계절 인기순"):
        menu.sort_buttons[sort].click()
        QTest.qWait(30)
        r.step(f"인기 탭 {sort}", "menu", lambda: menu.popular_sort == sort)
    menu.open_option("M012")
    menu.popup.toggle_like()
    menu.popup.hide()
    menu.show_category("My Menu")
    r.step("♥ 좋아요 → My Menu에 모임", "menu", lambda: [i["name"] for i in r.session.likes()] == ["딸기라떼"])


def sold_out_and_stock(r):
    menu_data = r.session.vault.read("menu")
    menu_data["M001"]["sold_out"] = True
    menu_data["M002"]["stock"] = 1
    r.session.vault.write("menu", menu_data)
    r.router.open_action("guest")
    menu = r.screen("menu")
    menu.show_category("커피")
    cards = [c for c in menu.grid_area.widget().findChildren(QWidget) if getattr(c, "item", {}).get("id") == "M001"]
    r.step("품절 카드는 + 버튼이 꺼짐", "menu", lambda: cards[0].sold_out and not cards[0].plus.isEnabled())
    menu.open_option("M002")
    menu.popup.change_quantity(1)
    menu.popup.add_to_cart()
    r.step("재고보다 많이 담기 → 이유 안내", "menu", lambda: "재고" in menu.popup.message.text())


def ticket_lookup(r):
    r.router.open_action("guest")
    menu = r.screen("menu")
    menu.show_category("승차권")
    panel = menu.ticket_panel
    r.step("T1-0 승차권 탭", "menu")
    panel.open_lookup()
    panel.name_field.setText("홍길동")
    panel.birth_field.setText("9001")
    panel.lookup()
    r.step("T1-1 생년월일 틀림 → 안내", "menu")
    panel.birth_field.setText("900101")
    panel.lookup()
    panel.print_selected()
    r.step("T1-2 예매표 출력", "menu")


def ticket_purchase(r, with_drink=True):
    def run(r):
        login_password(r)
        menu = r.screen("menu")
        menu.show_category("승차권")
        panel = menu.ticket_panel
        panel.open_route()
        panel.dest_field.setText("대전복합")
        panel.day_buttons[1].setChecked(True)
        panel.search()
        r.step("T1-4 시간표", "menu")
        next(b for b in panel.time_buttons if b.isEnabled() and b.bus["grade"] == "우등").setChecked(True)
        panel.open_seats()
        panel.change_count("어른", 1)
        for seat in [s for s, b in panel.seat_buttons.items() if b.isEnabled()][:2]:
            panel.toggle_seat(seat, True)
        r.step("T1-5 좌석 2개 고름", "menu")
        panel.confirm_seats()
        panel.set_benefit(0, "경로")
        r.step("T1-6 혜택·확인 (좌석 5분 유지)", "menu", lambda: bool(panel.hold_id))
        panel.add_to_cart(panel.on_drinks)
        if with_drink:
            add_from_popup(r, "M001")
        r.step("T1-7 승차권 + 음료 장바구니", "menu", lambda: len(r.session.tickets) == 1)
        menu.check_button.click()
        r.step("05 장바구니 (승차권 줄 먼저)", "cart")
        r.screen("cart").pay_button.click()
        if r.router.current_name == "benefit":
            r.step("06 혜택 (승차권은 할인 제외)", "benefit")
            r.screen("benefit").go_cash()
        pay_cash(r, [50000, 50000])
        r.step("T1-8 완료 · 승차권 출력 안내", "done", lambda: r.session.last_order.get("tickets"))
    return run


def ticket_hold_expires(r):
    r.router.open_action("guest")
    menu = r.screen("menu")
    menu.show_category("승차권")
    panel = menu.ticket_panel
    panel.open_route()
    panel.dest_field.setText("대전복합")
    panel.day_buttons[1].setChecked(True)
    panel.search()
    next(b for b in panel.time_buttons if b.isEnabled()).setChecked(True)
    panel.open_seats()
    panel.toggle_seat(next(s for s, b in panel.seat_buttons.items() if b.isEnabled()), True)
    panel.confirm_seats()
    panel.add_to_cart(panel.on_drinks)
    for hold in panel.office.holds.values():         # 5분이 지난 것처럼
        hold["until"] = datetime.now() - timedelta(seconds=1)
    menu.tick_tickets()
    r.step("장바구니 승차권 5분 지남 → 빼고 안내", "menu", lambda: r.session.tickets == [])


def admin_all(r):
    touch_idle(r)
    r.router.open_action("admin")
    login = r.screen("admin_login")
    login.password.setText("wrong")
    login.password_login()
    r.step("09-A 운영자 비밀번호 틀림", "admin_login")
    login.password.setText("demo")
    login.password_login()
    admin = r.screen("admin")
    r.step("09-B 메뉴 관리", "admin")
    admin.menu_table.selectRow(0)
    admin.toggle_sold_out()
    r.step("09-B 품절 전환", "admin", lambda: r.session.vault.read("menu")["M001"]["sold_out"])
    admin.show_tab("members")
    r.step("09-C 회원·주문 (전화번호 가림)", "admin", lambda: "****" in admin.member_table.item(0, 3).text())
    admin.show_tab("events")
    admin.new_event()
    admin.ev_name.setText("주말 축제")
    admin.ev_start.setText("2026-10-01")
    admin.ev_end.setText("2026-12-31")
    admin.ev_bonus.setText("100")
    admin.save_event()
    r.step("09-D 이벤트 저장", "admin", lambda: r.session.policy()["events"][-1]["name"] == "주말 축제")
    admin.show_tab("points")
    admin.point_table.selectRow(1)
    admin.adjust_delta.setText("+500")
    admin.save_adjust()
    r.step("09-E 사유 없이 포인트 조정 → 안내", "admin", lambda: "사유" in admin.message.text())
    admin.adjust_reason.setText("시연 보상")
    admin.save_adjust()
    r.step("09-E 포인트 조정 저장", "admin")
    admin.logout()
    r.step("로그아웃 → 고객 HOME", "home", lambda: r.router.admin_id is None)
    r.router.open_action("guest")
    r.screen("menu").show_category("커피")
    r.step("품절이 손님 화면에 반영", "menu")


def display_switch_mid_order(r):
    r.router.open_action("guest")
    r.session.add("M001", None, 2)
    r.router.set_display(large=True)
    r.step("주문 중 큰 글자로 바꿈 (장바구니 유지)", None, lambda: r.session.count() == 2)
    r.router.set_display(contrast=True)
    r.step("고대비로 바꿈", None, lambda: r.session.count() == 2)
    r.router.set_display(large=False, contrast=False)


def idle_everywhere(r):
    for name, setup in (("로그인", lambda: r.router.open_action("member")),
                        ("회원가입", lambda: r.router.open_action("signup")),
                        ("메뉴", lambda: r.router.open_action("guest"))):
        setup()
        r.router.time_out()
        r.step(f"{name} 화면에서 60초 → 대기 화면", "idle", lambda: r.session.customer is None and r.session.cart == {})


SCENARIOS = [
    ("비회원 기본 주문", "대기 → HOME → 비회원 → 메뉴 → 옵션 → 장바구니 → 현금 → 완료 → 대기", guest_basic),
    ("돈이 모자람 · 반환", "현금 → 부족 → 반환", guest_short_cash_refund),
    ("현금 45초 경고 · 60초 반환", "현금 → 45초 경고 → 60초 자동 반환 → 대기", cash_timeout),
    ("회원 얼굴 로그인", "HOME → 회원 → ID → 얼굴 성공 → My Menu", member_face_success),
    ("얼굴 3번 실패 → 잠금 → 비밀번호", "얼굴 불일치 ×3 → 잠금 → 비밀번호 → My Menu", member_face_lock_then_password),
    ("비밀번호 틀림 · 없는 ID", "비밀번호 실패 → 회원 ID 다시", member_password_fail),
    ("카메라 고장", "얼굴 인증 중 카메라 오류 → 비밀번호 안내", camera_broken),
    ("아이디 찾기 · 임시 비밀번호", "02-C → 임시 비밀번호 → 로그인 → 새 비밀번호 → My Menu", find_account),
    ("RFID 카드", "카드 연결 → 카드 태그 · 모르는 카드", card_login),
    ("회원가입 오류 → 얼굴 등록", "10 빈칸·중복·비밀번호 다름 → 10-B → My Menu", signup_errors_then_face),
    ("회원가입 (얼굴 없이)", "10 → My Menu", signup_no_face),
    ("얼굴 등록 중 카메라 고장", "10-B 카메라 오류", enroll_camera_broken),
    ("회원 전체 주문", "알레르기 → 쿠폰·포인트 → 현금 → 잔돈 포인트 → 완료 → 더 주문", member_full_order),
    ("완료 15초 → 로그아웃", "08 시간 지남 → 대기", member_done_timeout),
    ("0원 결제", "포인트 전액 → 0원 결제 → 완료", zero_won),
    ("최근 주문 · 카페인 알리미", "다시 담기 · 톱니바퀴 설정 · 제한 질문 예/아니요 · 그래프", recent_reorder_and_caffeine),
    ("인기 탭 · 좋아요", "인기 3가지 정렬 · ♥ → My Menu", popular_and_like),
    ("옵션 습관 · 에코 포인트 · 동전 팁", "옵션 미리 선택 → 개인 컵 → 동전 팁 → 완료", batch1_habit_eco_coin),
    ("품절 · 재고 부족", "품절 카드 · 재고 넘게 담기", sold_out_and_stock),
    ("승차권 예매표 출력", "T1 → 조회 오류 → 출력", ticket_lookup),
    ("승차권 + 음료 결제", "T1 노선 → 시간표 → 좌석 → 혜택 → 음료 → 결제 → 완료", ticket_purchase(None, True)),
    ("승차권만 결제", "T1 → 결제 → 완료", ticket_purchase(None, False)),
    ("좌석 5분 지남", "장바구니 승차권 시간 초과", ticket_hold_expires),
    ("운영자 전체", "로그인 오류 → 메뉴·회원·이벤트·포인트 → 로그아웃 → 손님 화면 반영", admin_all),
    ("주문 중 화면 설정 바꾸기", "큰 글자 · 고대비 전환", display_switch_mid_order),
    ("어느 화면이든 60초 무입력", "로그인·가입·메뉴 → 대기", idle_everywhere),
]


def run_all(out):
    shots = out / "화면"
    shots.mkdir(parents=True, exist_ok=True)
    monitor = Monitor(out)
    results = []
    for run_name, size, display in RUNS:
        for number, (name, path, scenario) in enumerate(SCENARIOS, 1):
            r = Run(monitor, number, name, path, size, display, shots if not display else None)
            started = time.perf_counter()
            crashed = ""
            try:
                scenario(r)
            except Exception as error:                # 시나리오가 중간에 멈춤 = 큰 문제
                crashed = f"{type(error).__name__}: {error}"
                r.steps.append({"label": "(중간에 멈춤)", "screen": r.router.current_name,
                                "problems": [f"시나리오 진행 불가: {crashed}",
                                             traceback.format_exc().strip().splitlines()[-3]],
                                "picture": ""})
            r.close()
            results.append({"run": run_name, "number": number, "name": name, "path": path, "steps": r.steps,
                            "seconds": time.perf_counter() - started})
            bad = sum(bool(s["problems"]) for s in r.steps)
            print(f"[{run_name}] {number:02d} {name}: 단계 {len(r.steps)}개 · 문제 {bad}개", flush=True)
    write_report(out, results)
    return results


def write_report(out, results):
    lines = ["# 시나리오 점검 결과", "",
             f"점검 시각: {datetime.now():%Y-%m-%d %H:%M} · 플로차트 v4 갈래 {len(SCENARIOS)}가지 × "
             f"{len(RUNS)}가지 화면(기본 글자 1440×900, 큰 글자 1200×800)", "",
             "| 화면 | 번호 | 시나리오 | 지나간 길 | 단계 | 결과 |", "|---|---|---|---|---|---|"]
    for result in results:
        bad = [s for s in result["steps"] if s["problems"]]
        mark = "통과" if not bad else f"문제 {len(bad)}"
        lines.append(f"| {result['run']} | {result['number']:02d} | {result['name']} | {result['path']} | "
                     f"{len(result['steps'])} | {mark} |")
    lines += ["", "## 단계별 기록", ""]
    for result in results:
        lines.append(f"### [{result['run']}] {result['number']:02d}. {result['name']}")
        lines.append("")
        for index, step in enumerate(result["steps"], 1):
            picture = f" · 그림 `화면/{step['picture']}`" if step["picture"] else ""
            state = "✔" if not step["problems"] else "✘"
            lines.append(f"{index}. {state} {step['label']} — 화면 `{step['screen']}`{picture}")
            for problem in step["problems"]:
                lines.append(f"    - {problem}")
        lines.append("")
    (out / "점검결과.md").write_text("\n".join(lines), encoding="utf-8")
    write_html(out, results)


HTML_STYLE = """
body { margin: 0; background: #F7EEE3; color: #3C1B03; font: 15px/1.6 "Malgun Gothic", sans-serif; }
header { background: #3C1B03; color: #fff; padding: 28px 16px; text-align: center; }
main { max-width: 1100px; margin: 0 auto; padding: 20px 16px 60px; }
section { background: #fff; border-radius: 16px; padding: 18px 22px; margin-bottom: 18px; }
table { width: 100%; border-collapse: collapse; }
th, td { border-bottom: 1px solid #E8D9C6; padding: 6px 8px; text-align: left; }
th { background: #FBF6EF; }
.ok { color: #2E7D4F; font-weight: 700; }
.bad { color: #D4573C; font-weight: 700; }
.steps { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 12px; margin-top: 10px; }
.step { background: #FBF6EF; border-radius: 12px; padding: 8px; font-size: 14px; }
.step img { width: 100%; border-radius: 8px; display: block; margin-bottom: 4px; }
details summary { cursor: pointer; font-weight: 700; font-size: 16px; }
"""


def write_html(out, results):
    """사람이 보기 쉬운 결과 쪽. 그림은 기본 글자 실행에서만 찍으므로 그 단계만 그림이 있다."""
    steps = sum(len(r["steps"]) for r in results)
    bad_steps = sum(bool(s["problems"]) for r in results for s in r["steps"])
    rows = []
    for result in results:
        bad = sum(bool(s["problems"]) for s in result["steps"])
        mark = '<span class="ok">통과</span>' if not bad else f'<span class="bad">문제 {bad}</span>'
        rows.append(f"<tr><td>{escape(result['run'])}</td><td>{result['number']:02d}</td>"
                    f"<td>{escape(result['name'])}</td><td>{escape(result['path'])}</td>"
                    f"<td>{len(result['steps'])}</td><td>{mark}</td></tr>")
    blocks = []
    for result in results:
        cards = []
        for index, step in enumerate(result["steps"], 1):
            picture = f'<img src="화면/{step["picture"]}" alt="">' if step["picture"] else ""
            state = '<span class="ok">✔</span>' if not step["problems"] else '<span class="bad">✘</span>'
            problems = "".join(f'<div class="bad">{escape(text)}</div>' for text in step["problems"])
            cards.append(f'<div class="step">{picture}{state} {index}. {escape(step["label"])}{problems}</div>')
        opened = " open" if any(s["problems"] for s in result["steps"]) else ""
        blocks.append(f"<section><details{opened}><summary>[{escape(result['run'])}] {result['number']:02d}. "
                      f"{escape(result['name'])} — {escape(result['path'])}</summary>"
                      f'<div class="steps">{"".join(cards)}</div></details></section>')
    page = ("<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>시나리오 점검 결과</title><style>{HTML_STYLE}</style></head><body>"
            f"<header><h1>시나리오 점검 결과</h1><p>{datetime.now():%Y-%m-%d %H:%M} · "
            f"시나리오 {len(results)}번 실행 · 단계 {steps}개 · 문제 있는 단계 {bad_steps}개</p></header><main>"
            "<section><table><tr><th>화면</th><th>번호</th><th>시나리오</th><th>지나간 길</th>"
            f"<th>단계</th><th>결과</th></tr>{''.join(rows)}</table></section>"
            "<p>시나리오 제목을 누르면 단계별 화면이 펼쳐집니다. 그림은 기본 글자(1440×900) 실행에서만 찍습니다.</p>"
            f"{''.join(blocks)}</main></body></html>")
    (out / "점검결과.html").write_text(page, encoding="utf-8")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    app = QApplication(sys.argv[:1])
    results = run_all(out)
    problems = sum(bool(s["problems"]) for r in results for s in r["steps"])
    steps = sum(len(r["steps"]) for r in results)
    print(f"\n시나리오 {len(results)}개 · 단계 {steps}개 · 문제 있는 단계 {problems}개 → {out / '점검결과.md'}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
