"""06 쿠폰 · 포인트 사용 (회원만, 와이어프레임 v2.1).

플로차트: Quick Order 또는 장바구니(회원) → 쿠폰·포인트 사용 선택 → 07 현금 투입.
쿠폰은 한 주문에 1장, 포인트와 함께 쓸 수 있다. 계산과 검사는 domain/benefits.py.
"""

from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QRadioButton, QVBoxLayout, QWidget

from gui import theme
from gui.screens.checkout import clear, money_row, screen_header
from gui.screens.login import nav_bar
from gui.widgets import FixedWidthCard, Card, button, label, message_label, text_field


class BenefitScreen(QWidget):
    def __init__(self, router):
        super().__init__()
        self.router = router
        self.session = router.session
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 24, 40, 20)
        layout.setSpacing(16)
        layout.addLayout(screen_header("쿠폰 · 포인트 사용", "혜택 적용 · 4 / 6"))
        body = QHBoxLayout()
        body.setSpacing(20)

        choose_card = Card()
        left = QVBoxLayout(choose_card)
        left.setContentsMargins(24, 20, 24, 20)
        left.setSpacing(10)
        self.coupon_title = label("", 20, bold=True)
        left.addWidget(self.coupon_title)
        self.coupon_list = QVBoxLayout()
        left.addLayout(self.coupon_list)
        left.addSpacing(8)
        self.points_title = label("", 20, bold=True)
        left.addWidget(self.points_title)
        point_row = QHBoxLayout()
        self.points_field = text_field("0")
        self.points_field.setFixedWidth(200)
        point_row.addWidget(self.points_field)
        point_row.addWidget(label("P", 20, bold=True))
        self.all_points_button = button("전액 사용", "outline", self.use_all_points)
        point_row.addWidget(self.all_points_button)
        point_row.addWidget(button("안 씀", "outline", lambda: self.set_points(0)))
        point_row.addStretch()
        left.addLayout(point_row)
        self.rule = label("", 14, muted=True)
        left.addWidget(self.rule)
        self.message = message_label()
        left.addWidget(self.message)
        left.addStretch()
        body.addWidget(choose_card, 1)

        summary = FixedWidthCard(340)
        right = QVBoxLayout(summary)
        right.setContentsMargins(22, 20, 22, 20)
        right.setSpacing(10)
        right.addWidget(label("적용된 금액", 22, title=True))
        row, self.before_value = money_row("할인 전", theme.won(0))
        right.addLayout(row)
        row, self.coupon_value = money_row("쿠폰 할인", theme.won(0))
        right.addLayout(row)
        row, self.points_value = money_row("포인트 사용", "0P")
        right.addLayout(row)
        row, self.final_value = money_row("할인 후 결제액", theme.won(0), big=True)
        right.addLayout(row)
        right.addStretch()
        right.addWidget(button("혜택 적용 · 금액 갱신", "outline", self.apply))
        self.pay_button = button("결제로 이동 →", "primary", self.go_cash)
        right.addWidget(self.pay_button)
        right.addWidget(button("혜택 없이 결제", "outline", self.pay_without_benefit))
        body.addWidget(summary)
        layout.addLayout(body, 1)
        layout.addLayout(nav_bar(router, lambda: router.show_screen("cart")))

    def on_show(self):
        self.message.setText("")
        coupons = self.session.coupons()
        self.coupon_title.setText(f"사용 가능한 쿠폰 · {len(coupons)}장 중 1장 선택")
        clear(self.coupon_list)
        self.coupon_group = QButtonGroup(self)
        choices = [(None, "쿠폰 안 씀", "")] + [
            (c["id"], c["name"], f"{c.get('min_order', 0):,}원 이상 · {c.get('expires') or '기한 없음'}까지")
            for c in coupons]
        for coupon_id, name, detail in choices:
            radio = QRadioButton(f"{name}   {detail}".strip())
            radio.setFont(theme.font(17, bold=coupon_id is not None))
            radio.setProperty("coupon_id", coupon_id)
            radio.setChecked(coupon_id == self.session.coupon_id)
            radio.setMinimumHeight(44)
            radio.toggled.connect(self.apply)
            self.coupon_group.addButton(radio)
            self.coupon_list.addWidget(radio)
        policy = self.session.policy()
        balance = self.session.customer["extra"]["points"]
        self.points_title.setText(f"사용할 포인트 · 보유 {balance:,}P")
        self.rule.setText(f"1P = 1원 · {policy['point_unit']}P 단위 · 최소 {policy['min_use']:,}P · "
                          f"결제액의 {policy['max_use_percent']}%까지"
                          + ("\n승차권 금액은 쿠폰·포인트 할인에서 빠져요 (음료에만 적용)" if self.session.tickets else ""))
        self.update_summary()                      # 장바구니가 바뀌었으면 여기서 선택이 풀린다
        self.points_field.setText(str(self.session.use_points))
        if self.session.benefit_note:
            self.message.setText(self.session.benefit_note)
            self.session.benefit_note = ""
            for radio in self.coupon_group.buttons():
                radio.blockSignals(True)
                radio.setChecked(radio.property("coupon_id") is None)
                radio.blockSignals(False)

    def selected_coupon(self):
        checked = self.coupon_group.checkedButton()
        return checked.property("coupon_id") if checked else None

    def entered_points(self):
        text = self.points_field.text().replace(",", "").replace("P", "").strip() or "0"
        if not text.isdigit():
            raise ValueError("포인트는 숫자로 입력하세요")
        return int(text)

    def apply(self):
        try:
            self.session.set_benefit(self.selected_coupon(), self.entered_points())
            self.message.setText("")
        except ValueError as error:
            self.message.setText(str(error))
        self.update_summary()

    def set_points(self, amount):
        self.points_field.setText(str(amount))
        self.apply()

    def use_all_points(self):
        try:
            self.session.set_benefit(self.selected_coupon(), 0)
        except ValueError as error:
            self.message.setText(str(error))
            return
        self.set_points(self.session.max_points())

    def update_summary(self):
        benefit = self.session.benefit()
        self.before_value.setText(theme.won(self.session.total()))
        self.coupon_value.setText(f"−{theme.won(benefit['coupon_discount'])}")
        self.points_value.setText(f"−{benefit['points_used']:,}P")
        self.final_value.setText(theme.won(benefit["final_total"]))
        self.pay_button.setText(f"{theme.won(benefit['final_total'])} 결제로 이동 →")
        self.all_points_button.setText(f"전액 사용 · {self.session.max_points():,}P")

    def go_cash(self):
        self.apply()
        if not self.message.text():
            self.router.show_screen("cash")

    def pay_without_benefit(self):
        self.session.set_benefit(None, 0)
        self.router.show_screen("cash")
