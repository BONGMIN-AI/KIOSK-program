"""회원카드 신청 · 운영자 승인 · 발급 · 분실 재발급 (11/01).

발급 방식은 **운영자 승인**으로 정했다. 키오스크에는 카드를 내보내는 기계가 없으므로
  ① 손님이 가입할 때(또는 로그인 화면에서) 신청 → ② 운영자 화면에 '승인 대기'로 넘어감
  → ③ 운영자가 '허용'을 누르고 빈 카드를 리더기에 대면 그 카드 번호가 회원에게 할당됨
  → ④ 카운터에서 손님에게 카드를 건넨다.
분실하면 손님이 재발급을 신청하는 순간 예전 카드를 바로 막고(분실 신고), 재발급 수수료(기본 1,000원)는
카운터에서 받는다.

카드 혜택(운영자 정책 값): 카드를 받은 뒤 첫 주문 음료 10% 할인 · 매 주문 적립률 +1%p · 카드만 대면 로그인.
카드 번호(UID)는 회원 카드에 해시로만 저장하고, 화면·기록에는 끝 4자리만 보인다.
"""
from datetime import datetime

from core import schema
from .customers import card_hash, link_card

REQUESTS = "card_requests"
KINDS = {"new": "신규 발급", "reissue": "분실 재발급"}
STATUS = {"waiting": "승인 대기", "approved": "카드 찍기 대기", "issued": "발급 완료", "rejected": "거절"}
OPEN = ("waiting", "approved")

CARD_DEFAULTS = {"card_first_discount": 10, "card_bonus_rate": 1.0, "card_reissue_fee": 1000}


def has_card(customer: dict | None) -> bool:
    return bool(customer and customer["extra"].get("card_hash"))


def requests_of(vault) -> dict:
    return vault.read(REQUESTS, default={})


def open_request(vault, customer_id: str) -> dict | None:
    """이 회원의 처리 중인 신청 (승인 대기·카드 찍기 대기). 없으면 None."""
    return next((r for r in requests_of(vault).values()
                 if r["customer_id"] == customer_id and r["status"] in OPEN), None)


def _save_request(vault, request: dict) -> None:
    requests = requests_of(vault)
    requests[request["id"]] = request
    vault.write(REQUESTS, requests)


def request_card(vault, customer_id: str, kind: str = "new", policy: dict | None = None,
                 now: datetime | None = None) -> dict:
    """회원카드를 신청한다. kind='reissue'(분실)이면 예전 카드를 바로 막고 수수료를 붙인다."""
    if kind not in KINDS:
        raise ValueError(f"없는 신청 종류입니다: {kind}")
    customers = vault.read("customers", default={})
    if customer_id not in customers:
        raise ValueError("회원을 찾을 수 없어요")
    record = customers[customer_id]
    pending = open_request(vault, customer_id)
    if pending:
        raise ValueError(f"이미 신청한 회원카드가 있어요 ({STATUS[pending['status']]}) · 카운터에 물어봐 주세요")
    if kind == "new" and has_card(record):
        raise ValueError("이미 회원카드가 있어요. 잃어버렸으면 분실 재발급을 신청해 주세요")
    if kind == "reissue" and not (has_card(record) or record["extra"].get("card_issued_at")):
        raise ValueError("발급받은 회원카드가 없어요. 먼저 회원카드를 신청해 주세요")
    policy = {**CARD_DEFAULTS, **(policy or {})}
    now = now or datetime.now()
    if kind == "reissue" and has_card(record):          # 분실 신고: 예전 카드는 지금부터 못 쓴다
        record["extra"].setdefault("lost_card_hashes", []).append(record["extra"].pop("card_hash"))
        record["extra"]["card_lost_at"] = now.isoformat(timespec="seconds")
        schema.touch(record)
        vault.write("customers", customers)
    request = {
        "id": schema.next_id("R", requests_of(vault)), "customer_id": customer_id, "kind": kind,
        "fee": policy["card_reissue_fee"] if kind == "reissue" else 0, "status": "waiting",
        "requested_at": now.isoformat(timespec="seconds"), "decided_at": "", "issued_at": "",
        "card_tail": "", "by": "",
    }
    _save_request(vault, request)
    return request


def _get(vault, request_id: str, status: str) -> dict:
    request = requests_of(vault).get(request_id)
    if request is None:
        raise ValueError("신청을 찾을 수 없어요")
    if request["status"] != status:
        raise ValueError(f"지금은 할 수 없어요 · 신청 상태: {STATUS[request['status']]}")
    return request


def approve_request(vault, request_id: str, admin_id: str, now: datetime | None = None) -> dict:
    """운영자 '허용'. 다음은 빈 카드를 리더기에 대서 issue_card."""
    request = _get(vault, request_id, "waiting")
    request.update(status="approved", decided_at=(now or datetime.now()).isoformat(timespec="seconds"),
                   by=admin_id)
    _save_request(vault, request)
    return request


def reject_request(vault, request_id: str, admin_id: str, now: datetime | None = None) -> dict:
    request = requests_of(vault).get(request_id)
    if request is None or request["status"] not in OPEN:
        raise ValueError("처리 중인 신청만 거절할 수 있어요")
    request.update(status="rejected", decided_at=(now or datetime.now()).isoformat(timespec="seconds"),
                   by=admin_id)
    _save_request(vault, request)
    return request


def issue_card(vault, request_id: str, card_uid: str, admin_id: str, now: datetime | None = None) -> dict:
    """허용된 신청에 빈 카드를 할당한다. 이미 누가 쓰거나 분실 신고된 카드는 거절."""
    request = _get(vault, request_id, "approved")
    digest = card_hash(card_uid)
    customers = vault.read("customers", default={})
    if any(digest in record["extra"].get("lost_card_hashes", []) for record in customers.values()):
        raise ValueError("분실 신고된 카드예요. 다른 빈 카드를 대 주세요")
    link_card(vault, request["customer_id"], card_uid)    # 다른 회원 카드면 여기서 ValueError
    now = now or datetime.now()
    customers = vault.read("customers", default={})
    record = customers[request["customer_id"]]
    record["extra"]["card_issued_at"] = now.isoformat(timespec="seconds")
    if request["kind"] == "new":
        record["extra"]["card_first_discount"] = True   # 카드 받은 뒤 첫 주문 할인
    schema.touch(record)
    vault.write("customers", customers)
    request.update(status="issued", issued_at=now.isoformat(timespec="seconds"),
                   card_tail=card_uid.strip().upper()[-4:], by=admin_id)
    _save_request(vault, request)
    return request


def is_lost_card(vault, card_uid: str) -> bool:
    digest = card_hash(card_uid)
    return any(digest in record["extra"].get("lost_card_hashes", [])
               for record in vault.read("customers", default={}).values())


def card_status_text(vault, customer: dict) -> str:
    """회원에게 보여 줄 한 줄: 카드 없음 / 승인 대기 / 카운터에서 받기 / 사용 중."""
    pending = open_request(vault, customer["id"])
    if pending and pending["status"] == "waiting":
        return "회원카드 승인 대기 중"
    if pending:
        return "회원카드 발급 중 · 카운터에서 받아 가세요"
    if has_card(customer):
        return "회원카드 사용 중"
    return ""


def first_card_discount(customer: dict | None, total: int, policy: dict | None = None) -> int:
    """카드 받은 뒤 첫 주문 할인 (10원 단위 버림). 해당 없으면 0."""
    if not has_card(customer) or not customer["extra"].get("card_first_discount"):
        return 0
    percent = {**CARD_DEFAULTS, **(policy or {})}["card_first_discount"]
    return total * percent // 100 // 10 * 10
