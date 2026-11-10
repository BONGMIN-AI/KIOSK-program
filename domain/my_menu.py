"""My Menu 탭 (핵심 기능): 평소 주문(Quick Order) · 좋아요 음료 · 카페인 리포트.

모두 회원의 지난 주문(orders)과 회원 카드만 읽어서 계산한다. 화면은 이 함수들의 결과만 보여 준다.
"""
from datetime import date, datetime, timedelta

from core import schema
from .options import line_key
from .titles import customer_lines

SHOT_CAFFEINE_MG = 75      # 샷 1회 추가
LARGE_SIZE_RATE = 1.3      # L 사이즈는 기본(M)의 1.3배
WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"]


def week_start(day: date) -> date:
    """일요일부터 시작하는 달력 한 주의 첫날."""
    return day - timedelta(days=(day.weekday() + 1) % 7)


# ---------------------------------------------------------------- 평소 주문
def usual_order(orders: dict, customer_id: str, menu: dict) -> dict | None:
    """가장 자주 시킨 메뉴+옵션 한 가지. 횟수가 같으면 더 최근 것. 주문이 없으면 None."""
    counts, last_seen = {}, {}
    for index, lines in enumerate(customer_lines(orders, customer_id)):
        for line in lines:
            if line["menu_id"] not in menu or menu[line["menu_id"]].get("hidden"):
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
        kept = [_repeat_line(line, menu) for line in lines
                if line.get("menu_id") in menu and not menu[line["menu_id"]].get("hidden")]
        if kept:
            return {"lines": kept, "count": sum(line["quantity"] for line in kept)}
    return None


def option_habit(orders: dict, customer_id: str, menu_id: str) -> dict | None:
    """옵션 습관 (M3, 11/01): 이 회원이 이 메뉴에서 가장 많이 고른 옵션 묶음. 같으면 더 최근 것.

    옵션 창을 열 때 미리 골라 둔다. 이 메뉴를 산 적이 없거나 옵션이 없는 메뉴면 None.
    """
    counts, last_seen = {}, {}
    for index, lines in enumerate(customer_lines(orders, customer_id)):
        for line in lines:
            options = line.get("options") or {}
            if line.get("menu_id") != menu_id or not options:
                continue
            key = line_key(menu_id, options)
            counts[key] = counts.get(key, 0) + line["quantity"]
            last_seen[key] = (index, options)
    if not counts:
        return None
    best = max(counts, key=lambda key: (counts[key], last_seen[key][0]))
    return dict(last_seen[best][1])


# ---------------------------------------------------------------- 좋아요
def likes_of(customer: dict) -> list[str]:
    return list(customer["extra"].get("likes", []))


MAX_LIKES = 6                  # My Menu '좋아요한 음료' 칸에 다 보이는 만큼 (11/03)


def toggle_like(vault, customer_id: str, menu_id: str) -> bool:
    """좋아요를 켜거나 끈다. 켜졌으면 True. 이미 6잔이면 더 켜지 않고 ValueError."""
    customers = vault.read("customers", default={})
    if customer_id not in customers:
        raise ValueError("회원을 찾을 수 없습니다")
    if menu_id not in vault.read("menu", default={}):
        raise ValueError(f"없는 메뉴입니다: {menu_id}")
    record = customers[customer_id]
    likes = likes_of(record)
    liked = menu_id not in likes
    if liked and len(likes) >= MAX_LIKES:
        raise ValueError(f"즐겨찾기는 최대 {MAX_LIKES}잔만 가능해요\n다른 음료의 ♥를 먼저 풀어 주세요")
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


def caffeine_by_day(orders: dict, customer_id: str, menu: dict) -> dict:
    """{날짜: 그날 마신 카페인(mg)} — 이 회원의 모든 주문."""
    days = {}
    for order in orders.values():
        if (order.get("customer") or {}).get("id") != customer_id:
            continue
        day = datetime.fromisoformat(order["created_at"]).date()
        for line in order["lines"]:
            item = menu.get(line["menu_id"])
            if item:
                days[day] = days.get(day, 0) + caffeine_of(item, line.get("options"), line["quantity"])
    return days


def daily_caffeine(orders: dict, customer_id: str, menu: dict, start: date) -> list[int]:
    """start부터 7일 동안 날마다 마신 카페인(mg)."""
    days = caffeine_by_day(orders, customer_id, menu)
    return [days.get(start + timedelta(days=index), 0) for index in range(7)]


def caffeine_report(orders: dict, customer_id: str, menu: dict, today: date | None = None) -> dict:
    """이번 주(일~토) 요일별 카페인과 가장 많이 마신 요일 한 줄."""
    today = today or date.today()
    sunday = week_start(today)
    this_week = daily_caffeine(orders, customer_id, menu, sunday)
    last_week = daily_caffeine(orders, customer_id, menu, sunday - timedelta(days=7))
    total, last_total = sum(this_week), sum(last_week)
    change = None if last_total == 0 else round((total - last_total) / last_total * 100)
    today_index = (today.weekday() + 1) % 7
    days_so_far = this_week[: today_index + 1]
    if total == 0:
        message = "이번 주 카페인 기록이 아직 없어요"
    else:
        top = this_week.index(max(this_week))
        message = f"{WEEKDAYS[top]}요일에 가장 많은 카페인을 섭취했어요!"
    suggest_decaf = bool(this_week[today_index]) or (total > 0 and all(days_so_far))
    return {"days": WEEKDAYS, "this_week": this_week, "total": total, "last_week_total": last_total,
            "change_percent": change, "message": message, "suggest_decaf": suggest_decaf}


