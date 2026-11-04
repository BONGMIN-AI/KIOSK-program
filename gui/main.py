"""실행: python -m gui.main [--fullscreen] [--demo]

--demo : 비밀번호·data 폴더 없이 메모리에 샘플 데이터를 만들어 화면만 확인한다(저장되지 않음).
         운영자 로그인은 admin / demo.
그 밖에는 처음에 운영자가 금고를 연다(관리자 ID·비밀번호).

화면 흐름은 플로차트 v2.1 · 와이어프레임 v2.1을 따른다.
"""

import argparse
import faulthandler
import sys
import traceback
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QLabel, QLayout, QMainWindow

import config
from core import auth, schema
from core.storage import MemoryVault
from domain import seed
from domain.random_members import make_random_members
from domain.team_members import add_team_members
from face import create_face_provider
from face.presence import CameraPresence, presence_wanted
from gui import theme
from gui.card_reader import CardReader
from gui.serial_card import start_serial_reader
from gui.router import Router
from gui.screens.admin import AdminLoginScreen, AdminScreen
from gui.screens.benefit import BenefitScreen
from gui.screens.checkout import CartScreen, CashScreen, DoneScreen
from gui.screens.dine import DineScreen
from gui.screens.find_account import FindAccountScreen
from gui.screens.home import HomeScreen
from gui.screens.idle import IdleScreen
from gui.screens.login import LoginScreen
from gui.screens.menu import MenuScreen
from gui.screens.placeholder import PlaceholderScreen
from gui.screens.signup import EnrollScreen, SignupScreen
from gui.screens.unlock import UnlockScreen
from gui.widgets import CameraView, ConfirmBox, CountdownBox, Notice

DEMO_ADMIN = ("admin", "demo")
ERROR_LOG = config.ROOT / "logs" / "kiosk_error.log"   # 오류 기록 (얼굴·비밀번호 같은 개인 정보는 쓰지 않는다)


def demo_vault(random_members=False):
    """시연·테스트용: 메모리에만 있는 금고에 샘플 데이터를 채운다.

    random_members=True(시연 모드 실행)이면 주문 습관이 다른 무작위 회원 16명(user01~user16 / 1234)과
    팀원 시연 계정 2명(withtop77 김휘원 · jisung0642 김지성 / 1234)도 더한다.
    자동 테스트는 정해진 4명만 쓴다.
    """
    vault = MemoryVault()
    vault.write("settings", dict(schema.DEFAULT_SETTINGS))
    seed.run(vault)
    seed.add_demo_events(vault)
    if random_members:
        make_random_members(vault)
        add_team_members(vault)          # 팀원 시연 계정 withtop77 · jisung0642 / 1234
    return vault


def real_face(vault):
    """실제 카메라 얼굴 공급자 (D435가 있으면 깊이로 입체 확인)."""
    return create_face_provider(vault, config.CAMERA_INDEX)


def real_admin_check(admin_id, password):
    """금고 열쇠(keystore)로 운영자 비밀번호를 확인한다. 틀리면 AuthError."""
    auth.unlock(config.KEYSTORE_PATH, config.DATA_DIR, admin_id, password)


def demo_admin_check(admin_id, password):
    if (admin_id, password) != DEMO_ADMIN:
        raise ValueError("시연 모드 운영자는 admin / demo 입니다")


