"""관리자 카드 (11/04 회의): 미리 정해 둔 카드 한 장을 대면 운영자 얼굴 확인 → 바로 운영자 화면.

카드 번호(해시)와 운영자 얼굴 특징은 회원 금고가 아니라 data/admin_badge.bin 한 파일에 둔다.
시연 모드는 메모리 금고라 끄면 사라지지만, 관리자 카드는 시연 모드 · 실제 모드 모두에서 계속 써야 하기 때문이다.
파일은 Windows DPAPI로 이 PC의 이 Windows 계정에서만 풀리게 암호화한다 (비밀번호 없이, 다른 PC로 복사하면 못 연다).
data/ 폴더는 GitHub · 배포 ZIP에 넣지 않는다. 등록은 tools/register_admin_badge.py (본인이 직접, 카메라 앞에서).
"""
import ctypes
import json
import sys
from ctypes import wintypes

import config
from core.auth import admin_face_key
from domain.customers import card_hash

PATH = config.DATA_DIR / "admin_badge.bin"
ADMIN_ID = "admin"
ADMIN_KEY = admin_face_key(ADMIN_ID)


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(data: bytes, protect: bool) -> bytes:
    if sys.platform != "win32":
        raise OSError("관리자 카드는 Windows에서만 쓸 수 있어요")
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    buffer = ctypes.create_string_buffer(data, len(data))
    source = _Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    result = _Blob()
    entropy_bytes = b"coffee-spoon-admin-badge"
    entropy_buffer = ctypes.create_string_buffer(entropy_bytes, len(entropy_bytes))
    entropy = _Blob(len(entropy_bytes), ctypes.cast(entropy_buffer, ctypes.POINTER(ctypes.c_char)))
    call = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    ok = call(ctypes.byref(source), None, ctypes.byref(entropy), None, None, 0x1, ctypes.byref(result))
    if not ok:
        raise OSError("관리자 카드 파일을 열 수 없어요 (다른 PC · 다른 Windows 계정에서 만든 파일)")
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        kernel32.LocalFree(result.pbData)


def load(path=None) -> dict:
    """저장된 관리자 카드 {card_hash, face_profiles}. 없거나 못 열면 빈 dict."""
    try:
        return json.loads(_dpapi((path or PATH).read_bytes(), protect=False).decode("utf-8"))
    except (OSError, ValueError):
        return {}


def save(data: dict, path=None) -> None:
    path = path or PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_dpapi(json.dumps(data).encode("utf-8"), protect=True))


def is_admin_card(number: str, path=None) -> bool:
    data = load(path)
    try:
        return bool(data.get("card_hash")) and data["card_hash"] == card_hash(number)
    except ValueError:
        return False


class BadgeVault:
    """얼굴 공급자(OpenCVFace)가 쓰는 금고 모양 (read · write 'face_profiles')만 흉내 낸다."""

    def __init__(self, path=None):
        self.path = path

    def read(self, name, default=None):
        value = load(self.path).get(name)
        return default if value is None else value

    def write(self, name, value):
        data = load(self.path)
        data[name] = value
        save(data, self.path)
