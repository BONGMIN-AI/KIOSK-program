"""SV1520 보고서 해석과 키오스크 카드 경로."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from gui.hid_card import HidCardReader
from gui.hid_device import card_uid


def test_known_sv1520_report():
    report = bytes.fromhex("00 0a 00 63 90 00 04 d4 12 d4 73 08" + " 00" * 53)
    assert card_uid(report) == "D412D473"
    assert card_uid(b"\x00" * 65) is None


def test_hid_reader_uses_existing_duplicate_rule():
    app = QApplication.instance() or QApplication([])
    received = []
    reader = HidCardReader(screen=lambda: "idle")
    reader.scanned.connect(received.append)
    reader.deliver("D412D473")
    reader.deliver("D412D473")
    assert received == ["D412D473"]
    reader.card_removed()
    reader.last_at = 0  # 기존 시리얼 리더의 3초 조용히 처리 규칙이 지난 상황
    reader.deliver("D412D473")
    assert received == ["D412D473", "D412D473"]
    reader.deleteLater()
    app.processEvents()
