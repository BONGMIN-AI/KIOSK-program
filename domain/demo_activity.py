"""메모리 시연 모드 전용 주문 및 재고 표본."""

import random
from collections import Counter
from datetime import datetime, time, timedelta

from .random_members import _line, _pick_options


# 시연 승차권: (도착지, 어른 요금). 실제 노선표(domain.tickets.DESTINATIONS)에서 몇 곳만 쓴다.
DEMO_ROUTES = (("대전복합", 13700), ("천안", 9200), ("청주", 11700), ("세종", 12600), ("전주", 20800), ("부산", 39400))


def _daily_count(rng, days_ago: int) -> int:
    """하루 주문 수: 최근 30일 약 10건, 3개월 안 약 4건, 그보다 전은 0~3건 (오늘만 튀지 않게 고르게)."""
    base = 10 if days_ago < 30 else 4 if days_ago < 90 else 1.5
    return max(0, round(rng.gauss(base, base * 0.3)))


def _demo_ticket(rng, when: datetime) -> dict:
    """주문 기록에 남는 승차권 한 묶음 (예매 내역과 같은 글자 · 숫자 구조)."""
    destination, fare = rng.choice(DEMO_ROUTES)
    count = rng.choices([1, 2], weights=[7, 3])[0]
    depart = (when + timedelta(minutes=rng.randrange(30, 180, 10))).isoformat(timespec="minutes")
    passengers = [{"seat": rng.randint(1, 28), "type": "어른", "benefit": "없음", "price": fare}
                  for _ in range(count)]
    return {"hold_id": "", "bus_id": "", "origin": "서울경부", "destination": destination, "depart": depart,
            "grade": "우등", "company": "시연고속", "platform": rng.randint(1, 12),
            "passengers": passengers, "count": count, "total": fare * count}


def add_demo_activity(vault, now: datetime | None = None, seed: int = 1107, days: int = 330) -> None:
    """비회원 주문을 약 11개월에 걸쳐 고르게 추가하고(일부는 승차권 포함) 재고 상태를 다양하게 만든다."""
    rng = random.Random(seed)
    now = now or datetime.now()
    menu = vault.read("menu", default={})
    orders = vault.read("orders", default={})
    available = [item for item in menu.values() if not item.get("hidden")]
    regular = [item for item in available if not item.get("season")]
    if not available:
        return

    made = []
    for days_ago in range(days, -1, -1):
        day = (now - timedelta(days=days_ago)).date()
        for _ in range(_daily_count(rng, days_ago)):
            # 시연 모드는 당일 전체 영업시간을 가상으로 채워 시간대 그래프를 보여 준다.
            hour = rng.choices(range(8, 22), weights=[2, 3, 5, 7, 8, 7, 5, 5, 6, 7, 8, 6, 4, 2])[0]
            when = datetime.combine(day, time(hour, rng.randrange(60), rng.randrange(60)))
            lines = []
            pool = regular if days_ago > 60 and regular else available
            for item in rng.sample(pool, k=min(rng.choices([1, 2, 3], weights=[5, 4, 1])[0], len(pool))):
                options = _pick_options(rng, item, 0.55, 0.25, 0.08)
                lines.append(_line(item, options, rng.choices([1, 2], weights=[8, 2])[0]))
            tickets = [_demo_ticket(rng, when)] if days_ago < 90 and rng.random() < 0.12 else []
            made.append((when, lines, tickets))

    made.sort(key=lambda row: row[0])                  # 주문번호가 시간 순서를 따르게
    for index, (when, lines, tickets) in enumerate(made):
        total = sum(line["subtotal"] for line in lines)
        ticket_total = sum(t["total"] for t in tickets)
        order_id = f"D{index + 1:04d}"
        orders[order_id] = {
            "id": order_id, "lines": lines, "total": total + ticket_total, "coupon_name": None,
            "coupon_discount": 0, "points_used": 0, "final_total": total + ticket_total,
            "tickets": tickets, "ticket_total": ticket_total, "cash": total + ticket_total, "change": 0,
            "change_breakdown": {}, "change_points": 0, "eco_points": 0,
            "earned_points": 0, "point_events": [], "issued_coupon": None,
            "new_titles": [], "customer": None, "status": "done",
            "created_at": when.isoformat(timespec="seconds"),
        }

    sold = Counter()
    for order in orders.values():
        for line in order.get("lines", []):
            sold[line.get("menu_id")] += line.get("quantity", 0)
    for index, item in enumerate(menu.values()):
        if item.get("hidden"):
            continue
        item["stock"] = rng.randint(2, 4) if index % 7 == 0 else rng.randint(8, 42)
        item["sold_out"] = item["stock"] == 0
        # 판매순과 계절 인기순도 같은 주문 기록을 근거로 표시한다.
        item["sold_count"] = sold[item["id"]]
        item["demo_season"] = {}
    vault.write("orders", orders)
    vault.write("menu", menu)
