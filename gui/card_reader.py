"""USB RFID 카드 리더 받기 (아이디어 R1, 10/29).

USB RFID 리더(125kHz·13.56MHz)는 대부분 키보드처럼 동작한다: 카드를 대면 카드 번호 숫자를 아주 빠르게
입력하고 Enter를 보낸다. 그래서 따로 드라이버 없이 키 입력을 지켜보다가
'숫자 6개 이상이 사람이 칠 수 없을 만큼 빠르게(글자 사이 0.08초 이하) 들어오고 Enter'면 카드로 본다.

카드를 받는 화면(00 대기 · 01 시작 · 02 로그인 · 카드 연결 대기)에서도 키 입력은 그대로 둔다.
카드로 판정되면 Enter만 막고, 입력 칸에 찍힌 번호는 로그인 화면을 다시 열면서 지운다.
"""

import time

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QWindow

MIN_DIGITS = 6
MAX_GAP_SECONDS = 0.08


class CardReader(QObject):
    scanned = Signal(str)

    def __init__(self, active=lambda: True, parent=None):
        super().__init__(parent)
        self.active = active          # () -> 지금 화면이 카드를 받는지
        self.buffer = ""
        self.last_key = 0.0

    def feed(self, text, now=None):
        """키 하나. 카드 번호가 끝나면(Enter) 번호를 돌려준다. 시험에서도 바로 부른다."""
        now = time.monotonic() if now is None else now
        if now - self.last_key > MAX_GAP_SECONDS:
            self.buffer = ""          # 너무 느리면 사람이 친 것 → 처음부터
        self.last_key = now
        if text in ("\r", "\n"):
            number, self.buffer = self.buffer, ""
            return number if len(number) >= MIN_DIGITS else None
        if text.isdigit():
            self.buffer += text
        else:
            self.buffer = ""
        return None

    def eventFilter(self, watched, event):
        # 키 하나는 창(QWindow)에 먼저 오고 그다음 입력 칸으로 넘어간다. 창에서 한 번만 센다.
        if event.type() != QEvent.Type.KeyPress or not isinstance(watched, QWindow) or not self.active():
            return False
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            number = self.feed("\r")
            if number:
                self.scanned.emit(number)
                return True
            return False
        text = event.text()
        if text:
            self.feed(text)
        # 숫자 키는 막지 않는다 (10/29: 막았더니 로그인 칸에 숫자 키보드 입력이 안 됨).
        # 카드였다면 입력 칸에 들어간 번호는 card_scanned가 회원 ID로 바꿔 덮어쓴다.
        return False
