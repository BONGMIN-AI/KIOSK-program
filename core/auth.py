"""관리자 인증과 키 관리 (envelope 방식).

    [데이터 키 DK]  무작위로 한 번 생성. 모든 데이터는 DK 로 암호화한다.
    [관리자 슬롯]   관리자마다 '비밀번호에서 만든 키(KEK)로 DK 를 감싼 것'을 가진다.

- 로그인 = 비밀번호로 KEK 를 만들어 DK 를 풀어 보는 것. 풀리면 성공(HMAC 으로 검증됨).
- 비밀번호를 바꾸거나 관리자를 추가해도 DK 는 그대로라 데이터를 다시 암호화할 필요가 없다.
- 관리자 ID 는 해시로만, 비밀번호는 저장하지 않는다. keystore.json 만으로는 데이터를 못 푼다.
- 5회 연속 실패하면 60초 잠금.
- 2차 인증(얼굴 인식 등)은 second_factor 콜백으로 끼운다. 얼굴은 '통과 여부'만 판정하고,
  키 재료로 쓰지 않는다 (얼굴 벡터는 매번 값이 조금씩 달라 키가 될 수 없음).
"""
import json
import time
from pathlib import Path

from . import crypto
from .storage import Vault, atomic_write

MAX_FAILURES = 5
LOCK_SECONDS = 60
_GENERIC_FAIL = "아이디 또는 비밀번호가 올바르지 않습니다"


class AuthError(Exception):
    pass


class AuthFailed(AuthError):
    pass


class LockedOut(AuthError):
    def __init__(self, remaining: int):
        super().__init__(f"로그인 시도 초과. {remaining}초 후 다시 시도하세요")
        self.remaining = remaining


def _load(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _save(path, ks: dict) -> None:
    atomic_write(Path(path), json.dumps(ks, indent=2).encode("utf-8"))


def _make_slot(data_key: bytes, password: str, iterations: int) -> dict:
    salt = crypto.random_salt()
    kek = crypto.derive_key(password, salt, iterations)
    return {
        "salt": salt.hex(),
        "iterations": iterations,
        "wrapped_dk": crypto.encrypt(kek, data_key).decode("ascii"),
    }


def init_keystore(keystore_path, admin_id: str, password: str,
                  iterations: int = crypto.DEFAULT_ITERATIONS) -> None:
    """최초 1회. 데이터 키를 만들고 첫 관리자를 등록한다."""
    if Path(keystore_path).exists():
        raise AuthError("keystore 가 이미 있습니다")
    if not admin_id.strip() or len(password) < 4:
        raise AuthError("ID 는 비울 수 없고 비밀번호는 4자 이상이어야 합니다")
    app_salt = crypto.random_salt()
    data_key = crypto.new_data_key()
    ks = {
        "schema_version": 1,
        "app_salt": app_salt.hex(),
        "slots": {crypto.hash_id(admin_id, app_salt): _make_slot(data_key, password, iterations)},
        "failures": {},
    }
    _save(keystore_path, ks)


def unlock(keystore_path, data_dir, admin_id: str, password: str,
           second_factor=None, now=time.time) -> Vault:
    """로그인. 성공하면 Vault 를 돌려준다. second_factor 는 () -> bool 함수."""
    ks = _load(keystore_path)
    app_salt = bytes.fromhex(ks["app_salt"])
    key_id = crypto.hash_id(admin_id, app_salt)
    fail = ks["failures"].get(key_id, {"count": 0, "locked_until": 0})
    t = now()
    if fail["locked_until"] > t:
        raise LockedOut(int(fail["locked_until"] - t) + 1)

    def register_failure():
        count = fail["count"] + 1
        locked = t + LOCK_SECONDS if count >= MAX_FAILURES else 0
        ks["failures"][key_id] = {"count": 0 if locked else count, "locked_until": locked}
        _save(keystore_path, ks)

    slot = ks["slots"].get(key_id)
    data_key = None
    if slot is not None:
        kek = crypto.derive_key(password, bytes.fromhex(slot["salt"]), slot["iterations"])
        try:
            data_key = crypto.decrypt(kek, slot["wrapped_dk"].encode("ascii"))
        except crypto.WrongKey:
            data_key = None
    if data_key is None:
        register_failure()
        raise AuthFailed(_GENERIC_FAIL)

    if second_factor is not None and not second_factor():
        register_failure()
        raise AuthFailed("2차 인증에 실패했습니다")

    if key_id in ks["failures"]:
        del ks["failures"][key_id]
        _save(keystore_path, ks)
    return Vault(data_dir, data_key)


def admin_exists(keystore_path, admin_id: str) -> bool:
    """관리자 ID가 등록되어 있는지만 확인한다. 얼굴 로그인 전에 ID를 먼저 검사할 때 쓴다."""
    ks = _load(keystore_path)
    return crypto.hash_id(admin_id, bytes.fromhex(ks["app_salt"])) in ks["slots"]


def admin_face_key(admin_id: str) -> str:
    """얼굴 특징을 저장할 때 회원 ID와 겹치지 않도록 관리자용 키를 따로 쓴다."""
    return f"ADMIN-{admin_id.strip().lower()}"


def add_admin(keystore_path, vault: Vault, new_id: str, new_password: str,
              iterations: int = crypto.DEFAULT_ITERATIONS) -> None:
    """로그인된 관리자가 다른 관리자를 추가. 관리자 2명 이상을 권장 (비밀번호 분실 대비)."""
    ks = _load(keystore_path)
    app_salt = bytes.fromhex(ks["app_salt"])
    key_id = crypto.hash_id(new_id, app_salt)
    if key_id in ks["slots"]:
        raise AuthError("이미 있는 관리자 ID 입니다")
    if len(new_password) < 4:
        raise AuthError("비밀번호는 4자 이상이어야 합니다")
    ks["slots"][key_id] = _make_slot(vault._key, new_password, iterations)
    _save(keystore_path, ks)
