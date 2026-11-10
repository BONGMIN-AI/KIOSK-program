"""관리자 매출과 주문 기록의 기간 및 인기 순위를 같은 주문으로 검증한다."""

from collections import Counter
from datetime import date, datetime, timedelta

from domain.sales import in_period, summary


def test_demo_popular_sales_counts_use_order_history():
    from gui.main import demo_vault

    vault = demo_vault(random_members=True)
    orders = vault.read("orders")
    menu = vault.read("menu")
    sold = Counter()
    for order in orders.values():
        for line in order["lines"]:
            sold[line["menu_id"]] += line["quantity"]
    assert all(item["sold_count"] == sold[menu_id] for menu_id, item in menu.items()
               if not item.get("hidden"))


def test_period_boundaries_and_top_menu_match_order_lines():
    today = date(2026, 11, 7)
    orders = {}
    for days, name, quantity, total in ((0, "라떼", 1, 4000), (6, "아메리카노", 2, 6000),
                                        (7, "차", 3, 9000), (29, "쿠키", 1, 3000),
                                        (30, "케이크", 1, 5000)):
        orders[str(days)] = {"created_at": datetime.combine(today - timedelta(days=days),
                                                            datetime.min.time()).isoformat(),
                             "final_total": total, "lines": [{"name": name, "quantity": quantity,
                                                                 "subtotal": total}]}
    for period in ("오늘", "최근 7일", "최근 30일"):
        records = [o for o in orders.values() if in_period(o, period, today)]
        result = summary(orders, period, today)
        quantities = Counter()
        for order in records:
            quantities.update({line["name"]: line["quantity"] for line in order["lines"]})
        assert result["count"] == len(records)
        assert result["total"] == sum(o["final_total"] for o in records)
        assert [(name, qty) for name, qty, _ in result["top"]] == quantities.most_common(5)
    assert summary(orders, "최근 7일", today)["count"] == 2
    assert summary(orders, "최근 30일", today)["count"] == 4
