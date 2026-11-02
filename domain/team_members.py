"""팀원 시연 계정 (11/03): 회의 때 팀원이 각자 맡아 보여 줄 기능이 바로 보이게 만든 회원 3명.

시연 모드를 켤 때마다 '오늘' 기준으로 새로 만든다 (생일 · 방문 간격 · 이번 주 카페인이 어느 날 실행해도 맞게).
비밀번호는 모두 1234.

- withtop77  나를 기억하는 KIOSK : "2일 만이에요!" · [얼죽아] · ICE·L·샷 미리 선택 · 좋아요 · 최근 주문 다시 담기 · 카페인 알리미
- asd1625    축하 · 혜택          : 로그인하면 생일 + 가입 1주년 팝업과 쿠폰 · 포인트 · 스마일 할인 · 개인 컵 · 잔돈 포인트 · 회원카드 신청(장바구니)
- jisung0642 칭호 · 재미          : "오늘 두 번째 방문이에요!" · 단골손님 9/10 (이번 주문으로 달성) · 칭호 현황 · 로고 이스터에그
"""
from datetime import datetime, timedelta

from core import schema
from .customers import hash_member_password
from .my_menu import week_caffeine
from .options import available_options
from .random_members import _line
from .titles import update_titles

ICE_L_SHOT = {"temperature": "ICE", "size": "L", "extras": ["shot"]}
ICE_R = {"temperature": "ICE", "size": "R", "extras": []}
HOT_R = {"temperature": "HOT", "size": "R", "extras": []}

# (아이디, 닉네임, 번호, 회원 번호)
TEAM = [
    ("withtop77", "얼음왕", "010-7700-0077", "C0201"),
    ("asd1625", "생일주인공", "010-1625-1625", "C0202"),
    ("jisung0642", "칭호수집가", "010-0642-0642", "C0203"),
]


def _plans(now: datetime, menu: dict) -> dict:
    """회원마다 지난 주문 [(며칠 전, 몇 시간 전, [(메뉴, 옵션, 수량)])]."""
    def options(menu_id, wanted):
        """원하는 옵션 중 그 메뉴가 고를 수 있는 것만 (디저트는 옵션 없음)."""
        rules = available_options(menu[menu_id])
        if not wanted or not rules["temperatures"]:
            return {}
        pick = lambda value, allowed: value if value in allowed else allowed[0]
        return {"temperature": pick(wanted["temperature"], rules["temperatures"]),
                "size": pick(wanted["size"], rules["sizes"]),
                "extras": [e for e in wanted["extras"] if e in rules["extras"]]}

    withtop = [(days, 2, [("M001", ICE_L_SHOT, 1)]) for days in (40, 33, 27, 22, 18, 14, 11, 8, 6, 4)]
    withtop += [(16, 3, [("M001", ICE_L_SHOT, 1), ("M044", {}, 1)]), (2, 1, [("M001", ICE_L_SHOT, 1),
                                                                             ("M007", ICE_R, 1)])]
    asd = [(20, 4, [("M012", ICE_R, 1)]), (9, 2, [("M002", HOT_R, 1), ("M041", {}, 1)])]
    jisung_menus = ["M002", "M003", "M014", "M015", "M021", "M031", "M041", "M044"]
    jisung = [(30 - index * 3, 3, [(menu_id, HOT_R, 1)]) for index, menu_id in enumerate(jisung_menus)]
    hours_ago = min(2, max(now.hour - 7, 0))           # 오늘 아침 (자정 직후면 방금)
    jisung.append((0, hours_ago, [("M001", ICE_R, 1)]))  # 오늘 이미 한 번 → '오늘 두 번째 방문'
    return {"withtop77": withtop, "asd1625": asd, "jisung0642": jisung}, options


def add_team_members(vault, now: datetime | None = None) -> list[str]:
    now = now or datetime.now()
    menu = vault.read("menu", default={})
    customers = vault.read("customers", default={})
    orders = vault.read("orders", default={})
    password = hash_member_password("1234")
    plans, options = _plans(now, menu)
    birthday = now.date().replace(year=2001) if (now.month, now.day) != (2, 29) else now.date().replace(2001, 2, 28)
    made = []
    for number, (login_id, nickname, phone, customer_id) in enumerate(TEAM, 1):
        extra = {"nickname": nickname, "login_id": login_id, "password_hash": password, "birthday": "",
                 "allergies": [], "privacy_agreed": True, "marketing_agreed": True, "face_enrolled": False,
                 "points": 0, "coupons": [], "visits": 0, "likes": []}
        record = schema.new_record(customer_id, nickname, phone, **extra)
        history = []
        for index, (days, hours, items) in enumerate(plans[login_id]):
            when = now - timedelta(days=days, hours=hours)
            lines = [_line(menu[menu_id], options(menu_id, opts), quantity)
                     for menu_id, opts, quantity in items if menu_id in menu]
            total = sum(line["subtotal"] for line in lines)
            order_id = f"HT{number}{index:02d}"
            orders[order_id] = {
                "id": order_id, "lines": lines, "total": total, "coupon_name": None, "coupon_discount": 0,
                "points_used": 0, "final_total": total, "tickets": [], "ticket_total": 0, "cash": total,
                "change": 0, "change_breakdown": {}, "change_points": 0, "eco_points": 0, "earned_points": 0,
                "point_events": [], "issued_coupon": None, "new_titles": [],
                "customer": {"id": customer_id, "nickname": nickname}, "status": "done",
                "created_at": when.isoformat(timespec="seconds"),
            }
            history.append(lines)
        record["extra"]["visits"] = len(history)
        update_titles(record, history, menu)
        customers[customer_id] = record
        made.append(customer_id)

    withtop = customers["C0201"]["extra"]
    withtop.update(points=1800, likes=["M001", "M007"], title="얼죽아")   # 대표 칭호는 얼죽아
    asd = customers["C0202"]
    asd["extra"].update(points=3000, birthday=birthday.isoformat())
    asd["created_at"] = (now - timedelta(days=365)).isoformat(timespec="seconds")   # 가입 1주년
    customers["C0203"]["extra"]["points"] = 700
    vault.write("customers", customers)
    vault.write("orders", orders)
    # 이번 주에 마신 잔 수 + 1잔을 제한으로: 한 잔 더 담으면 알리미가 묻는다
    used = week_caffeine(orders, "C0201", menu, now.date())["잔"]
    customers = vault.read("customers")
    customers["C0201"]["extra"]["caffeine_limit"] = {"unit": "잔", "amount": used + 1}
    vault.write("customers", customers)
    return made
