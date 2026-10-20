"""암호 도구. 다른 모듈은 cryptography 를 직접 쓰지 않고 이 파일만 거친다.

- 비밀번호 -> 키:  PBKDF2-HMAC-SHA256 (느리게 만들어 무차별 대입을 어렵게 함)
- 데이터 암호화:   Fernet (AES 암호화 + 변조 검출용 HMAC 이 함께 들어 있음)
"""
import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

DEFAULT_ITERATIONS = 600_000


class WrongKey(Exception):
    """키가 틀렸거나 데이터가 변조되어 복호화에 실패."""


def random_salt(n: int = 16) -> bytes:
    return os.urandom(n)


def derive_key(password: str, salt: bytes, iterations: int = DEFAULT_ITERATIONS) -> bytes:
    raw = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, dklen=32)
    return base64.urlsafe_b64encode(raw)


def new_data_key() -> bytes:
    return Fernet.generate_key()


def encrypt(key: bytes, plaintext: bytes) -> bytes:
    return Fernet(key).encrypt(plaintext)


def decrypt(key: bytes, token: bytes) -> bytes:
    try:
        return Fernet(key).decrypt(token)
    except InvalidToken as e:
        raise WrongKey("복호화 실패: 키가 틀렸거나 데이터가 변조됨") from e


def hash_id(admin_id: str, app_salt: bytes) -> str:
    """관리자 ID 는 원문 대신 솔트 + SHA-256 해시로만 저장한다."""
    return hashlib.sha256(app_salt + admin_id.strip().lower().encode("utf-8")).hexdigest()