TREND_VIEWS = ("이번 주", "주별", "월별")


def caffeine_trend(orders: dict, customer_id: str, menu: dict, view: str, today: date | None = None) -> dict:
    """그래프 한 장: {labels, values, current(강조할 칸)}. 주별은 최근 8주, 월별은 최근 6개월."""
    today = today or date.today()
    sunday = week_start(today)
    days = caffeine_by_day(orders, customer_id, menu)
    if view == "이번 주":
        return {"labels": WEEKDAYS, "values": daily_caffeine(orders, customer_id, menu, sunday),
                "current": (today.weekday() + 1) % 7}
    if view == "주별":
        sundays = [sunday - timedelta(weeks=back) for back in range(7, -1, -1)]
        values = [sum(days.get(start + timedelta(days=i), 0) for i in range(7)) for start in sundays]
        labels = []
        for index, start in enumerate(sundays):
            first_day = date(start.year, start.month, 1)
            first_sunday = first_day + timedelta(days=(6 - first_day.weekday()) % 7)
            ordinal = 1 + (start - first_sunday).days // 7
            month_changed = index == 0 or (start.year, start.month) != (sundays[index - 1].year, sundays[index - 1].month)
            labels.append(f"{start.month}월/{ordinal}주" if month_changed else f"{ordinal}주")
        return {"labels": labels, "values": values, "current": 7}
    if view == "월별":
        months = []
        year, month = today.year, today.month
        for _ in range(6):
            months.insert(0, (year, month))
            year, month = (year, month - 1) if month > 1 else (year - 1, 12)
        values = [sum(mg for day, mg in days.items() if (day.year, day.month) == key) for key in months]
        return {"labels": [f"{month}월" for _, month in months], "values": values, "current": 5}
    raise ValueError(f"없는 보기입니다: {view}")


# ---------------------------------------------------------------- 카페인 알리미 (10/31)
LIMIT_UNITS = ("잔", "mg")


def caffeine_limit(customer: dict) -> dict | None:
    """회원이 정한 이번 주 제한 {unit: '잔'|'mg', amount}. 없으면 None."""
    return customer["extra"].get("caffeine_limit")


def set_caffeine_limit(vault, customer_id: str, unit: str | None, amount: int = 0) -> None:
    """제한을 저장한다. unit이 None이거나 amount가 0이면 알리미를 끈다."""
    customers = vault.read("customers", default={})
    if customer_id not in customers:
        raise ValueError("회원을 찾을 수 없습니다")
    record = customers[customer_id]
    if unit is None or amount <= 0:
        record["extra"].pop("caffeine_limit", None)
    elif unit not in LIMIT_UNITS:
        raise ValueError(f"없는 단위입니다: {unit}")
    else:
        record["extra"]["caffeine_limit"] = {"unit": unit, "amount": int(amount)}
    schema.touch(record)
    vault.write("customers", customers)


def lines_caffeine(lines: list[dict], menu: dict) -> dict:
    """주문 줄들의 카페인 {'mg': 합, '잔': 카페인이 든 잔 수}."""
    used = {"mg": 0, "잔": 0}
    for line in lines:
        item = menu.get(line["menu_id"])
        if not item:
            continue
        mg = caffeine_of(item, line.get("options"), line["quantity"])
        used["mg"] += mg
        used["잔"] += line["quantity"] if mg else 0
    return used


def week_caffeine(orders: dict, customer_id: str, menu: dict, today: date | None = None) -> dict:
    """이번 주(일요일부터) 이미 마신 카페인 {'mg', '잔'}."""
    today = today or date.today()
    sunday = week_start(today)
    lines = []
    for order in orders.values():
        if (order.get("customer") or {}).get("id") != customer_id:
            continue
        if sunday <= datetime.fromisoformat(order["created_at"]).date() <= today:
            lines.extend(order["lines"])
    return lines_caffeine(lines, menu)


def limit_warning(limit: dict | None, used: dict, adding: dict) -> str | None:
    """담으면 제한을 넘을 때 손님에게 보여 줄 문구. 안 넘거나 카페인이 없으면 None."""
    if not limit or adding["mg"] == 0:
        return None
    unit, amount = limit["unit"], limit["amount"]
    after = used[unit] + adding[unit]
    if after <= amount:
        return None
    return (f"이번 주 카페인 제한 {amount:,}{unit}을 넘어요.\n"
            f"지금까지 {used[unit]:,}{unit} → 담으면 {after:,}{unit}")
