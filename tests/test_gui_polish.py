"""5단계 다듬기: 홍보 배너 · 대기 화면 움직임 · 언어/고대비/큰 글자 · 창 안 카메라 화면."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

pytest.importorskip("PySide6")
import numpy as np
from PySide6.QtWidgets import QApplication

from domain.customers import find_by_login_id, set_face_enrolled
from face import FaceError, FakeFace
from gui import theme
from gui.main import KioskWindow, demo_vault
from gui.widgets import PromoBanner


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


def test_login_shows_two_banner_pictures(window):
    window.router.open_action("member")
    banners = window.router.screens["login"].promo.findChildren(PromoBanner)
    assert len(banners) == 2
    assert all(not banner.picture.isNull() for banner in banners)
    assert banners[0].width() == banners[1].width()


def test_idle_animates_only_while_visible(window):
    idle = window.router.screens["idle"]
    assert idle.frame_timer.isActive()
    assert not idle.logo.isNull() and not idle.logo_front.isNull()
    window.router.show_screen("home")
    assert not idle.frame_timer.isActive()


def test_contrast_and_large_text_reset_for_next_customer(window, app):
    router = window.router
    router.show_screen("home")
    router.set_display(contrast=True)
    assert router.current_name == "home"
    assert theme.BG == "#000000"
    router.set_display(large=True)
    assert theme.font(20).pixelSize() == round(20 * theme.LARGE_SCALE)
    assert router.screens["home"].large_button.isChecked()
    router.show_screen("idle")
    assert router.display == {"contrast": False, "large": False}
    assert theme.BG == "#F7EEE3" and theme.font(20).pixelSize() == 20


def test_home_language_follows_idle_choice(window):
    router = window.router
    router.screens["idle"].set_language("English")
    router.show_screen("home")
    home = router.screens["home"]
    assert home.signup_button.text().startswith("First time?")
    home.set_language("日本語")
    assert router.screens["idle"].start_text().startswith("画面")
    router.show_screen("idle")
    assert router.language == "한국어"


def face_member(router):
    """bomin을 얼굴 등록 회원으로 만든다 (시연 데이터는 얼굴이 없다)."""
    vault = router.session.vault
    set_face_enrolled(vault, find_by_login_id(vault, "bomin")["id"], True)


class ViewerFace(FakeFace):
    """창 안 카메라 화면을 쓰는 공급자 대역: 프레임 몇 장을 보여 준다."""

    def __init__(self):
        self.viewer = None

    def identify_face(self, claimed_customer_id, on_status=print):
        frame = np.zeros((120, 160, 3), np.uint8)
        for _ in range(3):
            if self.viewer(frame, 1):
                raise FaceError("사용자가 얼굴 인증을 취소했습니다")
        return claimed_customer_id


def test_login_face_shows_in_screen_and_can_cancel(window):
    """10/29: 02 로그인은 창 전체를 덮지 않고 왼쪽 칸에 얼굴 기호, 오른쪽에 할 일 한 줄."""
    router = window.router
    provider = ViewerFace()
    router.face_factory = lambda vault: provider
    face_member(router)
    router.open_action("member")
    login = router.screens["login"]
    login.login_id.setText("bomin")
    seen = []
    original = login.show_face

    def watch(image, wait_ms=1):
        seen.append((login.face_picture.isVisible(), login.keyboard.isVisible(), router.camera_view.isVisible()))
        return original(image, wait_ms)
    login.show_face = watch
    login.face_login()
    assert seen and all(face and not keys and not cover for face, keys, cover in seen)
    assert router.current_name == "menu"
    # 취소하면 키보드가 돌아오고 실패 안내가 남는다
    router.open_action("member")
    login.login_id.setText("bomin")
    login.show_face = lambda image, wait_ms=1: True
    login.face_login()
    assert router.current_name == "login" and login.fail_box.isVisible() and login.keyboard.isVisible()
    assert not login.face_picture.isVisible() and "취소" in login.fail_text.text()


def test_login_has_signup_link(window):
    router = window.router
    router.open_action("member")
    login = router.screens["login"]
    assert login.signup_link.isVisible()
    login.signup_link.click()
    assert router.current_name == "signup"


def test_unexpected_camera_error_becomes_message(window):
    router = window.router

    class Broken(FakeFace):
        def identify_face(self, claimed_customer_id, on_status=print):
            raise RuntimeError("device lost")
    router.face_factory = lambda vault: Broken()
    face_member(router)
    router.open_action("member")
    login = router.screens["login"]
    login.login_id.setText("bomin")
    login.face_login()
    assert router.current_name == "login"
    assert "카메라를 쓰는 중 문제가" in login.fail_text.text()
    assert router.timer.isActive() and not router.camera_busy


# ---- 오류 안내 · 갑자기 꺼짐 대비

def test_timeout_returns_inserted_cash_and_tells_customer(window):
    router = window.router
    router.open_action("guest")
    router.session.add("M001", None, 1)
    router.show_screen("cash")
    router.screens["cash"].insert(1000)
    router.time_out()
    assert router.current_name == "idle" and router.session.inserted == 0
    assert router.notice.isVisible() and "1,000원" in router.notice.text()
    assert router.audit_memory[-1]["action"] == "cash_refund_timeout"


def test_cash_screen_refuses_money_after_enough(window):
    router = window.router
    router.open_action("guest")
    router.session.add("M001", None, 1)          # 3,000원
    router.show_screen("cash")
    cash = router.screens["cash"]
    cash.insert(5000)
    cash.insert(5000)
    assert router.session.inserted == 5000 and "이미 충분" in cash.event.text()


def test_back_from_cash_tells_refund(window):
    router = window.router
    router.open_action("guest")
    router.session.add("M001", None, 1)
    router.show_screen("cash")
    router.screens["cash"].insert(1000)
    router.screens["cash"].back()
    assert router.current_name == "cart" and "1,000원" in router.notice.text()


def test_unexpected_error_goes_home_with_refund(window, monkeypatch, tmp_path):
    import sys
    from gui import main as main_module
    from gui.main import install_error_handler
    monkeypatch.setattr(main_module, "ERROR_LOG", tmp_path / "kiosk_error.log")   # 실제 logs 폴더는 건드리지 않음
    router = window.router
    router.open_action("guest")
    router.session.add("M001", None, 1)
    router.show_screen("cash")
    router.screens["cash"].insert(1000)
    old_hook = sys.excepthook
    try:
        install_error_handler(window)
        try:
            raise RuntimeError("시험용 오류")
        except RuntimeError:
            sys.excepthook(*sys.exc_info())
    finally:
        sys.excepthook = old_hook
        import faulthandler
        faulthandler.disable()
        window.fault_log.close()
    assert "시험용 오류" in (tmp_path / "kiosk_error.log").read_text(encoding="utf-8")
    assert router.current_name == "idle" and router.session.inserted == 0
    assert "잠시 문제가 생겨" in router.notice.text() and "1,000원" in router.notice.text()


def test_restart_after_power_loss_reports_cash_left_inside(app):
    vault = demo_vault()
    first = KioskWindow(vault=vault, face_factory=lambda v: FakeFace())
    first.router.open_action("guest")
    first.router.session.add("M001", None, 1)
    first.router.session.insert(1000)              # 이 순간 전원이 꺼졌다고 본다 (창을 닫지 않고 버림)
    second = KioskWindow(vault=vault, face_factory=lambda v: FakeFace())
    assert "1,000원" in second.router.notice.text()
    assert second.router.audit_memory[-1]["action"] == "cash_unreturned"
    third = KioskWindow(vault=vault, face_factory=lambda v: FakeFace())
    assert not third.router.audit_memory                # 한 번 알렸으면 다시 알리지 않는다
    for window in (first, second, third):
        window.close()


def test_order_saved_halfway_is_finished_on_restart(app):
    from core.storage import JOURNAL
    from domain.cart import add_item
    from domain.orders import complete_order

    vault = demo_vault()

    class PowerCut(Exception):
        pass

    writes = []
    original = vault.write

    def cut_after_journal(name, data):
        original(name, data)
        writes.append(name)
        if len(writes) == 2:                       # journal과 첫 데이터만 쓰고 꺼짐
            raise PowerCut()
    vault.write = cut_after_journal
    with pytest.raises(PowerCut):
        complete_order(vault, add_item({}, "M001", 1, None, vault.read("menu")), 5000)
    vault.write = original
    assert vault.read(JOURNAL)
    window = KioskWindow(vault=vault, face_factory=lambda v: FakeFace())
    assert vault.read(JOURNAL) == {}
    assert any(order["cash"] == 5000 for order in vault.read("orders").values())
    assert window.router.audit_memory[0]["action"] == "journal_recovered"
    window.close()
