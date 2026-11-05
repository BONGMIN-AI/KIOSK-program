"""화면 이름으로 이동하고 무입력 시간을 확인한다.

손님 한 명의 주문 상태(session)와 화면들이 함께 쓰는 서비스(얼굴 인증·운영자 확인·감사 로그)도 여기서 들고 있다.
화면 이동은 플로차트 v2.1을 따른다:
  00 대기 → 01 시작 → (회원) 02 로그인 · (비회원) 03 메뉴 · (회원가입) 10 · (운영자) 09-A
"""

import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, QTimer
from PySide6.QtWidgets import QApplication, QPushButton, QStackedWidget, QWidget

import config
from core import audit
from core import admin_badge
from core.storage import recover_journal
from domain.customers import call_name, face_locked, find_by_card
from domain.kiosk_settings import load_kiosk, presence_on
from domain.member_cards import is_lost_card, register_first_tap, unused_card
from domain.visits import celebrate, easter_egg, visit_greeting
from domain.titles import title_name
from face import FaceError
from gui import theme
from gui.order import OrderSession

DEFAULT_DISPLAY = {"contrast": False, "large": False}
STAFF_SCREENS = ("unlock", "admin_login", "admin", "placeholder")   # 손님 화면 설정과 상관없어 다시 안 만든다
# 사람 감지 (11/02 C): 대기 화면에서 1m 안에 1초 머물면 시작, 주문 중 1.5m 안에 아무도 없으면 자리 비움
APPROACH_M, SEEN_M = 1.0, 1.5
APPROACH_TICKS = 2                     # 0.5초 × 2
NO_AWAY_SCREENS = ("idle", "unlock", "admin_login", "admin", "done")   # 완료 화면은 자기 시간으로 돌아간다
AWAY_ASK_SECONDS = 10


class Screens(dict):
    """화면 이름 → 화면. 고대비 · 큰 글자로 바꿀 때는 지금 화면만 바로 만들고 나머지는 쓸 때(또는 쉬는 틈에) 만든다.

    factories에 있는 화면은 처음 꺼낼 때 만들어 router에 붙인다 (11/03: 버튼 반응을 빠르게).
    """

    def __init__(self, router):
        super().__init__()
        self.router = router
        self.factories = {}

    def __missing__(self, name):
        if name not in self.factories:
            raise KeyError(name)
        screen = self.factories.pop(name)()
        self.router.addWidget(screen)
        dict.__setitem__(self, name, screen)
        return screen

    def __contains__(self, name):
        return dict.__contains__(self, name) or name in self.factories

    def get(self, name, default=None):
        return self[name] if name in self else default

    def clear(self):
        super().clear()
        self.factories.clear()

    def build_next(self):
        """쉬는 틈에 하나씩 만든다 (다 만들 때까지 다시 부른다)."""
        if self.factories:
            self[next(iter(self.factories))]
            QTimer.singleShot(0, self.router, self.build_next)   # router가 지워지면 같이 취소


