"""변조 탐지 감사 로그 (해시 체인).

각 줄이 '이전 줄의 해시'를 포함해서, 중간 줄을 고치거나 지우면 이후 해시가 전부 어긋난다.
개인정보는 넣지 않는다 (누가, 무엇을, 어떤 레코드 ID 에). 로그는 암호화하지 않는다.
한계: 맨 끝 줄을 통째로 잘라내는 것은 탐지하지 못한다.
"""
import hashlib
import json
import time
from pathlib import Path

GENESIS = "0" * 64


def _digest(entry: dict) -> str:
    body = {k: entry[k] for k in ("seq", "ts", "actor", "action", "target", "prev")}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


class AuditLog:
    def __init__(self, path):
        self._path = Path(path)

    def _entries(self) -> list:
        if not self._path.exists():
            return []
        lines = self._path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def append(self, actor: str, action: str, target: str = "", now=time.time) -> dict:
        entries = self._entries()
        prev = entries[-1]["hash"] if entries else GENESIS
        entry = {"seq": len(entries) + 1, "ts": int(now()), "actor": actor,
                 "action": action, "target": target, "prev": prev}
        entry["hash"] = _digest(entry)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def verify(self):
        """(True, None) 이면 정상. 아니면 (False, 처음 어긋난 seq)."""
        prev = GENESIS
        for i, entry in enumerate(self._entries(), start=1):
            if entry.get("seq") != i or entry.get("prev") != prev or entry.get("hash") != _digest(entry):
                return False, i
            prev = entry["hash"]
        return True, None
