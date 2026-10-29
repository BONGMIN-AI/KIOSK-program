"""한 손님의 주문 상태. 화면은 여기만 부르고, 계산은 모두 domain/ 함수가 한다."""

from datetime import date

from domain.benefits import apply_benefits, coupons_of, max_usable_points
from domain.cart import add_item, cart_lines, change_quantity
from domain.customers import allergy_warnings
from domain.my_menu import caffeine_report, likes_of, toggle_like, usual_order
from domain.options import available_options, option_price
from domain.orders import complete_order
from domain.payment import insert_cash, payment_status
from domain.policy import display_event, load_policy
from domain.titles import count_stats, customer_lines, progress
from core.schema import now_iso

# 왼쪽 카테고리 줄 순서. 회원이면 맨 앞에 My Menu가 붙는다.
CATEGORY_ORDER = ["커피", "디카페인", "논커피", "차", "에이드", "디저트"]
MY_MENU = "My Menu"
CASH_RECORD = "cash_session"    # 지금 손님이 넣은 현금. 키오스크가 갑자기 꺼져도 얼마가 남아 있었는지 알 수 있다


class OrderSession:
    def __init__(self, vault):
        self.vault = vault
        self._inserted = 0
        self.reset()

    @property
    def inserted(self):
        return self._inserted

    @inserted.setter
    def inserted(self, amount):
        """넣은 현금이 바뀔 때마다 금고에 기록한다 (꺼짐 대비)."""
        if amount != self._inserted and self.vault is not None:
            self.vault.write(CASH_RECORD, self.cash_record(amount))
        self._inserted = amount

    @staticmethod
    def cash_record(amount):
        return {"inserted": amount, "updated_at": now_iso()}

    def unreturned_cash(self):
        """지난번 실행이 현금이 들어 있는 채로 끝났으면 그 기록을 돌려주고 지운다 (없으면 None)."""
        record = self.vault.read(CASH_RECORD, default={}) or {}
        if not record.get("inserted"):
            return None
        self.vault.write(CASH_RECORD, self.cash_record(0))
        self._inserted = 0
        return record

    def reset(self):
        """새 손님. 장바구니·넣은 현금·회원 정보를 모두 비운다."""
        self.cart = {}
        self.customer = None          # 비회원이면 None
        self.coupon_id = None
        self.use_points = 0
        self.change_to_points = False
        self.benefit_note = ""        # 쿠폰·포인트 선택을 자동으로 풀었을 때 화면에 한 번 보여 줄 말
        self.inserted = 0
        self.last_order = None

    # 회원
    def login(self, customer):
        self.customer = customer

    def is_member(self):
        return self.customer is not None

    def reload_customer(self):
        """저장된 최신 회원 카드로 바꾼다 (좋아요·포인트가 바뀐 뒤)."""
        if self.customer:
            self.customer = self.vault.read("customers", default={})[self.customer["id"]]
        return self.customer

    def categories(self):
        return ([MY_MENU] if self.is_member() else []) + CATEGORY_ORDER

    def policy(self):
        return load_policy(self.vault.read("settings", default={}))

    # 메뉴
    def menu(self):
        return self.vault.read("menu", default={})

    def items_in(self, category):
        items = [item for item in self.menu().values() if item["category"] == category]
        return sorted(items, key=lambda item: item["id"])

    def options_for(self, menu_id):
        return available_options(self.menu()[menu_id])

    def unit_price(self, menu_id, options):
        return self.menu()[menu_id]["price"] + option_price(options or {})

    def current_event(self):
        """운영자가 정한 진행 중 이벤트(이름·문구·테마). 없으면 None."""
        if self.vault is None:
            return None
        return display_event(self.policy())

    def allergy_warning(self, menu_id):
        """회원 알레르기와 겹치는 성분 (예: ['우유']). 비회원이면 빈 목록."""
        item = self.menu()[menu_id]
        found = allergy_warnings(self.customer, [{"menu_id": menu_id, "name": item["name"]}], self.menu())
        return found[0].split(": ", 1)[1].split(", ") if found else []

    # My Menu (회원)
    def orders(self):
        return self.vault.read("orders", default={})

    def usual(self):
        return usual_order(self.orders(), self.customer["id"], self.menu())

    def likes(self):
        menu = self.menu()
        return [menu[menu_id] for menu_id in likes_of(self.customer) if menu_id in menu]

    def is_liked(self, menu_id):
        return self.is_member() and menu_id in likes_of(self.customer)

    def toggle_like(self, menu_id):
        liked = toggle_like(self.vault, self.customer["id"], menu_id)
        self.reload_customer()
        return liked

    def caffeine(self, today=None):
        return caffeine_report(self.orders(), self.customer["id"], self.menu(), today or date.today())

    def title_progress(self):
        stats = count_stats(customer_lines(self.orders(), self.customer["id"]), self.menu())
        return progress(stats)

    # 장바구니
    def add(self, menu_id, options=None, quantity=1):
        new_cart = add_item(self.cart, menu_id, quantity, options, self.menu())
        cart_lines(new_cart, self.menu())   # 재고가 모자라면 여기서 ValueError (장바구니는 그대로)
        self.cart = new_cart

    def change(self, key, quantity):
        new_cart = change_quantity(self.cart, key, quantity)
        cart_lines(new_cart, self.menu())
        self.cart = new_cart

    def lines(self):
        return cart_lines(self.cart, self.menu()) if self.cart else []

    def count(self):
        return sum(line["quantity"] for line in self.lines())

    def total(self):
        return sum(line["subtotal"] for line in self.lines())

    # 쿠폰·포인트 (회원)
    def coupons(self):
        return coupons_of(self.customer) if self.customer else []

    def _apply_benefit(self):
        return apply_benefits(self.total(), self.customer, self.coupon_id, self.use_points,
                              date.today().isoformat(), self.policy())

    def benefit(self):
        """지금 고른 쿠폰·포인트로 할인 계산. 비회원이면 할인 없음.

        06에서 고른 뒤 장바구니를 줄여 쿠폰·포인트가 더는 맞지 않으면(예: 결제액보다 많은 포인트)
        오류로 멈추지 않고 선택을 풀고 benefit_note로 알린다.
        """
        try:
            return self._apply_benefit()
        except ValueError as error:
            if not (self.coupon_id or self.use_points):
                raise
            self.coupon_id, self.use_points = None, 0
            self.benefit_note = f"장바구니가 바뀌어 쿠폰·포인트 선택을 풀었어요 · 다시 골라 주세요 ({error})"
            return self._apply_benefit()

    def max_points(self):
        if not self.customer:
            return 0
        after_coupon = self.total() - self.benefit()["coupon_discount"]
        return max_usable_points(after_coupon, self.customer["extra"]["points"], self.policy())

    def set_benefit(self, coupon_id, use_points):
        """화면에서 고른 값을 검사한 뒤 저장한다. 안 되면 ValueError(원래 값 유지)."""
        old = (self.coupon_id, self.use_points)
        self.coupon_id, self.use_points = coupon_id, int(use_points)
        try:
            return self._apply_benefit()
        except ValueError:
            self.coupon_id, self.use_points = old
            raise

    def final_total(self):
        return self.benefit()["final_total"]

    # 현금
    def insert(self, amount):
        self.inserted = insert_cash(self.inserted, amount)

    def status(self):
        return payment_status(self.final_total(), self.inserted)

    def refund(self):
        """투입 취소. 넣은 돈을 돌려주고 0으로 만든다."""
        amount, self.inserted = self.inserted, 0
        return amount

    def pay(self):
        change_to_points = self.change_to_points and self.is_member() and self.status()["change"] > 0
        order = complete_order(self.vault, self.cart, self.inserted,
                               customer_id=self.customer["id"] if self.customer else None,
                               coupon_id=self.coupon_id, use_points=self.use_points,
                               change_to_points=change_to_points,
                               also_write={CASH_RECORD: self.cash_record(0)})   # 주문과 함께 현금 기록도 0으로
        self.last_order = order
        self.cart = {}
        self._inserted = 0
        self.coupon_id, self.use_points, self.change_to_points = None, 0, False
        self.reload_customer()
        return order
