"""03 메뉴: 왼쪽 카테고리 줄 + 메뉴 카드 + 오른쪽 장바구니. 04 옵션 팝업도 여기서 띄운다.

회원이면 위에 회원 카드 줄([칭호] 닉네임 · 포인트 · 쿠폰 · 방문)이 나오고, 첫 탭이 My Menu다.
My Menu = 최근 주문 보기(지난 주문을 통째로 다시 담아 장바구니로) · ♥ 좋아요 · 카페인 리포트(그래프 · 알리미).
승차권 탭(T1)은 My Menu 다음에 있고, 가운데 칸만 승차권 화면(gui/screens/ticket.py)으로 바뀐다.
"""

import time
from io import BytesIO

from PIL import Image, ImageDraw

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel, QSizePolicy,
                               QScrollArea, QStackedWidget, QVBoxLayout, QWidget)

from domain.member_cards import lost as card_lost
from domain.my_menu import LIMIT_UNITS, TREND_VIEWS
from domain.popular import SORTS as POPULAR_SORTS
from domain.titles import title_name
from domain.customers import call_name
from gui import theme
from gui.order import CATEGORY_ORDER, MY_MENU, POPULAR, TICKET
from gui.screens.option import OptionPopup
from gui.screens.ticket import BusIcon, TicketCartLine, TicketPanel, clear, saved_routes_card
from gui.widgets import (FixedWidthCard, Card, CategoryIcon, ConfirmBox, CupIcon, ElidedLabel, GearButton, LimitBar, Overlay,
                         TapLabel, TrendBars, button, card_cart_line, label, link_button, menu_icon,
                         menu_photo_path, trimmed_pixmap)
CARD_MIN_WIDTH = 200     # 화면이 넓으면 한 줄에 카드를 더 놓는다 (최소 3칸)
GRID_GAP = 14
_popular_photo_cache = {}


