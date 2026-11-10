"""계절 테마를 바꾸면 대기 화면과 매장·포장 선택 배경이 함께 바뀐다."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from domain.seasonal_theme import IDLE_BACKGROUNDS, idle_backgrounds, set_theme
from face import FakeFace
from gui.main import KioskWindow, demo_vault


def test_idle_background_switches_with_theme_and_restores_default():
    app = QApplication.instance() or QApplication([])
    vault = demo_vault()
    window = KioskWindow(vault=vault, face_factory=lambda current: FakeFace())
    window.resize(1672, 941)
    window.show()
    idle = window.router.screens["idle"]
    try:
        for choice in ("autumn", "winter", "none", "autumn"):
            set_theme(vault, choice)
            window.router.show_screen("home")
            window.router.show_screen("idle")
            app.processEvents()
            assert idle.background_files == IDLE_BACKGROUNDS[choice]
            assert idle.background.size().width() == 1672
            assert idle.choice_background.size().height() == 941
            assert not idle.scaled_background.isNull()
            assert not idle.scaled_choice_background.isNull()
            assert idle_backgrounds(vault.read("settings")) == IDLE_BACKGROUNDS[choice]
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()
