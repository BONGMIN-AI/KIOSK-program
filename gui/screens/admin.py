"""09 운영자 (와이어프레임 v2.1): 09-A 로그인 · 09-B 메뉴 관리 · 09-C 회원·주문 조회 ·
09-D 이벤트·포인트 · 09-E 포인트 조정·감사 로그 · KIOSK 종료 · 로그아웃.

플로차트: 01 운영자 메뉴 → 09-A 운영자 로그인 → 메뉴·회원·이벤트·포인트·종료 → 로그아웃 → 01 고객 HOME.
운영자가 바꾼 것은 모두 감사 로그(해시 체인)에 남는다. 고객 전화번호는 가려서 보여 준다.
"""

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox,
                               QHBoxLayout, QHeaderView, QLabel, QScrollArea, QStackedWidget, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

import config
from core import audit, auth, schema
from core.validators import mask_phone
from domain import member_cards as card_logic
from domain import policy as policy_logic
from domain import kiosk_settings as kiosk_logic
from domain import sales as sales_logic
from domain.titles import title_name
from domain.customers import adjust_points, update_member_info
from face import FaceError
from gui import theme
from gui.order import CATEGORY_ORDER
from gui.screens.login import info_box, nav_bar
from gui.widgets import Card, TouchKeyboard, TrendBars, button, label, message_label, phone_field, text_field

# 왼쪽 목록 (11/02: 위쪽 탭 → 묶음별 세로 목록, 한 화면에 한 가지 일)
SECTIONS = [
    ("매장", [("sales", "매출 요약"), ("menu", "메뉴 · 재고")]),
    ("회원", [("members", "회원 목록"), ("orders", "주문 기록"), ("cards", "회원카드"), ("points", "포인트 조정")]),
    ("혜택 · 행사", [("events", "이벤트"), ("perks", "혜택 설정")]),
    ("화면 · 설정", [("banners", "광고 배너"), ("kiosk", "키오스크 설정")]),
    ("기록", [("log", "운영 기록")]),
]
TABS = [item for _, items in SECTIONS for item in items]
CARD_SECONDS = 20          # 허용 뒤 빈 카드를 찍을 시간 (기본값 · 운영자 '키오스크 설정'에서 바꿈)
THEME_NAMES = policy_logic.THEMES


def table(headers):
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.verticalHeader().setVisible(False)
    widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    widget.setFont(theme.font(15))
    widget.setStyleSheet(f"QTableWidget {{ background: {theme.CARD}; border: 1px solid {theme.LINE};"
                         f" border-radius: 12px; gridline-color: {theme.LINE}; }}"
                         f" QHeaderView::section {{ background: {theme.CARAMEL_LIGHT}; border: none;"
                         " padding: 6px; font-weight: bold; }")
    return widget


LOG_KINDS = {   # 운영 기록 걸러 보기 (11/02): 이름 → 이 글자로 시작하는 기록
    "전체": (), "로그인·종료": ("admin_", "kiosk_"), "메뉴": ("menu_",), "회원카드": ("card_",),
    "포인트": ("points_",), "이벤트·혜택": ("event_", "card_perks"), "회원": ("member_",),
    "화면·설정": ("banner_", "kiosk_settings"),
    "현금": ("cash_",),
}


def line_text(line):
    """주문 한 줄: '아메리카노(ICE·L·샷)×2' — 같은 메뉴라도 옵션이 다르면 구분된다."""
    options = line.get("options") or {}
    parts = [options.get("temperature"), options.get("size")]
    parts += ["샷" if e == "shot" else "시럽" if e == "syrup" else e for e in options.get("extras") or []]
    detail = "·".join(p for p in parts if p)
    return f"{line['name']}({detail})×{line['quantity']}" if detail else f"{line['name']}×{line['quantity']}"


def fit_columns(widget, stretch):
    """칸 폭을 글자 길이만큼 (잘리지 않게), stretch 칸만 남는 폭을 채운다."""
    header = widget.horizontalHeader()
    for index in range(widget.columnCount()):
        header.setSectionResizeMode(index, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(stretch, QHeaderView.ResizeMode.Stretch)


def add_checks(widget, keep=()):
    """맨 왼쪽 칸을 고르기 체크로 (fill_table 다음에 부른다). keep: 체크해 둘 키들."""
    widget.blockSignals(True)
    for row in range(widget.rowCount()):
        item = widget.item(row, 0)
        item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        key = item.data(Qt.ItemDataRole.UserRole)
        item.setCheckState(Qt.CheckState.Checked if key in keep else Qt.CheckState.Unchecked)
    widget.blockSignals(False)


def checked_keys(widget):
    """체크한 줄의 키들. 체크가 없으면 지금 고른 줄 하나."""
    keys = [widget.item(row, 0).data(Qt.ItemDataRole.UserRole) for row in range(widget.rowCount())
            if widget.item(row, 0) is not None and widget.item(row, 0).checkState() == Qt.CheckState.Checked]
    if not keys and selected_key(widget) is not None:
        keys = [selected_key(widget)]
    return keys


def check_all(widget):
    """'전체 선택': 다 체크돼 있으면 모두 풀고, 아니면 모두 체크."""
    rows = range(widget.rowCount())
    on = not all(widget.item(row, 0).checkState() == Qt.CheckState.Checked for row in rows)
    for row in rows:
        widget.item(row, 0).setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)


def fill_table(widget, rows, keys=None):
    """rows: 칸 문자열 목록들. keys: 줄마다 붙일 ID(선택할 때 쓴다). 채우는 동안은 바뀜 알림을 멈춘다."""
    widget.blockSignals(True)
    widget.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            item = QTableWidgetItem(str(value))
            if keys is not None and c == 0:
                item.setData(Qt.ItemDataRole.UserRole, keys[r])
            widget.setItem(r, c, item)
    widget.blockSignals(False)


def selected_key(widget):
    row = widget.currentRow()
    if row < 0 or widget.item(row, 0) is None:
        return None
    return widget.item(row, 0).data(Qt.ItemDataRole.UserRole)


def field_row(title, widget, width=110):
    row = QHBoxLayout()
    name = label(title, 15, bold=True)
    name.setFixedWidth(width)
    row.addWidget(name)
    row.addWidget(widget, 1)
    return row


def as_int(text, name):
    text = (text or "").replace(",", "").replace("+", "").replace("원", "").replace("P", "").strip()
    try:
        return int(text or "0")
    except ValueError as exc:
        raise ValueError(f"{name}은(는) 숫자로 입력하세요") from exc


# ---------------------------------------------------------------- 09-A
class AdminLoginScreen(QWidget):
    def __init__(self, router):
        super().__init__()
        self.router = router
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 24, 40, 20)
        layout.setSpacing(14)
        head = QHBoxLayout()
        head.addWidget(label("운영자 로그인", 32, title=True))
        head.addStretch()
        head.addWidget(label("운영자 · 인증 전", 16, muted=True))
        layout.addLayout(head)
        body = QHBoxLayout()
        body.setSpacing(20)
        left_card = Card()
        left = QVBoxLayout(left_card)
        left.setContentsMargins(24, 20, 24, 20)
        left.setSpacing(10)
        left.addWidget(label("운영자 계정으로 로그인해 주세요.", 22, bold=True))
        self.admin_id = text_field("운영자 ID", text="admin")
        self.password = text_field("비밀번호", password=True)
        self.password.returnPressed.connect(self.password_login)
        left.addWidget(self.admin_id)
        left.addWidget(self.password)
        left.addWidget(button("운영자 로그인 →", "primary", self.password_login))
        left.addWidget(button("ID + 얼굴로 로그인", "outline", self.face_login))
        self.message = message_label()
        left.addWidget(self.message)
        left.addStretch()
        body.addWidget(left_card, 1)
        right_card = Card()
        right_card.setFixedWidth(500)
        right = QVBoxLayout(right_card)
        right.setContentsMargins(22, 20, 22, 20)
        box, _ = info_box("운영자 전용 영역",
                          "메뉴 추가·조회·수정·삭제 · 가격·품절 관리 · 회원·주문 조회 · 이벤트·포인트 · "
                          "포인트 조정·감사 로그 · KIOSK 종료\n실패 시 \"운영자 계정을 확인해 주세요\"")
        right.addWidget(box)
        keyboard = TouchKeyboard()
        keyboard.attach(self.admin_id, self.password)
        right.addWidget(keyboard)
        right.addStretch()
        body.addWidget(right_card)
        layout.addLayout(body, 1)
        layout.addLayout(nav_bar(router, lambda: router.show_screen("home")))

    def on_show(self):
        self.password.clear()
        self.message.setText("")

    def password_login(self):
        admin_id = self.admin_id.text().strip().lower()
        if not admin_id or not self.password.text():
            self.message.setText("운영자 ID와 비밀번호를 모두 넣어 주세요")
            return
        try:
            self.router.admin_check(admin_id, self.password.text())
        except (auth.AuthError, ValueError) as error:
            self.message.setText(f"운영자 계정을 확인해 주세요 · {error}")
            return
        finally:
            self.password.clear()
        self.enter(admin_id, "비밀번호")

    def face_login(self):
        admin_id = self.admin_id.text().strip().lower()
        key = auth.admin_face_key(admin_id)
        scores = []
        try:
            matched = self.router.face().identify_face(key, scores.append)
        except (FaceError, ValueError) as error:
            self.message.setText(f"{error} · 비밀번호 로그인을 사용하세요")
            return
        score = next((text for text in reversed(scores) if text.startswith("얼굴 유사도")), "")
        if matched != key:
            self.message.setText(f"얼굴이 일치하지 않습니다. 비밀번호 로그인을 사용하세요 · {score}")
            return
        if score:
            print(f"[운영자 얼굴 로그인] {admin_id} · {score}")
        self.enter(admin_id, "얼굴")

    def enter(self, admin_id, how):
        self.router.admin_id = admin_id
        self.router.audit("admin_login", how)
        self.router.show_screen("admin")