class KioskWindow(QMainWindow):
    def __init__(self, event=theme.FROM_POLICY, vault=None, face_factory=real_face, admin_check=None,
                 presence=None, test_mode=False, web=False):
        super().__init__()
        theme.load_fonts()
        theme.set_display()          # 새 창은 기본 색·글자 크기로
        self.setWindowTitle("COFFEE & SPOON KIOSK")
        self.setWindowIcon(QIcon(str(theme.ASSETS / "logo_sub.png")))
        self.resize(1200, 800)
        if admin_check is None:
            admin_check = demo_admin_check if isinstance(vault, MemoryVault) else real_admin_check
        self.event = event
        self.router = Router(self, vault, face_factory, admin_check)
        self.router.rebuild = self.build_screens
        self.setCentralWidget(self.router)
        # 키오스크 창은 화면 크기 그대로다. 화면을 바꾸는 한 순간의 큰 최소 높이 때문에 창이 커진 채
        # 남지 않게 한다 (10/31 시나리오 점검: 큰 글자 02 비밀번호 실패 → 800px 창이 909px로).
        # 내용이 정말 넘치는지는 tools/check_layout.py가 '칸 눌림'으로 잡는다.
        self.layout().setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.router.camera_view = CameraView(self)      # 얼굴 인증 카메라를 창 안에 덮어 보여 준다
        self.router.notice = Notice(self)               # 위쪽 안내 띠 (현금 반환·오류 안내)
        self.router.away_box = CountdownBox(self)       # 자리 비움 '로그아웃할까요? (10)' (11/02 C)
        self.router.popup = ConfirmBox(self)            # 축하 · 이스터에그 팝업 (11/03 E)
        self.router.presence = presence                 # 카메라 사람 감지 (None이면 터치로만)
        # 테스트 모드(--test): 왼쪽 아래 카메라 상태 줄. F2로 언제든 켜고 끈다.
        self.camera_status = QLabel(self)
        self.camera_status.setObjectName("camera_status")
        self.camera_status.setStyleSheet("QLabel#camera_status { background: rgba(20, 10, 4, 200); color: white;"
                                         " border-radius: 10px; padding: 6px 12px; font-size: 14px; }")
        self.camera_status.setVisible(test_mode)
        self.router.camera_status = self.camera_status
        self.status_shortcut = QShortcut(QKeySequence("F2"), self)
        self.status_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.status_shortcut.activated.connect(lambda: self.camera_status.setVisible(not self.camera_status.isVisible()))
        self.card_reader = CardReader(self.router.card_active, self)   # USB RFID 리더 (키보드처럼 입력)
        self.card_reader.scanned.connect(self.router.card_scanned)
        QApplication.instance().installEventFilter(self.card_reader)
        # RC522 + 아두이노처럼 시리얼로 번호를 보내는 리더 (꽂혀 있지 않으면 None)
        self.serial_card = start_serial_reader(self.router.card_active, self.router.card_scanned, parent=self,
                                               on_status=lambda text: print(text, flush=True),
                                               screen=lambda: self.router.current_name)
        if self.serial_card is not None:
            self.serial_card.notice.connect(self.router.card_refused)
            self.serial_card.status.connect(self.router.card_status_line)   # 테스트 모드: 리더 연결 상태
            self.serial_card.seen.connect(self.router.card_status_line)     # 테스트 모드: 카드가 올 때마다
        # QR 회원 페이지 (--web, 11/04): 휴대폰으로 가입 · 내 정보 고치기. 키오스크와 같은 금고를 쓴다 (잠금 해제 전이면 None)
        self.member_site = None
        if web:
            from gui.member_site import start_member_site
            self.member_site = start_member_site(lambda: self.router.session.vault)
            print(f"QR 회원 페이지: {self.member_site.url}" if self.member_site else "QR 회원 페이지를 열지 못했어요 (포트 8080)",
                  flush=True)
        self.build_screens()
        self.router.show_screen("idle" if vault is not None else "unlock")
        if vault is not None:
            self.router.check_last_shutdown()
        self.quit_shortcut = QShortcut(QKeySequence("Ctrl+Shift+Q"), self)
        self.quit_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.quit_shortcut.activated.connect(self.close)

    STAFF_SCREENS = ("unlock", "admin_login", "admin", "placeholder")

    def build_screens(self, keep=()):
        """화면을 지금 색·글자 크기(theme)로 만든다. 고대비·큰 글자를 바꾸면 다시 부른다.

        keep: 다시 만들지 않고 그대로 둘 화면 (11/03: 손님 화면만 다시 만들어 버튼 반응을 빠르게).
        """
        app = QApplication.instance()
        app.removeEventFilter(self.router)        # 수백 개 위젯을 만드는 동안 무입력 감시를 쉬게 한다
        kept = {name: screen for name, screen in self.router.screens.items() if name in keep}
        for name, screen in list(self.router.screens.items()):
            if name in kept:
                continue
            self.router.removeWidget(screen)
            screen.setParent(None)
            screen.deleteLater()
        self.router.screens.clear()
        self.setFont(theme.font())
        self.setPalette(theme.palette())
        self.setStyleSheet(theme.stylesheet())
        screens = {
            "unlock": UnlockScreen, "dine": DineScreen, "home": HomeScreen,
            "login": LoginScreen, "find": FindAccountScreen, "signup": SignupScreen, "enroll": EnrollScreen,
            "menu": MenuScreen, "cart": CartScreen, "benefit": BenefitScreen,
            "cash": CashScreen, "done": DoneScreen,
            "admin_login": AdminLoginScreen, "admin": AdminScreen,
            "placeholder": PlaceholderScreen,
        }
        screens = {"idle": lambda router: IdleScreen(router, self.event), **screens}
        lazy = bool(keep)                         # 화면 설정을 바꿀 때만: 지금 화면 먼저, 나머지는 쉬는 틈에
        for name, screen in screens.items():
            if name in kept:
                dict.__setitem__(self.router.screens, name, kept[name])
            elif lazy:
                self.router.screens.factories[name] = lambda screen=screen: screen(self.router)
            else:
                self.router.add_screen(name, screen(self.router))
        if lazy:
            QTimer.singleShot(0, self.router, self.router.screens.build_next)
        app.installEventFilter(self.router)

    def closeEvent(self, event):
        self.router.stop_timer()
        self.router.presence_timer.stop()
        if self.router.presence is not None:
            self.router.presence.stop()
        # 창을 닫으면 무입력 감시도 함께 뗀다 (남아 있으면 다른 창의 입력마다 계속 불린다)
        QApplication.instance().removeEventFilter(self.router)
        QApplication.instance().removeEventFilter(self.card_reader)
        if self.serial_card is not None:
            self.serial_card.stop()
        if self.member_site is not None:
            self.member_site.stop()
        super().closeEvent(event)


