"""회원카드 (11/03 바꿈): 장바구니에 담아 음료와 함께 결제 → 음료 나올 때 카드 받기 → 다음 주문 때 처음 대면 등록.

키오스크와 운영자 PC가 서버로 이어져 있지 않아 '운영자 승인'은 시연이 어렵다. 그래서 승인 없이 결제로 받는다.
  ① 가입 · 비밀번호 로그인 때 '회원카드 신청' 체크 → 장바구니에 '회원카드' 한 줄 (음료와 함께 결제)
  ② 결제하면 카드 기록이 '미사용'으로 생긴다. 카드는 음료가 나올 때 같이 받는다 (이때는 카드 번호를 모른다).
  ③ 다음 주문 때 로그인하고 카드를 리더기에 처음 대면 그 번호가 회원에게 등록되고 '사용 중'이 된다.
     그 주문 음료 10% 할인(신규 카드만) · 그때부터 카드 회원 적립률(기본 3%) · 주문마다 스탬프 1개
     (10개면 음료 1잔 무료 쿠폰) · 카드만 대면 로그인.
분실 신고(My Menu 또는 운영자 화면)하면 예전 카드를 바로 막는다. 재발급 카드(500원)는 장바구니로 산다.
카드 번호(UID)는 회원 카드에 해시로만 저장하고, 화면·기록에는 끝 4자리만 보인다.
"""
from datetime import datetime

from core import schema
from . import coupons
from .customers import card_hash, link_card

REQUESTS = "card_requests"          # 카드 기록 (저장 이름은 예전 그대로)
KINDS = {"new": "신규", "reissue": "분실 재발급"}
STATUS = {"unused": "미사용", "issued": "사용 중", "revoked": "등록 해제"}
LIVE = ("unused", "issued")

CARD_DEFAULTS = {"card_price": 1000, "card_first_discount": 10, "card_point_rate": 3.0, "card_stamp_goal": 10,
                 "card_reissue_fee": 500}


def has_card(customer: dict | None) -> bool:
    """카드 번호까지 등록된 회원 (카드 적립 · 카드 로그인)."""
    return bool(customer and customer["extra"].get("card_hash"))


def requests_of(vault) -> dict:
    return vault.read(REQUESTS, default={})


def unused_card(vault, customer_id: str) -> dict | None:
    """결제해서 받았지만 아직 리더기에 대 보지 않은 카드."""
    return next((r for r in requests_of(vault).values()
                 if r["customer_id"] == customer_id and r["status"] == "unused"), None)


def card_price(kind: str, policy: dict | None = None) -> int:
    policy = {**CARD_DEFAULTS, **(policy or {})}
    return policy["card_reissue_fee"] if kind == "reissue" else policy["card_price"]


def card_point_bonus(policy: dict) -> float:
    """카드 회원 적립률(기본 3%)이 되도록 기본 적립률에 더할 %p."""
    policy = {**CARD_DEFAULTS, **policy}
    return max(0.0, float(policy["card_point_rate"]) - float(policy.get("base_rate", 1.0)))


def check_can_buy(vault, customer: dict, kind: str) -> None:
    """장바구니에 카드를 담아도 되는지. 안 되면 ValueError(손님에게 보일 말)."""
    if kind not in KINDS:
        raise ValueError(f"없는 카드 종류입니다: {kind}")
    if unused_card(vault, customer["id"]):
        raise ValueError("받으신 회원카드를 아직 등록하지 않았어요.\n로그인한 뒤 카드를 리더기에 대 주세요")
    extra = customer["extra"]
    if kind == "new" and has_card(customer):
        raise ValueError("이미 회원카드가 있어요. 잃어버렸으면 My Menu에서 분실 신고해 주세요")
    if kind == "new" and extra.get("card_lost_at"):
        raise ValueError("분실 신고한 카드가 있어요.\nMy Menu에서 재발급 카드를 장바구니에 담아 주세요")
    if kind == "reissue" and not lost(customer):
        raise ValueError("분실 신고한 회원카드가 없어요")


def lost(customer: dict) -> bool:
    """분실 신고(또는 운영자 분실 처리)를 해서 지금 쓸 카드가 없는 회원 → 재발급을 살 수 있다."""
    return bool(customer["extra"].get("card_lost_at")) and not has_card(customer)


def report_lost(vault, customer_id: str, now: datetime | None = None) -> dict:
    """분실 신고: 예전 카드를 지금부터 못 쓰게 막는다 (등록 전 카드면 그 기록을 닫는다)."""
    customers = vault.read("customers", default={})
    record = customers.get(customer_id)
    if record is None:
        raise ValueError("회원을 찾을 수 없어요")
    now = now or datetime.now()
    extra = record["extra"]
    if has_card(record):
        extra.setdefault("lost_card_hashes", []).append(extra.pop("card_hash"))
    extra.pop("card_first_discount", None)          # 재발급 카드에는 첫 주문 할인이 없다
    extra["card_lost_at"] = now.isoformat(timespec="seconds")
    schema.touch(record)
    vault.write("customers", customers)
    requests = requests_of(vault)
    for request in requests.values():
        if request["customer_id"] == customer_id and request["status"] in LIVE:
            request.update(status="revoked", decided_at=now.isoformat(timespec="seconds"), by="분실 신고")
    vault.write(REQUESTS, requests)
    return record


def stamp_coupon(settings: dict | None) -> dict | None:
    """스탬프를 다 모으면 주는 음료 무료 쿠폰 종류 (운영자가 쿠폰 화면에서 지웠으면 None)."""
    return next((t for t in coupons.templates(settings) if t["id"] == coupons.STAMP_TEMPLATE), None)


