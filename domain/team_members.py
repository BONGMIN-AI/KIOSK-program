"""시연 계정 (11/03 다시 짬): 커피와 버스표를 한 번에 사는 키오스크 + 회원을 기억하는 기능이 핵심.

시연 모드를 켤 때마다 '오늘' 기준으로 새로 만든다 (생일 · 방문 간격 · 이번 주 카페인 · 예매 시간이 어느 날 실행해도 맞게).
비밀번호는 모두 1234. 이름은 팀원 실제 이름, 전화번호는 시연용 임시 번호 (11/04 회의).
11/04 회의 2: 미리 만들어 두는 계정은 둘뿐이다. 조민기는 시연 때 회원가입부터(카드 신청 · 얼굴 등록) 하고,
임예찬은 비회원으로 예매표 출력(이름 임예찬 · 010-2007-2007)과 주문을 보여 준다. 얼굴은 미리 등록하지 않고 그 자리에서.

1 withtop77  김휘원 · 회원을 기억하는 기능 : 비밀번호 로그인 · "[얼죽아] 김휘원 님, 2일 만이에요!" · 오늘 생일 쿠폰 ·
                                  우유 알레르기 경고 · ★ 저장한 노선 · 다시 담기(quick) · ICE·L·샷 미리 선택 ·
                                  카페인 알리미 설정 · 경고 · 좋아요 · 칭호 현황 · 로고 이스터에그
3 jisung0642 김지성 · 다가가면 시작 · 얼굴 등록 · 버스표 구매 + 혜택 : 맨 앞 '포장' → 승차권 구매(경로 할인) → 음료 → 웃고 500원 → 쿠폰·포인트
                                  → 현금 · 잔돈 포인트 → 완료 '포장' · 단골손님 칭호 달성 · "오늘 두 번째 방문이에요!"
4 bomin      팀장 (시연은 하지 않고 설명). 시연 데이터의 MVP보민 · 3일 만 · [디카페인 지킴이]
"""
from datetime import datetime, time, timedelta

from core import schema
from .customers import hash_member_password
from .my_menu import week_caffeine
from .options import available_options
from .random_members import _line
from .tickets import ORIGIN, remember_route
from .titles import update_titles

ICE_L_SHOT = {"temperature": "ICE", "size": "L", "extras": ["shot"]}
ICE_R = {"temperature": "ICE", "size": "R", "extras": []}
HOT_R = {"temperature": "HOT", "size": "R", "extras": []}
# (아이디, 닉네임, 이름, 번호(시연용 임시), 회원 번호)
TEAM = [
    ("withtop77", "얼음왕", "김휘원", "010-7700-0077", "C0201"),
    ("jisung0642", "칭호수집가", "김지성", "010-0642-0642", "C0203"),
]
BOMIN_NAME = "김보민"
BOMIN = "C0001"


def _today_birthday(now):
    """시연하는 날이 생일 (2/29면 2/28)."""
    day = now.date()
    return (day.replace(year=2000) if (day.month, day.day) != (2, 29) else day.replace(2000, 2, 28)).isoformat()


def _options(menu, menu_id, wanted):
    """원하는 옵션 중 그 메뉴가 고를 수 있는 것만 (디저트는 옵션 없음)."""
    rules = available_options(menu[menu_id])
    if not wanted or not rules["temperatures"]:
        return {}
    pick = lambda value, allowed: value if value in allowed else allowed[0]
    return {"temperature": pick(wanted["temperature"], rules["temperatures"]),
            "size": pick(wanted["size"], rules["sizes"]),
            "extras": [e for e in wanted["extras"] if e in rules["extras"]]}


def _plans(now: datetime) -> dict:
    """회원마다 지난 주문 [(며칠 전, 몇 시간 전, [(메뉴, 옵션, 수량)])]."""
    withtop = [(days, 2, [("M001", ICE_L_SHOT, 1)]) for days in (40, 33, 27, 22, 18, 14, 11, 8, 6, 4)]
    withtop += [(16, 3, [("M001", ICE_L_SHOT, 1)]),                       # 우유 알레르기라 치즈케이크는 빼 둔다
                (2, 1, [("M001", ICE_L_SHOT, 1), ("M007", ICE_R, 1)])]
    jisung_menus = ["M002", "M003", "M014", "M015", "M021", "M031", "M041", "M044"]
    jisung = [(30 - index * 3, 3, [(menu_id, HOT_R, 1)]) for index, menu_id in enumerate(jisung_menus)]
    hours_ago = min(2, max(now.hour - 7, 0))            # 오늘 아침 (자정 직후면 방금)
    jisung.append((0, hours_ago, [("M001", ICE_R, 1)]))  # 오늘 이미 한 번 → '오늘 두 번째 방문'
    bomin = [(days, 2, [("M051", HOT_R, 1)]) for days in (25, 18, 12, 7, 3)]   # 우유 알레르기라 디카페인 아메리카노만
    return {"C0201": withtop, "C0203": jisung, BOMIN: bomin}


