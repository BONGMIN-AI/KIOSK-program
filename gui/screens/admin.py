"""09 운영자 (와이어프레임 v2.1): 09-A 로그인 · 09-B 메뉴 관리 · 09-C 회원·주문 조회 ·
09-D 이벤트·포인트 · 09-E 포인트 조정·감사 로그 · KIOSK 종료 · 로그아웃.

플로차트: 01 운영자 메뉴 → 09-A 운영자 로그인 → 메뉴·회원·이벤트·포인트·종료 → 로그아웃 → 01 고객 HOME.
운영자가 바꾼 것은 모두 감사 로그(해시 체인)에 남는다. 고객 전화번호는 가려서 보여 준다.
"""

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox,
                               QHBoxLayout, QHeaderView, QScrollArea, QStackedWidget, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

import config
from core import audit, auth, schema
from core.validators import mask_phone
from domain import policy as policy_logic
from domain.titles import title_name
from domain.customers import adjust_points
from face import FaceError
from gui import theme
from gui.order import CATEGORY_ORDER
from gui.screens.login import info_box, nav_bar
from gui.widgets import Card, TouchKeyboard, button, label, message_label, text_field

TABS = [("menu", "메뉴 관리"), ("members", "회원·주문 조회"), ("events", "이벤트·포인트"), ("points", "포인트 조정·로그")]
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