def add_stamp(vault, customer: dict, policy: dict, today=None) -> dict:
    """카드 회원 주문 하나 = 스탬프 1개. 목표를 채우면 음료 무료 쿠폰을 넣고 0부터 다시. (customer는 저장 전 기록)"""
    goal = int({**CARD_DEFAULTS, **policy}["card_stamp_goal"])
    extra = customer["extra"]
    if not goal or not has_card(customer):
        return None                                     # 카드가 없으면 스탬프도 없다 (완료 화면에 안 보임)
    extra["card_stamps"] = extra.get("card_stamps", 0) + 1
    coupon = None
    if extra["card_stamps"] >= goal:
        extra["card_stamps"] -= goal
        coupon = stamp_coupon(vault.read("settings", default={}))
    return {"stamps": extra["card_stamps"], "goal": goal, "coupon": coupon}


def purchase_card(vault, customer_id: str, kind: str, order_id: str, price: int,
                  now: datetime | None = None) -> dict:
    """결제가 끝난 카드: '미사용' 기록을 만든다 (카드는 음료와 함께 받는다)."""
    now = now or datetime.now()
    request = {
        "id": schema.next_id("R", requests_of(vault)), "customer_id": customer_id, "kind": kind,
        "fee": price, "status": "unused", "order_id": order_id,
        "requested_at": now.isoformat(timespec="seconds"), "decided_at": "", "issued_at": "",
        "card_tail": "", "by": "",
    }
    requests = requests_of(vault)
    requests[request["id"]] = request
    vault.write(REQUESTS, requests)
    return request


def register_first_tap(vault, customer_id: str, card_uid: str, now: datetime | None = None) -> dict:
    """받은 카드를 처음 리더기에 댔다: 번호를 회원에게 등록하고 '사용 중'으로. 분실·남의 카드는 거절.

    신규 카드면 이 주문(바로 지금 담고 있는 주문) 음료 10% 할인이 붙는다. 재발급 카드는 할인 없음.
    """
    request = unused_card(vault, customer_id)
    if request is None:
        raise ValueError("등록할 회원카드가 없어요")
    if is_lost_card(vault, card_uid):
        raise ValueError("분실 신고된 카드예요. 받으신 새 카드를 대 주세요")
    link_card(vault, customer_id, card_uid)              # 다른 회원 카드면 여기서 ValueError
    now = now or datetime.now()
    customers = vault.read("customers", default={})
    record = customers[customer_id]
    record["extra"]["card_issued_at"] = now.isoformat(timespec="seconds")
    if request["kind"] == "new":
        record["extra"]["card_first_discount"] = True
    schema.touch(record)
    vault.write("customers", customers)
    requests = requests_of(vault)
    requests[request["id"]].update(status="issued", issued_at=now.isoformat(timespec="seconds"),
                                   card_tail=card_uid.strip().upper()[-4:], by="첫 태그")
    vault.write(REQUESTS, requests)
    return requests[request["id"]]


def unregister_card(vault, request_id: str, admin_id: str, now: datetime | None = None) -> dict:
    """운영자 '등록 해제': 그 카드로는 더 로그인 · 적립할 수 없다 (등록 전 카드도 닫는다)."""
    requests = requests_of(vault)
    request = requests.get(request_id)
    if request is None or request["status"] not in LIVE:
        raise ValueError("미사용 · 사용 중인 카드만 등록 해제할 수 있어요")
    if request["status"] == "issued":
        customers = vault.read("customers", default={})
        record = customers.get(request["customer_id"])
        if record is not None:
            record["extra"].pop("card_hash", None)
            record["extra"].pop("card_first_discount", None)
            schema.touch(record)
            vault.write("customers", customers)
    request.update(status="revoked", decided_at=(now or datetime.now()).isoformat(timespec="seconds"), by=admin_id)
    vault.write(REQUESTS, requests)
    return request


def masked_card(tail: str) -> str:
    """카드 번호는 끝 4자리만: '****D273'."""
    return f"****{tail}" if tail else ""


def is_lost_card(vault, card_uid: str) -> bool:
    digest = card_hash(card_uid)
    return any(digest in record["extra"].get("lost_card_hashes", [])
               for record in vault.read("customers", default={}).values())


def card_status_text(vault, customer: dict) -> str:
    """회원에게 보여 줄 한 줄: 카드 없음('') / 등록 전 / 사용 중."""
    if unused_card(vault, customer["id"]):
        return "회원카드 등록 전"
    if has_card(customer):
        return "회원카드 사용 중"
    return ""


def perks_text(policy: dict | None = None) -> str:
    """회원카드 혜택: '첫 주문 10% 할인 · 매 주문 3% 적립 · 스탬프 10개 = 음료 1잔 무료'."""
    policy = {**CARD_DEFAULTS, **(policy or {})}
    parts = []
    if policy["card_first_discount"]:
        parts.append(f"첫 주문 {policy['card_first_discount']}% 할인")
    parts.append(f"매 주문 {policy['card_point_rate']:g}% 적립")
    if policy["card_stamp_goal"]:
        parts.append(f"스탬프 {policy['card_stamp_goal']}개 = 음료 1잔 무료")
    return " · ".join(parts)


def first_card_discount(customer: dict | None, total: int, policy: dict | None = None) -> int:
    """카드를 등록한 그 주문 할인 (10원 단위 버림). 해당 없으면 0."""
    if not has_card(customer) or not customer["extra"].get("card_first_discount"):
        return 0
    percent = {**CARD_DEFAULTS, **(policy or {})}["card_first_discount"]
    return total * percent // 100 // 10 * 10
