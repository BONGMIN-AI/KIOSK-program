"""KIOSK 데이터 스키마 공통 규칙. 자세한 표는 docs/SCHEMA.md."""
from datetime import datetime

DATASETS = ("customers", "menu", "orders", "settings", "face_profiles")

DEFAULT_SETTINGS = {
    "high_contrast": False,
    "large_mode": False,
    "store_name": "BONGMIN CAFE",
    "next_order_number": 1,
}

_REQUIRED = {"id": str, "name": str, "phone": str, "created_at": str, "updated_at": str, "extra": dict}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_record(record_id: str, name: str, phone: str, **extra) -> dict:
    t = now_iso()
    return {"id": record_id, "name": name, "phone": phone,
            "created_at": t, "updated_at": t, "extra": dict(extra)}


def touch(record: dict) -> dict:
    record["updated_at"] = now_iso()
    return record


def next_id(prefix: str, existing: dict, width: int = 4) -> str:
    """next_id('C', {'C0001': ...}) -> 'C0002'"""
    nums = [int(k[len(prefix):]) for k in existing if k.startswith(prefix) and k[len(prefix):].isdigit()]
    return f"{prefix}{(max(nums) + 1 if nums else 1):0{width}d}"


def validate_record(record: dict) -> list:
    """문제 목록을 돌려준다. 빈 리스트면 정상."""
    errors = []
    for field, kind in _REQUIRED.items():
        if field not in record:
            errors.append(f"필드 없음: {field}")
        elif not isinstance(record[field], kind):
            errors.append(f"타입 오류: {field} 는 {kind.__name__} 이어야 함")
    return errors
