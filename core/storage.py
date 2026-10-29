"""암호화 저장 계층.

다른 모듈은 파일 경로나 암호를 몰라도 된다. 아래 두 줄만 쓴다.
    data = vault.read("students", default={})
    vault.write("students", data)

- 디스크에는 항상 암호문(<이름>.json.enc)만 저장된다.
- 쓰기는 '임시 파일 -> 교체' 방식이라 도중에 전원이 꺼져도 파일이 반쯤 쓰이지 않는다.
- 이전 버전을 .bak 으로 남기고, 본 파일이 깨지면 .bak 으로 복구한다.
- 개발/테스트 때는 MemoryVault 를 쓰면 키도 파일도 필요 없다 (API 동일).
- 여러 파일을 한 묶음으로 바꿀 때(주문 = 회원·주문·재고·설정)는 write_together 를 쓴다.
  먼저 묶음 전체를 journal 에 적고 나서 하나씩 쓰므로, 도중에 꺼져도 다음 실행 때 recover_journal 이 마저 쓴다.
"""
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from . import crypto

SCHEMA_VERSION = 1
_NAME = re.compile(r"^[a-z0-9_]{1,40}$")


class DataCorrupted(Exception):
    """본 파일과 백업 모두 읽을 수 없음."""


def _check_name(name: str) -> str:
    if not _NAME.match(name):
        raise ValueError("데이터 이름은 영문 소문자, 숫자, _ 만 가능 (1~40자)")
    return name


def _bak(path: Path) -> Path:
    return Path(str(path) + ".bak")


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, _bak(path))
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def _pack(data) -> bytes:
    return json.dumps({"schema_version": SCHEMA_VERSION, "data": data},
                      ensure_ascii=False).encode("utf-8")


def _unpack(raw: bytes):
    return json.loads(raw.decode("utf-8"))["data"]


JOURNAL = "journal"


def write_together(vault, datasets: dict) -> None:
    """datasets({이름: 데이터})를 한 묶음으로 저장한다. 중간에 꺼지면 recover_journal 이 마저 쓴다."""
    vault.write(JOURNAL, datasets)
    for name, data in datasets.items():
        vault.write(name, data)
    vault.write(JOURNAL, {})


def recover_journal(vault) -> list:
    """지난번에 쓰다 만 묶음이 있으면 끝까지 쓰고, 다시 쓴 데이터 이름을 돌려준다."""
    pending = vault.read(JOURNAL, default={}) or {}
    for name, data in pending.items():
        vault.write(name, data)
    if pending:
        vault.write(JOURNAL, {})
    return sorted(pending)


class Vault:
    """암호화된 JSON 저장소. 직접 만들지 말고 core.auth.unlock() 이 돌려준 것을 쓴다."""

    def __init__(self, data_dir, data_key: bytes):
        self._dir = Path(data_dir)
        self._key = data_key

    def _path(self, name: str) -> Path:
        return self._dir / f"{_check_name(name)}.json.enc"

    def exists(self, name: str) -> bool:
        return self._path(name).exists()

    def list_names(self) -> list:
        return sorted(p.name[: -len(".json.enc")] for p in self._dir.glob("*.json.enc"))

    def read(self, name: str, default=None):
        path = self._path(name)
        if not path.exists():
            return default
        for candidate in (path, _bak(path)):
            try:
                return _unpack(crypto.decrypt(self._key, candidate.read_bytes()))
            except (crypto.WrongKey, ValueError, KeyError, FileNotFoundError):
                continue
        raise DataCorrupted(f"'{name}' 를 읽을 수 없습니다 (본 파일과 백업 모두 실패)")

    def write(self, name: str, data) -> None:
        atomic_write(self._path(name), crypto.encrypt(self._key, _pack(data)))


class MemoryVault:
    """Vault 와 같은 API 의 메모리 버전. 팀원이 개발/테스트할 때 사용."""

    def __init__(self):
        self._store = {}

    def exists(self, name: str) -> bool:
        return _check_name(name) in self._store

    def list_names(self) -> list:
        return sorted(self._store)

    def read(self, name: str, default=None):
        _check_name(name)
        if name not in self._store:
            return default
        return json.loads(self._store[name])

    def write(self, name: str, data) -> None:
        self._store[_check_name(name)] = json.dumps(data, ensure_ascii=False)
