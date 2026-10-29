"""05 장바구니 확인 · 07 현금 결제 · 08 주문 완료.

플로차트: 05 → (회원) 06 쿠폰·포인트 → 07 현금 / (비회원) 07 현금
07: 부족하면 추가 투입, 충분하면 거스름돈 계산 → 회원만 '잔돈을 포인트로' 체크 카드
08: 회원은 [칭호] 닉네임 · 적립 포인트 · 잔돈 포인트 · 새 칭호, 비회원은 번호만
승차권(승차권 탭)이 있으면 05에 승차권 줄, 08에 출력된 승차권과 '꼭 챙겨 주세요' 안내 (쿠폰·포인트는 음료에만)
"""

from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QCheckBox, QFrame, QGridLayout, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from domain.payment import breakdown_text
from domain.tickets import depart_text, ticket_summary, until_text
from gui import theme
from gui.screens.ticket import TicketCartLine, notice_label
from gui.widgets import Card, button, label, menu_icon

CASH_UNITS = (50000, 10000, 5000, 1000, 500, 100)


def screen_header(title, step):
    row = QHBoxLayout()
    row.addWidget(label(title, 32, title=True))
    row.addStretch()
    row.addWidget(label(step, 16, muted=True))
    return row


def scroll_card(margins=20):
    """줄이 많아져도 화면이 늘어나지 않도록, 안쪽이 위아래로 밀리는 카드. (카드, 안쪽 세로줄)을 돌려준다."""
    card = Card()
    outer = QVBoxLayout(card)
    outer.setContentsMargins(4, 4, 4, 4)
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    page = QWidget()
    inner = QVBoxLayout(page)
    inner.setContentsMargins(margins - 4, margins - 4, margins - 4, margins - 4)
    area.setWidget(page)
    outer.addWidget(area)
    return card, inner


def clear(layout):
    while layout.count():
        entry = layout.takeAt(0)
        if entry.widget():
            entry.widget().setParent(None)
        elif entry.layout():
            clear(entry.layout())


def money_row(name, amount, big=False):
    # 큰 글자에서 큰 줄은 이름 아래에 금액을 오른쪽 정렬로 둔다 (한 줄에 들어가지 않는다)
    stacked = big and theme.SCALE > 1
    row = QVBoxLayout() if stacked else QHBoxLayout()
    row.addWidget(label(name, 22 if big else 17, bold=big, muted=not big))
    if not stacked:
        row.addStretch()
    value = label(amount, 26 if big else 17, bold=True)
    if stacked:
        row.addWidget(value, alignment=Qt.AlignmentFlag.AlignRight)
    else:
        row.addWidget(value)
    return row, value


