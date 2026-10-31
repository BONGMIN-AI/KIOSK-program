"""화면 이름으로 이동하고 무입력 시간을 확인한다.

손님 한 명의 주문 상태(session)와 화면들이 함께 쓰는 서비스(얼굴 인증·운영자 확인·감사 로그)도 여기서 들고 있다.
화면 이동은 플로차트 v2.1을 따른다:
  00 대기 → 01 시작 → (회원) 02 로그인 · (비회원) 03 메뉴 · (회원가입) 10 · (운영자) 09-A
"""

from pathlib import Path

from PySide6.QtCore import QEvent, QTimer
from PySide6.QtWidgets import QApplication, QStackedWidget, QWidget

import config
from core import audit
from core.storage import recover_journal
from domain.customers import face_locked, find_by_card
from domain.member_cards import is_lost_card
from face import FaceError
from gui import theme
from gui.order import OrderSession

DEFAULT_DISPLAY = {"contrast": False, "large": False}


class Router(QStackedWidget):
    def __init__(self, parent=None, vault=None, face_factory=None, admin_check=None):
        super().__init__(parent)
        self.screens = {}
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
        self.card_wait = None                 # 회원 카드 연결 중이면 (카드 번호 -> None) 함수
        self.timer = QTimer(self)
        self.timer.setInterval(60_000)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.time_out)
        # 실제 키오스크처럼 돌아가기 15초 전에 미리 알려 준다 (특히 현금을 넣은 손님)
        self.warn_timer = QTimer(self)
        self.warn_timer.setInterval(45_000)
        self.warn_timer.setSingleShot(True)
        self.warn_timer.timeout.connect(self.warn_time_out)
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
        elif name != "unlock":
            self.restart_timer()
        if name != "admin":
            self.card_wait = None      # 카드 기다리기는 운영자 '회원카드 발급'에서만 (다른 화면에서 찍힌 카드를 잘못 할당하지 않게)
        if hasattr(screen, "on_show"):
            screen.on_show(**options)
        self.setCurrentWidget(screen)

    def restart_timer(self):
        self.timer.start()
        self.warn_timer.start()
        if self.warning_shown and self.notice is not None:   # 화면을 눌렀으니 경고 띠를 내린다
            self.notice.hide()
        self.warning_shown = False

    def stop_timer(self):
        self.timer.stop()
        self.warn_timer.stop()

    def warn_time_out(self):
        amount = self.session.inserted
        money = f"\n넣은 현금 {theme.won(amount)}은 반환돼요." if amount else ""
        left = min(15, (self.timer.remainingTime() + 999) // 1000) if self.timer.isActive() else 15
        if self.notice is not None:              # 11/01: 남은 초가 위쪽 띠에서 줄어든다
            self.notice.show_countdown(
                lambda s: f"{s}초 뒤 처음 화면으로 돌아가요. 계속하려면 화면을 눌러 주세요.{money}", left)
        self.warning_shown = True

    def time_out(self):
        """60초 동안 입력이 없으면 처음 화면으로. 넣은 현금이 있으면 반환하고 알려 준다."""
        amount = self.session.refund()
        if amount:
            self.audit("cash_refund_timeout", f"{amount}")
        self.show_screen("idle")
        if amount:
            self.notify(f"오래 입력이 없어 처음 화면으로 돌아왔어요.\n넣은 현금 {theme.won(amount)}을 반환했어요.", 10)

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
        """01 시작 화면의 고대비·큰 글자 버튼. 화면을 새로 만들고 지금 화면으로 돌아온다."""
        current = self.current_name
        self.apply_display({**self.display, **changes})
        self.show_screen(current)

    def apply_display(self, display):
        self.display = dict(display)
        theme.set_display(**self.display)
        if self.rebuild is not None:
            self.rebuild()

    def set_vault(self, vault):
        """운영자가 금고를 열면 주문에 쓸 데이터를 연결하고 대기 화면으로 간다."""
        self.session.vault = vault
        self.show_screen("idle")
        self.check_last_shutdown()

    def open_action(self, action):
        """01 시작 화면의 버튼."""
        self.pending_action = action
        self.session.reset()
        targets = {"guest": "menu", "member": "login", "signup": "signup", "admin": "admin_login"}
        self.show_screen(targets.get(action, "placeholder"))

    # 회원 카드 (RFID, 아이디어 R1)
    CARD_SCREENS = ("idle", "home", "login")

    def card_active(self):
        """지금 카드를 받는지: 대기·시작·로그인 화면이거나 카드 연결을 기다리는 중."""
        return self.session.vault is not None and (
            self.card_wait is not None or self.current_name in self.CARD_SCREENS) and not self.camera_busy

    def wait_card(self, on_card, seconds=15, on_timeout=None, owner=None, prompt="카드를 리더기에 대 주세요"):
        """카드 기다리기: seconds 안에 찍힌 카드 번호를 on_card로 넘긴다. 남은 초는 위쪽 띠에서 줄어든다.

        owner(기다리는 화면)가 그 사이 없어지면(큰 글자로 바꿔 화면을 새로 만들 때 등) 타이머도 함께 취소된다.
        """
        token = object()
        self.card_wait = on_card
        self._card_token = token
        if self.notice is not None:
            self.notice.show_countdown(lambda s: f"{prompt} · {s}초", seconds,
                                       alive=lambda: self.card_wait is on_card and self._card_token is token)

        def expire():
            if self.card_wait is on_card and self._card_token is token:
                self.card_wait = None
                if on_timeout:
                    on_timeout()
        QTimer.singleShot(seconds * 1000, owner or self, expire)

    def card_scanned(self, number):
        """카드가 찍혔다: 연결 중이면 그 화면에 넘기고, 아니면 그 회원으로 바로 얼굴 인증을 시작한다."""
        if self.card_wait is not None:
            on_card, self.card_wait = self.card_wait, None
            if self.notice is not None:
                self.notice.stop_countdown()
            on_card(number)
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
                self.notify("등록되지 않은 카드예요.\n회원카드는 회원가입 때나 로그인 화면에서 신청하고, 카운터에서 받아요.", 8)
            return
        self.audit("card_tag", customer["id"])
        login_id = customer["extra"]["login_id"]
        self.pending_action = "member"
        self.session.reset()
        if customer["extra"].get("face_enrolled") and not face_locked(self.session.vault, customer["id"]):
            self.show_screen("login", login_id=login_id, message="회원 카드 확인 · 얼굴 인증을 시작해요")
            QTimer.singleShot(0, self.screens["login"].face_login)     # 카드 = 아이디 입력, 바로 얼굴로
        else:
            self.show_screen("login", mode="password", login_id=login_id,
                             message="회원 카드 확인 · 얼굴 정보가 없어 비밀번호를 넣어 주세요")

    def card_refused(self, text):
        """시리얼 리더가 카드를 읽었지만 지금 화면이 받지 않거나 번호를 못 읽었을 때 (조용히 버리지 않는다)."""
        self.notify(text, 5)

    def start_member_order(self, customer):
        """회원 확인이 끝나면(얼굴·비밀번호·가입) My Menu가 먼저 열린 03 메뉴로 간다."""
        self.session.login(customer)
        self.show_screen("menu")

    # 서비스
    def face(self, viewer=None, on_step=None):
        """얼굴 공급자. 카메라·모델 문제는 FaceError로 알린다.

        viewer를 주면 그 화면 안 자리에 얼굴 기호를 그린다(02 로그인). 없으면 창 전체를 덮는 카메라 화면.
        """
        provider = self.face_factory(self.session.vault)
        if hasattr(provider, "viewer"):
            if viewer is not None:
                provider.viewer = viewer
            elif self.camera_view is not None:
                provider.viewer = self.camera_view.show_frame     # 별도 창 대신 키오스크 창 안에
        if on_step is not None and hasattr(provider, "on_step"):
            provider.on_step = on_step
        return provider

    def run_face(self, work, viewer=None, on_step=None):
        """카메라 작업 work(provider)를 한다. 그동안 무입력 타이머를 멈추고, 끝나면 카메라 화면을 닫는다.

        카메라·장치에서 예상 못 한 오류가 나도 프로그램이 멈추지 않도록 FaceError로 바꿔 알린다.
        """
        self.stop_timer()
        self.camera_busy = True
        try:
            return work(self.face(viewer, on_step))
        except ValueError:
            raise                               # FaceError·입력 오류는 화면이 그대로 안내한다
        except Exception as error:              # cv2.error·장치 끊김 등
            raise FaceError(f"카메라를 쓰는 중 문제가 생겼어요 ({type(error).__name__}). "
                            "비밀번호로 로그인하거나 직원을 불러 주세요") from error
        finally:
            self.camera_busy = False
            if self.camera_view is not None:
                self.camera_view.close_view()
            self.restart_timer()

    def audit(self, action, target=""):
        actor = self.admin_id or "system"
        if config.KEYSTORE_PATH.exists() and not self.audit_memory_only():
            audit.AuditLog(Path(config.DATA_DIR) / "audit.log").append(actor, action, target)
        else:
            self.audit_memory.append({"actor": actor, "action": action, "target": target})

    def audit_memory_only(self):
        # 메모리 금고(--demo·테스트)이면 실제 data 폴더 로그에 쓰지 않는다
        return type(self.session.vault).__name__ == "MemoryVault"

    def eventFilter(self, watched, event):
        inputs = (QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove,
                  QEvent.Type.KeyPress, QEvent.Type.Wheel, QEvent.Type.TouchBegin,
                  QEvent.Type.TouchUpdate)
        if isinstance(watched, QWidget) and watched.window() is self.window():
            if (event.type() in inputs and self.current_name not in ("idle", "unlock")
                    and not self.camera_busy):
                self.restart_timer()
        return super().eventFilter(watched, event)
