"""매출 요약 (11/02 B6): 기간별 매출·주문 수, 많이 팔린 메뉴, 시간대별 주문.

주문 기록(orders)만 읽어서 계산한다. 화면은 결과만 보여 준다.
"""
from datetime import date, datetime, timedelta

PERIODS = {"오늘": 0, "최근 7일": 6, "최근 30일": 29}
HOURS = range(7, 23)        # 키오스크 운영 시간 (7시~22시)


def _in_period(order: dict, start: date, today: date) -> bool:
    try:
        day = datetime.fromisoformat(order["created_at"]).date()
    except (KeyError, ValueError):
        return False
    return start <= day <= today


def summary(orders: dict, period: str = "오늘", today: date | None = None) -> dict:
    """{count, total, average, tickets, top: [(이름, 잔 수, 매출)], hours: [시간대별 주문 수], hour_labels}."""
    today = today or date.today()
    start = today - timedelta(days=PERIODS[period])
    chosen = [order for order in orders.values() if _in_period(order, start, today)]
    total = sum(order["final_total"] for order in chosen)
    menu_qty, menu_sales = {}, {}
    hours = {hour: 0 for hour in HOURS}
    for order in chosen:
        for line in order["lines"]:
            menu_qty[line["name"]] = menu_qty.get(line["name"], 0) + line["quantity"]
            menu_sales[line["name"]] = menu_sales.get(line["name"], 0) + line.get("subtotal", 0)
        hour = datetime.fromisoformat(order["created_at"]).hour
        if hour in hours:
            hours[hour] += 1
    top = sorted(menu_qty, key=lambda name: (-menu_qty[name], -menu_sales[name], name))[:5]
    return {
        "count": len(chosen), "total": total, "average": total // len(chosen) if chosen else 0,
        "tickets": sum(t["count"] for order in chosen for t in order.get("tickets", [])),
        "top": [(name, menu_qty[name], menu_sales[name]) for name in top],
        "hours": [hours[hour] for hour in HOURS], "hour_labels": [str(hour) for hour in HOURS],
    }