def log_error(text):
    ERROR_LOG.parent.mkdir(exist_ok=True)
    with ERROR_LOG.open("a", encoding="utf-8") as log:
        log.write(f"[{datetime.now().isoformat(timespec='seconds')}] {text}\n")


def install_error_handler(window):
    """화면 버튼 처리 중 예상 못 한 오류가 나도 프로그램을 끄지 않는다.

    오류 내용은 logs/kiosk_error.log에 남기고, 손님에게는 안내 띠를 보여 주며 처음 화면으로 돌아간다
    (넣은 현금이 있으면 반환 안내). 파이썬 자체가 멈추는 심각한 오류도 같은 파일에 남긴다.
    """
    def handle(kind, error, trace):
        if issubclass(kind, KeyboardInterrupt):
            sys.__excepthook__(kind, error, trace)
            return
        log_error("".join(traceback.format_exception(kind, error, trace)))
        try:
            window.router.recover_from_error()
        except Exception as again:                   # 복구도 실패하면 기록만 남긴다
            log_error(f"복구 실패: {again!r}")
    sys.excepthook = handle
    ERROR_LOG.parent.mkdir(exist_ok=True)
    window.fault_log = ERROR_LOG.open("a", encoding="utf-8")
    faulthandler.enable(window.fault_log)


def main():
    parser = argparse.ArgumentParser(description="COFFEE & SPOON KIOSK")
    parser.add_argument("--fullscreen", action="store_true")
    parser.add_argument("--demo", action="store_true", help="메모리 샘플 데이터로 실행(저장 안 됨)")
    parser.add_argument("--test", action="store_true", help="시연 데이터 + 왼쪽 아래 카메라 상태 줄 (직접 시험해 보기)")
    parser.add_argument("--web", action="store_true", help="QR 회원 페이지(가입 · 내 정보)를 같은 와이파이에 연다 (11/04)")
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    presence = CameraPresence(config.CAMERA_INDEX) if presence_wanted() else None
    demo = args.demo or args.test
    window = KioskWindow(vault=demo_vault(random_members=True) if demo else None, presence=presence,
                         test_mode=args.test, web=args.web)
    install_error_handler(window)
    if args.fullscreen:
        window.showFullScreen()
    else:
        window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
