"""회원이 로그아웃 확인을 방치하면 10초 뒤 세션과 현금을 정리한다."""
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from domain.customers import login_with_password
from face import FakeFace
from gui.main import KioskWindow, demo_vault


def test_manual_logout_counts_down_and_returns_cash():
    app = QApplication.instance() or QApplication([])
    window = KioskWindow(vault=demo_vault(), face_factory=lambda vault: FakeFace())
    window.show()
    router = window.router
    router.show_screen("dine")
    router.screens["dine"].choose(False)
    router.open_action("member")
    router.start_member_order(login_with_password(router.session.vault, "bomin", "1234"))
    router.popup.hide()
    router.notice.hide()
    router.session.insert(1000)

    router.ask_leave()
    box = router.away_box
    assert box.isVisible()
    assert box.yes_button.text() == "예, 로그아웃 (10)"
    box.count_down()
    assert box.yes_button.text() == "예, 로그아웃 (9)"
    box.no_button.click()
    assert router.current_name == "menu" and router.session.is_member()
    assert not box.tick.isActive()

    router.ask_leave()
    box.left = 1
    box.count_down()
    assert router.current_name == "idle"
    assert not router.session.is_member() and router.session.inserted == 0
    assert not box.isVisible() and not box.tick.isActive()
    window.close()
    app.processEvents()
