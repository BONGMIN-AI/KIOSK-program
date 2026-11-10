"""매출 요약 (11/02 B6): 기간별 매출·주문 수, 많이 팔린 메뉴, 시간대별 주문.

주문 기록(orders)만 읽어서 계산한다. 화면은 결과만 보여 준다.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta

PERIODS = {"오늘": 0, "최근 7일": 6, "최근 30일": 29}
HOURS = range(7, 23)        # 키오스크 운영 시간 (7시~22시)


def _in_period(order: dict, start: date, today: date) -> bool:
    try:
        day = datetime.fromisoformat(order["created_at"]).date()
    except (KeyError, ValueError):
        return False
    return start <= day <= today


def in_period(order: dict, period: str, today: date | None = None) -> bool:
    """매출 요약과 주문 기록에서 같은 날짜 범위를 사용한다."""
    today = today or date.today()
    return _in_period(order, today - timedelta(days=PERIODS[period]), today)


def summary(orders: dict, period: str = "오늘", today: date | None = None) -> dict:
    """{count, total, average, tickets, top: [(이름, 수량, 매출)], hours: [시간대별 주문 수], hour_labels}."""
    today = today or date.today()
    chosen = [order for order in orders.values() if in_period(order, period, today)]
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
    top = sorted(menu_qty, key=lambda name: (-menu_qty[name], -menu_sales[name], name))
    return {
        "count": len(chosen), "total": total, "average": total // len(chosen) if chosen else 0,
        "tickets": sum(t["count"] for order in chosen for t in order.get("tickets", [])),
        "top": [(name, menu_qty[name], menu_sales[name]) for name in top],
        "hours": [hours[hour] for hour in HOURS], "hour_labels": [str(hour) for hour in HOURS],
    }


def category_summary(orders: dict, menu: dict, period: str = "오늘", today: date | None = None) -> list[tuple]:
    """(분류, 판매 수량, 상품 매출). 상품 매출은 쿠폰 할인 전의 품목 소계다."""
    totals = defaultdict(lambda: [0, 0])
    for order in orders.values():
        if not in_period(order, period, today):
            continue
        for line in order.get("lines", []):
            category = menu.get(line.get("menu_id"), {}).get("category", "기타")
            totals[category][0] += line.get("quantity", 0)
            totals[category][1] += line.get("subtotal", 0)
    return sorted(((name, values[0], values[1]) for name, values in totals.items()),
                  key=lambda row: (-row[2], -row[1], row[0]))


def category_menu_summary(orders: dict, menu: dict, category: str, period: str = "오늘",
                          today: date | None = None) -> list[tuple]:
    """선택한 분류 안의 (메뉴명, 판매 수량, 상품 매출), 수량 많은 순."""
    totals = defaultdict(lambda: [0, 0])
    names = {}
    for order in orders.values():
        if not in_period(order, period, today):
            continue
        for line in order.get("lines", []):
            menu_id = line.get("menu_id")
            if menu.get(menu_id, {}).get("category", "기타") != category:
                continue
            key = menu_id or line.get("name")
            names[key] = line.get("name") or menu.get(menu_id, {}).get("name", "메뉴")
            totals[key][0] += line.get("quantity", 0)
            totals[key][1] += line.get("subtotal", 0)
    return sorted(((names[key], qty, amount) for key, (qty, amount) in totals.items()),
                  key=lambda row: (-row[1], -row[2], row[0]))


def hourly_day(orders: dict, day: date) -> dict:
    """선택한 하루의 주문 건수·실결제 매출·시간별 주문 수."""
    hours = {hour: 0 for hour in range(24)}
    count = total = 0
    for order in orders.values():
        try:
            when = datetime.fromisoformat(order["created_at"])
        except (KeyError, TypeError, ValueError):
            continue
        if when.date() != day:
            continue
        count += 1
        total += order.get("final_total", 0)
        if when.hour in hours:
            hours[when.hour] += 1
    return {"count": count, "total": total, "hours": [hours[hour] for hour in range(24)],
            "labels": [f"{hour:02d}" for hour in range(24)]}


def latest_order_day(orders: dict, today: date | None = None) -> date:
    """미래 주문을 제외한 가장 최근 주문 날짜. 기록이 없으면 오늘."""
    today = today or date.today()
    days = [_date(order.get("created_at")) for order in orders.values()]
    return max((day for day in days if day is not None and day <= today), default=today)


def _date(value):
    try:
        return datetime.fromisoformat(value).date()
    except (TypeError, ValueError):
        return None


def trend(orders: dict, customers: dict, card_requests: dict, kind: str,
          today: date | None = None, days: int = 14) -> list[tuple[str, int]]:
    """실제 기록에서 일별 days일(기본 14)·주별 12주·월별 12개월 추이를 만든다."""
    today = today or date.today()
    if kind == "일별 매출":
        dates = [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
        keys = dates
        labels = [f"{day.month}/{day.day}" for day in dates]
        bucket = lambda day: day
        records = ((o.get("created_at"), o.get("final_total", 0)) for o in orders.values())
    elif kind in ("주별 매출", "회원가입 추이", "카드 등록 추이"):
        this_week = today - timedelta(days=today.weekday())
        keys = [this_week - timedelta(weeks=offset) for offset in range(11, -1, -1)]
        labels = [f"{day.month}/{day.day}" for day in keys]
        bucket = lambda day: day - timedelta(days=day.weekday())
        if kind == "회원가입 추이":
            records = ((c.get("created_at"), 1) for c in customers.values())
        elif kind == "카드 등록 추이":
            records = ((r.get("issued_at"), 1) for r in card_requests.values()
                       if r.get("issued_at"))
        else:
            records = ((o.get("created_at"), o.get("final_total", 0)) for o in orders.values())
    elif kind == "월별 매출":
        month = today.year * 12 + today.month - 1
        keys = [divmod(month - offset, 12) for offset in range(11, -1, -1)]
        labels = [f"{year % 100:02d}/{index + 1}" for year, index in keys]
        bucket = lambda day: (day.year, day.month - 1)
        records = ((o.get("created_at"), o.get("final_total", 0)) for o in orders.values())
    else:
        raise ValueError(f"없는 분석 종류입니다: {kind}")
    totals = {key: 0 for key in keys}
    for timestamp, amount in records:
        day = _date(timestamp)
        if day is not None and day <= today:
            key = bucket(day)
            if key in totals:
                totals[key] += amount
    return list(zip(labels, (totals[key] for key in keys)))
