"""회원 혜택: 쿠폰 발행·사용과 포인트 사용. 와이어프레임 06 화면 규칙을 따른다.

- 쿠폰은 한 주문에 1장, 포인트와 함께 쓸 수 있다.
- 포인트 사용 단위·최소 사용량·최대 사용 비율과 방문 쿠폰 규칙은 운영자가 정한
  정책(domain/policy.py)을 따른다. 정책을 넘기지 않으면 기본값(100P 단위 등)을 쓴다.
- 1P = 1원.
"""
from datetime import date

from .policy import DEFAULT_POLICY, coupon_expiry

POINT_UNIT = DEFAULT_POLICY["point_unit"]
VISIT_COUPON_EVERY = DEFAULT_POLICY["visit_coupon_every"]
VISIT_COUPON_AMOUNT = DEFAULT_POLICY["visit_coupon_amount"]


def normalize_coupon(raw, index: int = 0) -> dict:
    """옛 데이터의 문자열 쿠폰도 1,000원 쿠폰으로 읽는다."""
    if isinstance(raw, str):
        return {"id": f"LEGACY{index + 1}", "name": raw, "amount": VISIT_COUPON_AMOUNT,
                "min_order": 0, "expires": ""}
    return raw


def coupons_of(customer: dict) -> list[dict]:
    return [normalize_coupon(raw, i) for i, raw in enumerate(customer["extra"].get("coupons", []))]


def make_visit_coupon(visits: int, existing: list, policy: dict | None = None) -> dict:
    policy = policy or DEFAULT_POLICY
    amount = policy["visit_coupon_amount"]
    return {
        "id": f"CP{visits:03d}-{len(existing) + 1}",
        "name": f"방문 {visits}회 축하 {amount:,}원 쿠폰",
        "amount": amount,
        "min_order": 0,
        "expires": coupon_expiry(policy),
    }


def apply_benefits(total: int, customer: dict | None, coupon_id: str | None = None,
                   use_points: int = 0, today: str | None = None, policy: dict | None = None) -> dict:
    """할인 계산만 한다. 저장은 orders.complete_order가 한다."""
    policy = policy or DEFAULT_POLICY
    unit, min_use = policy["point_unit"], policy["min_use"]
    if customer is None:
        if coupon_id or use_points:
            raise ValueError("비회원은 쿠폰과 포인트를 사용할 수 없습니다")
        return {"coupon": None, "coupon_discount": 0, "points_used": 0, "final_total": total}

    today = today or date.today().isoformat()
    coupon = None
    coupon_discount = 0
    if coupon_id:
        coupon = next((c for c in coupons_of(customer) if c["id"] == coupon_id), None)
        if coupon is None:
            raise ValueError("사용할 수 없는 쿠폰입니다")
        if coupon.get("expires") and coupon["expires"] < today:
            raise ValueError("유효기간이 지난 쿠폰입니다")
        if total < coupon.get("min_order", 0):
            raise ValueError(f"이 쿠폰은 {coupon['min_order']:,}원 이상 주문부터 쓸 수 있습니다")
        coupon_discount = min(coupon["amount"], total)

    after_coupon = total - coupon_discount
    use_points = int(use_points or 0)
    if use_points < 0:
        raise ValueError("포인트는 0 이상으로 입력하세요")
    if use_points:
        if use_points % unit:
            raise ValueError(f"포인트는 {unit}P 단위로 사용할 수 있습니다")
        if use_points < min_use:
            raise ValueError(f"포인트는 최소 {min_use:,}P부터 사용할 수 있습니다")
        limit = after_coupon * policy["max_use_percent"] // 100
        if use_points > limit:
            raise ValueError(f"포인트는 결제액의 {policy['max_use_percent']}%({limit:,}P)까지 쓸 수 있습니다")
        if use_points > customer["extra"]["points"]:
            raise ValueError(f"보유 포인트({customer['extra']['points']:,}P)보다 많이 쓸 수 없습니다")
        if use_points > after_coupon:
            raise ValueError(f"결제 금액({after_coupon:,}원)보다 많은 포인트는 쓸 수 없습니다")

    return {
        "coupon": coupon,
        "coupon_discount": coupon_discount,
        "points_used": use_points,
        "final_total": after_coupon - use_points,
    }


def max_usable_points(total_after_coupon: int, balance: int, policy: dict | None = None) -> int:
    policy = policy or DEFAULT_POLICY
    limit = min(total_after_coupon * policy["max_use_percent"] // 100, balance)
    limit -= limit % policy["point_unit"]
    return limit if limit >= policy["min_use"] else 0
