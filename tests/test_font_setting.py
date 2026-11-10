"""운영자 글꼴 선택은 저장되고 현재 화면에도 적용된다."""
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["KIOSK_CARD_PORT"] = "off"
os.environ["KIOSK_HID_CARD"] = "off"

from PySide6.QtWidgets import QApplication

from domain.kiosk_settings import font_style
from face import FakeFace
from gui import theme
from gui.main import KioskWindow, demo_vault


def test_admin_round_font_applies_and_survives_new_window():
    app = QApplication.instance() or QApplication([])
    vault = demo_vault()
    first = KioskWindow(vault=vault, face_factory=lambda v: FakeFace(v))
    first.show()
    router = first.router
    router.admin_id = "admin"
    router.show_screen("admin", tab="kiosk")
    admin = router.screens["admin"]
    assert admin.font_choice.currentData() == "default"
    admin.font_choice.setCurrentIndex(admin.font_choice.findData("round"))
    admin.save_kiosk()
    app.processEvents()
    assert font_style(vault.read("settings")) == "round"
    assert router.current_name == "admin"
    assert router.screens["admin"].font_choice.currentData() == "round"
    assert theme.font(17).family() == "Jua"
    first.close()
    first.deleteLater()
    app.processEvents()

    second = KioskWindow(vault=vault, face_factory=lambda v: FakeFace(v))
    assert theme.font(17).family() == "Jua"
    second.close()
    second.deleteLater()
    theme.set_font_style("default")