class CartScreen(QWidget):
    """05: 담은 메뉴의 수량을 고치고 결제로 넘어간다."""

    def __init__(self, router):
        super().__init__()
        self.router = router
        self.session = router.session
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 28, 40, 28)
        layout.setSpacing(18)
        layout.addLayout(screen_header("장바구니 확인", "주문 확인 · 3 / 6"))
        body = QHBoxLayout()
        body.setSpacing(20)
        lines_card, self.lines = scroll_card(20)
        self.lines.setSpacing(10)
        body.addWidget(lines_card, 1)
        summary = Card()
        summary.setFixedWidth(320)
        column = QVBoxLayout(summary)
        column.setContentsMargins(22, 22, 22, 22)
        column.setSpacing(12)
        column.addWidget(label("주문 합계", 22, title=True))
        row, self.count_value = money_row("총 수량", "0개")
        column.addLayout(row)
        row, self.total_value = money_row("합계", theme.won(0), big=True)
        column.addLayout(row)
        column.addStretch()
        self.pay_button = button("결제하기 →", "primary", self.go_pay)
        column.addWidget(self.pay_button)
        column.addWidget(button("← 메뉴 더 담기", "outline", lambda: self.router.show_screen("menu")))
        body.addWidget(summary)
        layout.addLayout(body, 1)

    def on_show(self):
        if self.session.expire_tickets():
            self.router.notify("좌석을 잡아 둔 5분이 지나 승차권을 장바구니에서 뺐어요 · 다시 골라 주세요", 6)
        clear(self.lines)
        for ticket in self.session.tickets:
            self.lines.addWidget(TicketCartLine(self.session, ticket, self.remove_ticket, big=True))
        lines = self.session.lines()
        for line in lines:
            self.lines.addWidget(self.make_line(line))
        if self.session.is_empty():
            self.lines.addWidget(label("장바구니가 비어 있어요", 18, muted=True))
        self.lines.addStretch()
        self.count_value.setText(f"{self.session.count()}개")
        self.total_value.setText(theme.won(self.session.total()))
        self.pay_button.setEnabled(not self.session.is_empty())

    def remove_ticket(self, hold_id):
        self.session.remove_ticket(hold_id)
        self.on_show()

    def make_line(self, line):
        box = QFrame()
        box.setStyleSheet(f"background: {theme.CREAM}; border-radius: 16px;")
        row = QHBoxLayout(box)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(12)
        row.addWidget(menu_icon(self.session.menu()[line["menu_id"]], 64))
        text = QVBoxLayout()
        text.addWidget(label(line["name"], 20, title=True))
        detail = line["option_label"] or "옵션 없음"
        text.addWidget(label(f"{detail} · {theme.won(line['unit_price'])}", 14, muted=True))
        row.addLayout(text, 1)
        for symbol, quantity in (("−", line["quantity"] - 1), ("+", line["quantity"] + 1)):
            step = button(symbol, "outline",
                          lambda checked=False, key=line["key"], q=quantity: self.change(key, q))
            step.setFixedWidth(56)
            row.addWidget(step)
            if symbol == "−":
                row.addWidget(label(str(line["quantity"]), 20, bold=True))
        price = label(theme.won(line["subtotal"]), 18, bold=True)
        price.setFixedWidth(100)
        price.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(price)
        row.addWidget(button("삭제", "outline", lambda checked=False, key=line["key"]: self.change(key, 0)))
        return box

    def change(self, key, quantity):
        try:
            self.session.change(key, quantity)
        except ValueError as error:
            self.router.notify(str(error), 4)    # 재고·최대 수량을 넘으면 그대로 두고 이유를 알린다
        self.on_show()

    def go_pay(self):
        # 회원은 06 쿠폰·포인트 화면을 거치고, 비회원은 바로 07 현금 결제 (승차권만 있으면 06은 건너뜀)
        self.router.show_screen("benefit" if self.session.is_member() and self.session.cart else "cash")


