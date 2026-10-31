"""10/31 최종 시나리오 점검(tools/run_scenarios.py)에서 찾아 고친 문제가 다시 생기지 않게."""
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

pytest.importorskip("PySide6")
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from face import FakeFace
from gui.main import KioskWindow, demo_vault


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    result = KioskWindow(vault=demo_vault(), face_factory=lambda vault: FakeFace())
    result.resize(1200, 800)
    result.show()
    app.processEvents()
    yield result
    result.close()
    result.deleteLater()
    app.processEvents()


def test_large_text_password_failure_keeps_window_size(window):
    """큰 글자에서 비밀번호를 틀리면 창이 800 → 909px로 커진 채 남았다."""
    router = window.router
    router.apply_display({"contrast": False, "large": True})
    router.open_action("member")
    login = router.screens["login"]
    login.login_id.setText("bomin")
    login.set_mode("password")
    login.password.setText("0000")
    login.password_login()
    QTest.qWait(80)
    assert window.height() == 800
    assert login.minimumSizeHint().height() <= 800


def test_option_popup_is_laid_out_when_it_appears(window):
    """처음 여는 옵션 창이 한 장면 납작하게(48px) 보였다."""
    router = window.router
    router.open_action("guest")
    menu = router.screens["menu"]
    menu.show_category("커피")
    menu.open_option("M003")
    assert menu.popup.card.height() >= menu.popup.card.minimumSizeHint().height() - 2


def test_keyboard_backspace_uses_text_not_missing_symbol(window):
    """⌫ 기호는 글꼴에 없어 네모로 보였다."""
    router = window.router
    router.open_action("member")
    texts = [b.text() for b in router.screens["login"].keyboard.findChildren(QPushButton)]
    assert "⌫" not in texts and "지움" in texts
