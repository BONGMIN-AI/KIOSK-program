"""11/04 회의: 관리자 카드 — 대면 운영자 얼굴 확인 → 바로 운영자 화면. 회원 카드로 등록되지 않는다."""
import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="관리자 카드 파일은 Windows DPAPI로 암호화")


@pytest.fixture
def badge(tmp_path, monkeypatch):
    from core import admin_badge
    from domain.customers import card_hash
    path = tmp_path / "admin_badge.bin"
    monkeypatch.setattr(admin_badge, "PATH", path)
    admin_badge.save({"card_hash": card_hash("ADM1N001"), "face_profiles": {}})
    return path


@pytest.fixture
def window():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from face import FakeFace
    from gui.main import KioskWindow, demo_vault
    app = QApplication.instance() or QApplication([])
    result = KioskWindow(vault=demo_vault(), face_factory=lambda vault: FakeFace())
    result.show()
    app.processEvents()
    yield result
    result.close()
    result.deleteLater()
    app.processEvents()


def test_admin_card_goes_to_admin_after_face(badge, window):
    router = window.router
    from PySide6.QtWidgets import QApplication
    router.show_screen("idle")
    router.card_scanned("ADM1N001")
    assert router.current_name == "admin_login"              # 운영자 로그인 화면으로 가서 그 안에서 얼굴 확인
    for _ in range(5):
        QApplication.processEvents()
    assert router.current_name == "admin" and router.admin_id == "admin"


def test_admin_card_never_links_to_member(badge, window):
    router = window.router
    member = next(iter(router.session.vault.read("customers").values()))
    router.session.login(member)
    router.show_screen("menu")
    router.card_scanned("ADM1N001")
    assert router.current_name == "menu" and "처음 화면" in router.notice.text()
    assert not any(c.get("extra", {}).get("card_hash") for c in router.session.vault.read("customers").values()
                   if c["id"] == member["id"])


def test_other_cards_are_not_admin(badge):
    from core import admin_badge
    assert admin_badge.is_admin_card("ADM1N001") and not admin_badge.is_admin_card("84E3D273")


def test_main_admin_face_survives_demo_restart(badge):
    from PySide6.QtWidgets import QApplication
    from core import admin_badge
    from gui.main import KioskWindow, demo_vault

    saved = admin_badge.load()
    saved["face_profiles"][admin_badge.ADMIN_KEY] = {"feature": [1.0]}
    admin_badge.save(saved)
    app = QApplication.instance() or QApplication([])

    class SavedFace:
        def __init__(self, vault):
            self.vault = vault

        def identify_face(self, key, on_status):
            assert key in self.vault.read("face_profiles", default={})
            return key

    for _ in range(2):
        kiosk = KioskWindow(vault=demo_vault(), face_factory=SavedFace)
        kiosk.show()
        app.processEvents()
        kiosk.router.show_screen("admin_login")
        kiosk.router.screens["admin_login"].face_login()
        assert kiosk.router.current_name == "admin"
        kiosk.close()
        kiosk.deleteLater()
        app.processEvents()
