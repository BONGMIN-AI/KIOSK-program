"""11/10: 매장 / 포장이 뜨면 오른쪽 위 운영자 버튼 · 손님이 떠나면 3초 뒤 버튼을 내린다 · 시연은 기본 테마."""
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

pytest.importorskip("PySide6")
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from face.presence import FakePresence
from gui.main import KioskWindow, demo_vault
from gui.router import CHOICE_GONE_TICKS


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    result = KioskWindow(vault=demo_vault())
    result.show()
    app.processEvents()
    yield result
    result.close()
    result.deleteLater()
    app.processEvents()


def test_demo_starts_with_basic_theme():
    assert demo_vault().read("settings")["season_theme"] == "none"


def test_admin_button_shows_with_dine_choice(window):
    router, idle = window.router, window.router.screens["idle"]
    assert idle.admin_button.isHidden()
    router.ask_dine()
    assert idle.admin_button.isVisible()
    assert idle.admin_button.geometry().right() > idle.width() - 40     # 오른쪽 위
    idle.admin_button.click()
    assert router.current_name == "admin_login" and not idle.dine_choice.isVisible()


def test_choice_closes_when_customer_leaves(window):
    router, idle = window.router, window.router.screens["idle"]
    router.presence = FakePresence(0.8)
    router.presence_active = lambda: True
    router.ask_dine()
    router.check_presence()
    assert idle.dine_choice.isVisible()
    router.presence.distance = None                  # 떠났다
    for _ in range(CHOICE_GONE_TICKS):
        router.check_presence()
    QTest.qWait(600)                                 # 흐려지며 들어가는 시간
    assert not idle.dine_choice.isVisible() and idle.admin_button.isHidden()