def popular_wide_photo(path, width=300, height=148):
    """정사각 메뉴 사진의 가장자리를 같은 배경색으로 이어 가로 칸에 맞춘다."""
    key = (str(path), width, height)
    if key not in _popular_photo_cache:
        source = Image.open(path).convert("RGB")
        w, h = source.size
        corners = [source.getpixel(point) for point in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
        background = tuple(sum(color[channel] for color in corners) // 4 for channel in range(3))
        top = max(0, min(12, 172 - height))              # 148 높이는 위 12px를 잘라 가운데, 172는 사진 그대로
        foreground = source.resize((172, 172), Image.Resampling.LANCZOS).crop((0, top, 172, top + height))
        canvas = Image.new("RGB", (width, height), background)
        fade = Image.new("L", (172, height))
        draw = ImageDraw.Draw(fade)
        for col in range(172):
            opacity = round(255 * min(1, col / 34, (171 - col) / 34))
            draw.line((col, 0, col, height), fill=opacity)
        canvas.paste(foreground, ((width - 172) // 2, 0), fade)
        canvas = canvas.convert("RGBA")
        rounded = Image.new("L", (width, height))
        ImageDraw.Draw(rounded).rounded_rectangle((0, 0, width - 1, height - 1), radius=14, fill=255)
        canvas.putalpha(rounded)
        data = BytesIO()
        canvas.save(data, format="PNG")
        pixmap = QPixmap()
        pixmap.loadFromData(data.getvalue())
        _popular_photo_cache[key] = pixmap, background
    return _popular_photo_cache[key]


def short_options(options):
    """'ICE · L · 추가 2' 처럼 짧게 (My Menu 한 줄에 들어가게)."""
    parts = [options.get("temperature"), options.get("size")]
    extras = options.get("extras") or []
    if extras:
        parts.append(f"추가 {len(extras)}")
    return " · ".join(part for part in parts if part)


class WidePhoto(QLabel):
    """카드 너비가 바뀔 때마다 그 너비로 넓힌 사진을 다시 그린다 (늘려 찌그러뜨리지 않는다)."""

    def __init__(self, path, height=148):
        super().__init__()
        self.path = path
        self.setFixedHeight(height)
        self.setMinimumWidth(1)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setPixmap(popular_wide_photo(path, height=height)[0])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = max(172, self.width())
        if self.pixmap().width() != width:
            self.setPixmap(popular_wide_photo(self.path, width, self.height())[0])


class MenuCard(Card):
    """메뉴 한 개. 누르면 옵션 팝업을 연다."""

    def __init__(self, item, on_open, badge=None, wide_photo=False):
        super().__init__()
        self.item = item
        self.on_open = on_open
        # 세로로 긴 카드: 칸 너비에 맞춰 늘어나고 높이는 고정 (나중에 실제 커피 사진을 위쪽에 넣는다)
        self.setMinimumWidth(CARD_MIN_WIDTH - 20)
        self.setFixedHeight(260 if badge else 290)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        photo = QFrame()
        photo.setStyleSheet(f"background: {theme.CREAM}; border-radius: 14px;")
        photo_layout = QHBoxLayout(photo)
        photo_layout.setContentsMargins(0, 10, 0, 10)
        photo_layout.setContentsMargins(0, 4, 0, 4)
        path = menu_photo_path(item)
        if badge and path:
            pixmap, background = popular_wide_photo(path)
            photo.setStyleSheet(f"background: rgb{background}; border-radius: 14px;")
            photo_layout.setContentsMargins(0, 0, 0, 0)
            picture = QLabel()
            picture.setPixmap(pixmap)
            picture.setScaledContents(True)
            picture.setFixedHeight(148)
            picture.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            photo_layout.addWidget(picture)
        elif path:          # 사진 칸을 사진 가장자리 색으로 채워 사진만 떠 보이지 않게 (좋아요 카드 11/09, 모든 메뉴 카드 11/09)
            height = 148 if wide_photo else 172
            background = popular_wide_photo(path, height=height)[1]
            photo.setStyleSheet(f"background: rgb{background}; border-radius: 14px;")
            photo_layout.setContentsMargins(0, 0, 0, 0)
            photo_layout.addWidget(WidePhoto(path, height), alignment=Qt.AlignmentFlag.AlignVCenter)
        else:
            photo_layout.addWidget(menu_icon(item, 128), alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(photo, 1)
        tag_text = badge or ("신메뉴" if item.get("new_menu") else None)
        if tag_text:                             # 인기 순위 또는 신메뉴 표시
            tag = QLabel(tag_text, photo)
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
        bubble = label("좋아하는 음료를\n추가해봐요!", 16, bold=True)
        bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bubble.setStyleSheet(f"color: {theme.BROWN};")
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
        self.built_columns = None                 # 지금 카드 격자를 몇 칸으로 놓았는지
        self.grid_area.installEventFilter(self)
        self.ticket_panel = TicketPanel(self.session, on_drinks=lambda: self.show_category(CATEGORY_ORDER[0]),
                                        on_pay=lambda: self.router.show_screen("cart"))
        self.ticket_panel.on_cart = self.refresh
        self.middle_stack = QStackedWidget()      # 메뉴 카드 칸 | 승차권 탭 화면
        self.middle_stack.addWidget(self.grid_area)
        self.middle_stack.addWidget(self.ticket_panel)
        middle.addWidget(self.middle_stack, 1)
        layout.addLayout(middle, 1)
        self.cart_panel = self.make_cart_panel()
        layout.addWidget(self.cart_panel)
        self.popup = OptionPopup(self, self.session, on_added=self.after_popup)
        self.popup.hide()
        self.confirm_box = ConfirmBox(self)       # 카페인 알리미 '그래도 담을까요?' (최근 주문 다시 담기)
        self.staff_box = ConfirmBox(self)
        self.staff_box.no_button.setText("취소")
        self.staff_box.no_button.clicked.connect(self.cancel_staff_call)
        self.staff_timer = QTimer(self)
        self.staff_timer.setInterval(1000)
        self.staff_timer.timeout.connect(self.tick_staff_call)
        self.staff_seconds = 0
        self.caffeine_settings = self.make_caffeine_settings()   # 톱니바퀴 → 알리미 설정 창
        self.titles_sheet = self.make_titles_sheet()             # E21 칭호 진행 현황
        self.ticket_lines = []
        self.ticket_clock = QTimer(self)          # 장바구니 승차권 줄의 좌석 유지 시간
        self.ticket_clock.setInterval(1000)
        self.ticket_clock.timeout.connect(self.tick_tickets)
        self.ticket_clock.start()

    # 왼쪽 카테고리 줄
    def make_sidebar(self):
        side = FixedWidthCard(150)
        column = QVBoxLayout(side)
        column.setContentsMargins(12, 16, 12, 16)
        column.setSpacing(0)
        logo = TapLabel(self.logo_tap)          # E22: 빠르게 다섯 번 누르면 숨은 쿠폰
        self.taps, self.last_tap = 0, 0.0
        logo.setPixmap(trimmed_pixmap("logo_sub.png").scaled(
            60, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(f"background: {theme.LOGO_PLATE}; border-radius: 12px;")
        column.addWidget(logo)
        brand = label("COFFEE\n& SPOON", 13, title=True)
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addWidget(brand)
        column.addSpacing(4)
        buttons_layout = QVBoxLayout()
        buttons_layout.setSpacing(0)
        column.addLayout(buttons_layout, 1)
        self.category_buttons = QButtonGroup(self)
        for name in [MY_MENU, POPULAR, TICKET] + CATEGORY_ORDER:
            item = button("", "category", lambda checked=False, name=name: self.show_category(name))
            item.setCheckable(True)
            item.setFixedHeight(66)
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
            buttons_layout.addWidget(item)
            if name != CATEGORY_ORDER[-1]:
                buttons_layout.addStretch(1)
        return side

    def make_top_bar(self):
        bar = Card()
        bar.setFixedHeight(60)
        row = QHBoxLayout(bar)
        row.setContentsMargins(20, 0, 20, 0)
        row.setSpacing(16)
        self.member_name = TapLabel(self.open_titles)    # E21: 회원 이름을 누르면 칭호 진행 현황
        self.member_name.setFont(theme.font(19, bold=True))
        self.member_name.setText("비회원 주문")
        row.addWidget(self.member_name)
        self.member_detail = ElidedLabel()
        self.member_detail.setFont(theme.font(15))
        self.member_detail.setStyleSheet(f"color: {theme.TEXT2};")
        row.addWidget(self.member_detail, 1)
        self.lost_card_link = link_button("회원카드를 잃어버렸어요", self.card_link_clicked)
        row.addWidget(self.lost_card_link)
        # 11/09: 얼굴 등록 · 회원카드 구매는 직원호출 왼쪽에 갈색 버튼으로 (My Menu에서, 필요한 회원에게만)
        self.face_button = button("얼굴 등록", "primary",
                                  lambda: self.router.show_screen("enroll", customer=self.session.customer))
        self.card_buy_button = button("회원카드 구매", "primary", self.buy_card)
        for item in (self.face_button, self.card_buy_button):
            item.setFixedHeight(42)
            item.hide()
            row.addWidget(item)
        self.staff_button = button("직원호출", "outline", self.call_staff)
        self.staff_button.setFixedSize(126, 42)
        row.addWidget(self.staff_button)
        return bar

    def call_staff(self):
        """5초 안에 취소할 수 있는 직원 호출 확인 창."""
        self.staff_seconds = 5
        self.staff_box.ask("직원 호출", "직원을 부를게요", "확인(5)", self.confirm_staff_call)
        self.staff_timer.start()

    def cancel_staff_call(self):
        self.staff_timer.stop()

    def tick_staff_call(self):
        self.staff_seconds -= 1
        if self.staff_seconds <= 0:
            self.staff_box.yes()
        else:
            self.staff_box.yes_button.setText(f"확인({self.staff_seconds})")

    def confirm_staff_call(self):
        self.staff_timer.stop()
        from PySide6.QtWidgets import QApplication
        QApplication.beep()
        self.staff_box.tell("직원 호출", "직원을 불렀어요")
        self.staff_box.on_yes = None

    def buy_card(self):
        """'회원카드 구매': 새 회원카드를 장바구니에 담는다 (음료와 함께 결제)."""
        try:
            self.session.add_card("new")
        except ValueError as error:
            self.router.notify(str(error), 5)
            return
        fee = self.session.card_total()
        self.router.notify(f"회원카드({fee:,}원)를 장바구니에 담았어요\n음료와 함께 결제해 주세요", 4)
        self.after_card_change()

    def card_link_clicked(self):
        if self.session.card_status():
            self.ask_lost_card()
        elif self.session.customer is not None and card_lost(self.session.customer):
            self.add_reissue_card()

    def logo_tap(self):
        """1초 안 간격으로 다섯 번 누르면 이스터에그 (E22)."""
        now = time.monotonic()
        self.taps = self.taps + 1 if now - self.last_tap <= 1.0 else 1
        self.last_tap = now
        if self.taps >= 5:
            self.taps = 0
            self.router.easter_egg()

    def make_titles_sheet(self):
        """E21 칭호 진행 현황: 칭호마다 지금 수 / 목표 수 막대."""
        sheet = Overlay(self, 600)
        sheet.body.addWidget(label("칭호 진행 현황", 26, title=True))
        self.title_rows = QVBoxLayout()
        self.title_rows.setSpacing(10)
        sheet.body.addLayout(self.title_rows)
        sheet.body.addWidget(button("닫기", "primary", sheet.hide))
        return sheet

    def open_titles(self):
        if self.session.customer is None:
            return
        clear(self.title_rows)
        for item in self.session.title_progress():
            head = QHBoxLayout()
            name = label(item["title"], 18, bold=True)
            head.addWidget(name)
            head.addWidget(label(item["description"], 14, muted=True), 1)
            head.addWidget(label("달성" if item["done"] else f"{item['count']} / {item['goal']}", 16, bold=True))
            self.title_rows.addLayout(head)
            bar = LimitBar()
            bar.set_ratio(item["count"] / item["goal"])
            self.title_rows.addWidget(bar)
        self.titles_sheet.open()

    def update_top_bar(self):
        customer = self.session.customer
        self.member_name.setCursor(Qt.CursorShape.ArrowCursor if customer is None else Qt.CursorShape.PointingHandCursor)
        if customer is None:
            self.member_name.setText("비회원 주문")
            self.member_detail.setText("로그인 없이 주문 중 · 회원 혜택·적립은 없어요")
            self.staff_button.hide()
            self.lost_card_link.hide()
            self.face_button.hide()
            self.card_buy_button.hide()
            return
        on_my_menu = self.category == MY_MENU
        self.face_button.setVisible(on_my_menu and not customer["extra"].get("face_enrolled"))
        self.card_buy_button.setVisible(on_my_menu and not self.session.card_status() and not card_lost(customer)
                                        and self.session.card_kind is None)
        extra = customer["extra"]
        title = f"[{title_name(extra['title'])}] " if extra.get("title") else ""
        self.member_name.setText(f"{title}{call_name(customer)} 님 ›")      # 11/04: 닉네임보다 이름
        card = {"회원카드 등록 전": "카드 등록 전"}.get(self.session.card_status(), "")
        card = f"  ·  {card}" if card else ""
        self.member_detail.setText(f"포인트 {extra['points']:,}P  ·  쿠폰 {len(self.session.coupons())}장"
                                   f"  ·  방문 {extra['visits']}회{card}")
        self.staff_button.show()
        status = self.session.card_status()
        reissue = card_lost(customer) and self.session.card_kind != "reissue"
        self.lost_card_link.setVisible(self.category == MY_MENU and (bool(status) or reissue))
        if reissue and not status:
            fee = self.session.policy()["card_reissue_fee"]
            self.lost_card_link.setText(f"회원카드 재발급 ({fee:,}원) 장바구니에 담기")
        else:
            self.lost_card_link.setText("회원카드를 잃어버렸어요")

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
        panel = FixedWidthCard(300)
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
        leave = button("처음으로", "outline", self.router.ask_leave)     # 회원이면 '로그아웃' (11/04)
        leave.setObjectName("leave_button")
        column.addWidget(leave)
        return panel

    # 화면 갱신
    def on_show(self):
        self.popup.hide()
        self.confirm_box.hide()
        self.staff_timer.stop()
        self.staff_box.hide()
        self.caffeine_settings.hide()
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
        self.update_top_bar()
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
        # 스크롤바가 생기고 없어짐에 따라 칸 수가 오락가락하지 않게, 스크롤 칸 바깥 너비에서 스크롤바 몫을 늘 뺀다
        bar = self.grid_area.verticalScrollBar().sizeHint().width()
        width = (self.grid_area.width() - bar - 10) if self.grid_area.width() > 100 else 700
        if self.category == POPULAR:
            return 4 if width >= 1060 else 3
        card = round(CARD_MIN_WIDTH * theme.SCALE)        # 큰 글자는 카드도 조금 넓게 (이름이 잘리지 않게)
        return max(3, (width + GRID_GAP) // (card + GRID_GAP))

    def eventFilter(self, watched, event):
        # 11/09: 화면을 만든 때의 너비가 아니라 실제로 놓인 너비로 칸 수를 맞춘다
        # (처음 들어갈 때 3칸 → 나중에 6칸처럼 달라져 '큰 글자가 남은 것'처럼 보이던 문제)
        if (watched is self.grid_area and event.type() == QEvent.Type.Resize
                and self.built_columns is not None and self.category != TICKET
                and self.columns() != self.built_columns):
            self.built_columns = None
            QTimer.singleShot(0, self, lambda: self.show_category(self.category))
        return super().eventFilter(watched, event)

    def card_grid(self, items, badges=None, wide_photo=False):
        """메뉴 카드를 빈틈 없이 채우는 격자. 칸 수는 화면 너비로 정한다. badges: 카드 위 작은 글(인기 순위)."""
        grid = QGridLayout()
        grid.setSpacing(GRID_GAP)
        count = self.columns()
        self.built_columns = count
        for index, item in enumerate(items):
            badge = badges[index] if badges else None
            grid.addWidget(MenuCard(item, self.open_option, badge, wide_photo), index // count, index % count)
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
        column.addStretch()
        return page

    def set_popular_sort(self, sort):
        self.popular_sort = sort
        # 누른 버튼이 들어 있는 화면을 바꾸므로 클릭이 끝난 뒤에 다시 그린다
        QTimer.singleShot(0, lambda: self.category == POPULAR and self.grid_area.setWidget(self.make_popular()))

    # My Menu (회원 첫 화면)
    def make_my_menu(self):
        with theme.font_adjust(4):
            return self._make_my_menu_content()

    def _make_my_menu_content(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(4, 4, 4, 4)
        column.setSpacing(14)
        # Quick Order / 좋아요한 음료 / 카페인 리포트 — 세 구간을 각각 카드 블록으로 나눈다
        if self.session.card_status() == "회원카드 등록 전":     # 11/03: 산 카드를 손님이 직접 등록
            column.addWidget(self.make_card_register())
        pair = QHBoxLayout()
        pair.setSpacing(18)
        quick = self.make_quick_order()
        quick.setFixedHeight(265)
        pair.addWidget(quick, 1)
        if self.session.ticket_sales_on():       # 승차권을 살 때 저장한 노선 (회원)
            divider = QFrame()
            divider.setObjectName("my_menu_vertical_divider")
            divider.setFixedWidth(2)
            divider.setStyleSheet(f"background: {theme.CARAMEL_LIGHT}; border: none;")
            glow = QGraphicsDropShadowEffect(divider)
            glow.setBlurRadius(16)
            glow.setOffset(0, 0)
            glow.setColor(QColor(139, 79, 31, 100))
            divider.setGraphicsEffect(glow)
            pair.addWidget(divider)
            routes = saved_routes_card(self.session, self.open_saved_route, self.forget_route)
            routes.setFixedHeight(265)
            pair.addWidget(routes, 1)
        column.addLayout(pair)
        likes = self.make_likes_card()
        likes.setFixedHeight(330)
        column.addWidget(likes)
        caffeine = self.make_caffeine_card()
        caffeine.setFixedHeight(round(280 * theme.SCALE))   # 11/09: 큰 글자에서 글이 겹치지 않게 칸도 키운다
        column.addWidget(caffeine)
        column.addStretch()
        return page

    def make_card_register(self):
        """My Menu 맨 위: 결제한 회원카드를 등록하는 줄 (산 바로 그 자리에서도 된다)."""
        card = Card()
        card.setObjectName("card_register")       # 바탕색이 안쪽 버튼까지 번지지 않게 이 상자에만
        card.setStyleSheet(f"#card_register {{ background: {theme.CARAMEL_LIGHT}; border-radius: 18px; }}")
        row = QHBoxLayout(card)
        row.setContentsMargins(20, 12, 16, 12)
        text = QVBoxLayout()
        text.addWidget(label("받으신 회원카드를 등록해 주세요", 18, bold=True))
        policy = self.session.policy()
        text.addWidget(label(f"등록하는 이번 주문 {policy['card_first_discount']}% 할인 · "
                             f"매 주문 {policy['card_point_rate']:g}% 적립", 14, muted=True))
        row.addLayout(text, 1)
        self.card_register_button = button("카드 등록", "primary", self.wait_card_register)
        self.card_register_button.setMinimumHeight(56)
        row.addWidget(self.card_register_button)
        return card

    def wait_card_register(self):
        """'카드 등록' → 위쪽 띠에 남은 초. 그 사이 리더기에 카드를 대면 router.member_card_tap이 등록한다."""
        customer_id = self.session.customer["id"]
        from domain.member_cards import unused_card
        alive = lambda: (self.isVisible() and self.session.customer is not None
                         and unused_card(self.session.vault, customer_id) is not None)
        self.router.notice.show_countdown(lambda s: f"받으신 회원카드를 리더기에 대 주세요 · {s}초", 20, alive)

    def ask_lost_card(self):
        fee = self.session.policy()["card_reissue_fee"]
        self.confirm_box.ask("회원카드 분실 신고", f"예전 카드는 바로 쓸 수 없게 막아요.\n"
                             f"새 카드({fee:,}원)를 장바구니에 담을까요?", "예, 분실 신고", self.report_lost_card)

    def report_lost_card(self):
        self.session.report_lost_card()
        self.router.audit("card_lost", self.session.customer["id"])
        self.router.notify("예전 카드를 막았어요.\n새 카드를 장바구니에 담았어요 · 음료와 함께 결제해 주세요", 7)
        self.after_card_change()

    def add_reissue_card(self):
        try:
            self.session.add_card("reissue")
        except ValueError as error:
            self.router.notify(str(error), 5)
            return
        self.router.notify("재발급 카드를 장바구니에 담았어요", 4)
        self.after_card_change()

    def after_card_change(self):
        self.update_top_bar()
        self.refresh()
        if self.category == MY_MENU:              # 그 사이 처음 화면으로 갔으면(회원 없음) 다시 그리지 않는다
            QTimer.singleShot(0, lambda: self.category == MY_MENU and self.session.customer is not None
                              and self.show_category(MY_MENU))

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
            column.addLayout(self.card_grid(likes[:6], wide_photo=True))
            for tile in card.findChildren(MenuCard):
                tile.setFixedHeight(260)
        else:
            row = QHBoxLayout()
            self.add_like_tile = AddLikeTile(lambda: self.show_category(CATEGORY_ORDER[0]))
            self.add_like_tile.setFixedSize(226, 260)
            row.addWidget(self.add_like_tile)
            row.addStretch()
            column.addLayout(row)
        return card

    def make_quick_order(self):
        """'최근 주문 보기' (10/31: 예전 Quick Order는 여러 잔을 시켜도 첫 잔만 담겼다)."""
        card = Card()
        column = QVBoxLayout(card)
        column.setContentsMargins(18, 14, 18, 14)
        column.setSpacing(16)
        recent = self.session.recent()
        self.quick_button = None
        head = QHBoxLayout()
        head.addWidget(label("최근 주문 보기", 14, bold=True), alignment=Qt.AlignmentFlag.AlignTop)
        head.addStretch()
        if recent is None:
            column.addLayout(head)
            column.addWidget(label("아직 주문 기록이 없어요", 22, title=True))
            column.addWidget(label("첫 주문 뒤 여기에 최근 주문이 생겨요", 15, muted=True))
            column.addStretch()
            return card
        lines = recent["lines"]
        self.quick_button = button("다시 담기 ▶", "secondary", lambda: self.reorder(lines))
        self.quick_button.setMinimumHeight(56)
        head.addWidget(self.quick_button, alignment=Qt.AlignmentFlag.AlignTop)
        column.addLayout(head)
        row = QHBoxLayout()
        row.setSpacing(22)
        photo = menu_icon(self.session.menu()[lines[0]["menu_id"]], 165,
                          (lines[0]["options"] or {}).get("temperature"))
        shadow = QGraphicsDropShadowEffect(photo)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(58, 29, 8, 65))
        photo.setGraphicsEffect(shadow)
        row.addWidget(photo, alignment=Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(13)
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
        text.addStretch()
        row.addLayout(text, 1)
        column.addLayout(row)
        column.addStretch()
        return card

    def reorder(self, lines, go_cart=True, caffeine_ok=False):
        """최근 주문(여러 줄)을 장바구니에 담고 장바구니 화면에서 확인한다."""
        note = None if caffeine_ok else self.session.caffeine_warning(lines)
        if note:                                 # 알리미 제한을 넘으면 먼저 묻는다 (아니요 = 그대로)
            self.confirm_box.ask("카페인 알리미", note + "\n그래도 담을까요?", "예, 담기",
                                 lambda: self.reorder(lines, go_cart, caffeine_ok=True))
            return
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

    caffeine_view = "이번 주"
    LIMIT_STEP = {"잔": 1, "mg": 50}
    LIMIT_START = {"잔": 3, "mg": 400}            # 단위를 처음 고르면 이 값부터

    def make_caffeine_card(self):
        """카페인 리포트 (10/31): 그래프(이번 주·주별·월별) + 이번 주 섭취량 + 카페인 알리미 상태.

        제한 바꾸기는 오른쪽 위 톱니바퀴 → 설정 창(make_caffeine_settings)에서 한다.
        """
        report = self.session.caffeine()
        card = Card()
        column = QVBoxLayout(card)
        column.setContentsMargins(18, 14, 18, 16)
        column.setSpacing(10)
        head = QHBoxLayout()
        head.addWidget(label("카페인 리포트", 14, bold=True))
        head.addStretch()
        self.view_buttons = {}
        for view in TREND_VIEWS:
            chip = button(view, "pill", lambda checked=False, view=view: self.set_caffeine_view(view))
            chip.setCheckable(True)
            chip.setChecked(view == self.caffeine_view)
            chip.setMinimumHeight(44)           # 22px 둥근 칩은 높이 44 이상이어야 둥글게 그려진다
            self.view_buttons[view] = chip
            head.addWidget(chip)
        self.gear_button = GearButton(self.open_caffeine_settings)
        head.addWidget(self.gear_button)
        column.addLayout(head)
        body = QHBoxLayout()
        body.setSpacing(22)
        trend = self.session.caffeine_trend(self.caffeine_view)
        self.trend_bars = TrendBars(trend["labels"], trend["values"], trend["current"],
                                    on_click=self.next_caffeine_view)
        body.addWidget(self.trend_bars, 3)
        text = QVBoxLayout()
        text.setSpacing(4)
        text.addWidget(label("이번 주 카페인 섭취량", 15, muted=True))
        amount = label(f"{report['total']:,}mg", 30, title=True)
        amount.setMinimumHeight(amount.fontMetrics().height() + 6)
        text.addWidget(amount)
        message = label(report["message"], 15, bold=True, guide=True)
        text.addWidget(message)
        text.addSpacing(8)
        self.alert_title = label("", 15, bold=True)  # 카페인 알리미 상태 (제한 대비 막대)
        text.addWidget(self.alert_title)
        self.alert_bar = LimitBar()
        text.addWidget(self.alert_bar)
        self.alert_text = label("", 14, muted=True, guide=True)
        text.addWidget(self.alert_text)
        text.addStretch()
        body.addLayout(text, 2)
        column.addLayout(body)
        self.show_limit()
        self.update_trend_limit()
        return card

    def make_caffeine_settings(self):
        """톱니바퀴를 누르면 뜨는 카페인 알리미 설정 창: 단위(잔/mg)와 이번 주 제한."""
        sheet = Overlay(self, 520)
        body = sheet.body
        body.addWidget(label("카페인 알리미 설정", 26, title=True))
        units = QHBoxLayout()
        units.setSpacing(8)
        self.unit_buttons = {}
        for unit in LIMIT_UNITS:
            chip = button(unit, "pill", lambda checked=False, unit=unit: self.change_limit(unit=unit))
            chip.setCheckable(True)
            chip.setMinimumHeight(48)
            self.unit_buttons[unit] = chip
            units.addWidget(chip, 1)
        body.addLayout(units)
        steps = QHBoxLayout()
        minus = button("−", "outline", lambda: self.change_limit(step=-1))
        plus = button("+", "outline", lambda: self.change_limit(step=1))
        for widget in (minus, plus):
            widget.setFixedSize(64, 52)
            widget.setFont(theme.font(22, bold=True))
            widget.setStyleSheet("padding: 0;")
        self.limit_amount = label("", 24, bold=True)
        self.limit_amount.setAlignment(Qt.AlignmentFlag.AlignCenter)
        steps.addWidget(minus)
        steps.addWidget(self.limit_amount, 1)
        steps.addWidget(plus)
        body.addLayout(steps)
        self.limit_status = label("", 15, muted=True, guide=True)
        body.addWidget(self.limit_status)
        row = QHBoxLayout()
        row.addWidget(button("알리미 끄기", "outline", lambda: self.change_limit(off=True)))
        self.settings_done = button("완료", "primary", sheet.hide)
        row.addWidget(self.settings_done, 1)
        body.addLayout(row)
        return sheet

    def open_caffeine_settings(self):
        self.show_limit()
        self.caffeine_settings.open()

    def show_limit(self):
        """설정 창과 리포트 블록의 알리미 글을 지금 제한에 맞춘다."""
        limit = self.session.caffeine_limit()
        used = self.session.caffeine_used() if limit else {}
        for unit, chip in self.unit_buttons.items():
            chip.setChecked(bool(limit) and limit["unit"] == unit)
        if limit:
            unit, amount = limit["unit"], limit["amount"]
            self.limit_amount.setText(f"주 {amount:,}{unit}")
            self.limit_status.setText(f"이번 주 {used[unit]:,}{unit} 마심 (장바구니 포함)")
        else:
            self.limit_amount.setText("꺼짐")
            self.limit_status.setText("단위를 고르거나 +를 누르면 켜져요")
        if self.category != MY_MENU or getattr(self, "alert_title", None) is None:
            return                               # 리포트 블록은 My Menu에만 있다
        if not limit:
            self.alert_title.setText("카페인 알리미 꺼짐")
            self.alert_bar.hide()
            self.alert_text.setText("오른쪽 위 톱니바퀴로 이번 주 제한을 정할 수 있어요")
            self.alert_text.setStyleSheet(f"color: {theme.TEXT2};")
            return
        self.alert_bar.show()
        self.alert_bar.set_ratio(used[unit] / amount)
        self.alert_title.setText(f"카페인 알리미 · 주 {amount:,}{unit}")
        left = amount - used[unit]
        self.alert_text.setText(f"{left:,}{unit} 남았어요" if left >= 0 else f"{-left:,}{unit} 넘었어요")
        self.alert_text.setStyleSheet(f"color: {theme.ACCENT if left < 0 else theme.TEXT2};")

    def change_limit(self, unit=None, step=0, off=False):
        """단위를 고르거나 −/+로 제한을 바꾸고 바로 저장한다. 0이 되거나 off면 알리미를 끈다."""
        limit = self.session.caffeine_limit()
        if off:
            self.session.set_caffeine_limit(None)
            self.show_limit()
            self.update_trend_limit()
            return
        if unit is not None:
            if limit and limit["unit"] == unit:  # 켜진 단위를 다시 누르면 그대로
                self.show_limit()
                return
            amount = self.LIMIT_START[unit]
        elif limit:
            unit = limit["unit"]
            amount = limit["amount"] + step * self.LIMIT_STEP[unit]
        elif step > 0:                           # 꺼진 상태에서 + → 잔 단위로 켠다
            unit, amount = "잔", self.LIMIT_START["잔"]
        else:
            return
        self.session.set_caffeine_limit(unit, max(0, amount))
        self.show_limit()
        self.update_trend_limit()

    def set_caffeine_view(self, view):
        self.caffeine_view = view
        for name, chip in self.view_buttons.items():
            chip.setChecked(name == view)
        trend = self.session.caffeine_trend(view)
        bars = self.trend_bars
        bars.labels, bars.values, bars.current = trend["labels"], trend["values"], trend["current"]
        self.update_trend_limit()

    def next_caffeine_view(self):
        """그래프를 누르면 이번 주 → 주별 → 월별 → 이번 주."""
        index = TREND_VIEWS.index(self.caffeine_view)
        self.set_caffeine_view(TREND_VIEWS[(index + 1) % len(TREND_VIEWS)])

    def update_trend_limit(self):
        """주별 그래프에는 mg 제한을 점선으로 긋는다."""
        if self.category != MY_MENU:
            return
        limit = self.session.caffeine_limit()
        mg_limit = limit and limit["unit"] == "mg" and self.caffeine_view == "주별"
        self.trend_bars.limit = limit["amount"] if mg_limit else None
        self.trend_bars.update()

    def refresh(self):
        while self.cart_list.count():
            widget = self.cart_list.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)   # 바로 화면에서 떼어 낸다
        self.ticket_lines = [TicketCartLine(self.session, ticket, self.remove_ticket)
                             for ticket in self.session.tickets]
        for line in self.ticket_lines:            # 승차권 줄이 먼저, 음료 줄은 아래 (와이어프레임 T1-7)
            self.cart_list.addWidget(line)
        if self.session.card_kind:
            self.cart_list.addWidget(card_cart_line(self.session.card_label(), self.session.card_total(),
                                                    self.remove_card))
        lines = self.session.lines()
        for line in lines:
            self.cart_list.addWidget(self.make_cart_line(line))
        if self.session.is_empty():
            empty = label("메뉴를 고르면 여기에 담겨요", 15, muted=True)
            self.cart_list.addWidget(empty)
        self.cart_title.setText(f"장바구니 · {self.session.count()}개")
        self.total_label.setText(theme.won(self.session.total()))
        self.check_button.setEnabled(not self.session.is_empty())
        if self.category == MY_MENU and self.session.is_member():
            self.show_limit()                     # 알리미 '남았어요'는 장바구니도 센다

    def remove_ticket(self, hold_id):
        self.session.remove_ticket(hold_id)
        self.refresh()

    def remove_card(self):
        self.session.remove_card()
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
        self.confirm_box.setGeometry(self.rect())
        self.staff_box.setGeometry(self.rect())
        self.caffeine_settings.setGeometry(self.rect())
        # 11/09: 넓은 화면(1920)에서는 오른쪽 장바구니를 넓게 (좁은 창은 메뉴 카드 3칸 자리를 지킨다)
        self.cart_panel.setFixedWidth(400 if self.width() >= 1600 else 300)
        super().resizeEvent(event)
