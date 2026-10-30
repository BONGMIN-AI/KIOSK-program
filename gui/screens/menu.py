"""03 메뉴: 왼쪽 카테고리 줄 + 메뉴 카드 + 오른쪽 장바구니. 04 옵션 팝업도 여기서 띄운다.

회원이면 위에 회원 카드 줄([칭호] 닉네임 · 포인트 · 쿠폰 · 방문)이 나오고, 첫 탭이 My Menu다.
My Menu = 최근 주문 보기(지난 주문을 통째로 다시 담아 장바구니로) · ♥ 좋아요 · 카페인 리포트.
승차권 탭(T1)은 My Menu 다음에 있고, 가운데 칸만 승차권 화면(gui/screens/ticket.py)으로 바뀐다.
"""

from datetime import date

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QSizePolicy,
                               QScrollArea, QStackedWidget, QVBoxLayout, QWidget)

from domain.popular import SORTS as POPULAR_SORTS
from gui import theme
from gui.order import CATEGORY_ORDER, MY_MENU, POPULAR, TICKET
from gui.screens.option import OptionPopup
from gui.screens.ticket import BusIcon, TicketCartLine, TicketPanel, saved_routes_card
from gui.widgets import (Card, CategoryIcon, CupIcon, ElidedLabel, WeekBars, button, label, menu_icon,
                         menu_photo_path, trimmed_pixmap)
CARD_MIN_WIDTH = 200     # 화면이 넓으면 한 줄에 카드를 더 놓는다 (최소 3칸)
GRID_GAP = 14


def short_options(options):
    """'ICE · L · 추가 2' 처럼 짧게 (My Menu 한 줄에 들어가게)."""
    parts = [options.get("temperature"), options.get("size")]
    extras = options.get("extras") or []
    if extras:
        parts.append(f"추가 {len(extras)}")
    return " · ".join(part for part in parts if part)


class MenuCard(Card):
    """메뉴 한 개. 누르면 옵션 팝업을 연다."""

    def __init__(self, item, on_open, badge=None):
        super().__init__()
        self.item = item
        self.on_open = on_open
        # 세로로 긴 카드: 칸 너비에 맞춰 늘어나고 높이는 고정 (나중에 실제 커피 사진을 위쪽에 넣는다)
        self.setMinimumWidth(CARD_MIN_WIDTH - 20)
        self.setFixedHeight(290)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        photo = QFrame()
        photo.setStyleSheet(f"background: {theme.CREAM}; border-radius: 14px;")
        photo_layout = QHBoxLayout(photo)
        photo_layout.setContentsMargins(0, 10, 0, 10)
        photo_layout.setContentsMargins(0, 4, 0, 4)
        size = 172 if menu_photo_path(item) else 128          # 사진은 칸을 거의 채우고, 그린 잔은 작게
        photo_layout.addWidget(menu_icon(item, size), alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(photo, 1)
        if badge:                                # 인기 탭: 사진 왼쪽 위에 '1위 · ♥ 58'
            tag = QLabel(badge, photo)
            tag.setFont(theme.font(13, bold=True))
            tag.setStyleSheet(f"background: {theme.ACCENT}; color: {theme.CARD}; border-radius: 10px;"
                              " padding: 3px 10px;")
            tag.adjustSize()
            tag.move(8, 8)
        name = label(item["name"], 18, title=True)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)
        row = QHBoxLayout()
        sold_out = item.get("sold_out") or item.get("stock", 0) <= 0
        price = label("품절" if sold_out else theme.won(item["price"]), 17)
        price.setStyleSheet(f"color: {theme.TEXT2 if sold_out else theme.CARAMEL}; font-weight: bold;")
        row.addWidget(price)
        row.addStretch()
        self.plus = button("+", "plus", lambda: self.on_open(self.item["id"]))
        self.plus.setFixedSize(40, 36)
        self.plus.setEnabled(not sold_out)
        row.addWidget(self.plus)
        layout.addLayout(row)
        self.sold_out = sold_out

    def mousePressEvent(self, event):
        if not self.sold_out:
            self.on_open(self.item["id"])


