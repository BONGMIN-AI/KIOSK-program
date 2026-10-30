"""발표와 연습에 쓰는 KIOSK 샘플 데이터."""
import zlib

from core import schema
from .customers import hash_member_password
from .options import TEMPERATURE_ONLY

CATEGORIES = {
    "커피": [("아메리카노", 3000, []), ("카페라떼", 4000, ["우유"]), ("바닐라라떼", 4500, ["우유"]),
             ("카푸치노", 4200, ["우유"]), ("카페모카", 4700, ["우유"]), ("카라멜마키아토", 4800, ["우유"]),
             ("콜드브루", 4300, []), ("연유라떼", 4800, ["우유"]), ("헤이즐넛라떼", 4600, ["우유", "기타 견과류(헤이즐넛·아몬드 등)"]),
             ("에스프레소", 2800, [])],
    "논커피": [("초코라떼", 4500, ["우유"]), ("딸기라떼", 4800, ["우유"]), ("고구마라떼", 4700, ["우유"]),
              ("말차라떼", 4700, ["우유"]), ("밀크티", 4500, ["우유"]), ("곡물라떼", 4600, ["우유", "기타 견과류(헤이즐넛·아몬드 등)"]),
              ("민트초코", 4800, ["우유"]), ("흑임자라떼", 4900, ["우유", "참깨"]), ("망고라떼", 4800, ["우유"]),
              ("블루베리라떼", 4800, ["우유"])],
    "차": [("유자차", 4000, []), ("레몬차", 4000, []), ("자몽차", 4200, []), ("캐모마일", 3800, []),
           ("페퍼민트", 3800, []), ("얼그레이", 3800, []), ("루이보스", 3800, []), ("히비스커스", 4000, []),
           ("녹차", 3500, []), ("복숭아 아이스티", 3800, ["복숭아"])],
    "에이드": [("레몬에이드", 4500, []), ("자몽에이드", 4500, []), ("청포도에이드", 4500, []),
              ("딸기에이드", 4700, []), ("망고에이드", 4700, []), ("블루레몬에이드", 4700, []),
              ("패션후르츠에이드", 4800, []), ("체리에이드", 4700, []), ("매실에이드", 4500, []),
              ("수박에이드", 4800, [])],
    "디저트": [("크루아상", 3500, ["밀", "우유", "알류(달걀 등)"]), ("초코쿠키", 2500, ["밀", "우유", "알류(달걀 등)"]),
              ("마카롱", 2800, ["우유", "알류(달걀 등)", "기타 견과류(헤이즐넛·아몬드 등)"]), ("치즈케이크", 5500, ["밀", "우유", "알류(달걀 등)"]),
              ("티라미수", 5800, ["밀", "우유", "알류(달걀 등)"]), ("베이글", 3300, ["밀"]),
              ("소금빵", 3200, ["밀", "우유"]), ("브라우니", 3800, ["밀", "우유", "알류(달걀 등)"]),
              ("와플", 5000, ["밀", "우유", "알류(달걀 등)"]), ("샌드위치", 6000, ["밀", "우유", "알류(달걀 등)"])],
    # 디카페인은 맨 뒤에 두어 기존 메뉴 ID(M001~M050)가 바뀌지 않게 한다. 화면 탭 순서는 app.py에서 정한다.
    "디카페인": [("디카페인 아메리카노", 3500, []), ("디카페인 카페라떼", 4500, ["우유"]),
               ("디카페인 바닐라라떼", 5000, ["우유"]), ("디카페인 카푸치노", 4700, ["우유"]),
               ("디카페인 카페모카", 5200, ["우유"]), ("디카페인 카라멜마키아토", 5300, ["우유"]),
               ("디카페인 콜드브루", 4800, []), ("디카페인 연유라떼", 5300, ["우유"]),
               ("디카페인 헤이즐넛라떼", 5100, ["우유", "기타 견과류(헤이즐넛·아몬드 등)"]),
               ("디카페인 에스프레소", 3300, [])],
}

# 1잔(기본 M 사이즈) 카페인 추정값(mg). 카페인 리포트용 예시 값이며, 없는 메뉴는 0이다.
# 디카페인 메뉴는 값을 넣지 않는다 (0으로 계산).
CAFFEINE_MG = {
    "아메리카노": 150, "카페라떼": 150, "바닐라라떼": 150, "카푸치노": 150, "카페모카": 160,
    "카라멜마키아토": 150, "콜드브루": 200, "연유라떼": 150, "헤이즐넛라떼": 150, "에스프레소": 75,
    "초코라떼": 10, "말차라떼": 70, "밀크티": 50, "민트초코": 10,
    "얼그레이": 40, "녹차": 30, "복숭아 아이스티": 20,
    "초코쿠키": 5, "티라미수": 10, "브라우니": 5,
}


# 온도·사이즈가 일반 음료와 다른 메뉴. 온도 표는 domain/options.py에 있다 (예전 데이터에도 적용되게).
SIZE_ONLY = {"에스프레소": ["M"], "디카페인 에스프레소": ["M"]}


