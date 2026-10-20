"""발표와 연습에 쓰는 KIOSK 샘플 데이터."""
from core import schema
from .customers import hash_member_password

CATEGORIES = {
    "커피": [("아메리카노", 3000, []), ("카페라떼", 4000, ["우유"]), ("바닐라라떼", 4500, ["우유"]),
             ("카푸치노", 4200, ["우유"]), ("카페모카", 4700, ["우유"]), ("카라멜마키아토", 4800, ["우유"]),
             ("콜드브루", 4300, []), ("연유라떼", 4800, ["우유"]), ("헤이즐넛라떼", 4600, ["우유", "기타 견과류(헤이즐넛·아몬드 등)"]),
             ("디카페인 아메리카노", 3500, [])],
    "논커피": [("초코라떼", 4500, ["우유"]), ("딸기라떼", 4800, ["우유"]), ("고구마라떼", 4700, ["우유"]),
              ("말차라떼", 4700, ["우유"]), ("밀크티", 4500, ["우유"]), ("곡물라떼", 4600, ["우유", "기타 견과류(헤이즐넛·아몬드 등)"]),
              ("민트초코", 4800, ["우유"]), ("흑임자라떼", 4900, ["우유", "참깨"]), ("망고라떼", 4800, ["우유"]),
              ("블루베리라떼", 4800, ["우유"])],
    "차": [("유자차", 4000, []), ("레몬차", 4000, []), ("자몽차", 4200, []), ("캐모마일", 3800, []),
           ("페퍼민트", 3800, []), ("얼그레이", 3800, []), ("루이보스", 3800, []), ("히비스커스", 4000, []),
           ("녹차", 3500, []), ("복숭아 아이스티", 3800, [])],
    "에이드": [("레몬에이드", 4500, []), ("자몽에이드", 4500, []), ("청포도에이드", 4500, []),
              ("딸기에이드", 4700, []), ("망고에이드", 4700, []), ("블루레몬에이드", 4700, []),
              ("패션후르츠에이드", 4800, []), ("체리에이드", 4700, []), ("매실에이드", 4500, []),
              ("수박에이드", 4800, [])],
    "디저트": [("크루아상", 3500, ["밀", "우유"]), ("초코쿠키", 2500, ["밀", "우유", "알류(달걀 등)"]),
              ("마카롱", 2800, ["우유", "알류(달걀 등)", "기타 견과류(헤이즐넛·아몬드 등)"]), ("치즈케이크", 5500, ["밀", "우유", "알류(달걀 등)"]),
              ("티라미수", 5800, ["밀", "우유", "알류(달걀 등)"]), ("베이글", 3300, ["밀"]),
              ("소금빵", 3200, ["밀", "우유"]), ("브라우니", 3800, ["밀", "우유", "알류(달걀 등)"]),
              ("와플", 5000, ["밀", "우유", "알류(달걀 등)"]), ("샌드위치", 6000, ["밀", "우유", "알류(달걀 등)"])],
}


def make_menu() -> dict:
    menu = {}
    index = 1
    for category, entries in CATEGORIES.items():
        for name, price, allergens in entries:
            menu_id = f"M{index:03d}"
            menu[menu_id] = {"id": menu_id, "name": name, "price": price,
                             "category": category, "allergens": allergens,
                             "stock": 20, "sold_count": 0, "sold_out": False}
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