class AddLikeTile(QFrame):
    """좋아요가 없을 때의 빈 칸: 점선 네모 + 큰 '+' + 말풍선. 누르면 커피 탭으로 간다."""

    def __init__(self, on_click):
        super().__init__()
        self.on_click = on_click
        self.setObjectName("add_like")
        self.setFixedHeight(200)
        self.setMinimumWidth(CARD_MIN_WIDTH - 20)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"QFrame#add_like {{ border: 3px dashed {theme.CARAMEL}; border-radius: 20px;"
                           f" background: {theme.CREAM}; }}")
        column = QVBoxLayout(self)
        column.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bubble = label("좋아하는 음료를 추가해봐요!", 16, bold=True)
        bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bubble.setStyleSheet(f"background: {theme.CARD}; color: {theme.BROWN}; border: 2px solid {theme.LINE};"
                             " border-radius: 14px; padding: 8px 14px;")
        column.addWidget(bubble, alignment=Qt.AlignmentFlag.AlignCenter)
        plus = label("+", 56, bold=True)
        plus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plus.setStyleSheet(f"color: {theme.CARAMEL};")
        column.addWidget(plus)

    def mousePressEvent(self, event):
        self.on_click()


class MenuScreen(QWidget):
    def __init__(self, router):
        super().__init__()
        self.router = router
        self.session = router.session
        self.category = CATEGORY_ORDER[0]
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        layout.addWidget(self.make_sidebar())
        middle = QVBoxLayout()
        middle.setSpacing(12)
        middle.addWidget(self.make_top_bar())
        self.banner = self.make_banner()
        middle.addWidget(self.banner)
        self.grid_area = QScrollArea()
        self.grid_area.setWidgetResizable(True)
        self.grid_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.ticket_panel = TicketPanel(self.session, on_drinks=lambda: self.show_category(CATEGORY_ORDER[0]),
                                        on_pay=lambda: self.router.show_screen("cart"))
        self.middle_stack = QStackedWidget()      # 메뉴 카드 칸 | 승차권 탭 화면
        self.middle_stack.addWidget(self.grid_area)
        self.middle_stack.addWidget(self.ticket_panel)
        middle.addWidget(self.middle_stack, 1)
        layout.addLayout(middle, 1)
        layout.addWidget(self.make_cart_panel())
        self.popup = OptionPopup(self, self.session, on_added=self.after_popup)
        self.popup.hide()
        self.ticket_lines = []
        self.ticket_clock = QTimer(self)          # 장바구니 승차권 줄의 좌석 유지 시간
        self.ticket_clock.setInterval(1000)
        self.ticket_clock.timeout.connect(self.tick_tickets)
        self.ticket_clock.start()

    # 왼쪽 카테고리 줄
    def make_sidebar(self):
        side = Card()
        side.setFixedWidth(150)
        column = QVBoxLayout(side)
        column.setContentsMargins(12, 16, 12, 16)
        column.setSpacing(6)
        logo = QLabel()
        logo.setPixmap(trimmed_pixmap("logo_sub.png").scaled(
            60, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(f"background: {theme.LOGO_PLATE}; border-radius: 12px;")
        column.addWidget(logo)
        brand = label("COFFEE\n& SPOON", 13, title=True)
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addWidget(brand)
        column.addSpacing(4)
        self.category_buttons = QButtonGroup(self)
        for name in [MY_MENU, POPULAR, TICKET] + CATEGORY_ORDER:
            item = button("", "category", lambda checked=False, name=name: self.show_category(name))
            item.setCheckable(True)
            item.setFixedHeight(58)             # 인기·승차권 탭이 늘어 회원 9칸이 큰 글자에서도 한 화면에
            inside = QVBoxLayout(item)          # 아이콘은 크게, 이름은 작게 두 줄로
            inside.setContentsMargins(0, 3, 0, 3)
            inside.setSpacing(0)
            if theme.SCALE == 1:                # 큰 글자에서는 이름만 크게 (칸 높이는 그대로)
                icon = BusIcon(name, 30) if name == TICKET else CategoryIcon(name, 30)
                inside.addWidget(icon, alignment=Qt.AlignmentFlag.AlignCenter)
            part = label(name, 15, bold=True)
            part.setAlignment(Qt.AlignmentFlag.AlignCenter)
            part.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            inside.addWidget(part)
            item.setObjectName(f"category_{name}")
            self.category_buttons.addButton(item)
            column.addWidget(item)
        column.addStretch()
        return side

    def make_top_bar(self):
        bar = Card()
        bar.setFixedHeight(60)
        row = QHBoxLayout(bar)
        row.setContentsMargins(20, 0, 20, 0)
        row.setSpacing(16)
        self.member_name = label("비회원 주문", 19, bold=True)
        row.addWidget(self.member_name)
        self.member_detail = label("", 15, muted=True)
        row.addWidget(self.member_detail)
        row.addStretch()
        return bar

    def update_top_bar(self):
        customer = self.session.customer
        if customer is None:
            self.member_name.setText("비회원 주문")
            self.member_detail.setText("로그인 없이 주문 중 · 회원 혜택·적립은 없어요")
            return
        extra = customer["extra"]
        title = f"[{extra['title']}] " if extra.get("title") else ""
        self.member_name.setText(f"{title}{extra['nickname']} 님")
        self.member_detail.setText(f"포인트 {extra['points']:,}P   ·   쿠폰 {len(self.session.coupons())}장"
                                   f"   ·   방문 {extra['visits']}회")

    def make_banner(self):
        banner = ElidedLabel()
        banner.setFixedHeight(48)
        banner.setFont(theme.font(16, bold=True))
        banner.setContentsMargins(18, 0, 18, 0)
        return banner

    def update_banner(self):
        """운영자가 정한 진행 중 이벤트를 테마 색으로 보여 준다. 없으면 숨긴다."""
        event = self.session.current_event()
        self.banner.setVisible(event is not None)
        if event is None:
            return
        background, foreground = theme.EVENT_THEMES[event["theme"]]
        icon = "★"                     # 이모지는 PC마다 네모로 보여서 글꼴에 있는 별을 쓴다
        self.banner.setText(f"{icon}  {event['name']}  ·  {event['message']}")
        self.banner.setStyleSheet(f"background: {background}; color: {foreground}; border-radius: 14px;")

    # 오른쪽 장바구니
    def make_cart_panel(self):
        panel = Card()
        panel.setFixedWidth(300)
        column = QVBoxLayout(panel)
        column.setContentsMargins(18, 18, 18, 18)
        column.setSpacing(10)
        self.cart_title = label("장바구니", 22, title=True)
        column.addWidget(self.cart_title)
        # 담은 메뉴가 많아도 패널이 늘어나지 않도록 목록은 위아래로 밀어 본다
        cart_page = QWidget()
        self.cart_list = QVBoxLayout(cart_page)
        self.cart_list.setContentsMargins(0, 0, 0, 0)
        self.cart_list.setSpacing(8)
        self.cart_list.setAlignment(Qt.AlignmentFlag.AlignTop)
        cart_scroll = QScrollArea()
        cart_scroll.setWidgetResizable(True)
        cart_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        cart_scroll.setWidget(cart_page)
        column.addWidget(cart_scroll, 1)
        total_row = QHBoxLayout()
        total_row.addWidget(label("합계", 17, bold=True))
        total_row.addStretch()
        self.total_label = label(theme.won(0), 24, bold=True)
        total_row.addWidget(self.total_label)
        column.addLayout(total_row)
        self.check_button = button("장바구니 확인 →", "accent",    # 템플릿처럼 주문 버튼은 코랄
                                   lambda: self.router.show_screen("cart"))
        column.addWidget(self.check_button)
        column.addWidget(button("← 처음으로", "outline", lambda: self.router.show_screen("idle")))
        return panel

    # 화면 갱신
    def on_show(self):
        self.popup.hide()
        self.update_banner()
        self.update_top_bar()
        self.ticket_panel.reset()
        member = self.session.is_member()
        for item in self.category_buttons.buttons():
            if item.objectName() == f"category_{MY_MENU}":
                item.setVisible(member)
            if item.objectName() == f"category_{TICKET}":
                item.setVisible(self.session.ticket_sales_on())
        # 회원은 My Menu가 먼저, 비회원은 커피 탭부터 (플로차트)
        self.show_category(MY_MENU if member else CATEGORY_ORDER[0])

    def show_category(self, name):
        self.category = name
        for item in self.category_buttons.buttons():
            item.setChecked(item.objectName() == f"category_{name}")
        self.middle_stack.setCurrentWidget(self.ticket_panel if name == TICKET else self.grid_area)
        if name == TICKET:
            self.refresh()
            return
        if name == MY_MENU:
            self.grid_area.setWidget(self.make_my_menu())
            self.refresh()
            return
        if name == POPULAR:
            self.grid_area.setWidget(self.make_popular())
            self.refresh()
            return
        grid_widget = QWidget()
        column = QVBoxLayout(grid_widget)
        column.setContentsMargins(4, 4, 4, 4)
        column.addLayout(self.card_grid(self.session.items_in(name)))
        column.addStretch()
        self.grid_area.setWidget(grid_widget)
        self.refresh()

    def columns(self):
        width = self.grid_area.viewport().width() or 700
        return max(3, (width + GRID_GAP) // (CARD_MIN_WIDTH + GRID_GAP))

    def card_grid(self, items, badges=None):
        """메뉴 카드를 빈틈 없이 채우는 격자. 칸 수는 화면 너비로 정한다. badges: 카드 위 작은 글(인기 순위)."""
        grid = QGridLayout()
        grid.setSpacing(GRID_GAP)
        count = self.columns()
        for index, item in enumerate(items):
            badge = badges[index] if badges else None
            grid.addWidget(MenuCard(item, self.open_option, badge), index // count, index % count)
        for col in range(count):
            grid.setColumnStretch(col, 1)
        return grid

    def open_option(self, menu_id):
        self.popup.open_for(menu_id)

    def after_popup(self):
        if self.category == MY_MENU:
            self.grid_area.setWidget(self.make_my_menu())
        self.refresh()

    # 인기 탭 (10/31): 다른 손님들의 좋아요·구매 기록으로 순위
    popular_sort = "좋아요순"

    def make_popular(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(4, 4, 4, 4)
        column.setSpacing(12)
        head = QHBoxLayout()
        head.addWidget(label("인기 메뉴", 24, title=True))
        head.addStretch()
        self.sort_buttons = {}
        for sort in POPULAR_SORTS:
            chip = button(sort, "pill", lambda checked=False, sort=sort: self.set_popular_sort(sort))
            chip.setCheckable(True)
            chip.setChecked(sort == self.popular_sort)
            chip.setMinimumHeight(44)
            self.sort_buttons[sort] = chip
            head.addWidget(chip)
        column.addLayout(head)
        rows = self.session.popular(self.popular_sort)
        if not rows:
            column.addWidget(label("아직 순위를 낼 기록이 없어요", 18, muted=True))
        else:
            badges = [f"{rank}위 · {row['text']}" for rank, row in enumerate(rows, 1)]
            column.addLayout(self.card_grid([row["item"] for row in rows], badges))
        column.addWidget(label("다른 손님들의 ♥ 좋아요와 주문 기록으로 매긴 순위예요 (시연용 기본값 포함)", 13, muted=True))
        column.addStretch()
        return page

    def set_popular_sort(self, sort):
        self.popular_sort = sort
        # 누른 버튼이 들어 있는 화면을 바꾸므로 클릭이 끝난 뒤에 다시 그린다
        QTimer.singleShot(0, lambda: self.category == POPULAR and self.grid_area.setWidget(self.make_popular()))

    # My Menu (회원 첫 화면)
    def make_my_menu(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(4, 4, 4, 4)
        column.setSpacing(14)
        # Quick Order / 좋아요한 음료 / 카페인 리포트 — 세 구간을 각각 카드 블록으로 나눈다
        column.addWidget(self.make_quick_order())
        if self.session.ticket_sales_on():       # 승차권을 살 때 저장한 노선 (회원)
            column.addWidget(saved_routes_card(self.session, self.open_saved_route, self.forget_route))
        column.addWidget(self.make_likes_card())
        column.addWidget(self.make_caffeine_card())
        column.addStretch()
        return page

    def open_saved_route(self, origin, destination):
        self.show_category(TICKET)
        self.ticket_panel.open_route_for(origin, destination)

    def forget_route(self, origin, destination):
        self.session.forget_route(origin, destination)
        # 누른 버튼이 들어 있는 화면을 바꾸므로 클릭이 끝난 뒤에 다시 그린다
        QTimer.singleShot(0, lambda: self.category == MY_MENU and self.grid_area.setWidget(self.make_my_menu()))

    def make_likes_card(self):
        card = Card()
        column = QVBoxLayout(card)
        column.setContentsMargins(18, 14, 18, 16)
        column.setSpacing(10)
        column.addWidget(label("♥ 좋아요한 음료", 14, bold=True))
        likes = self.session.likes()
        if likes:
            column.addLayout(self.card_grid(likes[:6]))
        else:
            row = QHBoxLayout()
            self.add_like_tile = AddLikeTile(lambda: self.show_category(CATEGORY_ORDER[0]))
            row.addWidget(self.add_like_tile, 1)
            hint = label("메뉴 옵션 창의 ♡를 누르면\n여기에 모여요", 15, muted=True)
            row.addWidget(hint, 1)
            column.addLayout(row)
        return card

    def make_quick_order(self):
        """'최근 주문 보기' (10/31: 예전 Quick Order는 여러 잔을 시켜도 첫 잔만 담겼다)."""
        card = Card()
        column = QVBoxLayout(card)
        column.setContentsMargins(18, 14, 18, 14)
        column.setSpacing(10)
        recent = self.session.recent()
        self.quick_button = None
        row = QHBoxLayout()
        row.setSpacing(18)
        text = QVBoxLayout()
        text.addWidget(label("최근 주문 보기", 14, bold=True))
        if recent is None:
            row.addWidget(CupIcon("latte", 96))
            text.addWidget(label("아직 주문 기록이 없어요", 22, title=True))
            text.addWidget(label("첫 주문 뒤 여기에 최근 주문이 생겨요", 15, muted=True))
            row.addLayout(text, 1)
            column.addLayout(row)
            return card
        lines = recent["lines"]
        row.addWidget(menu_icon(self.session.menu()[lines[0]["menu_id"]], 96))
        for line in lines[:3]:                   # 세 줄까지 보여 주고 나머지는 '외 n개'
            detail = f"  {short_options(line['options'])}" if line["options"] else ""
            row_text = ElidedLabel(f"{line['name']} × {line['quantity']}{detail}")
            row_text.setFont(theme.font(17, bold=True))
            text.addWidget(row_text)
        if len(lines) > 3:
            text.addWidget(label(f"외 {len(lines) - 3}가지", 15, muted=True))
        total = sum(self.session.unit_price(line["menu_id"], line["options"]) * line["quantity"] for line in lines)
        price = label(f"총 {recent['count']}개 · {theme.won(total)} (지금 가격)", 16, bold=True)
        price.setStyleSheet(f"color: {theme.CARAMEL};")
        text.addWidget(price)
        row.addLayout(text, 1)
        self.quick_button = button("다시 담기 ▶", "secondary", lambda: self.reorder(lines))
        self.quick_button.setMinimumHeight(64)
        row.addWidget(self.quick_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        column.addLayout(row)
        return card

    def reorder(self, lines, go_cart=True):
        """최근 주문(여러 줄)을 장바구니에 담고 장바구니 화면에서 확인한다."""
        try:
            self.session.add_lines(lines)
        except ValueError as error:
            self.router.notify(str(error), 5)
            return
        if go_cart:
            self.router.show_screen("cart")
        else:
            self.refresh()
            self.router.notify(f"{lines[0]['name']} 1잔을 담았어요", 3)

    def make_caffeine_card(self):
        report = self.session.caffeine()
        card = Card()
        row = QHBoxLayout(card)
        row.setContentsMargins(18, 14, 18, 14)
        row.setSpacing(18)
        row.addWidget(WeekBars(report["this_week"], date.today().weekday()))
        text = QVBoxLayout()
        text.addWidget(label("카페인 리포트", 14, bold=True))
        text.addWidget(label(f"이번 주 {report['total']:,}mg", 24, title=True))
        change = report["change_percent"]
        compare = "" if change is None else f" · 지난주 대비 {'▲' if change >= 0 else '▼'}{abs(change)}%"
        text.addWidget(label(report["message"] + compare, 15, muted=True))
        if report["suggest_decaf"]:
            text.addWidget(label("오늘은 디카페인 어때요? → 디카페인 탭", 15, bold=True))
        row.addLayout(text, 1)
        return card

    def refresh(self):
        while self.cart_list.count():
            widget = self.cart_list.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)   # 바로 화면에서 떼어 낸다
        self.ticket_lines = [TicketCartLine(self.session, ticket, self.remove_ticket)
                             for ticket in self.session.tickets]
        for line in self.ticket_lines:            # 승차권 줄이 먼저, 음료 줄은 아래 (와이어프레임 T1-7)
            self.cart_list.addWidget(line)
        lines = self.session.lines()
        for line in lines:
            self.cart_list.addWidget(self.make_cart_line(line))
        if self.session.is_empty():
            empty = label("메뉴를 고르면 여기에 담겨요", 15, muted=True)
            self.cart_list.addWidget(empty)
        self.cart_title.setText(f"장바구니 · {self.session.count()}개")
        self.total_label.setText(theme.won(self.session.total()))
        self.check_button.setEnabled(not self.session.is_empty())

    def remove_ticket(self, hold_id):
        self.session.remove_ticket(hold_id)
        self.refresh()

    def tick_tickets(self):
        """좌석 유지 시간을 줄이고, 다 지난 승차권은 장바구니에서 빼고 알린다."""
        if not self.isVisible() or not self.session.tickets:
            return
        if self.session.expire_tickets():
            self.router.notify("좌석을 잡아 둔 5분이 지나 승차권을 장바구니에서 뺐어요 · 다시 골라 주세요", 6)
            self.refresh()
            return
        for line in self.ticket_lines:
            line.update_time()

    def make_cart_line(self, line):
        box = QFrame()
        box.setStyleSheet(f"background: {theme.CREAM}; border-radius: 14px;")
        row = QHBoxLayout(box)
        row.setContentsMargins(10, 8, 10, 8)
        text = QVBoxLayout()
        text.setSpacing(0)
        text.addWidget(label(line["name"], 15, title=True))
        if line["option_label"]:
            text.addWidget(label(line["option_label"], 12, muted=True))
        price = label(theme.won(line["subtotal"]), 14)
        price.setStyleSheet(f"color: {theme.CARAMEL}; font-weight: bold;")
        text.addWidget(price)
        row.addLayout(text, 1)
        for symbol, delta in (("−", -1), ("+", 1)):
            step = button(symbol, "outline",
                          lambda checked=False, key=line["key"], q=line["quantity"] + delta:
                          self.change_quantity(key, q))
            side = 34 if theme.SCALE == 1 else 40
            step.setFixedSize(side, side)
            step.setStyleSheet("padding: 0;")
            row.addWidget(step)
            if delta < 0:
                row.addWidget(label(str(line["quantity"]), 15, bold=True))
        return box

    def change_quantity(self, key, quantity):
        try:
            self.session.change(key, quantity)
        except ValueError as error:
            self.router.notify(str(error), 4)    # 재고·최대 수량을 넘으면 그대로 두고 이유를 알린다
        self.refresh()

    def resizeEvent(self, event):
        self.popup.setGeometry(self.rect())
        super().resizeEvent(event)
        # 창 크기가 바뀌어 한 줄 칸 수가 달라지면 카드를 다시 놓는다
        if getattr(self, "shown_columns", None) not in (None, self.columns()):
            self.show_category(self.category)
        self.shown_columns = self.columns()
