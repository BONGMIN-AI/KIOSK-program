"""달성과제·칭호 (서브 기능 A1).

회원의 지난 주문(orders)을 세어 조건을 넘으면 칭호를 준다.
칭호는 회원 카드 extra["titles"](받은 순서)에 쌓이고, 가장 최근 칭호가 대표 칭호(extra["title"])가 된다.
대표 칭호는 My Menu·영수증·대기 화면에 [칭호] 닉네임으로 나온다.
"""

# (칭호, 설명, 세는 방법, 목표 수) — 세는 방법은 count_stats()가 만드는 이름
TITLES = [
    ("새내기", "첫 주문 완료", "orders", 1),
    ("아아수호자", "ICE 아메리카노 10잔", "ice_americano", 10),
    ("라떼 장인", "라떼 메뉴 10잔", "latte", 10),
    ("디카페인 지킴이", "디카페인 메뉴 5잔", "decaf", 5),
    ("딸기 완주자", "딸기 메뉴 5잔", "strawberry", 5),
    ("신메뉴 헌터", "서로 다른 메뉴 10가지", "kinds", 10),
    ("단골손님", "주문 10번", "orders", 10),
]


def customer_lines(orders: dict, customer_id: str) -> list[list[dict]]:
    """회원의 주문들을 주문 하나당 줄 목록으로 돌려준다(오래된 순)."""
    mine = [o for o in orders.values() if (o.get("customer") or {}).get("id") == customer_id]
    mine.sort(key=lambda order: order["created_at"])
    return [order["lines"] for order in mine]


def count_stats(order_lines: list[list[dict]], menu: dict) -> dict:
    stats = {"orders": len(order_lines), "ice_americano": 0, "latte": 0, "decaf": 0,
             "strawberry": 0, "kinds": 0}
    kinds = set()
    for lines in order_lines:
        for line in lines:
            item = menu.get(line["menu_id"], {})
            name = line.get("name") or item.get("name", "")
            quantity = line["quantity"]
            kinds.add(line["menu_id"])
            options = line.get("options") or {}
            if name == "아메리카노" and options.get("temperature") == "ICE":
                stats["ice_americano"] += quantity
            if "라떼" in name:
                stats["latte"] += quantity
            if item.get("decaf"):
                stats["decaf"] += quantity
            if "딸기" in name:
                stats["strawberry"] += quantity
    stats["kinds"] = len(kinds)
    return stats


def earned_titles(stats: dict) -> list[str]:
    return [name for name, _, key, goal in TITLES if stats.get(key, 0) >= goal]


def progress(stats: dict) -> list[dict]:
    """My Menu에 보여 줄 달성 현황: 칭호마다 지금 수 / 목표 수."""
    return [{"title": name, "description": desc, "count": min(stats.get(key, 0), goal), "goal": goal,
             "done": stats.get(key, 0) >= goal} for name, desc, key, goal in TITLES]


def update_titles(customer: dict, order_lines: list[list[dict]], menu: dict) -> list[str]:
    """새로 받은 칭호를 회원 카드에 더하고, 새 칭호 목록을 돌려준다."""
    extra = customer["extra"]
    have = list(extra.get("titles", []))
    new = [name for name in earned_titles(count_stats(order_lines, menu)) if name not in have]
    if new:
        extra["titles"] = have + new
        extra["title"] = new[-1]
    return new