class CashScreen(QWidget):
    """07: 현금을 넣고(시연은 버튼), 충분하면 결제를 끝낸다."""

    def __init__(self, router):
        super().__init__()
        self.router = router
        self.session = router.session
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 28, 40, 28)
        layout.setSpacing(18)
        layout.addLayout(screen_header("현금 결제", "결제 · 5 / 6"))
        body = QHBoxLayout()
        body.setSpacing(20)

        insert_card = Card()
        left = QVBoxLayout(insert_card)
        left.setContentsMargins(24, 22, 24, 22)
        left.setSpacing(14)
        left.addWidget(label("현금을 넣어 주세요", 26, title=True))
        left.addWidget(label("시연: 넣을 지폐·동전을 누르세요. 넣을 때마다 금액이 더해집니다.", 15, muted=True))
        grid = QGridLayout()
        grid.setSpacing(12)
        self.cash_buttons = []
        for index, unit in enumerate(CASH_UNITS):
            item = button(f"{unit:,}원", "outline", lambda checked=False, u=unit: self.insert(u))
            item.setObjectName(f"cash_{unit}")
            item.setMinimumHeight(72)
            grid.addWidget(item, index // 3, index % 3)
            self.cash_buttons.append(item)
        left.addLayout(grid)
        # 방금 일어난 일(받음·반환·거절)은 위 작은 줄, 지금 상태(더 넣을 돈·거스름돈)는 아래 큰 줄에 따로 쓴다.
        # 그래서 반환 뒤에도 큰 줄은 항상 지금 상태를 맞게 보여 준다.
        self.event = label("", 16, bold=True)
        self.event.setStyleSheet(f"color: {theme.CARAMEL};")
        self.event.setWordWrap(True)
        left.addWidget(self.event)
        self.status = label("", 20, bold=True)
        self.status.setWordWrap(True)
        left.addWidget(self.status)
        self.change_text = label("", 16, muted=True)
        left.addWidget(self.change_text)
        left.addStretch()
        left.addWidget(button("투입 취소 · 반환", "outline", self.refund))
        body.addWidget(insert_card, 1)

        summary = Card()
        summary.setFixedWidth(340)
        right = QVBoxLayout(summary)
        right.setContentsMargins(22, 22, 22, 22)
        right.setSpacing(12)
        right.addWidget(label("결제 금액", 22, title=True))
        row, self.total_value = money_row("주문 금액", theme.won(0))
        right.addLayout(row)
        row, self.discount_value = money_row("쿠폰 + 포인트", theme.won(0))
        right.addLayout(row)
        row, self.inserted_value = money_row("넣은 현금", theme.won(0))
        right.addLayout(row)
        row, self.remain_value = money_row("남은 금액", theme.won(0))
        right.addLayout(row)
        row, self.final_value = money_row("최종 결제액", theme.won(0), big=True)
        right.addLayout(row)
        right.addStretch()
        self.change_card = self.make_change_card()
        right.addWidget(self.change_card)
        self.pay_button = button("결제 완료", "primary", self.finish)
        right.addWidget(self.pay_button)
        right.addWidget(button("← 장바구니", "outline", self.back))
        body.addWidget(summary)
        layout.addLayout(body, 1)

    def make_change_card(self):
        """회원에게만 보이는 '잔돈을 포인트로 적립' 카드 (거스름돈이 정해진 뒤에만)."""
        card = QFrame()
        card.setStyleSheet(f"QFrame {{ background: {theme.CARD}; border: 3px solid {theme.BROWN};"
                           " border-radius: 16px; }")
        column = QVBoxLayout(card)
        column.setContentsMargins(14, 10, 14, 10)
        self.change_check = QCheckBox()
        self.change_check.setFont(theme.font(18, bold=True))
        self.change_check.setStyleSheet("border: none;")
        self.change_check.toggled.connect(self.toggle_change_points)
        column.addWidget(self.change_check)
        self.change_note = label("회원에게만 보임", 13, muted=True)
        self.change_note.setStyleSheet(f"border: none; color: {theme.TEXT2};")
        column.addWidget(self.change_note)
        return card

    def toggle_change_points(self, checked):
        self.session.change_to_points = checked
        self.update_status()

    def on_show(self):
        self.set_change_check(self.session.change_to_points)
        self.update_status()
        if self.session.benefit_note:              # 쿠폰·포인트 선택이 풀렸으면 알린다
            self.update_status(self.session.benefit_note)
            self.session.benefit_note = ""

    def set_change_check(self, checked):
        self.change_check.blockSignals(True)
        self.change_check.setChecked(checked)
        self.change_check.blockSignals(False)

    def insert(self, amount):
        status = self.session.status()
        if status["total"] == 0:
            self.update_status(f"현금이 필요 없어서 {theme.won(amount)}은 받지 않았어요")
            return
        if status["paid"]:      # 실제 기계처럼, 충분해진 뒤에는 더 받지 않고 넣은 돈을 바로 내보낸다
            self.update_status(f"이미 충분해서 {theme.won(amount)}은 받지 않았어요 · 반환구에서 꺼내 주세요")
            return
        self.session.insert(amount)
        self.update_status(f"{theme.won(amount)} 받았어요")

    def state_text(self, status):
        """(큰 줄, 작은 줄): 지금 상태만 보고 정한다. 반환·거절 같은 '방금 일'은 event 줄이 맡는다."""
        if status["total"] == 0:
            return "쿠폰·포인트로 전액 할인됐어요", "현금 없이 '결제 완료'를 눌러 주세요"
        if not status["paid"]:
            if status["cash"] == 0:
                return f"현금 {theme.won(status['total'])}을 넣어 주세요", "넣을 때마다 금액이 더해져요"
            return (f"{theme.won(status['shortage'])} 더 넣어 주세요",
                    f"지금까지 {theme.won(status['cash'])} 받았어요")
        if status["change"] == 0:
            return "딱 맞아요 · '결제 완료'를 눌러 주세요", "거스름돈 없음"
        if self.session.is_member() and self.session.change_to_points:
            return (f"충분해요 · 잔돈 {theme.won(status['change'])}은 포인트로 적립돼요",
                    "'결제 완료'를 누르면 적립돼요 · 현금 거스름돈 0원")
        return (f"충분해요 · '결제 완료'를 누르면 거스름돈 {theme.won(status['change'])}이 나와요",
                breakdown_text(status["breakdown"]))

    def update_status(self, event=""):
        status = self.session.status()
        self.total_value.setText(theme.won(self.session.total()))
        self.discount_value.setText(f"−{theme.won(self.session.total() - status['total'])}")
        self.final_value.setText(theme.won(status["total"]))
        # 와이어프레임 E: 회원에게만, 현금이 충분해 거스름돈이 정해진 뒤에 보인다. 거스름돈 0원이면 흐리게.
        show_card = self.session.is_member() and status["paid"] and status["total"] > 0
        self.change_card.setVisible(show_card)
        no_change = status["change"] == 0
        self.change_check.setEnabled(not no_change)
        if show_card and no_change:
            self.change_check.setText("거스름돈이 없어요")
            self.change_note.setText("딱 맞게 넣으셨어요 · 회원에게만 보임")
        show_card = show_card and not no_change
        if show_card:
            arrow = " → " if theme.SCALE == 1 else "\n→ "     # 큰 글자는 두 줄로
            self.change_check.setText(f"잔돈 {theme.won(status['change'])}{arrow}포인트 적립")
            self.change_note.setText(f"+{status['change']:,}P 적립 · 회원에게만 보임")
        self.inserted_value.setText(theme.won(status["cash"]))
        self.remain_value.setText(theme.won(status["shortage"]))
        state, detail = self.state_text(status)
        self.event.setText(event)
        self.status.setText(state)
        self.change_text.setText(detail)
        # 충분해지면(또는 0원 결제) 지폐·동전 투입구를 막는다. 0원 결제도 '결제 완료'로 끝낼 수 있다.
        for item in self.cash_buttons:
            item.setEnabled(not status["paid"])
        self.pay_button.setEnabled(status["paid"])

    def refund(self):
        amount = self.session.refund()
        self.session.change_to_points = False     # 다시 넣을 때 잔돈 적립은 새로 고른다
        self.set_change_check(False)
        self.update_status(f"넣은 {theme.won(amount)}을 돌려드렸어요 · 반환구에서 꺼내 주세요"
                           if amount else "돌려드릴 현금이 없어요")

    def back(self):
        amount = self.session.refund()
        self.router.show_screen("benefit" if self.session.is_member() and self.session.cart else "cart")
        if amount:
            self.router.notify(f"넣은 현금 {theme.won(amount)}을 반환했어요")

    def finish(self):
        try:
            self.session.pay()
        except ValueError as error:
            cash = self.session.inserted
            kept = f" · 넣은 {theme.won(cash)}은 그대로 있어요 (반환을 누르면 돌려드려요)" if cash else ""
            self.update_status(f"결제하지 못했어요: {error}{kept}")
            return
        self.router.show_screen("done")


class DoneScreen(QWidget):
    """08: 주문번호와 거스름돈 안내. 처음 화면으로 돌아간다."""

    def __init__(self, router):
        super().__init__()
        self.router = router
        self.session = router.session
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 28, 40, 28)
        layout.setSpacing(18)
        layout.addLayout(screen_header("주문 완료", "완료 · 6 / 6"))
        body = QHBoxLayout()
        body.setSpacing(20)
        number_card = Card()
        left = QVBoxLayout(number_card)
        left.setContentsMargins(28, 28, 28, 28)
        left.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.addWidget(center(label("주문이 완료되었습니다", 26, title=True)))
        self.ticket_box = self.make_ticket_box()                    # 승차권을 산 주문만
        self.ticket_box.hide()
        left.addWidget(self.ticket_box)
        self.number_title = center(label("대기 번호", 18, muted=True))
        left.addWidget(self.number_title)
        self.number = center(label("", 110 if theme.SCALE == 1 else 84, bold=True))   # 큰 글자에서도 한 화면에
        left.addWidget(self.number)
        self.waiting = center(label("", 24, bold=True))
        left.addWidget(self.waiting)
        self.ready_hint = center(label("준비되면 번호로 불러 드릴게요.", 18, muted=True))
        left.addWidget(self.ready_hint)
        self.change_notice = center(label("", 20, bold=True))      # 거스름돈이 나왔을 때만
        self.change_notice.setStyleSheet(f"background: {theme.WARN_BG}; border-radius: 12px; padding: 10px;")
        left.addWidget(self.change_notice)
        left.addSpacing(10)
        left.addLayout(self.make_order_status())
        body.addWidget(number_card, 1)
        receipt, self.receipt = scroll_card(22)
        receipt.setFixedWidth(380)
        self.receipt.setSpacing(8)
        body.addWidget(receipt)
        layout.addLayout(body, 1)
        # 주문이 끝나도 바로 로그아웃하지 않고 묻는다. 15초 동안 답이 없으면 '아니요'(로그아웃·처음 화면).
        ask = QHBoxLayout()
        ask.setSpacing(14)
        question = QVBoxLayout()
        self.ask_label = label("", 24, bold=True)
        question.addWidget(self.ask_label)
        self.ask_hint = label("", 15, muted=True)
        self.ask_hint.setWordWrap(True)
        question.addWidget(self.ask_hint)
        ask.addLayout(question, 1)
        self.more_button = button("예 · 더 주문하기", "primary", self.order_more)
        self.finish_button = button("아니요 · 끝내기", "outline", self.finish_visit)
        for item in (self.more_button, self.finish_button):
            item.setMinimumWidth(220)
            ask.addWidget(item)
        layout.addLayout(ask)
        self.countdown = QTimer(self)
        self.countdown.setInterval(1000)
        self.countdown.timeout.connect(self.tick)
        self.seconds_left = 0

    ASK_SECONDS = 15

    def make_ticket_box(self):
        """T1-8: 나온 승차권 내용 + 바로 아래 '꼭 챙겨 주세요' 안내."""
        box = QFrame()
        box.setStyleSheet(f"QFrame {{ background: {theme.CARAMEL_LIGHT}; border-radius: 16px; }}")
        column = QVBoxLayout(box)
        column.setContentsMargins(18, 12, 18, 12)
        column.setSpacing(6)
        column.addWidget(center(label("승차권이 나왔어요", 22, bold=True)))
        self.ticket_rows = QVBoxLayout()
        self.ticket_rows.setSpacing(4)
        column.addLayout(self.ticket_rows)
        column.addWidget(notice_label())
        return box

    def show_tickets(self, order):
        clear(self.ticket_rows)
        for ticket in order.get("tickets", []):
            seats = ", ".join(str(p["seat"]) for p in ticket["passengers"])
            depart = datetime.fromisoformat(ticket["depart"])
            # 자동 줄바꿈은 큰 글자에서 눌려서 줄을 직접 나눈다
            lines = [f"{ticket['origin']} → {ticket['destination']} · {depart_text(ticket['depart'])} · {ticket['grade']}",
                     f"좌석 {seats} · {ticket['platform']}번 승차장 · {until_text(depart, datetime.now())}"]
            self.ticket_rows.addWidget(center(label("\n".join(lines), 16, bold=True)))
    # 디자인 템플릿의 Order Status. 매장 주문 화면과 아직 연결되지 않아 시간에 따라 넘어가는 시연용 표시다.
    ORDER_STEPS = (("주문 접수", 0), ("만드는 중", 3), ("마무리", 9), ("픽업 대기", 13))

    def make_order_status(self):
        row = QHBoxLayout()
        row.setSpacing(6)
        self.status_parts = []
        for index, (text, _start) in enumerate(self.ORDER_STEPS):
            if index:
                line = QFrame()
                line.setFixedHeight(3)
                line.setStyleSheet(f"background: {theme.LINE};")
                holder = QVBoxLayout()               # 선을 점 높이 가운데에 맞춘다
                holder.addSpacing(round(12 * theme.SCALE))
                holder.addWidget(line)
                holder.addStretch()
                row.addLayout(holder, 1)
                self.status_parts.append(line)
            column = QVBoxLayout()
            column.setSpacing(4)
            dot = label("●", 18, bold=True)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name = label(text, 15, bold=True)
            name.setAlignment(Qt.AlignmentFlag.AlignCenter)
            column.addWidget(dot)
            column.addWidget(name)
            column.addStretch()                  # 칸이 길어져도 점은 위에 붙어 선과 같은 높이에
            row.addLayout(column)
            self.status_parts.append((dot, name))
        return row

    def update_order_status(self):
        elapsed = self.ASK_SECONDS - self.seconds_left
        current = max(i for i, (_text, start) in enumerate(self.ORDER_STEPS) if elapsed >= start)
        steps = [part for part in self.status_parts if isinstance(part, tuple)]
        lines = [part for part in self.status_parts if not isinstance(part, tuple)]
        for index, (dot, name) in enumerate(steps):
            color = theme.ACCENT if index == current else (theme.BROWN if index < current else theme.LINE)
            dot.setStyleSheet(f"color: {color};")
            name.setStyleSheet(f"color: {theme.BROWN if index <= current else theme.TEXT2};")
        for index, line in enumerate(lines):
            line.setStyleSheet(f"background: {theme.BROWN if index < current else theme.LINE};")
        self.current_step = self.ORDER_STEPS[current][0]

    def tick(self):
        self.seconds_left -= 1
        if self.seconds_left <= 0:
            self.finish_visit()
            return
        self.update_ask()

    def update_ask(self):
        self.update_order_status()
        self.ask_label.setText(f"더 주문하시겠어요? ({self.seconds_left})")
        if self.session.is_member():
            self.ask_hint.setText("예: 로그인 그대로 메뉴로 · 아니요: 로그아웃하고 처음 화면 (시간이 지나면 아니요)")
        else:
            self.ask_hint.setText("예: 메뉴로 · 아니요: 처음 화면 (시간이 지나면 아니요)")

    def order_more(self):
        self.countdown.stop()
        self.router.show_screen("menu")         # 회원이면 로그인 그대로 My Menu부터

    def finish_visit(self):
        self.countdown.stop()
        self.router.show_screen("idle")         # 로그아웃 · 다음 손님

    def hideEvent(self, event):
        self.countdown.stop()
        super().hideEvent(event)

    def on_show(self):
        self.seconds_left = self.ASK_SECONDS
        self.update_ask()
        self.countdown.start()
        order = self.session.last_order
        if order is None:
            return
        number = int(order["id"][1:])
        self.number.setText(f"{number:03d}")
        has_tickets, has_drinks = bool(order.get("tickets")), bool(order["lines"])
        self.ticket_box.setVisible(has_tickets)
        if has_tickets:
            self.show_tickets(order)
        # 승차권이 있으면 번호를 줄이고, 승차권만 샀으면 음료 대기 번호를 숨긴다
        self.number.setFont(theme.font((64 if theme.SCALE == 1 else 48) if has_tickets
                                       else (110 if theme.SCALE == 1 else 84), bold=True))
        for widget in (self.number, self.waiting):
            widget.setVisible(has_drinks)
        self.number_title.setVisible(has_drinks and not (has_tickets and theme.SCALE > 1))
        self.ready_hint.setVisible(has_drinks and not has_tickets)
        show_status = has_drinks and not (has_tickets and theme.SCALE > 1)   # 큰 글자는 승차권 안내가 먼저
        for part in self.status_parts:
            for widget in (part if isinstance(part, tuple) else (part,)):
                widget.setVisible(show_status)
        member = order.get("customer")
        if member:
            title = f"[{member['title']}] " if member.get("title") else ""
            self.waiting.setText(f"대기자: {title}{member['nickname']}")
        else:
            self.waiting.setText(f"비회원 {number:03d}번")
        self.change_notice.setVisible(order["change"] > 0)
        self.change_notice.setText(f"거스름돈 {theme.won(order['change'])}이 나왔어요 · 반환구에서 꼭 챙겨 주세요")
        clear(self.receipt)
        self.receipt.addWidget(label("영수증", 22, title=True))
        for line in order["lines"]:
            text = f"{line['name']} × {line['quantity']}"
            if line["option_label"]:
                text += f"\n  {line['option_label']}"
            row = QHBoxLayout()
            row.addWidget(label(text, 15))
            row.addStretch()
            row.addWidget(label(theme.won(line["subtotal"]), 15, bold=True))
            self.receipt.addLayout(row)
        for ticket in order.get("tickets", []):
            row = QHBoxLayout()
            row.addWidget(label(f"승차권 {ticket['origin']}→{ticket['destination']} × {ticket['count']}\n"
                                f"  {ticket_summary(ticket)}", 15))
            row.addStretch()
            row.addWidget(label(theme.won(ticket["total"]), 15, bold=True))
            self.receipt.addLayout(row)
        if order.get("tickets"):
            self.receipt.addWidget(label("  (승차권은 쿠폰·포인트 할인·적립 제외)", 13, muted=True))
        if any(p["benefit"] != "없음" for t in order.get("tickets", []) for p in t["passengers"]):
            self.receipt.addWidget(label("  할인 승차권은 승차 때 증명서 확인", 13, muted=True))
        self.receipt.addStretch()
        discount = order.get("coupon_discount", 0) + order.get("points_used", 0)
        rows = [("주문 금액", theme.won(order["total"]))]
        if discount:
            rows.append(("쿠폰 + 포인트", f"−{theme.won(discount)}"))
        rows += [("결제 금액", theme.won(order["final_total"])), ("받은 현금", theme.won(order["cash"])),
                 ("거스름돈", theme.won(order["change"]))]
        for name, value in rows:
            row, _ = money_row(name, value, big=(name == "거스름돈"))
            self.receipt.addLayout(row)
        self.receipt.addWidget(label(breakdown_text(order["change_breakdown"]), 14, muted=True))
        if member:
            self.add_member_benefits(order, member)

    def add_member_benefits(self, order, member):
        """이번 주문으로 받은 혜택 (회원)."""
        self.receipt.addSpacing(8)
        self.receipt.addWidget(label("이번 주문으로 받은 혜택", 18, bold=True))
        events = f" ({', '.join(order['point_events'])})" if order.get("point_events") else ""
        lines = [f"적립 포인트 +{order['earned_points']:,}P{events}"]
        if order.get("change_points"):
            lines.append(f"잔돈 포인트 +{order['change_points']:,}P")
        lines.append(f"포인트 잔액 {member['points']:,}P · 방문 {member['visits']}회")
        if order.get("issued_coupon"):
            lines.append(f"새 쿠폰: {order['issued_coupon']}")
        for text in lines:
            self.receipt.addWidget(label(text, 15))
        for title in order.get("new_titles", []):
            badge = label(f"★ 새 칭호 획득 · [{title}]", 18, bold=True)
            badge.setStyleSheet(f"color: {theme.CARAMEL};")
            self.receipt.addWidget(badge)


def center(widget):
    widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return widget
