"""시리얼(COM 포트) RFID 카드 리더 받기 (11/01: RC522 + Arduino Uno/Nano).

키보드처럼 입력하는 USB 리더는 gui/card_reader.py가 받는다. RC522 모듈은 SPI라서 아두이노가 읽고
USB 시리얼로 'CARD 84E3D237'(UID 16진수) 한 줄을 보낸다(tools/arduino/rfid_rc522_serial). 여기서는 그 줄을
뒤 스레드에서 읽어 키보드 리더와 똑같이 scanned 신호로 넘긴다. 받는 쪽(router.card_scanned)은 그대로다.

포트 고르기: 환경 변수 KIOSK_CARD_PORT(예: COM5)가 있으면 그것, 없으면 아두이노로 보이는 포트를 찾는다.
'off'면 쓰지 않는다. pyserial이 없거나 아두이노가 없으면 조용히 건너뛴다(키보드 리더·ID 입력은 그대로).
"""

import os
import threading

from PySide6.QtCore import QObject, Signal

MIN_DIGITS = 6
BAUD = 9600
RETRY_SECONDS = 3
# 아두이노 정품(2341·2A03), 복제품 CH340(1A86), FTDI(0403), CP210x(10C4)
ARDUINO_VIDS = {0x2341, 0x2A03, 0x1A86, 0x0403, 0x10C4}


HEX_DIGITS = set("0123456789ABCDEF")


def parse_line(line):
    """'CARD 84E3D237' → '84E3D237' (카드 UID 16진수, 대문자로 맞춤). 카드 줄이 아니면(준비·알림 등) None."""
    text = line.strip()
    if not text.startswith("CARD "):
        return None
    number = text[5:].strip().upper()
    return number if len(number) >= MIN_DIGITS and set(number) <= HEX_DIGITS else None


def find_port(ports=None):
    """쓸 포트 이름. 환경 변수 → 아두이노로 보이는 첫 포트 → 없으면 None."""
    chosen = os.environ.get("KIOSK_CARD_PORT", "").strip()
    if chosen.lower() == "off":
        return None
    if chosen:
        return chosen
    if ports is None:
        try:
            from serial.tools import list_ports
        except ImportError:
            return None
        ports = list_ports.comports()
    for port in ports:
        if getattr(port, "vid", None) in ARDUINO_VIDS:
            return port.device
    return None


class _Relay(QObject):
    """뒤 스레드 → 화면 스레드 다리 (Qt 신호는 스레드를 넘어 안전하게 전달된다)."""

    number = Signal(str)
    text = Signal(str)


class SerialCardReader(QObject):
    """카드 번호는 scanned, 연결 상태 글은 status. 둘 다 화면 스레드에서 받는다."""

    scanned = Signal(str)
    status = Signal(str)

    def __init__(self, active=lambda: True, port=None, parent=None):
        super().__init__(parent)
        self.active = active           # () -> 지금 화면이 카드를 받는지 (키보드 리더와 같은 규칙)
        self.port = port
        self.stopping = threading.Event()
        self.thread = None
        self.relay = _Relay()
        self.relay.number.connect(self.deliver)
        self.relay.text.connect(self.status)

    def deliver(self, number):
        if self.active():
            self.scanned.emit(number)

    def start(self):
        """포트가 있고 pyserial이 있으면 읽기 시작. 시작했으면 True."""
        try:
            import serial  # noqa: F401
        except ImportError:
            return False
        self.port = self.port or find_port()
        if not self.port:
            return False
        self.thread = threading.Thread(target=self.run, name="serial-card", daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.stopping.set()

    def run(self):
        import serial
        while not self.stopping.is_set():
            try:
                with serial.serial_for_url(self.port, BAUD, timeout=0.5) as link:   # COM5 · loop:// 모두
                    self.relay.text.emit(f"카드 리더 연결: {self.port}")
                    while not self.stopping.is_set():
                        line = link.readline().decode("ascii", errors="ignore")
                        number = parse_line(line)
                        if number:
                            self.relay.number.emit(number)
                        elif line.startswith(("READY", "ERROR")):
                            self.relay.text.emit(f"카드 리더: {line.strip()}")
            except (OSError, serial.SerialException):
                # 뽑혔거나 아직 없음 → 잠시 뒤 다시 (키오스크는 계속 돈다)
                self.relay.text.emit(f"카드 리더를 다시 찾는 중: {self.port}")
                self.stopping.wait(RETRY_SECONDS)


def start_serial_reader(active, on_card, on_status=print, parent=None):
    """키오스크 창에서 부른다. 리더가 없어 시작하지 못하면 None."""
    reader = SerialCardReader(active, parent=parent)
    reader.scanned.connect(on_card)
    reader.status.connect(on_status)
    return reader if reader.start() else None
