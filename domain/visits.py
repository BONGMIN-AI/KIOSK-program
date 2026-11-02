"""회원을 기억하는 인사와 선물 (11/03 E묶음).

- E14 방문 간격 인사: 로그인하면 "3일 만이에요!" · "오늘 두 번째 방문이에요!"
- E19 기념일 · 생일 쿠폰: 생일 주간(앞뒤 3일) · 가입 n주년 주간에 해마다 한 번 쿠폰을 넣어 준다
- E22 이스터에그: 로고를 빠르게 다섯 번 누르면 100원 쿠폰 (회원마다 한 번)
"""
from datetime import date, datetime

from . import coupons

WEEK_DAYS = 3                  # 생일 · 가입일 앞뒤 3일이면 그 주간으로 본다
ORDINALS = {2: "두", 3: "세", 4: "네", 5: "다섯"}


def visit_times(orders: dict, customer_id: str) -> list[str]:
    return sorted(o["created_at"] for o in orders.values() if (o.get("customer") or {}).get("id") == customer_id)


def visit_greeting(orders: dict, customer_id: str, now: datetime | None = None) -> str:
    now = now or datetime.now()
    times = visit_times(orders, customer_id)
    if not times:
        return "첫 주문을 환영해요!"
    today = now.date()
    today_count = sum(t[:10] == today.isoformat() for t in times)
    if today_count:
        nth = today_count + 1
        return f"오늘 {ORDINALS.get(nth, str(nth))} 번째 방문이에요!"
    days = (today - date.fromisoformat(times[-1][:10])).days
    if days == 1:
        return "어제도 와 주셨네요!"
    if days < 30:
        return f"{days}일 만이에요!"
    return f"오랜만이에요! {days}일 만에 오셨어요"


def _this_year(day: date, year: int) -> date:
    try:
        return day.replace(year=year)
    except ValueError:                     # 2월 29일생은 평년에 2월 28일
        return day.replace(year=year, day=28)


def _near(day: date, today: date) -> bool:
    return abs((_this_year(day, today.year) - today).days) <= WEEK_DAYS


def celebrate(vault, customer_id: str, today: date | None = None) -> list[dict]:
    """생일 · 가입 기념 주간이면 쿠폰을 넣고 [{title, text}]를 돌려준다. 같은 해에는 한 번만."""
    today = today or date.today()
    customers = vault.read("customers", default={})
    record = customers.get(customer_id)
    if record is None:
        return []
    extra = record["extra"]
    gifts = []
    birthday = extra.get("birthday") or ""
    if len(birthday) == 10 and extra.get("birthday_coupon_year") != today.year:
        if _near(date.fromisoformat(birthday), today):
            gifts.append(("birthday_coupon_year", coupons.BIRTHDAY_TEMPLATE, "생일 축하해요!"))
    joined = date.fromisoformat(record["created_at"][:10])
    years = today.year - joined.year
    if years >= 1 and extra.get("anniversary_coupon_year") != today.year and _near(joined, today):
        gifts.append(("anniversary_coupon_year", coupons.ANNIVERSARY_TEMPLATE, f"가입 {years}주년이에요!"))
    kinds = {t["id"]: t for t in coupons.templates(vault.read("settings", default={}))}
    result = []
    for flag, template_id, title in gifts:
        kind = kinds.get(template_id)
        if kind is None:                   # 운영자가 그 쿠폰 종류를 지웠으면 주지 않는다
            continue
        coupons.issue(vault, [customer_id], template_id, "자동", reason=title, today=today)
        customers = vault.read("customers")
        customers[customer_id]["extra"][flag] = today.year
        vault.write("customers", customers)
        result.append({"title": title, "text": f"{kind['name']} 쿠폰을 넣어 드렸어요.\n{kind['days']}일 안에 써 주세요."})
    return result


def easter_egg(vault, customer_id: str, today: date | None = None) -> dict | None:
    """숨은 쿠폰 (회원마다 한 번). 이미 받았거나 운영자가 쿠폰 종류를 지웠으면 None."""
    customers = vault.read("customers", default={})
    record = customers.get(customer_id)
    kinds = {t["id"]: t for t in coupons.templates(vault.read("settings", default={}))}
    if record is None or record["extra"].get("easter_egg") or coupons.EASTER_EGG_TEMPLATE not in kinds:
        return None
    coupons.issue(vault, [customer_id], coupons.EASTER_EGG_TEMPLATE, "자동", reason="이스터에그", today=today)
    customers = vault.read("customers")
    customers[customer_id]["extra"]["easter_egg"] = True
    vault.write("customers", customers)
    return kinds[coupons.EASTER_EGG_TEMPLATE]
