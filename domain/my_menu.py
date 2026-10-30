"""My Menu 탭 (핵심 기능): 평소 주문(Quick Order) · 좋아요 음료 · 카페인 리포트.

모두 회원의 지난 주문(orders)과 회원 카드만 읽어서 계산한다. 화면은 이 함수들의 결과만 보여 준다.
"""
from datetime import date, datetime, timedelta

from core import schema
from .options import line_key
from .titles import customer_lines

SHOT_CAFFEINE_MG = 75      # 샷 1회 추가
LARGE_SIZE_RATE = 1.3      # L 사이즈는 기본(M)의 1.3배
WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


# ---------------------------------------------------------------- 평소 주문
def usual_order(orders: dict, customer_id: str, menu: dict) -> dict | None:
    """가장 자주 시킨 메뉴+옵션 한 가지. 횟수가 같으면 더 최근 것. 주문이 없으면 None."""
    counts, last_seen = {}, {}
    for index, lines in enumerate(customer_lines(orders, customer_id)):
        for line in lines:
            if line["menu_id"] not in menu:
                continue
            key = line_key(line["menu_id"], line.get("options") or {})
            counts[key] = counts.get(key, 0) + line["quantity"]
            last_seen[key] = (index, line)
    if not counts:
        return None
    best = max(counts, key=lambda key: (counts[key], last_seen[key][0]))
    line = last_seen[best][1]
    return {"menu_id": line["menu_id"], "name": menu[line["menu_id"]]["name"],
            "options": line.get("options") or {}, "option_label": line.get("option_label", ""),
            "unit_price": line["unit_price"], "times": counts[best]}


def _repeat_line(line: dict, menu: dict) -> dict:
    return {"menu_id": line["menu_id"], "name": menu[line["menu_id"]]["name"],
            "options": line.get("options") or {}, "option_label": line.get("option_label", ""),
            "quantity": line["quantity"]}


def recent_order(orders: dict, customer_id: str, menu: dict) -> dict | None:
    """가장 최근 주문 한 건의 음료·디저트 줄 전부 (10/31: 평소 주문은 첫 잔만 담겨서 이것으로 바꿨다).

    지금 메뉴에 없는 줄은 뺀다. 주문이 없으면 None.
    """
    for lines in reversed(customer_lines(orders, customer_id)):
        kept = [_repeat_line(line, menu) for line in lines if line.get("menu_id") in menu]
        if kept:
            return {"lines": kept, "count": sum(line["quantity"] for line in kept)}
    return None


# ---------------------------------------------------------------- 좋아요
def likes_of(customer: dict) -> list[str]:
    return list(customer["extra"].get("likes", []))


def toggle_like(vault, customer_id: str, menu_id: str) -> bool:
    """좋아요를 켜거나 끈다. 켜졌으면 True."""
    customers = vault.read("customers", default={})
    if customer_id not in customers:
        raise ValueError("회원을 찾을 수 없습니다")
    if menu_id not in vault.read("menu", default={}):
        raise ValueError(f"없는 메뉴입니다: {menu_id}")
    record = customers[customer_id]
    likes = likes_of(record)
    liked = menu_id not in likes
    if liked:
        likes.append(menu_id)
    else:
        likes.remove(menu_id)
    record["extra"]["likes"] = likes
    schema.touch(record)
    vault.write("customers", customers)
    return liked


# ---------------------------------------------------------------- 카페인 리포트
def caffeine_of(item: dict, options: dict | None, quantity: int = 1) -> int:
    """한 줄의 카페인(mg). 디카페인은 0. L은 1.3배, 샷 추가는 1회 75mg."""
    if item.get("decaf"):
        return 0
    options = options or {}
    amount = item.get("caffeine_mg", 0)
    if options.get("size") == "L":
        amount *= LARGE_SIZE_RATE
    if "shot" in options.get("extras", []):
        amount += SHOT_CAFFEINE_MG
    return round(amount) * quantity


def daily_caffeine(orders: dict, customer_id: str, menu: dict, monday: date) -> list[int]:
    """monday부터 7일 동안 날마다 마신 카페인(mg)."""
    days = [0] * 7
    for order in orders.values():
        if (order.get("customer") or {}).get("id") != customer_id:
            continue
        day = datetime.fromisoformat(order["created_at"]).date()
        index = (day - monday).days
        if 0 <= index < 7:
            for line in order["lines"]:
                item = menu.get(line["menu_id"])
                if item:
                    days[index] += caffeine_of(item, line.get("options"), line["quantity"])
    return days


def caffeine_report(orders: dict, customer_id: str, menu: dict, today: date | None = None) -> dict:
    """이번 주(월~일) 요일별 카페인과 지난주 대비 변화, 화면에 쓸 한 줄 문구."""
    today = today or date.today()
    monday = today - timedelta(days=today.weekday())
    this_week = daily_caffeine(orders, customer_id, menu, monday)
    last_week = daily_caffeine(orders, customer_id, menu, monday - timedelta(days=7))
    total, last_total = sum(this_week), sum(last_week)
    change = None if last_total == 0 else round((total - last_total) / last_total * 100)
    days_so_far = this_week[: today.weekday() + 1]
    if total == 0:
        message = "이번 주 카페인 기록이 아직 없어요"
    elif all(days_so_far):
        message = "이번 주는 매일 카페인을 드셨네요"
    elif change is not None and change > 0:
        message = f"지난주보다 {change}% 더 드셨어요"
    elif change is not None and change < 0:
        message = f"지난주보다 {-change}% 덜 드셨어요"
    else:
        message = f"이번 주 {total:,}mg 드셨어요"
    # 오늘 이미 카페인을 마셨거나, 이번 주 매일 마셨으면 디카페인을 권한다
    suggest_decaf = bool(this_week[today.weekday()]) or (total > 0 and all(days_so_far))
    return {"days": WEEKDAYS, "this_week": this_week, "total": total, "last_week_total": last_total,
            "change_percent": change, "message": message, "suggest_decaf": suggest_decaf}
