"""11/01: RC522 + 아두이노(시리얼) 카드 리더. 실물 없이 가짜 포트로 확인한다."""
import os
import time
from types import SimpleNamespace

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

pytest.importorskip("PySide6")
serial = pytest.importorskip("serial")
from PySide6.QtWidgets import QApplication

from domain.customers import link_card
from face import FakeFace
from gui import serial_card
from gui.main import KioskWindow, demo_vault
from gui.serial_card import SerialCardReader, find_port, parse_line


def test_parse_line_takes_only_card_lines():
    assert parse_line("CARD 84E3D237\r\n") == "84E3D237"              # 4바이트 카드 UID (16진수)
    assert parse_line("CARD 04a1b2c3d4e5f6") == "04A1B2C3D4E5F6"        # 7바이트 카드, 대문자로
    assert parse_line("CARD 0012345678") == "0012345678"
    assert parse_line("READY RC522 v0x18 gain max") is None
    assert parse_line("INFO read failed: Timeout in communication.") is None
    assert parse_line("CARD 12ZZ5678") is None and parse_line("CARD 123") is None


def test_find_port_prefers_setting_then_arduino(monkeypatch):
    ports = [SimpleNamespace(device="COM3", vid=0x8087), SimpleNamespace(device="COM7", vid=0x1A86)]
    monkeypatch.delenv("KIOSK_CARD_PORT", raising=False)
    assert find_port(ports) == "COM7"                      # CH340 복제 아두이노
    assert find_port([ports[0]]) is None
    monkeypatch.setenv("KIOSK_CARD_PORT", "COM9")
    assert find_port(ports) == "COM9"
    monkeypatch.setenv("KIOSK_CARD_PORT", "off")
    assert find_port(ports) is None


class FakeLink:
    """아두이노 대신: 준비 줄 → 카드 줄 하나 → 그 뒤로는 빈 줄."""

    def __init__(self, *args, **kwargs):
        self.lines = [b"READY RC522 v0x92\r\n", b"CARD 84E3D237\r\n"]

    def readline(self):
        time.sleep(0.01)
        return self.lines.pop(0) if self.lines else b""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def wait_for(condition, seconds=2.0):
    end = time.monotonic() + seconds
    while not condition() and time.monotonic() < end:
        QApplication.processEvents()
        time.sleep(0.01)
    return condition()


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    result = KioskWindow(vault=demo_vault(), face_factory=lambda vault: FakeFace())
    result.show()
    app.processEvents()
    yield result
    result.close()
    result.deleteLater()
    app.processEvents()


def test_card_from_serial_starts_member_login(window, monkeypatch):
    router = window.router
    assert window.serial_card is None                     # 테스트에서는 실물 포트를 열지 않는다
    member = next(iter(router.session.vault.read("customers").values()))
    link_card(router.session.vault, member["id"], "84E3D237")
    monkeypatch.setattr(serial, "serial_for_url", FakeLink)
    reader = SerialCardReader(router.card_active, port="COM_TEST", parent=window)
    reader.scanned.connect(router.card_scanned)
    notes = []
    reader.status.connect(notes.append)
    router.show_screen("home")
    assert reader.start()
    assert wait_for(lambda: router.current_name in ("dine", "login", "menu"))   # 매장/포장 → 카드 회원 로그인
    reader.stop()
    assert any("READY" in note for note in notes)


def test_card_ignored_when_screen_does_not_take_cards(window):
    router = window.router
    got = []
    reader = SerialCardReader(router.card_active, port="COM_TEST", parent=window)
    reader.scanned.connect(got.append)
    router.open_action("guest")                           # 메뉴 화면은 카드를 받지 않는다
    reader.deliver("84E3D237")
    assert got == []
    router.show_screen("home")
    reader.deliver("84E3D237")
    assert got == ["84E3D237"]


def test_removed_card_is_taken_again_right_away(window, monkeypatch):
    """11/04: 리더(tap 판)가 REMOVED를 보내면 같은 카드를 떼었다 다시 대도 바로 받는다."""
    import gui.serial_card as serial_card
    router = window.router
    got = []
    reader = SerialCardReader(router.card_active, port="COM_TEST", parent=window, screen=lambda: "idle")
    reader.scanned.connect(got.append)
    router.show_screen("idle")
    reader.deliver("84E3D237")
    monkeypatch.setattr(serial_card, "QUIET_SECONDS", 0.0)
    reader.deliver("84E3D237")                            # 대고 있는 중 → 한 번만
    assert got == ["84E3D237"]
    reader.card_removed()
    reader.deliver("84E3D237")                            # 뗐다가 다시 대면 바로
    assert got == ["84E3D237", "84E3D237"]


def test_misread_notice_shows_once_in_a_while(window):
    """11/04: '못 읽음'이 따다닥 와도 안내는 한 번만."""
    notes = []
    reader = SerialCardReader(window.router.card_active, port="COM_TEST", parent=window)
    reader.notice.connect(notes.append)
    for _ in range(5):
        reader.misread()
    assert len(notes) == 1


class SilentLink(FakeLink):
    """ALIVE를 한 번 보내고 멈춘 리더."""

    opened = 0

    def __init__(self, *args, **kwargs):
        SilentLink.opened += 1
        self.lines = [b"READY RC522 v0x18 gain max tap\r\n", b"ALIVE\r\n"]


def test_silent_reader_is_reopened(window, monkeypatch):
    """11/04: ALIVE를 보내던 리더가 조용해지면 포트를 다시 연다 (우노는 이때 리셋된다)."""
    import gui.serial_card as serial_card
    monkeypatch.setattr(serial_card, "SILENT_SECONDS", 0.2)
    monkeypatch.setattr(serial, "serial_for_url", SilentLink)
    SilentLink.opened = 0
    reader = SerialCardReader(window.router.card_active, port="COM_TEST", parent=window)
    assert reader.start()
    assert wait_for(lambda: SilentLink.opened >= 2)
    reader.stop()