def fill_table(widget, rows, keys=None):
    """rows: 칸 문자열 목록들. keys: 줄마다 붙일 ID(선택할 때 쓴다)."""
    widget.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            item = QTableWidgetItem(str(value))
            if keys is not None and c == 0:
                item.setData(Qt.ItemDataRole.UserRole, keys[r])
            widget.setItem(r, c, item)


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
        tabs = QHBoxLayout()
        self.tab_group = QButtonGroup(self)
        for key, name in TABS:
            tab = button(name, "option", lambda checked=False, k=key: self.show_tab(k))
            tab.setCheckable(True)
            tab.setObjectName(f"tab_{key}")
            self.tab_group.addButton(tab)
            tabs.addWidget(tab, 1)
        layout.addLayout(tabs)
        self.pages = QStackedWidget()
        self.page_of = {"menu": self.make_menu_page(), "members": self.make_members_page(),
                        "events": self.make_events_page(), "points": self.make_points_page()}
        for page in self.page_of.values():
            self.pages.addWidget(page)
        layout.addWidget(self.pages, 1)
        self.message = message_label()
        layout.addWidget(self.message)
        bottom = nav_bar(router, lambda: router.show_screen("home"))
        bottom.addWidget(button("KIOSK 종료", "outline", self.shutdown))
        bottom.addWidget(button("로그아웃", "primary", self.logout))
        layout.addLayout(bottom)

    def vault(self):
        return self.router.session.vault

    def on_show(self, tab="menu"):
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
    def make_menu_page(self):
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)
        left = QVBoxLayout()
        search_row = QHBoxLayout()
        self.menu_search = text_field("메뉴명 검색")
        self.menu_search.textChanged.connect(self.load_menu)
        search_row.addWidget(self.menu_search, 1)
        search_row.addWidget(button("+ 추가", "outline", self.new_menu))
        left.addLayout(search_row)
        self.menu_table = table(["메뉴명", "분류", "가격", "재고", "상태"])
        self.menu_table.itemSelectionChanged.connect(self.select_menu)
        left.addWidget(self.menu_table, 1)
        row.addLayout(left, 3)
        form_card = Card()
        form = QVBoxLayout(form_card)
        form.setContentsMargins(18, 14, 18, 14)
        form.setSpacing(8)
        self.menu_form_title = label("선택 메뉴 수정", 20, bold=True)
        form.addWidget(self.menu_form_title)
        self.menu_name = text_field("메뉴명")
        self.menu_category = QComboBox()
        self.menu_category.addItems(CATEGORY_ORDER)
        self.menu_category.setFont(theme.font(16))
        self.menu_category.setMinimumHeight(48)
        self.menu_price = text_field("가격")
        self.menu_stock = text_field("재고")
        for title, widget in (("메뉴명 *", self.menu_name), ("카테고리 *", self.menu_category),
                              ("가격 *", self.menu_price), ("재고", self.menu_stock)):
            form.addLayout(field_row(title, widget))
        self.sold_out_button = button("판매 중 ↔ 품절", "outline", self.toggle_sold_out)
        form.addWidget(self.sold_out_button)
        actions = QHBoxLayout()
        actions.addWidget(button("수정 저장", "primary", self.save_menu))
        actions.addWidget(button("선택 삭제", "outline", self.delete_menu))
        form.addLayout(actions)
        form.addWidget(label("* 필수 · 삭제는 두 번 눌러 확인 · 이미지는 컵 그림으로 자동 표시", 13, muted=True))
        form.addStretch()
        row.addWidget(form_card, 2)
        self.editing_menu = None
        return page

    def load_menu(self):
        keyword = self.menu_search.text().strip()
        items = [i for i in sorted(self.vault().read("menu", default={}).values(), key=lambda i: i["id"])
                 if keyword in i["name"]]
        fill_table(self.menu_table, [[i["name"], i["category"], f"{i['price']:,}", i["stock"],
                                      "품절" if i.get("sold_out") else "판매 중"] for i in items],
                   [i["id"] for i in items])

    def select_menu(self):
        menu_id = selected_key(self.menu_table)
        if menu_id is None:
            return
        item = self.vault().read("menu")[menu_id]
        self.editing_menu = menu_id
        self.menu_form_title.setText(f"선택 메뉴 수정 · {item['name']}")
        self.menu_name.setText(item["name"])
        self.menu_category.setCurrentText(item["category"])
        self.menu_price.setText(str(item["price"]))
        self.menu_stock.setText(str(item["stock"]))

    def new_menu(self):
        self.editing_menu = None
        self.menu_table.clearSelection()
        self.menu_form_title.setText("새 메뉴 추가")
        for field in (self.menu_name, self.menu_price, self.menu_stock):
            field.clear()

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
        self.done(f"{menu_id} '{name}' 저장했습니다")

    def toggle_sold_out(self):
        menu = self.vault().read("menu", default={})
        item = menu.get(self.editing_menu or "")
        if item is None:
            self.fail("메뉴를 먼저 선택하세요")
            return
        if item["sold_out"] and item["stock"] == 0:
            self.fail("재고가 0개입니다. 재고를 먼저 채우고 저장하세요")
            return
        item["sold_out"] = not item["sold_out"]
        self.vault().write("menu", menu)
        self.router.audit("menu_sold_out" if item["sold_out"] else "menu_on_sale", item["id"])
        self.load_menu()
        self.done(f"{item['name']} → {'품절' if item['sold_out'] else '판매 중'}")

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
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)
        search_row = QHBoxLayout()
        self.member_search = text_field("회원 ID / 닉네임 / 주문번호")
        self.member_search.textChanged.connect(self.load_members)
        search_row.addWidget(self.member_search, 1)
        search_row.addWidget(button("전체 보기", "outline", lambda: self.member_search.clear()))
        column.addLayout(search_row)
        column.addWidget(label("회원 데이터 · 주문 완료 후 상태", 17, bold=True))
        self.member_table = table(["회원 ID", "닉네임", "칭호", "전화번호", "포인트", "쿠폰", "방문 횟수"])
        column.addWidget(self.member_table, 1)
        column.addWidget(label("주문 데이터", 17, bold=True))
        self.order_table = table(["주문번호", "품목 / 수량", "결제 금액", "결제 방식", "회원", "시각"])
        column.addWidget(self.order_table, 1)
        return page

    def load_members(self):
        keyword = self.member_search.text().strip().lower()
        customers = self.vault().read("customers", default={})
        rows, keys = [], []
        for customer_id, record in sorted(customers.items()):
            extra = record["extra"]
            if keyword and keyword not in extra.get("login_id", "").lower() and keyword not in extra["nickname"].lower():
                continue
            rows.append([extra.get("login_id", ""), extra["nickname"], title_name(extra.get("title", "")),
                         mask_phone(record["phone"]), f"{extra['points']:,}P",
                         f"{len(extra.get('coupons', []))}장", f"{extra['visits']}회"])
            keys.append(customer_id)
        fill_table(self.member_table, rows, keys)
        orders = self.vault().read("orders", default={})
        order_rows = []
        for order_id, order in sorted(orders.items(), reverse=True):
            member = order.get("customer") or {}
            text = ", ".join(f"{l['name']}×{l['quantity']}" for l in order["lines"])
            if keyword and keyword not in order_id.lower() and keyword not in member.get("nickname", "").lower():
                continue
            order_rows.append([order_id, text, f"{order['final_total']:,}원", "현금",
                               member.get("nickname", "비회원"), order["created_at"][5:16].replace("T", " ")])
        fill_table(self.order_table, order_rows)
        if keyword and not rows and not order_rows:
            self.fail(f"'{keyword}'에 맞는 회원·주문이 없어요")

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
        self.policy_text = label("", 14, muted=True)
        self.policy_text.setWordWrap(True)
        left.addWidget(self.policy_text)
        row.addLayout(left, 3)
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
        row.addWidget(scroll, 3)
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
        coupon = (f"방문 {policy['visit_coupon_every']}회마다 {policy['visit_coupon_amount']:,}원 쿠폰"
                  if policy["visit_coupon_every"] else "방문 쿠폰 끔")
        self.policy_text.setText(f"기본 정책: 적립 {policy['base_rate']:g}% · {policy['point_unit']}P 단위 · "
                                 f"최소 {policy['min_use']}P · 결제액의 {policy['max_use_percent']}%까지 · {coupon} · "
                                 f"개인 컵 {policy['eco_points']}P/잔\n"
                                 "* 회원 주문만 적립 · 한 메뉴에 이벤트가 겹치면 가장 높은 적립률 1개 · "
                                 "진행 중 이벤트 테마가 손님 화면(대기 띠·메뉴 배너)에 적용")
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
    def make_points_page(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(label("회원 포인트 조정 · 사유 필수", 17, bold=True))
        self.point_table = table(["회원 ID", "닉네임", "포인트", "최근 내역"])
        column.addWidget(self.point_table, 1)
        adjust = QHBoxLayout()
        self.adjust_delta = text_field("+500 / -300")
        self.adjust_reason = text_field("조정 사유 (필수)")
        adjust.addWidget(self.adjust_delta, 1)
        adjust.addWidget(self.adjust_reason, 2)
        adjust.addWidget(button("조정 저장", "primary", self.save_adjust))
        column.addLayout(adjust)
        self.audit_title = label("감사 로그", 17, bold=True)
        column.addWidget(self.audit_title)
        self.audit_table = table(["번호", "시각", "운영자", "행동", "대상"])
        column.addWidget(self.audit_table, 1)
        return page

    def load_points(self):
        customers = self.vault().read("customers", default={})
        rows, keys = [], []
        for customer_id, record in sorted(customers.items()):
            extra = record["extra"]
            last = (extra.get("point_history") or [{}])[-1]
            rows.append([extra.get("login_id", ""), extra["nickname"], f"{extra['points']:,}P",
                         f"{last.get('delta', 0):+,}P {last.get('reason', '')}" if last else ""])
            keys.append(customer_id)
        fill_table(self.point_table, rows, keys)
        self.load_audit()

    def load_audit(self):
        if self.router.audit_memory_only() or not config.KEYSTORE_PATH.exists():
            entries = [{"seq": i + 1, "ts": 0, **e} for i, e in enumerate(self.router.audit_memory)]
            state = "메모리 기록(시연 모드)"
        else:
            log = audit.AuditLog(Path(config.DATA_DIR) / "audit.log")
            entries = log._entries()
            ok, broken = log.verify()
            state = "무결성 검사: 정상" if ok else f"무결성 검사: {broken}번째 줄부터 변조 의심"
        self.audit_title.setText(f"감사 로그 · {state}")
        fill_table(self.audit_table, [[e["seq"], datetime.fromtimestamp(e["ts"]).strftime("%m-%d %H:%M") if e["ts"] else "-",
                                       e["actor"], e["action"], e["target"]] for e in reversed(entries[-50:])])

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
