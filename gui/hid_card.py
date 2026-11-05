"""SV1520 USB HID 리더를 기존 카드 처리 흐름에 연결한다."""

import ctypes as C
import os
import threading
import time

from gui import hid_device
from gui.serial_card import SerialCardReader

VID, PID = 0x0483, 0x572B
RETRY_SECONDS = 3
REMOVAL_GAP = 1.0


class HidCardReader(SerialCardReader):
    """시리얼 리더의 화면별 허용·중복 방지 규칙을 그대로 사용한다."""

    def __init__(self, active=lambda: True, parent=None, screen=lambda: None):
        super().__init__(active=active, parent=parent, screen=screen)
        self.handle = None

    def start(self):
        if os.name != "nt" or os.environ.get("KIOSK_HID_CARD", "").lower() == "off":
            return False
        self.thread = threading.Thread(target=self.run, name="hid-card", daemon=True)
        self.thread.start()
        return True

    def stop(self):
        super().stop()
        if self.handle is not None:
            hid_device.kernel.CancelIoEx(self.handle, None)

    def run(self):
        while not self.stopping.is_set():
            try:
                self.listen_hid()
            except (OSError, ValueError) as exc:
                self.relay.text.emit(f"SV1520 리더 재연결 대기: {exc}")
            self.stopping.wait(RETRY_SECONDS)

    def listen_hid(self):
        for path in hid_device.hid_paths():
            if self.stopping.is_set():
                return
            if f"vid_{VID:04x}&pid_{PID:04x}" not in path.lower():
                continue
            handle = hid_device.kernel.CreateFileW(path, 0x80000000, 3, None, 3, 0, None)
            if handle == hid_device.INVALID:
                raise C.WinError(C.get_last_error())
            self.handle = handle
            try:
                self.read_reports(handle)
            finally:
                self.handle = None
                hid_device.kernel.CloseHandle(handle)
            return
        self.relay.text.emit("SV1520 리더를 찾는 중")

    def read_reports(self, handle):
        pre = C.c_void_p()
        caps = hid_device.HIDP_CAPS()
        if not hid_device.hid.HidD_GetPreparsedData(handle, C.byref(pre)):
            raise C.WinError(C.get_last_error())
        try:
            hid_device.hid.HidP_GetCaps(pre, C.byref(caps))
        finally:
            hid_device.hid.HidD_FreePreparsedData(pre)
        if caps.InputReportByteLength <= 0:
            raise ValueError("입력 보고서가 없음")
        self.relay.text.emit("SV1520 카드 리더 연결")
        last_uid, last_seen = None, 0.0
        while not self.stopping.is_set():
            data = C.create_string_buffer(caps.InputReportByteLength)
            count = hid_device.W.DWORD()
            if not hid_device.kernel.ReadFile(handle, data, len(data), C.byref(count), None):
                if self.stopping.is_set():
                    return
                raise C.WinError(C.get_last_error())
            uid = hid_device.card_uid(data.raw[:count.value])
            if not uid:
                continue
            now = time.monotonic()
            if last_uid == uid and now - last_seen < REMOVAL_GAP:
                last_seen = now
                continue
            if last_uid == uid:
                self.relay.removed.emit()
            last_uid, last_seen = uid, now
            self.relay.number.emit(uid)


def start_hid_reader(active, on_card, on_status=print, parent=None, screen=lambda: None):
    reader = HidCardReader(active, parent=parent, screen=screen)
    reader.scanned.connect(on_card)
    reader.status.connect(on_status)
    return reader if reader.start() else None
