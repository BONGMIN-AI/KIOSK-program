"""주문 완료와 고객·재고·주문번호 갱신."""
from datetime import datetime

from core import schema
from core.storage import write_together
from .benefits import apply_benefits, coupons_of, make_visit_coupon
from .cart import cart_lines
from .customers import add_point_history
from .payment import change_breakdown, payment_status
from .policy import calculate_points, load_policy
from .titles import customer_lines, update_titles


def complete_order(vault, cart: dict, cash: int, customer_id: str | None = None,
                   coupon_id: str | None = None, use_points: int = 0,
                   now: datetime | None = None, change_to_points: bool = False,
                   also_write: dict | None = None) -> dict:
    """현금이 충분할 때만 주문·재고·회원 카드를 한 번에 저장한다.

    현금이 부족하면 ValueError를 내고 아무것도 바꾸지 않는다.
    적립률·이벤트·방문 쿠폰은 운영자가 정한 settings["point_policy"]를 따른다.
    change_to_points=True이면(회원만) 거스름돈을 현금 대신 포인트로 적립한다(서브 기능 C1).
    주문이 끝나면 칭호 달성도 검사한다(서브 기능 A1).
    also_write({이름: 데이터})는 주문과 같은 묶음으로 함께 저장한다 (예: 키오스크의 투입 현금 기록을 0으로).
    """
    now = now or datetime.now()
    if not cart:
        raise ValueError("장바구니가 비어 있습니다")
    menu = vault.read("menu", default={})
    lines = cart_lines(cart, menu)
    total = sum(line["subtotal"] for line in lines)

    customers = vault.read("customers", default={}) if customer_id else {}
    if customer_id and customer_id not in customers:
        raise ValueError("회원을 찾을 수 없습니다")
    customer = customers.get(customer_id) if customer_id else None
    if change_to_points and customer is None:
        raise ValueError("잔돈 포인트 적립은 회원만 할 수 있습니다")
    settings = vault.read("settings", default=dict(schema.DEFAULT_SETTINGS))
    policy = load_policy(settings)
    benefit = apply_benefits(total, customer, coupon_id, use_points,
                             now.date().isoformat(), policy)

    payment = payment_status(benefit["final_total"], cash)
    if not payment["paid"]:
        raise ValueError(f"현금이 {payment['shortage']:,}원 부족합니다")

    order_number = int(settings.get("next_order_number", 1))
    order_id = f"O{order_number:04d}"
    settings["next_order_number"] = order_number + 1

    for line in lines:
        item = menu[line["menu_id"]]
        item["stock"] -= line["quantity"]
        item["sold_count"] = item.get("sold_count", 0) + line["quantity"]
        item["sold_out"] = item["stock"] == 0

    points = calculate_points(policy, lines, menu, benefit["final_total"], now) if customer else None
    earned_points = points["earned"] if points else 0
    change_points = payment["change"] if change_to_points else 0
    cash_change = payment["change"] - change_points
    customer_snapshot = None
    issued_coupon = None
    new_titles = []
    orders = vault.read("orders", default={})
    if customer:
        extra = customer["extra"]
        coupons = coupons_of(customer)
        if benefit["coupon"]:
            coupons = [c for c in coupons if c["id"] != benefit["coupon"]["id"]]
        extra["points"] = extra["points"] - benefit["points_used"] + earned_points
        if benefit["points_used"]:
            add_point_history(customer, -benefit["points_used"], f"주문 {order_id} 결제에 사용", "system")
        if earned_points:
            note = f"주문 {order_id} 적립"
            if points["events"]:
                note += " (" + ", ".join(points["events"]) + ")"
            add_point_history(customer, earned_points, note, "system")
        if change_points:
            extra["points"] += change_points
            add_point_history(customer, change_points, f"주문 {order_id} 잔돈 적립", "system")
        extra["visits"] += 1
        every = policy["visit_coupon_every"]
        if every and extra["visits"] % every == 0:
            new_coupon = make_visit_coupon(extra["visits"], coupons, policy)
            coupons.append(new_coupon)
            issued_coupon = new_coupon["name"]
        extra["coupons"] = coupons
        history = customer_lines(orders, customer_id) + [lines]
        new_titles = update_titles(customer, history, menu)
        schema.touch(customer)
        customer_snapshot = {
            "id": customer_id,
            "nickname": extra["nickname"],
            "title": extra.get("title", ""),
            "points": extra["points"],
            "visits": extra["visits"],
            "coupon_count": len(coupons),
            "coupon": issued_coupon,
        }

    order = {
        "id": order_id,
        "lines": lines,
        "total": total,
        "coupon_name": benefit["coupon"]["name"] if benefit["coupon"] else None,
        "coupon_discount": benefit["coupon_discount"],
        "points_used": benefit["points_used"],
        "final_total": benefit["final_total"],
        "cash": cash,
        "change": cash_change,
        "change_breakdown": change_breakdown(cash_change),
        "change_points": change_points,
        "earned_points": earned_points,
        "point_events": points["events"] if points else [],
        "issued_coupon": issued_coupon,
        "new_titles": new_titles,
        "customer": customer_snapshot,
        "status": "waiting",
        "created_at": now.isoformat(timespec="seconds"),
    }
    orders[order_id] = order
    # 회원 카드·주문·재고·주문번호를 한 묶음으로 저장한다 (중간에 꺼져도 다음 실행 때 마저 저장됨)
    datasets = {"orders": orders, "menu": menu, "settings": settings}
    if customer:
        datasets["customers"] = customers
    datasets.update(also_write or {})
    write_together(vault, datasets)
    return order