# ---------------------------------------------------------------- 09-B ~ 09-E
class AdminScreen(QWidget):
    def __init__(self, router):
        super().__init__()
        self.router = router
        self.pending_delete = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 18, 32, 16)
        layout.setSpacing(10)
        head = QHBoxLayout()
        self.title = label("운영자", 30, title=True)
        head.addWidget(self.title)
        head.addStretch()
        self.who = label("", 16, muted=True)
        head.addWidget(self.who)
        layout.addLayout(head)
        body = QHBoxLayout()
        body.setSpacing(16)
        nav = Card()
        nav.setFixedWidth(168 if theme.SCALE == 1 else 190)
        nav_box = QVBoxLayout(nav)
        nav_box.setContentsMargins(0, 0, 0, 0)
        nav_scroll = QScrollArea()                 # 목록이 길어지면(큰 글자) 위아래로 민다
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        nav_inner = QWidget()
        nav_scroll.setWidget(nav_inner)
        nav_box.addWidget(nav_scroll)
        tree = QVBoxLayout(nav_inner)
        tree.setContentsMargins(8, 10, 8, 10)
        tree.setSpacing(2)
        self.tab_group = QButtonGroup(self)
        for section, items in SECTIONS:
            head_label = label(section, 14, bold=True, muted=True)
            head_label.setContentsMargins(8, 6, 0, 0)
            tree.addWidget(head_label)
            for key, name in items:
                tab = button(name, "category", lambda checked=False, k=key: self.show_tab(k))
                tab.setCheckable(True)
                tab.setObjectName(f"tab_{key}")
                tab.setStyleSheet("text-align: left; padding-left: 12px;")
                tab.setFont(theme.font(15, bold=True))
                tab.setMinimumHeight(38)
                self.tab_group.addButton(tab)
                tree.addWidget(tab)
        tree.addStretch()
        body.addWidget(nav)
        self.pages = QStackedWidget()
        self.page_of = {"sales": self.make_sales_page(), "menu": self.make_menu_page(),
                        "members": self.make_members_page(),
                        "orders": self.make_orders_page(),
                        "cards": self.make_cards_page(), "points": self.make_points_page(),
                        "events": self.make_events_page(), "perks": self.make_perks_page(),
                        "banners": self.make_banners_page(), "kiosk": self.make_kiosk_page(),
                        "log": self.make_log_page()}
        for page in self.page_of.values():
            self.pages.addWidget(page)
        body.addWidget(self.pages, 1)
        layout.addLayout(body, 1)
        self.message = message_label()
        layout.addWidget(self.message)
        bottom = nav_bar(router, lambda: router.show_screen("home"))
        bottom.addWidget(button("KIOSK 종료", "outline", self.shutdown))
        bottom.addWidget(button("로그아웃", "primary", self.logout))
        layout.addLayout(bottom)

    def vault(self):
        return self.router.session.vault

    def on_show(self, tab="sales"):
        self.who.setText(f"{self.router.admin_id} · 로그인됨")
        self.show_tab(tab)

    def show_tab(self, key):
        self.pending_delete = None
        self.message.setText("")
        for tab in self.tab_group.buttons():
            tab.setChecked(tab.objectName() == f"tab_{key}")
        self.title.setText(dict(TABS)[key])
        self.pages.setCurrentWidget(self.page_of[key])
        getattr(self, f"load_{key}")()

    def done(self, text):
        self.message.setStyleSheet(f"color: {theme.BROWN};")
        self.message.setText(text)

    def fail(self, error):
        self.message.setStyleSheet(f"color: {theme.ERROR};")
        self.message.setText(str(error))

    # ---- 09-B 메뉴 관리
    # ---- 매출 요약 (11/02 B6)
    def make_sales_page(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(12)
        periods = QHBoxLayout()
        self.sales_period = "오늘"
        self.sales_buttons = {}
        for name in sales_logic.PERIODS:
            chip = button(name, "pill", lambda checked=False, n=name: self.set_sales_period(n))
            chip.setCheckable(True)
            chip.setMinimumHeight(44)
            self.sales_buttons[name] = chip
            periods.addWidget(chip)
        periods.addStretch()
        column.addLayout(periods)
        tiles = QHBoxLayout()
        self.sales_tiles = {}
        for key, name in (("total", "매출"), ("count", "주문"), ("average", "평균 결제"), ("tickets", "승차권")):
            tile = Card()
            box = QVBoxLayout(tile)
            box.setContentsMargins(16, 10, 16, 10)
            box.addWidget(label(name, 14, muted=True))
            value = label("", 24, title=True)
            box.addWidget(value)
            self.sales_tiles[key] = value
            tiles.addWidget(tile, 1)
        column.addLayout(tiles)
        body = QHBoxLayout()
        body.setSpacing(16)
        top_card = Card()
        top = QVBoxLayout(top_card)
        top.setContentsMargins(16, 12, 16, 12)
        top.addWidget(label("많이 팔린 메뉴", 16, bold=True))
        self.sales_top = table(["순위", "메뉴", "잔 수", "매출"])
        fit_columns(self.sales_top, 1)
        top.addWidget(self.sales_top, 1)
        body.addWidget(top_card, 1)
        hour_card = Card()
        hours = QVBoxLayout(hour_card)
        hours.setContentsMargins(16, 12, 16, 12)
        hours.addWidget(label("시간대별 주문", 16, bold=True))
        self.sales_hours = TrendBars([str(h) for h in sales_logic.HOURS], [0] * len(sales_logic.HOURS), -1)
        hours.addWidget(self.sales_hours)
        hours.addStretch()
        body.addWidget(hour_card, 1)
        column.addLayout(body, 1)
        return page

    def set_sales_period(self, name):
        self.sales_period = name
        self.load_sales()

    def load_sales(self):
        data = sales_logic.summary(self.vault().read("orders", default={}), self.sales_period)
        for name, chip in self.sales_buttons.items():
            chip.setChecked(name == self.sales_period)
        self.sales_tiles["total"].setText(f"{data['total']:,}원")
        self.sales_tiles["count"].setText(f"{data['count']:,}건")
        self.sales_tiles["average"].setText(f"{data['average']:,}원")
        self.sales_tiles["tickets"].setText(f"{data['tickets']:,}매")
        fill_table(self.sales_top, [[f"{rank}", name, f"{qty:,}잔", f"{sales:,}원"]
                                    for rank, (name, qty, sales) in enumerate(data["top"], 1)])
        bars = self.sales_hours
        bars.values = data["hours"]
        bars.current = data["hours"].index(max(data["hours"])) if any(data["hours"]) else -1
        bars.update()

    def make_menu_page(self):
        """메뉴 · 재고 (11/02): 분류로 걸러 보기, 체크로 여러 개 품절·판매 재개, 오른쪽은 고른 메뉴 하나 수정."""
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)
        left = QVBoxLayout()
        search_row = QHBoxLayout()
        self.menu_search = text_field("메뉴명 검색")
        self.menu_search.textChanged.connect(self.load_menu)
        search_row.addWidget(self.menu_search, 1)
        self.menu_filter = QComboBox()
        self.menu_filter.addItems(["전체 분류", *CATEGORY_ORDER, "품절만"])
        self.menu_filter.setFont(theme.font(15))
        self.menu_filter.setMinimumHeight(48)
        self.menu_filter.currentTextChanged.connect(lambda _text: self.load_menu())
        search_row.addWidget(self.menu_filter)
        search_row.addWidget(button("+ 새 메뉴", "outline", self.new_menu))
        left.addLayout(search_row)
        self.menu_table = table(["", "메뉴명", "분류", "가격", "재고", "상태"])
        fit_columns(self.menu_table, 1)
        self.menu_table.itemSelectionChanged.connect(self.select_menu)
        self.menu_table.itemChanged.connect(lambda _item: self.update_menu_buttons())
        left.addWidget(self.menu_table, 1)
        batch = QHBoxLayout()
        batch.addWidget(button("전체 선택", "outline", lambda: check_all(self.menu_table)))
        batch.addStretch()
        self.sold_out_button = button("품절로", "outline", lambda: self.set_sold_out(True))
        self.on_sale_button = button("판매 재개", "outline", lambda: self.set_sold_out(False))
        batch.addWidget(self.sold_out_button)
        batch.addWidget(self.on_sale_button)
        left.addLayout(batch)
        row.addLayout(left, 3)
        form_card = Card()
        form = QVBoxLayout(form_card)
        form.setContentsMargins(18, 14, 18, 14)
        form.setSpacing(8)
        self.menu_form_title = label("메뉴를 고르세요", 20, bold=True)
        form.addWidget(self.menu_form_title)
        self.menu_name = text_field("메뉴명")
        self.menu_category = QComboBox()
        self.menu_category.addItems(CATEGORY_ORDER)
        self.menu_category.setFont(theme.font(16))
        self.menu_category.setMinimumHeight(48)
        self.menu_price = text_field("가격")
        self.menu_stock = text_field("재고")
        for title, widget in (("메뉴명", self.menu_name), ("분류", self.menu_category),
                              ("가격", self.menu_price), ("재고", self.menu_stock)):
            form.addLayout(field_row(title, widget))
        actions = QHBoxLayout()
        self.menu_save_button = button("저장", "primary", self.save_menu)
        self.menu_delete_button = button("삭제", "outline", self.delete_menu)
        actions.addWidget(self.menu_save_button, 2)
        actions.addWidget(self.menu_delete_button, 1)
        form.addLayout(actions)
        form.addStretch()
        row.addWidget(form_card, 2)
        self.editing_menu = None
        return page

    def load_menu(self, keep=()):
        keyword = self.menu_search.text().strip()
        category = self.menu_filter.currentText()
        items = [i for i in sorted(self.vault().read("menu", default={}).values(), key=lambda i: i["id"])
                 if keyword in i["name"] and (category == "전체 분류" or i["category"] == category
                                              or (category == "품절만" and i.get("sold_out")))]
        fill_table(self.menu_table, [["", i["name"], i["category"], f"{i['price']:,}원", f"{i['stock']}개",
                                      "품절" if i.get("sold_out") else "판매 중"] for i in items],
                   [i["id"] for i in items])
        add_checks(self.menu_table, keep)
        self.update_menu_buttons()

    def checked_menu(self):
        menu = self.vault().read("menu", default={})
        return [menu[key] for key in checked_keys(self.menu_table) if key in menu]

    def update_menu_buttons(self):
        """품절로 · 판매 재개는 고른 메뉴의 상태에 맞을 때만, 삭제는 메뉴를 하나 골랐을 때만."""
        items = self.checked_menu()
        self.sold_out_button.setEnabled(any(not i.get("sold_out") for i in items))
        self.on_sale_button.setEnabled(any(i.get("sold_out") and i["stock"] > 0 for i in items))
        self.menu_delete_button.setEnabled(self.editing_menu is not None)

    def select_menu(self):
        menu_id = selected_key(self.menu_table)
        if menu_id is None:
            return
        item = self.vault().read("menu")[menu_id]
        self.editing_menu = menu_id
        self.menu_form_title.setText(item["name"])
        self.menu_name.setText(item["name"])
        self.menu_category.setCurrentText(item["category"])
        self.menu_price.setText(str(item["price"]))
        self.menu_stock.setText(str(item["stock"]))
        self.update_menu_buttons()

    def new_menu(self):
        self.editing_menu = None
        self.menu_table.clearSelection()
        self.menu_form_title.setText("새 메뉴")
        for field in (self.menu_name, self.menu_price, self.menu_stock):
            field.clear()
        self.update_menu_buttons()

    def save_menu(self):
        try:
            name = self.menu_name.text().strip()
            price = as_int(self.menu_price.text(), "가격")
            stock = as_int(self.menu_stock.text(), "재고")
            category = self.menu_category.currentText()
            if not name or price <= 0 or stock < 0:
                raise ValueError("메뉴명·가격(1원 이상)·재고(0개 이상)를 확인하세요")
        except ValueError as error:
            self.fail(error)
            return
        menu = self.vault().read("menu", default={})
        menu_id = self.editing_menu or schema.next_id("M", menu, width=3)
        old = menu.get(menu_id, {})
        menu[menu_id] = {**old, "id": menu_id, "name": name, "category": category, "price": price,
                         "stock": stock, "sold_count": old.get("sold_count", 0), "sold_out": stock == 0,
                         "allergens": old.get("allergens", []), "decaf": category == "디카페인",
                         "caffeine_mg": 0 if category == "디카페인" else old.get("caffeine_mg", 0)}
        self.vault().write("menu", menu)
        self.router.audit("menu_save", menu_id)
        self.editing_menu = menu_id
        self.load_menu()
        self.done(f"'{name}' 저장했어요")

    def set_sold_out(self, sold_out):
        """체크한 메뉴(없으면 고른 메뉴)를 한꺼번에 품절 또는 판매 재개. 재고가 0개면 판매 재개는 건너뛴다."""
        menu = self.vault().read("menu", default={})
        changed, skipped = [], []
        for item in self.checked_menu():
            target = menu[item["id"]]
            if not sold_out and target["stock"] == 0:
                skipped.append(target["name"])
                continue
            if bool(target.get("sold_out")) != sold_out:
                target["sold_out"] = sold_out
                changed.append(target["id"])
                self.router.audit("menu_sold_out" if sold_out else "menu_on_sale", target["id"])
        if not changed:
            self.fail("바꿀 메뉴가 없어요" + (f" (재고 0개: {', '.join(skipped)})" if skipped else ""))
            return
        self.vault().write("menu", menu)
        self.load_menu()
        note = f"\n재고가 0개라 그대로: {', '.join(skipped)}" if skipped else ""
        self.done(f"{len(changed)}개 {'품절' if sold_out else '판매 재개'}{note}")

    def toggle_sold_out(self):
        """고른 메뉴가 모두 판매 중이면 품절로, 아니면 판매 재개 (예전 단추 이름 그대로 둔 바로가기)."""
        items = self.checked_menu()
        self.set_sold_out(all(not i.get("sold_out") for i in items))

    def delete_menu(self):
        menu = self.vault().read("menu", default={})
        if self.editing_menu not in menu:
            self.fail("삭제할 메뉴를 먼저 선택하세요")
            return
        if self.pending_delete != self.editing_menu:
            self.pending_delete = self.editing_menu
            self.fail(f"'{menu[self.editing_menu]['name']}'을(를) 삭제할까요? 한 번 더 누르면 삭제합니다")
            return
        removed = menu.pop(self.editing_menu)
        self.vault().write("menu", menu)
        self.router.audit("menu_delete", removed["id"])
        self.pending_delete = None
        self.new_menu()
        self.load_menu()
        self.done(f"{removed['name']} 메뉴를 삭제했습니다")

    # ---- 09-C 회원·주문 조회
    def make_members_page(self):
        """회원 목록 (11/02): 검색 · 표 · 고른 회원의 상세 (주문 · 칭호 · 카드 · 알레르기 · 카페인)."""
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)
        left = QVBoxLayout()
        self.member_search = text_field("회원 ID · 닉네임 · 전화번호 끝자리")
        self.member_search.textChanged.connect(self.load_members)
        left.addWidget(self.member_search)
        self.member_table = table(["회원 ID", "닉네임", "칭호", "전화번호", "포인트", "쿠폰", "방문", "카드"])
        fit_columns(self.member_table, 1)
        self.member_table.itemSelectionChanged.connect(self.show_member_detail)
        left.addWidget(self.member_table, 1)
        row.addLayout(left, 3)
        detail = Card()
        detail.setMinimumWidth(300)
        box = QVBoxLayout(detail)
        box.setContentsMargins(18, 14, 18, 14)
        box.setSpacing(6)
        self.member_detail_title = label("회원을 고르세요", 20, bold=True)
        box.addWidget(self.member_detail_title)
        self.member_detail_text = label("", 15)
        self.member_detail_text.setWordWrap(True)
        self.member_detail_text.setAlignment(Qt.AlignmentFlag.AlignTop)
        box.addWidget(self.member_detail_text, 1)
        # 정보 수정 (11/02 B5): 고른 회원이 있을 때만 '정보 수정'이 켜지고, 누르면 수정 칸이 열린다
        self.member_form = QWidget()
        form = QVBoxLayout(self.member_form)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)
        self.edit_nickname = text_field("닉네임")
        self.edit_phone = phone_field("010-0000-0000")
        self.edit_birthday = text_field("생일 2000-01-31")
        self.edit_allergies = text_field("알레르기 (쉼표로: 우유, 땅콩)")
        self.edit_marketing = QCheckBox("마케팅 수신 동의")
        self.edit_marketing.setFont(theme.font(15))
        for title, widget in (("닉네임", self.edit_nickname), ("전화번호", self.edit_phone),
                              ("생일", self.edit_birthday), ("알레르기", self.edit_allergies)):
            form.addLayout(field_row(title, widget, 80))
        form.addWidget(self.edit_marketing)
        self.member_form.hide()
        box.addWidget(self.member_form, 1)
        buttons = QHBoxLayout()
        self.member_edit_button = button("정보 수정", "outline", self.edit_member)
        self.member_save_button = button("저장", "primary", self.save_member)
        self.member_cancel_button = button("취소", "outline", self.show_member_detail)
        for widget in (self.member_edit_button, self.member_save_button, self.member_cancel_button):
            buttons.addWidget(widget)
        box.addLayout(buttons)
        row.addWidget(detail, 2)
        return page

    def edit_member(self):
        customer_id = selected_key(self.member_table)
        record = self.vault().read("customers", default={}).get(customer_id)
        if record is None:
            return
        extra = record["extra"]
        self.edit_nickname.setText(extra["nickname"])
        self.edit_phone.setText(record["phone"])
        self.edit_birthday.setText(extra.get("birthday", ""))
        self.edit_allergies.setText(", ".join(extra.get("allergies", [])))
        self.edit_marketing.setChecked(bool(extra.get("marketing_agreed")))
        self.member_detail_text.hide()
        self.member_form.show()
        self.set_member_buttons(editing=True)

    def save_member(self):
        customer_id = selected_key(self.member_table)
        allergies = [name.strip() for name in self.edit_allergies.text().replace("·", ",").split(",") if name.strip()]
        try:
            record = update_member_info(self.vault(), customer_id, self.edit_nickname.text(), self.edit_phone.text(),
                                       self.edit_birthday.text(), allergies, self.edit_marketing.isChecked())
        except ValueError as error:
            self.fail(error)
            return
        self.router.audit("member_update", customer_id)
        row = self.member_table.currentRow()
        self.load_members()
        self.member_table.selectRow(row)
        self.done(f"{record['extra']['nickname']} 님 정보를 저장했어요")

    def set_member_buttons(self, editing=False):
        chosen = selected_key(self.member_table) is not None
        self.member_edit_button.setVisible(not editing)
        self.member_edit_button.setEnabled(chosen)
        self.member_save_button.setVisible(editing)
        self.member_cancel_button.setVisible(editing)

    def load_members(self):
        keyword = self.member_search.text().strip().lower()
        customers = self.vault().read("customers", default={})
        rows, keys = [], []
        for customer_id, record in sorted(customers.items()):
            extra = record["extra"]
            haystack = f"{extra.get('login_id', '')} {extra['nickname']} {record['phone'][-4:]}".lower()
            if keyword and keyword not in haystack:
                continue
            rows.append([extra.get("login_id", ""), extra["nickname"], title_name(extra.get("title", "")),
                         mask_phone(record["phone"]), f"{extra['points']:,}P",
                         f"{len(extra.get('coupons', []))}장", f"{extra['visits']}회",
                         "있음" if extra.get("card_hash") else ""])
            keys.append(customer_id)
        fill_table(self.member_table, rows, keys)
        self.member_detail_title.setText("회원을 고르세요")
        self.member_detail_text.setText("")
        self.member_form.hide()
        self.member_detail_text.show()
        self.set_member_buttons()

    def show_member_detail(self):
        customer_id = selected_key(self.member_table)
        customers = self.vault().read("customers", default={})
        if customer_id not in customers:
            self.set_member_buttons()
            return
        record = customers[customer_id]
        extra = record["extra"]
        orders = [o for o in self.vault().read("orders", default={}).values()
                  if (o.get("customer") or {}).get("id") == customer_id]
        orders.sort(key=lambda o: o["created_at"], reverse=True)
        card = (card_logic.card_status_text(self.vault(), record) or "없음").replace("회원카드 ", "")
        limit = extra.get("caffeine_limit")
        lines = [
            f"이름 {record['name']} · 전화 {mask_phone(record['phone'])}",
            f"포인트 {extra['points']:,}P · 쿠폰 {len(extra.get('coupons', []))}장 · 방문 {extra['visits']}회",
            f"칭호 {', '.join(title_name(t) for t in extra.get('titles', [])) or '없음'}",
            f"알레르기 {', '.join(extra.get('allergies', [])) or '없음'}",
            f"회원카드 {card} · 얼굴 {'등록' if extra.get('face_enrolled') else '없음'}",
            f"카페인 제한 {limit['amount']}{limit['unit']}/주" if limit else "카페인 제한 없음",
            "",
            f"최근 주문 {len(orders)}건",
        ]
        for order in orders[:5]:
            items = ", ".join(line_text(l) for l in order["lines"])
            lines.append(f"{order['created_at'][5:10]}  {items}  {order['final_total']:,}원")
        self.member_detail_title.setText(f"{extra['nickname']} ({extra.get('login_id', '')})")
        self.member_detail_text.setText("\n".join(lines))
        self.member_form.hide()
        self.member_detail_text.show()
        self.set_member_buttons()

    def make_orders_page(self):
        """주문 기록 (11/02): 주문번호 · 회원 · 메뉴로 찾기, 품목은 줄이지 않고 다 보이게."""
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)
        search_row = QHBoxLayout()
        self.order_search = text_field("주문번호 · 회원 닉네임 · 메뉴명")
        self.order_search.textChanged.connect(self.load_orders)
        search_row.addWidget(self.order_search, 1)
        self.order_period = QComboBox()
        self.order_period.addItems(["전체 기간", "오늘", "최근 7일", "최근 30일"])
        self.order_period.setFont(theme.font(15))
        self.order_period.setMinimumHeight(48)
        self.order_period.currentTextChanged.connect(lambda _text: self.load_orders())
        search_row.addWidget(self.order_period)
        column.addLayout(search_row)
        self.order_table = table(["주문번호", "품목", "결제 금액", "회원", "시각"])
        fit_columns(self.order_table, 1)
        self.order_table.setWordWrap(True)
        column.addWidget(self.order_table, 1)
        self.order_total = label("", 15, bold=True)
        column.addWidget(self.order_total)
        return page

    def load_orders(self):
        keyword = self.order_search.text().strip().lower()
        days = {"오늘": 0, "최근 7일": 7, "최근 30일": 30}.get(self.order_period.currentText())
        today = datetime.now().date()
        rows, total = [], 0
        for order_id, order in sorted(self.vault().read("orders", default={}).items(),
                                      key=lambda pair: pair[1]["created_at"], reverse=True):
            member = (order.get("customer") or {}).get("nickname", "비회원")
            items = ", ".join(line_text(l) for l in order["lines"])
            if order.get("tickets"):
                items += f" · 승차권 {sum(t['count'] for t in order['tickets'])}매"
            if keyword and keyword not in f"{order_id} {member} {items}".lower():
                continue
            if days is not None and (today - datetime.fromisoformat(order["created_at"]).date()).days > days:
                continue
            rows.append([order_id, items, f"{order['final_total']:,}원", member,
                         order["created_at"][5:16].replace("T", " ")])
            total += order["final_total"]
        fill_table(self.order_table, rows)
        self.order_table.resizeRowsToContents()
        self.order_total.setText(f"{len(rows)}건 · 합계 {total:,}원")

    # ---- 09-D 이벤트·포인트
    def make_events_page(self):
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)
        left = QVBoxLayout()
        top = QHBoxLayout()
        top.addWidget(label("이벤트 목록", 17, bold=True))
        top.addStretch()
        top.addWidget(button("+ 새 이벤트", "outline", self.new_event))
        left.addLayout(top)
        self.event_table = table(["이벤트", "기간", "혜택", "상태 · 테마"])
        self.event_table.itemSelectionChanged.connect(self.select_event)
        left.addWidget(self.event_table, 1)
        row.addLayout(left, 5)            # 11/02: 기본 정책 글은 '혜택 설정'으로 옮기고 입력 칸을 넓게
        form_card = Card()
        form = QVBoxLayout(form_card)
        form.setContentsMargins(18, 12, 18, 12)
        form.setSpacing(5)
        self.event_form_title = label("새 이벤트", 19, bold=True)
        form.addWidget(self.event_form_title)
        self.ev_name = text_field("이벤트 이름")
        self.ev_start = text_field("2026-10-20")
        self.ev_end = text_field("2026-10-31")
        self.ev_days = text_field("매일 / 평일 / 주말 / 월,수,금")
        self.ev_hours = text_field("하루 종일이면 비움 · 14-17")
        self.ev_rate = text_field("이벤트 적립률 %")
        self.ev_bonus = text_field("보너스 P")
        self.ev_min = text_field("보너스 최소 결제액")
        self.ev_message = text_field("배너 문구 (비우면 자동)")
        for title, widget in (("이름 *", self.ev_name), ("시작일 *", self.ev_start), ("종료일 *", self.ev_end),
                              ("요일", self.ev_days), ("시간", self.ev_hours), ("적립률", self.ev_rate),
                              ("보너스", self.ev_bonus), ("최소 결제", self.ev_min), ("문구", self.ev_message)):
            widget.setMinimumHeight(40)
            form.addLayout(field_row(title, widget, 90))
        category_row = QHBoxLayout()
        category_row.addWidget(label("대상", 15, bold=True))
        self.ev_categories = {}
        for name in CATEGORY_ORDER:
            box = QCheckBox(name)
            box.setFont(theme.font(14))
            self.ev_categories[name] = box
            category_row.addWidget(box)
        form.addLayout(category_row)
        theme_row = QHBoxLayout()
        theme_row.addWidget(label("테마", 15, bold=True))
        self.theme_group = QButtonGroup(self)
        for key, name in THEME_NAMES.items():
            background, foreground = theme.EVENT_THEMES[key]
            chip = button(name, "option")
            chip.setCheckable(True)
            chip.setProperty("theme", key)
            chip.setMinimumHeight(40)
            chip.setStyleSheet(f"QPushButton {{ background: {background}; color: {foreground}; }}"
                               f" QPushButton:checked {{ border: 3px solid {theme.BROWN}; }}")
            self.theme_group.addButton(chip)
            theme_row.addWidget(chip, 1)
        form.addLayout(theme_row)
        self.ev_enabled = QCheckBox("켜짐")
        self.ev_enabled.setFont(theme.font(15, bold=True))
        actions = QHBoxLayout()
        actions.addWidget(self.ev_enabled)
        actions.addWidget(button("이벤트 저장", "primary", self.save_event), 1)
        actions.addWidget(button("선택 삭제", "outline", self.delete_event))
        form.addLayout(actions)
        scroll = QScrollArea()          # 칸이 많아 화면이 낮으면 위아래로 밀어 본다
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(form_card)
        row.addWidget(scroll, 8)
        self.editing_event = None
        return page

    def policy(self):
        return policy_logic.load_policy(self.vault().read("settings", default={}))

    def save_policy(self, policy):
        settings = self.vault().read("settings", default={})
        settings["point_policy"] = policy_logic.validate_policy(policy)
        self.vault().write("settings", settings)

    def load_events(self):
        policy = self.policy()
        events = policy["events"]
        fill_table(self.event_table, [[e["name"], f"{e['start'][5:]}~{e['end'][5:]}",
                                       policy_logic.describe_event(e).split(" · ", 4)[-1],
                                       f"{policy_logic.event_status(e)} · {THEME_NAMES.get(e.get('theme', 'basic'))}"]
                                      for e in events], [e["id"] for e in events])
        if self.editing_event is None:
            self.new_event()

    def new_event(self):
        self.editing_event = None
        self.event_table.clearSelection()
        self.event_form_title.setText("새 이벤트")
        for field in (self.ev_name, self.ev_start, self.ev_end, self.ev_days, self.ev_hours, self.ev_rate,
                      self.ev_bonus, self.ev_min, self.ev_message):
            field.clear()
        for box in self.ev_categories.values():
            box.setChecked(False)
        self.ev_enabled.setChecked(True)
        self.set_theme("basic")

    def set_theme(self, key):
        for chip in self.theme_group.buttons():
            chip.setChecked(chip.property("theme") == key)

    def select_event(self):
        event_id = selected_key(self.event_table)
        event = next((e for e in self.policy()["events"] if e["id"] == event_id), None)
        if event is None:
            return
        self.editing_event = event_id
        self.event_form_title.setText(f"선택 이벤트 수정 · {event['name']}")
        self.ev_name.setText(event["name"])
        self.ev_start.setText(event["start"])
        self.ev_end.setText(event["end"])
        self.ev_days.setText(",".join(policy_logic.WEEKDAY_NAMES[d] for d in event["weekdays"]))
        self.ev_hours.setText(f"{event['hours'][0]}-{event['hours'][1]}" if event.get("hours") else "")
        self.ev_rate.setText(f"{event['rate']:g}" if event["rate"] else "")
        self.ev_bonus.setText(str(event["bonus_points"] or ""))
        self.ev_min.setText(str(event["min_order"] or ""))
        self.ev_message.setText(event.get("message", ""))
        for name, box in self.ev_categories.items():
            box.setChecked(name in event["categories"])
        self.ev_enabled.setChecked(event.get("enabled", True))
        self.set_theme(event.get("theme", "basic"))

    def save_event(self):
        checked = self.theme_group.checkedButton()
        try:
            policy, event = policy_logic.upsert_event(self.policy(), {
                "id": self.editing_event or "", "name": self.ev_name.text(),
                "start": self.ev_start.text().strip(), "end": self.ev_end.text().strip(),
                "weekdays": self.ev_days.text(), "hours": self.ev_hours.text(),
                "categories": [n for n, box in self.ev_categories.items() if box.isChecked()],
                "rate": float(self.ev_rate.text() or 0), "bonus_points": as_int(self.ev_bonus.text(), "보너스"),
                "min_order": as_int(self.ev_min.text(), "최소 결제액"),
                "theme": checked.property("theme") if checked else "basic",
                "message": self.ev_message.text(), "enabled": self.ev_enabled.isChecked()})
            self.save_policy(policy)
        except ValueError as error:
            self.fail(error)
            return
        self.router.audit("event_save", event["id"])
        self.editing_event = event["id"]
        self.load_events()
        self.done(f"{event['id']} '{event['name']}' 저장 · {policy_logic.event_status(event)}")

    def delete_event(self):
        if self.editing_event is None:
            self.fail("삭제할 이벤트를 먼저 선택하세요")
            return
        if self.pending_delete != self.editing_event:
            self.pending_delete = self.editing_event
            self.fail(f"{self.editing_event} 이벤트를 삭제할까요? 한 번 더 누르면 삭제합니다")
            return
        self.save_policy(policy_logic.remove_event(self.policy(), self.editing_event))
        self.router.audit("event_delete", self.editing_event)
        self.pending_delete = None
        self.editing_event = None
        self.load_events()
        self.done("이벤트를 삭제했습니다")

    # ---- 09-E 포인트 조정·감사 로그
    # ---- 회원카드 발급 (11/01): 신청 → 허용 → 빈 카드 찍기 → 카운터에서 전달
    def make_cards_page(self):
        """회원카드: '신규 신청' / '등록 회원'으로 나눠 보고, 맨 왼쪽 체크로 골라 한꺼번에 처리한다 (11/02)."""
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(10)
        views = QHBoxLayout()
        self.card_view = "new"
        self.card_view_buttons = {}
        for key, name in (("new", "신규 신청"), ("issued", "등록 회원")):
            chip = button(name, "pill", lambda checked=False, k=key: self.set_card_view(k))
            chip.setCheckable(True)
            chip.setMinimumHeight(44)
            self.card_view_buttons[key] = chip
            views.addWidget(chip)
        views.addStretch()
        column.addLayout(views)
        self.card_table = table(["", "신청", "회원 (아이디)", "종류", "수수료", "상태", "카드 번호", "신청 시각"])
        header = self.card_table.horizontalHeader()
        for index in range(self.card_table.columnCount()):          # 글자 길이만큼 (회원 칸만 남는 폭을 채운다)
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.card_table.itemChanged.connect(lambda _item: self.update_card_buttons())
        self.card_table.itemSelectionChanged.connect(self.update_card_buttons)
        column.addWidget(self.card_table, 1)
        actions = QHBoxLayout()
        self.card_register_button = button("카드 등록", "primary", self.register_cards)
        self.card_approve_button = button("승인", "outline", self.approve_cards)
        self.card_reject_button = button("거절", "outline", self.reject_cards)
        self.card_unregister_button = button("등록 해제", "outline", self.unregister_cards)
        for widget, stretch in ((self.card_register_button, 2), (self.card_approve_button, 1),
                                (self.card_reject_button, 1), (self.card_unregister_button, 1)):
            actions.addWidget(widget, stretch)
        column.addLayout(actions)
        self.card_queue = []
        return page

    # ---- 혜택 설정 (11/02): 회원카드 혜택 · 개인 컵 에코 포인트
    PERKS = (("card_first_discount", "회원카드 첫 주문 할인", "%", "10"),
             ("card_bonus_rate", "회원카드 추가 적립", "%p", "1"),
             ("card_reissue_fee", "카드 재발급 수수료", "원", "1000"),
             ("eco_points", "개인 컵 에코 포인트", "P/잔", "100"))

    def make_perks_page(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(10)
        form = Card()
        rows = QVBoxLayout(form)
        rows.setContentsMargins(22, 16, 22, 16)
        rows.setSpacing(12)
        self.perk_fields = {}
        for key, title, unit, hint in self.PERKS:
            row = QHBoxLayout()
            name = label(title, 17, bold=True)
            name.setFixedWidth(230 if theme.SCALE == 1 else 260)
            row.addWidget(name)
            field = text_field(hint)
            field.setFixedWidth(110)
            self.perk_fields[key] = field
            row.addWidget(field)
            row.addWidget(label(unit, 16, bold=True))
            row.addStretch(1)
            rows.addLayout(row)
        column.addWidget(form)
        save = QHBoxLayout()
        save.addStretch()
        save.addWidget(button("혜택 저장", "primary", self.save_perks))
        column.addLayout(save)
        column.addWidget(label("기본 적립 정책", 16, bold=True))
        self.policy_text = label("", 14, muted=True)
        column.addWidget(self.policy_text)
        column.addStretch()
        return page

    def load_perks(self):
        policy = self.policy()
        coupon = (f"방문 {policy['visit_coupon_every']}회마다 {policy['visit_coupon_amount']:,}원 쿠폰"
                  if policy["visit_coupon_every"] else "방문 쿠폰 없음")
        self.policy_text.setText(f"적립 {policy['base_rate']:g}% (회원 주문만) · {coupon}\n"
                                 f"포인트는 {policy['point_unit']}P 단위 · 최소 {policy['min_use']}P · "
                                 f"결제액의 {policy['max_use_percent']}%까지\n"
                                 "이벤트가 겹치면 가장 높은 적립률 하나만 적용돼요")
        for key, field in self.perk_fields.items():
            field.setText(f"{policy[key]:g}" if key == "card_bonus_rate" else str(policy[key]))

    def save_perks(self):
        policy = self.policy()
        try:
            for key, field in self.perk_fields.items():
                text = field.text().strip() or field.placeholderText()
                if key == "card_bonus_rate":
                    try:
                        policy[key] = float(text.replace("%p", "").replace("%", ""))
                    except ValueError as exc:
                        raise ValueError("추가 적립은 숫자로 입력하세요 (예: 1 또는 1.5)") from exc
                else:
                    policy[key] = as_int(text.replace("%", ""), "혜택 값")
            self.save_policy(policy)
        except ValueError as error:
            self.fail(error)
            return
        self.router.audit("card_perks_save", " ".join(f"{k}={policy[k]}" for k in self.perk_fields))
        self.load_perks()
        self.done(f"혜택을 저장했어요 · {card_logic.perks_text(policy)} · 재발급 {policy['card_reissue_fee']:,}원 · "
                  f"개인 컵 {policy['eco_points']}P/잔")

    def set_card_view(self, view):
        self.card_view = view
        self.load_cards()

    def load_cards(self, keep=None):
        """신규 신청(승인 대기 · 카드 대기 · 거절) 또는 등록 회원(등록됨 · 해제). keep: 다시 그린 뒤 체크해 둘 신청들."""
        requests = card_logic.requests_of(self.vault())
        customers = self.vault().read("customers", default={})
        statuses = ("waiting", "approved", "rejected") if self.card_view == "new" else ("issued", "revoked")
        order = {"waiting": 0, "approved": 1, "rejected": 2, "issued": 0, "revoked": 1}
        items = sorted((r for r in requests.values() if r["status"] in statuses),
                       key=lambda r: (order[r["status"]], r["requested_at"]))
        rows, keys = [], []
        for request in items:
            extra = customers.get(request["customer_id"], {}).get("extra", {})
            rows.append(["", request["id"], f"{extra.get('nickname', '?')} ({extra.get('login_id', '')})",
                         card_logic.KINDS[request["kind"]], f"{request['fee']:,}원" if request["fee"] else "무료",
                         card_logic.STATUS[request["status"]], card_logic.masked_card(request["card_tail"]),
                         request["requested_at"][5:16].replace("T", " ")])
            keys.append(request["id"])
        self.card_table.blockSignals(True)
        fill_table(self.card_table, rows, keys)
        keep = set(keep or [])
        for row, key in enumerate(keys):                        # 맨 왼쪽 칸 = 고르기 체크
            item = self.card_table.item(row, 0)
            item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            item.setCheckState(Qt.CheckState.Checked if key in keep else Qt.CheckState.Unchecked)
        self.card_table.blockSignals(False)
        waiting = sum(r["status"] == "waiting" for r in requests.values())
        issued = sum(r["status"] == "issued" for r in requests.values())
        self.card_view_buttons["new"].setText(f"신규 신청 ({waiting})" if waiting else "신규 신청")
        self.card_view_buttons["issued"].setText(f"등록 회원 ({issued})")
        for key, chip in self.card_view_buttons.items():
            chip.setChecked(key == self.card_view)
        tab = next(t for t in self.tab_group.buttons() if t.objectName() == "tab_cards")
        tab.setText(f"회원카드 ({waiting})" if waiting else "회원카드")
        self.update_card_buttons()

    def checked_card_requests(self):
        """체크한 신청들. 체크가 없으면 지금 고른 줄 하나."""
        checked = checked_keys(self.card_table)
        requests = card_logic.requests_of(self.vault())
        return [requests[key] for key in checked if key in requests]

    def update_card_buttons(self):
        """고른 신청의 상태에 맞는 버튼만 켠다 (등록 해제는 등록된 회원을 골랐을 때만)."""
        statuses = {request["status"] for request in self.checked_card_requests()}
        self.card_approve_button.setEnabled("waiting" in statuses)
        self.card_register_button.setEnabled("approved" in statuses)
        self.card_reject_button.setEnabled(bool(statuses & {"waiting", "approved"}))
        self.card_unregister_button.setEnabled("issued" in statuses)
        self.card_approve_button.setVisible(self.card_view == "new")
        self.card_register_button.setVisible(self.card_view == "new")
        self.card_reject_button.setVisible(self.card_view == "new")
        self.card_unregister_button.setVisible(self.card_view == "issued")

    def approve_cards(self):
        targets = [r["id"] for r in self.checked_card_requests() if r["status"] == "waiting"]
        for request_id in targets:
            card_logic.approve_request(self.vault(), request_id, self.router.admin_id)
            self.router.audit("card_approved", request_id)
        self.load_cards(keep=targets)
        self.done(f"{len(targets)}건 승인했어요")

    def register_cards(self):
        """승인된 신청마다 빈 카드를 차례로 찍는다 (남은 초는 위쪽 띠)."""
        self.card_queue = [r["id"] for r in self.checked_card_requests() if r["status"] == "approved"]
        self.next_card_in_queue()

    def next_card_in_queue(self):
        if not self.card_queue:
            return
        request_id = self.card_queue[0]
        request = card_logic.requests_of(self.vault())[request_id]
        nickname = self.vault().read("customers", default={}).get(request["customer_id"], {}).get(
            "extra", {}).get("nickname", "")
        self.done(f"{nickname} 님 카드를 리더기에 대 주세요")

        def on_card(number):
            try:
                issued = card_logic.issue_card(self.vault(), request_id, number, self.router.admin_id)
            except ValueError as error:
                self.card_queue = []
                self.fail(f"{error}\n'카드 등록'을 다시 눌러 주세요")
                return
            self.router.audit("card_issued", f"{request_id} {issued['customer_id']}")
            self.card_queue.pop(0)
            fee = f"\n재발급 수수료 {issued['fee']:,}원을 받아 주세요" if issued["fee"] else ""
            self.load_cards(keep=self.card_queue)
            self.done(f"카드 등록 완료 ({card_logic.masked_card(issued['card_tail'])})\n"
                      f"카운터에서 손님에게 건네 주세요{fee}")
            if self.card_queue:
                QTimer.singleShot(1500, self.next_card_in_queue)   # 다음 사람 카드

        def on_timeout():
            self.card_queue = []
            self.fail("카드가 찍히지 않았어요.\n'카드 등록'을 다시 눌러 주세요")

        seconds = kiosk_logic.load_kiosk(self.vault().read("settings", default={}))["card_wait_seconds"]
        self.router.wait_card(on_card, seconds, owner=self, prompt=f"{nickname} 님 카드를 리더기에 대 주세요",
                              on_timeout=on_timeout)

    def reject_cards(self):
        targets = [r["id"] for r in self.checked_card_requests() if r["status"] in ("waiting", "approved")]
        for request_id in targets:
            card_logic.reject_request(self.vault(), request_id, self.router.admin_id)
            self.router.audit("card_rejected", request_id)
        self.load_cards()
        self.done(f"{len(targets)}건 거절했어요")

    def unregister_cards(self):
        targets = [r["id"] for r in self.checked_card_requests() if r["status"] == "issued"]
        for request_id in targets:
            card_logic.unregister_card(self.vault(), request_id, self.router.admin_id)
            self.router.audit("card_unregistered", request_id)
        self.load_cards()
        self.done(f"{len(targets)}건 등록 해제했어요 · 그 카드로는 더 로그인할 수 없어요")

    def make_points_page(self):
        """포인트 조정 (11/02): 회원 찾기 → 고르고 → 금액·사유를 다 넣었을 때만 저장."""
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)
        self.point_search = text_field("회원 ID · 닉네임")
        self.point_search.textChanged.connect(self.load_points)
        column.addWidget(self.point_search)
        self.point_table = table(["회원 ID", "닉네임", "포인트", "최근 내역"])
        fit_columns(self.point_table, 3)
        self.point_table.itemSelectionChanged.connect(self.update_adjust_button)
        column.addWidget(self.point_table, 1)
        adjust = QHBoxLayout()
        self.adjust_delta = text_field("+500 / -300")
        self.adjust_reason = text_field("조정 사유")
        for field in (self.adjust_delta, self.adjust_reason):
            field.textChanged.connect(lambda _text: self.update_adjust_button())
        adjust.addWidget(self.adjust_delta, 1)
        adjust.addWidget(self.adjust_reason, 2)
        self.adjust_button = button("저장", "primary", self.save_adjust)
        adjust.addWidget(self.adjust_button)
        column.addLayout(adjust)
        return page

    def update_adjust_button(self):
        ready = (selected_key(self.point_table) is not None and bool(self.adjust_delta.text().strip())
                 and bool(self.adjust_reason.text().strip()))
        self.adjust_button.setEnabled(ready)

    def load_points(self):
        keyword = self.point_search.text().strip().lower()
        customers = self.vault().read("customers", default={})
        rows, keys = [], []
        for customer_id, record in sorted(customers.items()):
            extra = record["extra"]
            if keyword and keyword not in f"{extra.get('login_id', '')} {extra['nickname']}".lower():
                continue
            last = (extra.get("point_history") or [{}])[-1]
            rows.append([extra.get("login_id", ""), extra["nickname"], f"{extra['points']:,}P",
                         f"{last.get('delta', 0):+,}P {last.get('reason', '')}" if last else ""])
            keys.append(customer_id)
        fill_table(self.point_table, rows, keys)
        self.update_adjust_button()

    # ---- 광고 배너 (11/02 B7): 시작 화면 왼쪽 광고 넣기 · 빼기 · 순서 · 보이기
    def make_banners_page(self):
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)
        left = QVBoxLayout()
        self.banner_table = table(["", "순서", "그림", "글", "보이기"])
        fit_columns(self.banner_table, 3)
        self.banner_table.itemSelectionChanged.connect(self.show_banner_preview)
        self.banner_table.itemChanged.connect(lambda _item: self.update_banner_buttons())
        left.addWidget(self.banner_table, 1)
        moves = QHBoxLayout()
        self.banner_up = button("▲ 위로", "outline", lambda: self.move_banner(-1))
        self.banner_down = button("▼ 아래로", "outline", lambda: self.move_banner(1))
        self.banner_show = button("보이기", "outline", lambda: self.show_banners(True))
        self.banner_hide = button("숨기기", "outline", lambda: self.show_banners(False))
        self.banner_delete = button("삭제", "outline", self.delete_banners)
        for widget in (self.banner_up, self.banner_down, self.banner_show, self.banner_hide, self.banner_delete):
            moves.addWidget(widget)
        left.addLayout(moves)
        add = QHBoxLayout()
        self.banner_file = QComboBox()
        self.banner_file.setFont(theme.font(14))
        self.banner_file.setMinimumHeight(44)
        files = [f"{p.name}" for p in sorted(theme.ASSETS.glob("promo_*"))]
        files += [f"menu/{p.name}" for p in sorted((theme.ASSETS / "menu").glob("M*.png"))]
        self.banner_file.addItems(files)
        self.banner_caption = text_field("아래에 쓸 글 (비워도 돼요)")
        add.addWidget(self.banner_file, 2)
        add.addWidget(self.banner_caption, 2)
        add.addWidget(button("+ 추가", "primary", self.add_banner))
        left.addLayout(add)
        row.addLayout(left, 3)
        preview = Card()
        preview_box = QVBoxLayout(preview)
        preview_box.setContentsMargins(14, 12, 14, 12)
        self.banner_preview = QLabel()
        self.banner_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner_preview.setMinimumSize(220, 220)
        preview_box.addWidget(self.banner_preview, 1)
        row.addWidget(preview, 2)
        return page

    def banners(self):
        return kiosk_logic.all_slides(self.vault().read("settings", default={}))

    def load_banners(self, keep=()):
        slides = self.banners()
        fill_table(self.banner_table, [["", f"{index + 1}", s["file"].split("/")[-1].rsplit(".", 1)[0],
                                        s.get("caption", ""), "보임" if s.get("on") else "숨김"]
                                       for index, s in enumerate(slides)],
                   list(range(len(slides))))
        add_checks(self.banner_table, keep)
        self.update_banner_buttons()
        self.show_banner_preview()

    def update_banner_buttons(self):
        chosen = checked_keys(self.banner_table)
        slides = self.banners()
        states = {bool(slides[i].get("on")) for i in chosen if i < len(slides)}
        one = len(chosen) == 1
        self.banner_up.setEnabled(one and chosen[0] > 0)
        self.banner_down.setEnabled(one and chosen[0] < len(slides) - 1)
        self.banner_show.setEnabled(False in states)
        self.banner_hide.setEnabled(True in states)
        self.banner_delete.setEnabled(bool(chosen))

    def show_banner_preview(self):
        index = selected_key(self.banner_table)
        slides = self.banners()
        if index is None or index >= len(slides):
            self.banner_preview.clear()
            return
        picture = QPixmap(str(theme.ASSETS / slides[index]["file"]))
        self.banner_preview.setPixmap(picture.scaled(260, 260, Qt.AspectRatioMode.KeepAspectRatio,
                                                     Qt.TransformationMode.SmoothTransformation))

    def save_banners(self, slides, keep=(), note=""):
        try:
            kiosk_logic.save_slides(self.vault(), slides)
        except ValueError as error:
            self.fail(error)
            return
        self.router.audit("banner_save", f"{sum(bool(s.get('on')) for s in slides)}/{len(slides)}")
        self.load_banners(keep)
        if note:
            self.done(note)

    def move_banner(self, step):
        index = checked_keys(self.banner_table)[0]
        slides = self.banners()
        slides[index], slides[index + step] = slides[index + step], slides[index]
        self.save_banners(slides, keep=[index + step])

    def show_banners(self, on):
        chosen = checked_keys(self.banner_table)
        slides = self.banners()
        for index in chosen:
            slides[index]["on"] = on
        self.save_banners(slides, keep=chosen, note=f"{len(chosen)}장 {'보이기' if on else '숨기기'}")

    def delete_banners(self):
        chosen = set(checked_keys(self.banner_table))
        slides = [s for index, s in enumerate(self.banners()) if index not in chosen]
        self.save_banners(slides, note=f"{len(chosen)}장 삭제했어요")

    def add_banner(self):
        file = self.banner_file.currentText()
        fit = "contain" if file.startswith("promo_") else "cover"
        slides = self.banners() + [{"file": file, "caption": self.banner_caption.text().strip(), "fit": fit, "on": True}]
        self.banner_caption.clear()
        self.save_banners(slides, keep=[len(slides) - 1], note="광고를 맨 뒤에 추가했어요")

    # ---- 키오스크 설정 (11/02 B8)
    def make_kiosk_page(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(10)
        form = Card()
        rows = QVBoxLayout(form)
        rows.setContentsMargins(22, 16, 22, 16)
        rows.setSpacing(12)
        self.kiosk_fields = {}
        for key, name, unit, default, low, high in kiosk_logic.KIOSK_FIELDS:
            row = QHBoxLayout()
            title = label(name, 17, bold=True)
            title.setFixedWidth(280 if theme.SCALE == 1 else 330)
            row.addWidget(title)
            field = text_field(str(default))
            field.setFixedWidth(110)
            self.kiosk_fields[key] = field
            row.addWidget(field)
            row.addWidget(label(f"{unit}  ({low}~{high})", 15, muted=True))
            row.addStretch(1)
            rows.addLayout(row)
        self.ticket_switch = QCheckBox("승차권 탭 보이기")
        self.ticket_switch.setFont(theme.font(17, bold=True))
        rows.addWidget(self.ticket_switch)
        column.addWidget(form)
        save = QHBoxLayout()
        save.addStretch()
        save.addWidget(button("기본값으로", "outline", self.reset_kiosk))
        save.addWidget(button("설정 저장", "primary", self.save_kiosk))
        column.addLayout(save)
        column.addStretch()
        return page

    def load_kiosk(self):
        settings = self.vault().read("settings", default={})
        values = kiosk_logic.load_kiosk(settings)
        for key, field in self.kiosk_fields.items():
            field.setText(str(values[key]))
        self.ticket_switch.setChecked(settings.get("ticket_sales", True) is not False)

    def reset_kiosk(self):
        for key, field in self.kiosk_fields.items():
            field.setText(str(kiosk_logic.KIOSK_DEFAULTS[key]))
        self.ticket_switch.setChecked(True)

    def save_kiosk(self):
        raw = {key: field.text().strip() or field.placeholderText() for key, field in self.kiosk_fields.items()}
        try:
            saved = kiosk_logic.save_kiosk(self.vault(), raw, self.ticket_switch.isChecked())
        except ValueError as error:
            self.fail(error)
            return
        self.router.apply_kiosk_settings()
        self.router.audit("kiosk_settings_save", " ".join(f"{k}={v}" for k, v in saved.items()))
        self.load_kiosk()
        self.done("키오스크 설정을 저장했어요")

    def make_log_page(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)
        filters = QHBoxLayout()
        self.log_kind = QComboBox()
        self.log_kind.addItems(list(LOG_KINDS))
        self.log_period = QComboBox()
        self.log_period.addItems(["전체 기간", "오늘", "최근 7일"])
        for combo in (self.log_kind, self.log_period):
            combo.setFont(theme.font(15))
            combo.setMinimumHeight(44)
            combo.currentTextChanged.connect(lambda _text: self.load_audit())
            filters.addWidget(combo)
        filters.addStretch()
        self.audit_title = label("", 15, bold=True)
        filters.addWidget(self.audit_title)
        column.addLayout(filters)
        self.audit_table = table(["번호", "시각", "운영자", "행동", "대상"])
        fit_columns(self.audit_table, 4)
        column.addWidget(self.audit_table, 1)
        return page

    def load_log(self):
        self.load_audit()

    def load_audit(self):
        if self.router.audit_memory_only() or not config.KEYSTORE_PATH.exists():
            entries = [{"seq": i + 1, "ts": e.get("ts", 0), **e} for i, e in enumerate(self.router.audit_memory)]
            state = "메모리 기록(시연 모드)"
        else:
            log = audit.AuditLog(Path(config.DATA_DIR) / "audit.log")
            entries = log._entries()
            ok, broken = log.verify()
            state = "무결성 검사: 정상" if ok else f"무결성 검사: {broken}번째 줄부터 변조 의심"
        prefixes = LOG_KINDS[self.log_kind.currentText()]
        days = {"오늘": 0, "최근 7일": 7}.get(self.log_period.currentText())
        today = datetime.now().date()
        shown = [e for e in entries
                 if (not prefixes or e["action"].startswith(prefixes))
                 and (days is None or (e["ts"] and (today - datetime.fromtimestamp(e["ts"]).date()).days <= days))]
        self.audit_title.setText(f"{len(shown)}건 · {state}")
        fill_table(self.audit_table, [[e["seq"], datetime.fromtimestamp(e["ts"]).strftime("%m-%d %H:%M") if e["ts"] else "-",
                                       e["actor"], e["action"], e["target"]] for e in reversed(shown[-200:])])

    def save_adjust(self):
        customer_id = selected_key(self.point_table)
        if customer_id is None:
            self.fail("포인트를 조정할 회원을 먼저 선택하세요")
            return
        try:
            delta = as_int(self.adjust_delta.text().replace("+", ""), "조정 포인트")
            if self.adjust_delta.text().strip().startswith("-"):
                delta = -abs(delta)
            record = adjust_points(self.vault(), customer_id, delta, self.adjust_reason.text(),
                                   self.router.admin_id)
        except ValueError as error:
            self.fail(error)
            return
        self.router.audit("points_adjust", f"{customer_id} {delta:+d}")
        self.adjust_delta.clear()
        self.adjust_reason.clear()
        self.load_points()
        self.done(f"{record['extra']['nickname']} {delta:+,}P → 잔액 {record['extra']['points']:,}P")

    # ---- 종료·로그아웃
    def logout(self):
        """플로차트: 로그아웃 → 고객 HOME(01). 운영자 기록을 남기고 운영자 상태를 지운다."""
        self.router.audit("admin_logout")
        self.router.admin_id = None
        self.router.show_screen("home")

    def shutdown(self):
        self.router.audit("kiosk_shutdown")
        self.router.admin_id = None
        self.window().close()
        QApplication.instance().quit()