# 인기 탭 시연용 기본값 (10/31): (좋아요 수, 누적 판매 잔 수). 적지 않은 메뉴는 작은 값을 자동으로 정한다.
POPULAR_DEMO = {
    "아메리카노": (48, 1250), "카페라떼": (41, 860), "바닐라라떼": (52, 640), "카라멜마키아토": (37, 410),
    "콜드브루": (29, 380), "연유라떼": (33, 300), "딸기라떼": (58, 520), "초코라떼": (26, 330),
    "말차라떼": (35, 290), "고구마라떼": (22, 240), "밀크티": (24, 210), "레몬에이드": (31, 450),
    "자몽에이드": (27, 360), "청포도에이드": (30, 340), "복숭아 아이스티": (25, 480), "유자차": (28, 390),
    "치즈케이크": (34, 280), "소금빵": (39, 310), "크루아상": (21, 260), "디카페인 아메리카노": (18, 230),
}
# 계절마다 잘 팔리는 비율 (봄·여름·가을·겨울, 합 1). 분류 기본값 위에 메뉴별 값을 덮어쓴다.
SEASON_SHARE = {
    "에이드": (0.25, 0.45, 0.2, 0.1), "차": (0.2, 0.1, 0.3, 0.4), "디저트": (0.25, 0.25, 0.25, 0.25),
    "딸기라떼": (0.35, 0.1, 0.15, 0.4), "고구마라떼": (0.1, 0.05, 0.4, 0.45), "복숭아 아이스티": (0.2, 0.55, 0.2, 0.05),
    "콜드브루": (0.25, 0.4, 0.25, 0.1), "유자차": (0.15, 0.05, 0.3, 0.5),
}
DEFAULT_SHARE = (0.25, 0.3, 0.25, 0.2)


def popularity(name: str, category: str) -> dict:
    """메뉴 하나의 시연용 인기 값: demo_likes · sold_count · demo_season(계절별 판매 잔 수)."""
    likes, sold = POPULAR_DEMO.get(name, (3 + zlib.crc32(name.encode()) % 15, 40 + zlib.crc32(name.encode()) % 160))
    share = SEASON_SHARE.get(name, SEASON_SHARE.get(category, DEFAULT_SHARE))
    seasons = dict(zip(("봄", "여름", "가을", "겨울"), (round(sold * part) for part in share)))
    return {"demo_likes": likes, "sold_count": sold, "demo_season": seasons}


def make_menu() -> dict:
    menu = {}
    index = 1
    for category, entries in CATEGORIES.items():
        for name, price, allergens in entries:
            menu_id = f"M{index:03d}"
            menu[menu_id] = {"id": menu_id, "name": name, "price": price,
                             "category": category, "allergens": allergens,
                             "caffeine_mg": CAFFEINE_MG.get(name, 0), "decaf": category == "디카페인",
                             "stock": 20, "sold_count": 0, "sold_out": False,
                             **popularity(name, category)}
            if name in TEMPERATURE_ONLY:
                menu[menu_id]["temperatures"] = TEMPERATURE_ONLY[name]
            if name in SIZE_ONLY:
                menu[menu_id]["sizes"] = SIZE_ONLY[name]
            index += 1
    return menu


def make_demo_customers() -> dict:
    profiles = [
        ("C0001", "김팀장", "MVP보민", "bomin", "010-1000-0001", ["우유"], 1400, 8),
        ("C0002", "팀원1", "딸기완주자", "member1", "010-1000-0002", [], 900, 4),
        ("C0003", "팀원2", "신메뉴헌터", "member2", "010-1000-0003", ["기타 견과류(헤이즐넛·아몬드 등)"], 500, 3),
        ("C0004", "팀원3", "아아수호자", "member3", "010-1000-0004", [], 200, 1),
    ]
    # 와이어프레임 06 화면을 그대로 시연할 수 있도록 bomin에게 쿠폰 2장을 넣어 둔다.
    demo_coupons = {
        "C0001": [
            {"id": "WELCOME1", "name": "1,000원 할인 쿠폰", "amount": 1000,
             "min_order": 10000, "expires": "2026-12-31"},
            {"id": "WELCOME2", "name": "500원 할인 쿠폰", "amount": 500,
             "min_order": 5000, "expires": "2026-12-31"},
        ],
    }
    result = {}
    for customer_id, name, nickname, login_id, phone, allergies, points, visits in profiles:
        result[customer_id] = schema.new_record(
            customer_id, name, phone, nickname=nickname, login_id=login_id,
            password_hash=hash_member_password("1234"), birthday="",
            allergies=allergies, privacy_agreed=True, marketing_agreed=False,
            face_enrolled=False, points=points,
            coupons=demo_coupons.get(customer_id, []), visits=visits,
        )
    return result


def run(vault) -> None:
    vault.write("menu", make_menu())
    vault.write("customers", make_demo_customers())
    vault.write("orders", {})
    vault.write("face_profiles", {})


DEMO_EVENTS = [
    {"name": "가을 더블 포인트", "start": "2026-10-20", "end": "2026-11-11", "categories": ["커피"],
     "rate": 3, "bonus_points": 200, "min_order": 10000, "theme": "season",
     "message": "회원은 커피 3% 적립 + 1만원 이상 200P · 11/11까지"},
    {"name": "할로윈 축제", "start": "2026-10-31", "end": "2026-10-31", "categories": [],
     "rate": 0, "bonus_points": 300, "min_order": 0, "theme": "festival"},
]


def add_demo_events(vault) -> None:
    """시연용 기간 이벤트를 운영자 정책에 넣는다. (자동 테스트는 이벤트 없이 기본 적립률로 계산)"""
    from .policy import load_policy, upsert_event, validate_policy

    settings = vault.read("settings", default={})
    policy = load_policy(settings)
    for event in DEMO_EVENTS:
        policy, _ = upsert_event(policy, event)
    settings["point_policy"] = validate_policy(policy)
    vault.write("settings", settings)
