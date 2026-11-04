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
HELD_SECONDS = 6.0             # 같은 화면에서 같은 카드가 이 안에 다시 오면(대고 있는 중) 한 번만 받는다
QUIET_SECONDS = 3.0            # 카드를 받은 직후에는 어떤 카드 · '못 읽음' 신호도 받지 않는다 (11/03: 성공과 실패가 함께 뜸)
MISREAD_GAP = 4.0              # '못 읽음' 안내는 이 안에 한 번만 (11/04: 따다닥 여러 번 뜸)
SILENT_SECONDS = 12.0          # ALIVE를 보내는 리더가 이만큼 조용하면 멈춘 것 → 포트를 다시 열어 보드를 리셋
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
    misread = Signal()
    removed = Signal()


class SerialCardReader(QObject):
    """카드 번호는 scanned, 연결 상태 글은 status. 둘 다 화면 스레드에서 받는다."""

    scanned = Signal(str)
    status = Signal(str)
    seen = Signal(str)                 # 테스트 모드: 카드가 올 때마다 어떻게 했는지 한 줄 (받음 · 넘김 · 안 받는 화면)
    notice = Signal(str)               # 손님에게 보여 줄 안내 (받지 않는 화면 · 번호를 못 읽음)

    def __init__(self, active=lambda: True, port=None, parent=None, screen=lambda: None):
        super().__init__(parent)
        self.active = active           # () -> 지금 화면이 카드를 받는지 (키보드 리더와 같은 규칙)
        self.screen = screen           # () -> 지금 화면 이름 (화면이 바뀌면 대고 있던 카드도 다시 받는다)
        self.port = port
        self.stopping = threading.Event()
        self.thread = None
        self.relay = _Relay()
        self.relay.number.connect(self.deliver)
        self.relay.text.connect(self.status)
        self.relay.misread.connect(self.misread)
        self.relay.removed.connect(self.card_removed)
        self.last_number, self.last_at, self.last_screen = None, 0.0, None
        self.misread_at = -MISREAD_GAP

    def quiet(self):
        """방금(3초 안) 카드를 받았는지. 그동안 리더기에 남은 카드를 다시 읽거나 '못 읽음'이 와도 넘긴다."""
        import time
        return time.monotonic() - self.last_at < QUIET_SECONDS

    def card_removed(self):
        """11/04 리더(tap 판): 카드를 뗐다 → 같은 카드라도 다음에 대면 바로 받는다."""
        self.last_number = None
        self.seen.emit("카드를 뗌")

    def misread(self):
        import time
        if self.quiet():
            self.seen.emit("카드 리더 '못 읽음' · 방금 읽은 직후라 넘김")
            return
        if time.monotonic() - self.misread_at < MISREAD_GAP:
            self.seen.emit("카드 리더 '못 읽음' · 안내는 방금 했음")
            return
        self.misread_at = time.monotonic()
        self.notice.emit("카드를 읽지 못했어요 · 카드를 떼었다가 리더기 가운데에 다시 대 주세요")

    def deliver(self, number):
        """11/03: 같은 화면에서 2.5초 안에 다시 온 같은 카드(대고 있는 중)만 넘긴다.

        예전에는 다시 올 때마다 기다리는 시간을 늘려서, 카드를 리더기 가까이 두면 영영 안 받았다.
        이제는 처리한 때부터만 재고, 화면이 바뀌면(등록 → 처음 화면 등) 같은 카드라도 바로 받는다.
        """
        import time
        now = time.monotonic()
        tail = f"****{number[-4:]}"
        screen = self.screen()
        if self.quiet():
            self.seen.emit(f"카드 {tail} · 방금 읽은 직후라 넘김")
            return
        if number == self.last_number and screen == self.last_screen and now - self.last_at < HELD_SECONDS:
            self.seen.emit(f"카드 {tail} · 방금 처리한 카드라 넘김 (떼었다 다시 대면 받아요)")
            return
        if not self.active():
            self.seen.emit(f"카드 {tail} · 이 화면은 카드를 안 받아요")
            self.notice.emit("카드는 처음 화면 · 시작 화면 · 로그인 화면에서 대 주세요\n"
                             "(받은 카드 등록은 로그인한 뒤 메뉴 화면에서)")
            return
        self.last_number, self.last_at, self.last_screen = number, now, screen
        self.seen.emit(f"카드 {tail} · 받음")
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
                    self.listen(link)
            except (OSError, serial.SerialException):
                # 뽑혔거나 아직 없음 → 잠시 뒤 다시 (키오스크는 계속 돈다)
                self.relay.text.emit(f"카드 리더를 다시 찾는 중: {self.port}")
                self.stopping.wait(RETRY_SECONDS)


    def listen(self, link):
        """한 줄씩 받는다. ALIVE를 보내는 리더가 오래 조용하면 돌아가서 포트를 다시 연다 (보드 리셋)."""
        import time
        heard, alive = time.monotonic(), False
        while not self.stopping.is_set():
            line = link.readline().decode("ascii", errors="ignore")
            now = time.monotonic()
            if line.strip():
                heard = now
            elif alive and now - heard > SILENT_SECONDS:
                self.relay.text.emit("카드 리더가 응답이 없어 다시 연결해요")
                return
            number = parse_line(line)
            if number:
                self.relay.number.emit(number)
            elif line.startswith("INFO"):      # 카드는 느꼈지만 번호를 못 읽음
                self.relay.misread.emit()
            elif line.startswith("REMOVED"):
                self.relay.removed.emit()
            elif line.startswith("ALIVE"):
                alive = True
            elif line.startswith(("READY", "ERROR", "STATUS")):
                self.relay.text.emit(f"카드 리더: {line.strip()}")


def start_serial_reader(active, on_card, on_status=print, parent=None, screen=lambda: None):
    """키오스크 창에서 부른다. 리더가 없어 시작하지 못하면 None."""
    reader = SerialCardReader(active, parent=parent, screen=screen)
    reader.scanned.connect(on_card)
    reader.status.connect(on_status)
    return reader if reader.start() else None
