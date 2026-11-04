"""쿠폰 관리 (11/02 B10): 쿠폰 종류 만들기 · 회원에게 발급 · 발급/사용 내역.

쿠폰 종류는 settings["coupon_templates"], 발급 기록은 coupon_log 데이터셋에 둔다.
발급한 쿠폰은 회원 카드 extra["coupons"]에 들어가고, 06 쿠폰·포인트 화면에서 그대로 쓴다.
생일 쿠폰(E19)·이스터에그 쿠폰(E22)도 여기 종류로 발급한다.
"""
from datetime import date, datetime, timedelta

from core import schema

LOG = "coupon_log"
DEFAULT_TEMPLATES = [
    {"id": "T001", "name": "웰컴 1,000원 할인", "amount": 1000, "min_order": 5000, "days": 30},
    {"id": "T002", "name": "생일 축하 2,000원", "amount": 2000, "min_order": 0, "days": 14},
    {"id": "T003", "name": "이스터에그 100원", "amount": 100, "min_order": 0, "days": 30},
    {"id": "T004", "name": "가입 기념 1,000원", "amount": 1000, "min_order": 0, "days": 14},
    {"id": "T005", "name": "음료 1잔 무료 (5,000원까지)", "amount": 5000, "min_order": 0, "days": 60},
]
BIRTHDAY_TEMPLATE, EASTER_EGG_TEMPLATE, ANNIVERSARY_TEMPLATE = "T002", "T003", "T004"
STAMP_TEMPLATE = "T005"                  # 회원카드 스탬프를 다 모으면 (11/03)


def templates(settings: dict | None) -> list[dict]:
    stored = (settings or {}).get("coupon_templates")
    return [dict(t) for t in (stored if stored is not None else DEFAULT_TEMPLATES)]


def validate_template(raw: dict) -> dict:
    name = (raw.get("name") or "").strip()
    if not name:
        raise ValueError("쿠폰 이름을 입력하세요")
    try:
        amount, min_order, days = (int(str(raw.get(key) or 0).replace(",", "").replace("원", "").strip())
                                   for key in ("amount", "min_order", "days"))
    except ValueError as exc:
        raise ValueError("금액 · 최소 주문 · 유효 일수는 숫자로 입력하세요") from exc
    if not 10 <= amount <= 50000:
        raise ValueError("할인 금액은 10~50,000원 사이로 입력하세요")
    if min_order < 0 or not 1 <= days <= 365:
        raise ValueError("최소 주문은 0원 이상, 유효 일수는 1~365일로 입력하세요")
    return {"name": name, "amount": amount, "min_order": min_order, "days": days}


def add_template(vault, raw: dict) -> dict:
    settings = vault.read("settings", default={})
    items = templates(settings)
    template = {"id": schema.next_id("T", {t["id"]: t for t in items}, width=3), **validate_template(raw)}
    settings["coupon_templates"] = items + [template]
    vault.write("settings", settings)
    return template


def delete_templates(vault, template_ids: list[str]) -> int:
    settings = vault.read("settings", default={})
    items = templates(settings)
    kept = [t for t in items if t["id"] not in template_ids]
    settings["coupon_templates"] = kept
    vault.write("settings", settings)
    return len(items) - len(kept)


def issue(vault, customer_ids: list[str], template_id: str, actor: str, reason: str = "운영자 발급",
          today: date | None = None) -> int:
    """쿠폰 종류 하나를 여러 회원에게 발급한다. 발급한 장 수를 돌려준다."""
    template = next((t for t in templates(vault.read("settings", default={})) if t["id"] == template_id), None)
    if template is None:
        raise ValueError("쿠폰 종류를 찾을 수 없어요")
    today = today or date.today()
    customers = vault.read("customers", default={})
    log = vault.read(LOG, default=[])
    issued = 0
    for customer_id in customer_ids:
        record = customers.get(customer_id)
        if record is None:
            continue
        coupons = record["extra"].setdefault("coupons", [])
        coupon = {"id": f"{template_id}-{customer_id}-{len(log) + issued + 1}", "name": template["name"],
                  "amount": template["amount"], "min_order": template["min_order"],
                  "expires": (today + timedelta(days=template["days"])).isoformat(), "template": template_id}
        coupons.append(coupon)
        schema.touch(record)
        log.append({"at": datetime.now().isoformat(timespec="seconds"), "customer_id": customer_id,
                    "coupon_id": coupon["id"], "name": template["name"], "amount": template["amount"],
                    "expires": coupon["expires"], "by": actor, "reason": reason})
        issued += 1
    vault.write("customers", customers)
    vault.write(LOG, log)
    return issued


def history(vault, today: date | None = None) -> list[dict]:
    """발급 기록 + 지금 상태(미사용 · 사용함 · 기간 지남). 최근 것부터."""
    today = (today or date.today()).isoformat()
    customers = vault.read("customers", default={})
    rows = []
    for entry in reversed(vault.read(LOG, default=[])):
        record = customers.get(entry["customer_id"], {})
        held = {c.get("id") for c in record.get("extra", {}).get("coupons", []) if isinstance(c, dict)}
        if entry["coupon_id"] in held:
            state = "기간 지남" if entry["expires"] < today else "미사용"
        else:
            state = "사용함"
        rows.append({**entry, "nickname": record.get("extra", {}).get("nickname", "?"), "state": state})
    return rows
