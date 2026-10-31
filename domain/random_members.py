"""시연용 무작위 회원 (11/01): 알레르기·포인트·쿠폰·좋아요·카페인 제한·주문 습관이 서로 다른 회원 여러 명.

같은 seed면 언제나 같은 회원이 만들어진다(시연·캡처가 매번 같게). 주문 기록은 지난 8주 안에 흩어 두어
칭호·카페인 그래프·인기 탭·옵션 습관·최근 주문이 회원마다 다르게 보인다.
주문 번호(대기 번호)는 건드리지 않도록 지난 주문은 'H'로 시작하는 번호를 쓴다.
연습용이라 비밀번호는 모두 1234이고 해시 하나를 같이 쓴다 (만들기 빠르게).
"""
import random
from datetime import datetime, timedelta

from core import schema
from .allergens import ALLERGENS
from .customers import hash_member_password
from .options import available_options, option_label, option_price
from .titles import update_titles

SURNAMES = "김이박최정강조윤장임한오서신권황안송류홍"
GIVEN = ["민준", "서연", "도윤", "하은", "시우", "지유", "예준", "수아", "주원", "지민", "하준", "채원",
         "지호", "서윤", "준우", "다은", "현우", "예린", "건우", "소율"]
NICKNAMES = ["아침형인간", "카공족", "라떼러버", "디카페인생활", "딸기덕후", "출근길한잔", "야근요정", "말차매니아",
             "단골예정", "달달구리", "산책러", "버스여행자", "에이드파", "케이크헌터", "차분한차", "샷추가왕"]

# 손님 유형: (이름, 자주 고르는 메뉴, ICE 비율, L 비율, 샷 추가 비율)
PROFILES = [
    ("얼죽아", ["M001", "M001", "M001", "M007"], 0.95, 0.6, 0.3),
    ("라떼파", ["M002", "M003", "M009", "M008", "M006"], 0.5, 0.4, 0.1),
    ("디카페인", ["M051", "M052", "M053", "M024", "M029"], 0.4, 0.2, 0.0),
    ("달콤파", ["M012", "M011", "M005", "M006", "M045", "M049"], 0.6, 0.3, 0.0),
    ("차·에이드", ["M021", "M022", "M031", "M033", "M030", "M026"], 0.7, 0.3, 0.0),
    ("골고루", ["M001", "M002", "M014", "M015", "M031", "M041", "M044", "M047", "M013", "M018"], 0.5, 0.3, 0.1),
]


def _pick_options(rng: random.Random, item: dict, ice_rate: float, large_rate: float, shot_rate: float) -> dict:
    rules = available_options(item)
    if not rules["temperatures"]:
        return {}
    temps = rules["temperatures"]
    temperature = "ICE" if "ICE" in temps and rng.random() < ice_rate else temps[0]
    size = "L" if "L" in rules["sizes"] and rng.random() < large_rate else rules["sizes"][0]
    extras = ["shot"] if "shot" in rules["extras"] and rng.random() < shot_rate else []
    return {"temperature": temperature, "size": size, "extras": extras}


def _line(item: dict, options: dict, quantity: int) -> dict:
    unit = item["price"] + (option_price(options) if options else 0)
    return {"key": f"{item['id']}|{option_label(options)}", "menu_id": item["id"], "name": item["name"],
            "options": options, "option_label": option_label(options) if options else "",
            "quantity": quantity, "unit_price": unit, "subtotal": unit * quantity}


def make_random_members(vault, count: int = 16, seed: int = 1101, now: datetime | None = None) -> list[str]:
    """회원 count명과 그들의 지난 주문을 금고에 더한다. 만든 회원 번호 목록을 돌려준다."""
    rng = random.Random(seed)
    now = now or datetime.now()
    menu = vault.read("menu", default={})
    customers = vault.read("customers", default={})
    orders = vault.read("orders", default={})
    password = hash_member_password("1234")
    made = []
    history_number = 1
    for index in range(count):
        customer_id = f"C{101 + index:04d}"
        profile = PROFILES[index % len(PROFILES)]
        _, favorites, ice_rate, large_rate, shot_rate = profile
        favorites = [menu_id for menu_id in favorites if menu_id in menu]
        allergies = rng.sample(ALLERGENS, rng.choice([0, 0, 1, 1, 2]))
        coupons = [{"id": f"RND{index:02d}{n}", "name": f"{amount:,}원 할인 쿠폰", "amount": amount,
                    "min_order": amount * 5, "expires": "2026-12-31"}
                   for n, amount in enumerate(rng.sample([500, 1000, 2000], rng.choice([0, 0, 1, 2])))]
        extra = {
            "nickname": NICKNAMES[index % len(NICKNAMES)], "login_id": f"user{index + 1:02d}",
            "password_hash": password, "birthday": f"{rng.randint(1975, 2007)}-{rng.randint(1, 12):02d}-"
                                                  f"{rng.randint(1, 28):02d}",
            "allergies": allergies, "privacy_agreed": True, "marketing_agreed": rng.random() < 0.4,
            "face_enrolled": False, "points": rng.randrange(0, 5001, 100), "coupons": coupons, "visits": 0,
            "likes": rng.sample(sorted(set(favorites)), min(len(set(favorites)), rng.randint(0, 3))),
            "random_profile": profile[0],
        }
        if rng.random() < 0.35:
            extra["caffeine_limit"] = rng.choice([{"unit": "잔", "amount": rng.randint(3, 10)},
                                                  {"unit": "mg", "amount": rng.randrange(300, 901, 50)}])
        record = schema.new_record(customer_id, f"{rng.choice(SURNAMES)}{rng.choice(GIVEN)}",
                                   f"010-{rng.randint(2000, 9999)}-{rng.randint(1000, 9999)}", **extra)
        # 지난 8주 동안 주문 1~14번 (최근일수록 조금 더 자주)
        history = []
        for _ in range(rng.randint(1, 14)):
            when = now - timedelta(days=int(rng.triangular(0, 56, 3)), hours=rng.randint(0, 9),
                                   minutes=rng.randint(0, 59))
            lines = []
            for _ in range(rng.choice([1, 1, 1, 2, 2, 3])):
                item = menu[rng.choice(favorites)]
                lines.append(_line(item, _pick_options(rng, item, ice_rate, large_rate, shot_rate),
                                   rng.choice([1, 1, 1, 2])))
            history.append((when, lines))
        history.sort(key=lambda pair: pair[0])
        for when, lines in history:
            total = sum(line["subtotal"] for line in lines)
            order_id = f"H{history_number:04d}"
            history_number += 1
            orders[order_id] = {
                "id": order_id, "lines": lines, "total": total, "coupon_name": None, "coupon_discount": 0,
                "points_used": 0, "final_total": total, "tickets": [], "ticket_total": 0, "cash": total,
                "change": 0, "change_breakdown": {}, "change_points": 0, "eco_points": 0, "earned_points": 0,
                "point_events": [], "issued_coupon": None, "new_titles": [],
                "customer": {"id": customer_id, "nickname": extra["nickname"]}, "status": "done",
                "created_at": when.isoformat(timespec="seconds"),
            }
        record["extra"]["visits"] = len(history)
        update_titles(record, [lines for _, lines in history], menu)
        customers[customer_id] = record
        made.append(customer_id)
    vault.write("customers", customers)
    vault.write("orders", orders)
    return made