def _add_history(orders, menu, customer_id, nickname, plan, now, prefix):
    history = []
    for index, (days, hours, items) in enumerate(plan):
        # 며칠 전 주문은 그날 낮 시각으로 (자정 넘어 켜도 '2일 만'이 '3일 만'으로 바뀌지 않게). 오늘 주문만 지금 기준
        if days == 0:
            when = now - timedelta(hours=hours)
        else:
            when = datetime.combine(now.date() - timedelta(days=days), time(14, 0)) - timedelta(hours=hours)
        lines = [_line(menu[menu_id], _options(menu, menu_id, opts), quantity)
                 for menu_id, opts, quantity in items if menu_id in menu]
        total = sum(line["subtotal"] for line in lines)
        order_id = f"{prefix}{index:02d}"
        orders[order_id] = {
            "id": order_id, "lines": lines, "total": total, "coupon_name": None, "coupon_discount": 0,
            "points_used": 0, "final_total": total, "tickets": [], "ticket_total": 0, "cash": total,
            "change": 0, "change_breakdown": {}, "change_points": 0, "eco_points": 0, "earned_points": 0,
            "point_events": [], "issued_coupon": None, "new_titles": [],
            "customer": {"id": customer_id, "nickname": nickname}, "status": "done",
            "created_at": when.isoformat(timespec="seconds"),
        }
        history.append(lines)
    return history


def add_team_members(vault, now: datetime | None = None) -> list[str]:
    now = now or datetime.now()
    menu = vault.read("menu", default={})
    customers = vault.read("customers", default={})
    orders = vault.read("orders", default={})
    password = hash_member_password("1234")
    plans = _plans(now)
    made = []
    for login_id, nickname, name, phone, customer_id in TEAM:
        number = int(customer_id[-1])                   # 주문 번호 HT1 · HT3 (예전과 같게)
        extra = {"nickname": nickname, "login_id": login_id, "password_hash": password, "birthday": "",
                 "allergies": [], "privacy_agreed": True, "marketing_agreed": True, "face_enrolled": False,
                 "points": 0, "coupons": [], "visits": 0, "likes": []}
        record = schema.new_record(customer_id, name, phone, **extra)
        history = _add_history(orders, menu, customer_id, nickname, plans[customer_id], now, f"HT{number}")
        record["extra"]["visits"] = len(history)
        update_titles(record, history, menu)
        customers[customer_id] = record
        made.append(customer_id)

    # 1 withtop77: 저장한 노선 · 좋아요 · 대표 칭호 얼죽아 · 오늘 생일 · 우유 알레르기 (11/04: bomin에서 옮김)
    withtop = customers["C0201"]
    withtop["extra"].update(points=1800, likes=["M001", "M007"], title="얼죽아", allergies=["우유"],
                            birthday=_today_birthday(now))
    for destination, days in (("동대구", 12), ("대전복합", 2)):
        for _ in range(3):
            remember_route(withtop, ORIGIN, destination, (now - timedelta(days=days)).date().isoformat())
    # 3 jisung0642
    customers["C0203"]["extra"]["points"] = 700
    # 4 bomin(팀장): 디카페인 기록 → [디카페인 지킴이] · 3일 만 (생일 · 우유 알레르기는 11/04에 withtop77로 옮김)
    if BOMIN in customers:
        bomin = customers[BOMIN]
        bomin["name"] = BOMIN_NAME
        bomin["extra"]["birthday"] = ""                   # 생일은 withtop77로 (알레르기는 자동 점검용으로 그대로)
        history = _add_history(orders, menu, BOMIN, bomin["extra"]["nickname"], plans[BOMIN], now, "HTB")
        update_titles(bomin, history, menu)
    vault.write("customers", customers)
    vault.write("orders", orders)
    # 1: 이번 주에 마신 잔 수 + 1잔을 제한으로 → 커피를 두 잔 담으면 알리미가 묻는다
    used = week_caffeine(orders, "C0201", menu, now.date())["잔"]
    customers = vault.read("customers")
    customers["C0201"]["extra"]["caffeine_limit"] = {"unit": "잔", "amount": used + 1}
    vault.write("customers", customers)
    return made
