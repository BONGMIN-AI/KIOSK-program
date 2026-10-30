"""인기 탭 (10/31): 좋아요순 · 판매순 · 이번 계절 인기순.

실제 기록(회원 카드의 좋아요, 주문 기록, 메뉴의 sold_count)에 시연용 기본값(메뉴의 demo_likes,
demo_season)을 더해 순위를 매긴다. 시연 데이터는 domain/seed.py가 만든다. 화면은 결과만 보여 준다.
"""
from datetime import date, datetime

SEASONS = {"봄": (3, 4, 5), "여름": (6, 7, 8), "가을": (9, 10, 11), "겨울": (12, 1, 2)}
SORTS = ("좋아요순", "판매순", "계절 인기순")


def season_of(day: date) -> str:
    return next(name for name, months in SEASONS.items() if day.month in months)


def _drinks_and_desserts(menu: dict) -> list[dict]:
    return [item for item in menu.values() if not item.get("hidden")]


def like_counts(customers: dict, menu: dict) -> dict:
    """메뉴별 좋아요 수 = 회원들이 누른 ♥ + 시연용 기본값."""
    counts = {menu_id: item.get("demo_likes", 0) for menu_id, item in menu.items()}
    for customer in customers.values():
        for menu_id in customer.get("extra", {}).get("likes", []):
            if menu_id in counts:
                counts[menu_id] += 1
    return counts


def season_counts(orders: dict, menu: dict, season: str) -> dict:
    """이번 계절(올해·지난해 모두)에 팔린 잔 수 + 시연용 기본값."""
    counts = {menu_id: item.get("demo_season", {}).get(season, 0) for menu_id, item in menu.items()}
    months = SEASONS[season]
    for order in orders.values():
        try:
            month = datetime.fromisoformat(order["created_at"]).month
        except (KeyError, ValueError):
            continue
        if month not in months:
            continue
        for line in order.get("lines", []):
            if line.get("menu_id") in counts:
                counts[line["menu_id"]] += line.get("quantity", 0)
    return counts


def ranking(sort: str, menu: dict, customers: dict, orders: dict, today: date | None = None,
            limit: int = 9) -> list[dict]:
    """[{item, value, text}] 많은 순. 같으면 메뉴 번호 순. 값이 0인 메뉴는 뺀다."""
    if sort == "좋아요순":
        counts = like_counts(customers, menu)
        text = lambda value: f"♥ {value:,}"
    elif sort == "판매순":
        counts = {menu_id: item.get("sold_count", 0) for menu_id, item in menu.items()}
        text = lambda value: f"누적 {value:,}잔"
    elif sort == "계절 인기순":
        season = season_of(today or date.today())
        counts = season_counts(orders, menu, season)
        text = lambda value: f"{season} {value:,}잔"
    else:
        raise ValueError(f"없는 정렬입니다: {sort}")
    items = [item for item in _drinks_and_desserts(menu) if counts.get(item["id"], 0) > 0]
    items.sort(key=lambda item: (-counts[item["id"]], item["id"]))
    return [{"item": item, "value": counts[item["id"]], "text": text(counts[item["id"]])} for item in items[:limit]]