class Router(QStackedWidget):
    def __init__(self, parent=None, vault=None, face_factory=None, admin_check=None):
        super().__init__(parent)
        self.screens = Screens(self)
        self.pending_action = None
        self.session = OrderSession(vault)
        self.face_factory = face_factory      # () -> 얼굴 공급자 (create_face_provider 또는 시험용 FakeFace)
        self.admin_check = admin_check        # (운영자 ID, 비밀번호) -> 맞으면 그대로, 틀리면 예외
        self.admin_id = None                  # 로그인한 운영자
        self.audit_memory = []                # --demo처럼 data 폴더가 없을 때의 감사 기록
        self.language = "한국어"                # 00 대기·01 시작 화면 언어
        self.display = dict(DEFAULT_DISPLAY)  # 고대비·큰 글자 (지금 손님에게만)
        self.rebuild = None                   # KioskWindow가 넣어 준다: 화면을 새로 만든다
        self.camera_view = None               # KioskWindow가 넣어 준다: 창 안 카메라 화면
        self.camera_busy = False              # 카메라를 쓰는 동안은 무입력 타이머를 멈춘다
        self.notice = None                    # KioskWindow가 넣어 준다: 위쪽 안내 띠
        self.recovering = False               # 오류 처리 중 또 오류가 나면 되풀이하지 않는다
        self.warning_shown = False            # '15초 뒤 처음 화면' 경고를 띄운 상태
        self.timer = QTimer(self)
        self.timer.setInterval(60_000)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.time_out)
        # 실제 키오스크처럼 돌아가기 15초 전에 미리 알려 준다 (특히 현금을 넣은 손님)
        self.warn_timer = QTimer(self)
        self.warn_timer.setInterval(45_000)
        self.warn_timer.setSingleShot(True)
        self.warn_timer.timeout.connect(self.warn_time_out)
        self.presence = None                  # KioskWindow가 넣어 준다: 카메라 사람 감지 (없으면 터치로만)
        self.away_box = None                  # KioskWindow가 넣어 준다: '로그아웃할까요? (10)' 상자
        self.popup = None                     # KioskWindow가 넣어 준다: 축하 · 이스터에그 팝업
        self.near_ticks = 0
        self.approach_armed = False           # 한 번 1m 밖으로 물러나야 다음 '다가오면 시작'이 된다 (11/03)
        self.camera_status = None             # KioskWindow가 넣어 준다 (테스트 모드): 카메라가 본 것 한 줄
        self.last_seen = time.monotonic()
        self.presence_timer = QTimer(self)
        self.presence_timer.setInterval(500)
        self.presence_timer.timeout.connect(self.check_presence)
        self.presence_timer.start()
        self.apply_kiosk_settings()
        QApplication.instance().installEventFilter(self)

    def add_screen(self, name, screen):
        self.screens[name] = screen
        self.addWidget(screen)

    @property
    def current_name(self):
        for name, screen in self.screens.items():
            if screen is self.currentWidget():
                return name
        return None

    def show_screen(self, name, **options):
        screen = self.screens[name]
        if name == "idle":
            # 처음 화면으로 가면 새 손님: 장바구니·넣은 현금·회원·운영자 로그인을 모두 비운다.
            if self.notice is not None:
                self.notice.hide()                 # 앞 손님에게 띄운 안내도 함께 내린다 (11/03)
            if self.popup is not None:
                self.popup.hide()
            if self.admin_id:
                self.audit("admin_logout")
            self.pending_action = None
            self.admin_id = None
            self.session.reset()
            self.stop_timer()
            self.language = "한국어"
            if self.display != DEFAULT_DISPLAY:    # 다음 손님은 기본 화면으로
                self.apply_display(DEFAULT_DISPLAY)
                screen = self.screens[name]
        elif name == "admin":
            self.stop_timer()          # 11/02: 운영자 화면은 직접 '로그아웃'할 때만 나간다 (무입력 시간 없음)
        elif name != "unlock":
            self.restart_timer()
        if hasattr(screen, "on_show"):
            screen.on_show(**options)
        for leave in screen.findChildren(QPushButton, "leave_button"):
            leave.setText(self.leave_text())
        self.setCurrentWidget(screen)

    def leave_text(self):
        """처음 화면으로 가는 버튼 글 (11/04): 회원이면 '로그아웃' (메뉴로 가는 줄 알고 누르는 일이 있어서)."""
        return "로그아웃" if self.session.is_member() else "처음으로"

    def ask_leave(self):
        """'로그아웃' · '처음으로' 버튼: 회원이거나 담은 것이 있으면 한 번 묻고 처음 화면으로."""
        session = self.session
        has_items = bool(session.cart or session.tickets or session.card_kind)
        if self.popup is None or not (session.is_member() or has_items):
            self.show_screen("idle")
            return
        lost = "\n담은 메뉴 · 승차권은 지워져요." if has_items else ""
        if session.is_member():
            self.popup.ask("로그아웃할까요?", "처음 화면으로 돌아가요." + lost + "\n메뉴를 더 보려면 '아니요'를 눌러 주세요.",
                           "예, 로그아웃", lambda: self.show_screen("idle"))
        else:
            self.popup.ask("처음으로 갈까요?", "처음 화면으로 돌아가요." + lost, "예, 처음으로",
                           lambda: self.show_screen("idle"))

    def apply_kiosk_settings(self):
        """운영자 '키오스크 설정'의 시간들을 타이머에 넣는다 (시작할 때 · 저장할 때)."""
        settings = load_kiosk(self.session.vault.read("settings", default={}) if self.session.vault else {})
        self.idle_ms = settings["idle_seconds"] * 1000
        self.warn_ms = (settings["idle_seconds"] - settings["warn_seconds"]) * 1000
        self.timer.setInterval(self.idle_ms)
        self.warn_timer.setInterval(self.warn_ms)
        self.warn_seconds = settings["warn_seconds"]
        self.away_seconds = settings["away_seconds"]
        self.present_idle_seconds = settings["present_idle_seconds"]
        return settings

    def restart_timer(self):
        self.input_at = time.monotonic()      # 마지막으로 화면을 만진 때 (사람이 있으면 최대 120초까지 기다린다)
        self.timer.start(self.idle_ms)
        self.warn_timer.start(self.warn_ms)
        if self.warning_shown and self.notice is not None:   # 화면을 눌렀으니 경고 띠를 내린다
            self.notice.hide()
        self.warning_shown = False

    def stop_timer(self):
        self.timer.stop()
        self.warn_timer.stop()

    def person_here(self):
        """카메라가 지금 키오스크 앞(1.5m 안)에 사람을 보고 있는지."""
        if not self.presence_active():
            return False
        distance = self.presence.latest()
        return distance is not None and distance <= SEEN_M

    def wait_longer(self):
        """사람이 앞에 있고 마지막 터치에서 최대 시간(기본 120초)이 안 됐으면 경고 · 복귀를 미룬다 (11/03)."""
        warn = getattr(self, "warn_seconds", 15)
        left = getattr(self, "present_idle_seconds", 120) - warn - (time.monotonic() - getattr(self, "input_at", 0))
        if self.person_here() and left > 0:
            self.warn_timer.start(int(left * 1000))           # 마지막 터치에서 120초 - 경고 시간에 경고
            self.timer.start(int((left + warn) * 1000))
            return True
        return False

    def warn_time_out(self):
        if self.wait_longer():
            return
        amount = self.session.inserted
        money = f"\n넣은 현금 {theme.won(amount)}은 반환돼요." if amount else ""
        warn = getattr(self, "warn_seconds", 15)
        left = min(warn, (self.timer.remainingTime() + 999) // 1000) if self.timer.isActive() else warn
        if self.notice is not None:              # 11/01: 남은 초가 위쪽 띠에서 줄어든다
            self.notice.show_countdown(
                lambda s: f"{s}초 뒤 처음 화면으로 돌아가요. 계속하려면 화면을 눌러 주세요.{money}", left)
        self.warning_shown = True

    def time_out(self):
        """60초 동안 입력이 없으면 처음 화면으로. 넣은 현금이 있으면 반환하고 알려 준다."""
        self.leave("오래 입력이 없어", "cash_refund_timeout")

    def leave(self, why, audit_action):
        amount = self.session.refund()
        if amount:
            self.audit(audit_action, f"{amount}")
        if self.away_box is not None:
            self.away_box.hide()
        self.show_screen("idle")
        if amount:
            self.notify(f"{why} 처음 화면으로 돌아왔어요.\n넣은 현금 {theme.won(amount)}을 반환했어요.", 10)

    # ---- 사람 감지 (11/02 C)
    def presence_active(self):
        if self.presence is None or not getattr(self.presence, "working", True):
            return False
        return presence_on(self.session.vault.read("settings", default={}) if self.session.vault else {})

    def check_presence(self):
        """0.5초마다: 대기 화면이면 다가온 사람을 맞고, 주문 중이면 자리를 비웠는지 본다."""
        active = self.presence_active()
        idle = self.screens.get("idle")
        if self.presence is not None and idle is not None and idle.show_approach_hint != active:
            idle.set_approach_hint(active)          # '가까이 오시면 자동으로 시작' 안내
        now = time.monotonic()
        if not active:
            self.last_seen = now
            self.show_camera_status(None, "카메라 사람 감지 꺼짐" if self.presence is not None else "카메라 없음")
            return
        distance = self.presence.latest()
        name = self.current_name
        if name == "idle":
            near = distance is not None and distance <= APPROACH_M
            if not near:
                self.approach_armed = True            # 1m 밖(또는 아무도 없음)을 한 번 봤다 → 다가오면 시작
            self.near_ticks = self.near_ticks + 1 if near and self.approach_armed else 0
            if self.near_ticks >= APPROACH_TICKS:
                self.near_ticks = 0
                self.approach_armed = False
                self.last_seen = now
                self.audit("presence_start")
                self.ask_dine()
            self.show_camera_status(distance, "대기 · 1m 안으로 다가오면 시작" if self.approach_armed
                                    else "대기 · 1m 밖으로 한 번 물러났다가 다가오세요")
            return
        self.approach_armed = False
        self.near_ticks = 0
        seen = distance is not None and distance <= SEEN_M
        asking = self.away_box is not None and self.away_box.isVisible()
        if seen or self.camera_busy or name in NO_AWAY_SCREENS:
            self.last_seen = now                 # 11/03: 질문은 사람이 돌아와도 닫지 않는다 (아니요 · 로그아웃을 직접)
            self.show_camera_status(distance, "주문 중 · 자리에 있음" if seen else "이 화면은 자리 비움을 보지 않음")
            return
        left = getattr(self, "away_seconds", 10) - (now - self.last_seen)
        self.show_camera_status(distance, f"주문 중 · 아무도 없음 → {max(0, int(left + 0.99))}초 뒤 자리 비움 질문")
        if not asking and left <= 0:
            self.ask_away()

    def card_status_line(self, text):
        """테스트 모드: 카드 리더에서 온 것을 상태 줄 둘째 줄에 남긴다 (반응이 없을 때 이유 찾기)."""
        print(text, flush=True)
        self.card_line = text
        if self.camera_status is not None and self.camera_status.isVisible():
            self.show_camera_status(getattr(self, "last_distance", None), getattr(self, "last_state", ""))

    def show_camera_status(self, distance, state):
        """테스트 모드: 화면 왼쪽 아래에 카메라가 본 거리와 지금 판단을 보여 준다 (F2로 켜고 끔)."""
        if self.camera_status is None or not self.camera_status.isVisible():
            return
        self.last_distance, self.last_state = distance, state
        seen = "사람 없음" if distance is None else f"가장 가까운 사람 {distance:.2f}m"
        card = getattr(self, "card_line", "카드 리더: 아직 카드가 오지 않았어요")
        self.camera_status.setText(f"카메라: {seen}  ·  {state}\n{card}")
        self.camera_status.adjustSize()
        self.camera_status.move(12, self.window().height() - self.camera_status.height() - 12)
        self.camera_status.raise_()

    def ask_away(self):
        if self.away_box is None:
            return
        member = self.session.is_member()
        money = f"\n넣은 현금 {theme.won(self.session.inserted)}은 반환돼요." if self.session.inserted else ""
        self.away_box.ask_countdown(
            "자리를 비우셨나요?",
            ("계속 주문하려면 '아니요'를 눌러 주세요." if member else "계속하려면 '아니요'를 눌러 주세요.") + money,
            (lambda s: f"로그아웃 ({s})") if member else (lambda s: f"처음 화면으로 ({s})"),
            AWAY_ASK_SECONDS, lambda: self.leave("자리를 비워", "cash_refund_away"))

    def notify(self, text, seconds=6):
        if self.notice is not None:
            self.notice.show_message(text, seconds)

    def recover_from_error(self):
        """예상 못 한 오류: 넣은 현금을 반환하고 처음 화면으로 돌아가 손님에게 알린다."""
        if self.recovering:
            return
        self.recovering = True
        try:
            amount = self.session.refund()
            self.audit("unexpected_error", self.current_name or "")
            self.show_screen("idle")
            money = f"\n넣은 현금 {theme.won(amount)}을 반환했어요." if amount else ""
            self.notify(f"잠시 문제가 생겨 처음 화면으로 돌아왔어요.{money}\n계속되면 직원을 불러 주세요.", 10)
        finally:
            self.recovering = False

    def check_last_shutdown(self):
        """지난번 실행이 현금이 들어 있는 채로 꺼졌는지 확인하고 직원에게 알린다 (기록은 감사 로그에)."""
        if self.session.vault is None:
            return
        recovered = recover_journal(self.session.vault)
        if recovered:
            self.audit("journal_recovered", ",".join(recovered))
        record = self.session.unreturned_cash()
        if record:
            self.audit("cash_unreturned", f"{record['inserted']} {record.get('updated_at', '')}")
            self.notify(f"지난번에 키오스크가 꺼질 때 손님이 넣은 현금 {theme.won(record['inserted'])}이 "
                        "반환되지 않았어요.\n직원이 확인해 주세요 (운영자 메뉴 → 포인트 조정·로그에 기록).", 20)

    def set_display(self, **changes):
        """01 시작 화면의 고대비·큰 글자 버튼. 손님 화면만 새로 만들고 지금 화면으로 돌아온다."""
        current = self.current_name
        self.apply_display({**self.display, **changes})
        self.show_screen(current)

    def apply_display(self, display):
        self.display = dict(display)
        theme.set_display(**self.display)
        if self.rebuild is not None:
            self.rebuild(keep=STAFF_SCREENS)

    def set_vault(self, vault):
        """운영자가 금고를 열면 주문에 쓸 데이터를 연결하고 대기 화면으로 간다."""
        self.session.vault = vault
        self.apply_kiosk_settings()        # 금고가 열리면 운영자가 정한 시간을 읽는다
        self.show_screen("idle")
        self.check_last_shutdown()

    def open_action(self, action):
        """01 시작 화면의 버튼."""
        self.pending_action = action
        takeout = self.session.takeout
        self.session.reset()
        self.session.takeout = takeout                # 00-B에서 고른 매장 / 포장은 그대로
        targets = {"guest": "menu", "member": "login", "signup": "signup", "admin": "admin_login"}
        self.show_screen(targets.get(action, "placeholder"))

    # 회원 카드 (RFID, 아이디어 R1)
    CARD_SCREENS = ("idle", "dine", "home", "login")
    MEMBER_CARD_SCREENS = ("menu", "cart", "benefit")     # 로그인한 회원이 받은 카드를 처음 대는 곳 (11/03)

    def card_active(self):
        """지금 카드를 받는지: 대기·시작·로그인 화면이거나, 로그인한 회원의 주문 화면 (받은 카드 처음 대기)."""
        member = self.session.customer is not None and self.current_name in self.MEMBER_CARD_SCREENS
        return self.session.vault is not None and (
            self.current_name in self.CARD_SCREENS or member) and not self.camera_busy

    def card_scanned(self, number):
        """카드가 찍혔다: 로그인한 회원이면 받은 카드 등록, 아니면 그 회원으로 바로 얼굴 인증을 시작한다."""
        if admin_badge.is_admin_card(number):             # 11/04: 관리자 카드 → 운영자 얼굴 확인
            self.admin_card_login()
            return
        if self.session.customer is not None and self.current_name in self.MEMBER_CARD_SCREENS:
            self.member_card_tap(number)
            return
        try:
            customer = find_by_card(self.session.vault, number)
        except ValueError as error:
            self.notify(str(error))
            return
        if customer is None:
            if is_lost_card(self.session.vault, number):
                self.notify("분실 신고된 카드예요. 이 카드로는 로그인할 수 없어요.\n새 카드는 카운터에서 받아 주세요.", 8)
            else:
                self.notify("처음 쓰는 카드예요.\n로그인한 뒤 카드를 대면 등록돼요.", 8)
            return
        self.audit("card_tag", customer["id"])
        if self.session.takeout is None and "dine" in self.screens:     # 매장 / 포장을 아직 안 골랐으면 그것부터
            self.ask_dine(then=lambda: self.card_login(customer))
            self.notify(f"{call_name(customer)} 님 카드 확인 · 매장 / 포장을 골라 주세요", 4)   # 칭호같은 닉네임 대신 이름
            return
        self.card_login(customer)

    def admin_card_login(self):
        """관리자 카드를 댔다 (11/04): 운영자 로그인 화면으로 가서 그 안에서 얼굴 확인 → 맞으면 운영자 화면.
        회원 카드로는 절대 등록하지 않는다."""
        if self.current_name not in self.CARD_SCREENS:
            self.notify("관리자 카드는 처음 화면 · 시작 화면에서 대 주세요", 5)
            return
        if self.session.vault is None:
            self.notify("키오스크 잠금을 먼저 풀어 주세요", 5)
            return
        self.session.reset()
        self.show_screen("admin_login", badge=True)     # 운영자 로그인 화면 안에서 바로 얼굴 확인 (11/04)

    def ask_dine(self, then=None):
        """매장 / 포장 묻기 (11/03): 대기 화면이면 그 위에 버튼 두 개가 떠오르고, 다른 화면이면 00-B 화면."""
        idle = self.screens.get("idle")
        if self.current_name == "idle" and idle is not None:
            idle.dine_choice.open_choice(then)
        else:
            self.show_screen("dine", then=then)

    def choosing_dine(self):
        """지금 매장 / 포장을 묻고 있는지 (대기 화면 위 버튼 또는 00-B 화면)."""
        idle = self.screens.get("idle")
        return self.current_name == "dine" or (
            self.current_name == "idle" and idle is not None and idle.dine_choice.isVisible())

    def choose_dine(self, takeout):
        """시험 · 점검 도구용: 지금 떠 있는 매장 / 포장에서 고른다."""
        if self.current_name == "idle":
            self.screens["idle"].dine_choice.choose(takeout)
        else:
            self.screens["dine"].choose(takeout)

    def card_login(self, customer):
        """카드로 찾은 회원: 아이디를 채운 로그인 화면으로 (얼굴이 있으면 바로 얼굴 인증)."""
        login_id = customer["extra"]["login_id"]
        self.pending_action = "member"
        takeout = self.session.takeout
        self.session.reset()
        self.session.takeout = takeout                # 방금 고른 매장 / 포장은 그대로
        if customer["extra"].get("face_enrolled") and not face_locked(self.session.vault, customer["id"]):
            self.show_screen("login", login_id=login_id, message="회원 카드 확인 · 얼굴 인증을 시작해요")
            QTimer.singleShot(0, self.screens["login"].face_login)     # 카드 = 아이디 입력, 바로 얼굴로
        else:
            self.show_screen("login", mode="password", login_id=login_id,
                             message="회원 카드 확인 · 얼굴 정보가 없어 비밀번호를 넣어 주세요")

    def member_card_tap(self, number):
        """로그인한 회원이 주문 중에 카드를 댔다: 받은 카드면 번호를 등록하고 카드 적립을 시작한다."""
        customer = self.session.customer
        try:
            if unused_card(self.session.vault, customer["id"]) is None:
                owner = find_by_card(self.session.vault, number)
                self.notify("이미 등록된 회원카드예요." if owner and owner["id"] == customer["id"]
                            else "로그인한 회원의 카드가 아니에요.", 5)
                return
            record = register_first_tap(self.session.vault, customer["id"], number)
        except ValueError as error:
            self.notify(str(error), 6)
            return
        self.audit("card_registered", customer["id"])
        self.session.reload_customer()
        policy = self.session.policy()
        first = f"이번 주문 {policy['card_first_discount']}% 할인\n" if (
            record["kind"] == "new" and policy["card_first_discount"]) else ""
        text = f"카드 ****{record['card_tail']}\n{first}매 주문 {policy['card_point_rate']:g}% 적립 · 다음부터 카드만 대면 로그인"
        if self.notice is not None:
            self.notice.hide()                  # '리더기에 대 주세요' 초시계를 내리고
        if self.popup is not None:
            self.popup.tell("회원카드 등록 완료!", text)      # 한 번에 한 번만, 또렷하게
        else:
            self.notify(f"회원카드 등록 완료\n{text}", 8)
        menu = self.screens.get("menu")
        if menu is not None:
            menu.after_card_change()            # 위 회원 줄 · 장바구니 · My Menu '카드 등록' 줄을 다시 그린다

    def card_refused(self, text):
        """시리얼 리더가 카드를 읽었지만 지금 화면이 받지 않거나 번호를 못 읽었을 때 (조용히 버리지 않는다)."""
        self.notify(text, 5)

    def start_member_order(self, customer):
        """회원 확인이 끝나면(얼굴·비밀번호·가입) My Menu가 먼저 열린 03 메뉴로 간다."""
        greeting = visit_greeting(self.session.vault.read("orders", default={}), customer["id"])
        gifts = celebrate(self.session.vault, customer["id"])          # E19 생일 · 가입 기념 쿠폰
        self.session.login(self.session.vault.read("customers", default={}).get(customer["id"], customer))
        self.show_screen("menu")
        title = customer["extra"].get("title")
        title = f"[{title_name(title)}] " if title else ""
        hello = f"{title}{call_name(customer)} 님, {greeting}"   # E14 방문 간격 인사 (11/04: '[얼죽아] 김휘원 님,')
        if unused_card(self.session.vault, customer["id"]):              # 받은 카드를 아직 안 댔으면
            self.notify(f"{hello}\n받으신 회원카드를 리더기에 대면 등록돼요", 8)
        else:
            self.notify(hello, 4)
        if gifts and self.popup is not None:
            self.popup.tell(" · ".join(g["title"] for g in gifts), "\n".join(g["text"] for g in gifts))

    def easter_egg(self):
        """E22: 메뉴 화면 로고를 빠르게 다섯 번 → 100원 쿠폰 (회원마다 한 번)."""
        if self.popup is None:
            return
        customer = self.session.customer
        if customer is None:
            self.popup.tell("숨은 쿠폰을 찾았어요!", "회원으로 로그인하면\n100원 할인 쿠폰을 받을 수 있어요.")
            return
        kind = easter_egg(self.session.vault, customer["id"])
        if kind is None:
            self.popup.tell("이미 찾으셨네요!", "숨은 쿠폰은 한 번만 받을 수 있어요.")
            return
        self.audit("easter_egg", customer["id"])
        self.session.reload_customer()
        menu = self.screens.get("menu")
        if menu is not None:
            menu.update_top_bar()
        self.popup.tell("숨은 쿠폰을 찾았어요!", f"{kind['name']} 쿠폰을 넣어 드렸어요.\n결제할 때 쓸 수 있어요.")

    # 서비스
    def face(self, viewer=None, on_step=None, vault=None):
        """얼굴 공급자. 카메라·모델 문제는 FaceError로 알린다.

        viewer를 주면 그 화면 안 자리에 얼굴 기호를 그린다(02 로그인). 없으면 창 전체를 덮는 카메라 화면.
        """
        provider = self.face_factory(vault if vault is not None else self.session.vault)
        if hasattr(provider, "viewer"):
            if viewer is not None:
                provider.viewer = viewer
            elif self.camera_view is not None:
                provider.viewer = self.camera_view.show_frame     # 별도 창 대신 키오스크 창 안에
        if on_step is not None and hasattr(provider, "on_step"):
            provider.on_step = on_step
        return provider

    def run_face(self, work, viewer=None, on_step=None, vault=None):
        """카메라 작업 work(provider)를 한다. 그동안 무입력 타이머를 멈추고, 끝나면 카메라 화면을 닫는다.

        카메라·장치에서 예상 못 한 오류가 나도 프로그램이 멈추지 않도록 FaceError로 바꿔 알린다.
        """
        self.stop_timer()
        self.camera_busy = True
        shared_camera = None
        try:
            if self.presence is not None:
                shared_camera = self.presence.pause(handoff=True)  # 연결은 유지하고 읽기만 넘긴다
            provider = self.face(viewer, on_step, vault)
            if shared_camera is not None and hasattr(provider, "shared_camera"):
                provider.shared_camera = shared_camera
                provider.use_depth = shared_camera[1]
            return work(provider)
        except ValueError:
            raise                               # FaceError·입력 오류는 화면이 그대로 안내한다
        except Exception as error:              # cv2.error·장치 끊김 등
            raise FaceError(f"카메라를 쓰는 중 문제가 생겼어요 ({type(error).__name__}). "
                            "비밀번호로 로그인하거나 직원을 불러 주세요") from error
        finally:
            self.camera_busy = False
            if self.camera_view is not None:
                self.camera_view.close_view()
            if self.presence is not None:
                self.presence.resume()
            self.last_seen = time.monotonic()
            self.restart_timer()

    def audit(self, action, target=""):
        actor = self.admin_id or "system"
        if config.KEYSTORE_PATH.exists() and not self.audit_memory_only():
            audit.AuditLog(Path(config.DATA_DIR) / "audit.log").append(actor, action, target)
        else:
            self.audit_memory.append({"actor": actor, "action": action, "target": target, "ts": time.time()})

    def audit_memory_only(self):
        # 메모리 금고(--demo·테스트)이면 실제 data 폴더 로그에 쓰지 않는다
        return type(self.session.vault).__name__ == "MemoryVault"

    def eventFilter(self, watched, event):
        inputs = (QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove,
                  QEvent.Type.KeyPress, QEvent.Type.Wheel, QEvent.Type.TouchBegin,
                  QEvent.Type.TouchUpdate)
        if isinstance(watched, QWidget) and watched.window() is self.window():
            if (event.type() in inputs and self.current_name not in ("idle", "unlock", "admin")
                    and not self.camera_busy):
                self.restart_timer()
            if event.type() in inputs:
                self.last_seen = time.monotonic()      # 화면을 만지는 사람은 자리에 있다
        return super().eventFilter(watched, event)
