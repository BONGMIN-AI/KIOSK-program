"""09 운영자 (와이어프레임 v2.1): 09-A 로그인 · 09-B 메뉴 관리 · 09-C 회원·주문 조회 ·
09-D 이벤트·포인트 · 09-E 포인트 조정·감사 로그 · KIOSK 종료 · 로그아웃.

플로차트: 01 운영자 메뉴 → 09-A 운영자 로그인 → 메뉴·회원·이벤트·포인트·종료 → 로그아웃 → 01 고객 HOME.
운영자가 바꾼 것은 모두 감사 로그(해시 체인)에 남는다. 고객 전화번호는 가려서 보여 준다.
"""

from datetime import date, datetime, timedelta
from pathlib import Path
import shutil
from uuid import uuid4

import numpy as np
from PySide6.QtCore import QElapsedTimer, QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QImage, QImageReader, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox, QFrame,
                               QFileDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

import config
from core import admin_badge, audit, auth, schema
from face import guide_view
from core.validators import mask_phone
from domain import member_cards as card_logic
from domain import policy as policy_logic
from domain import coupons as coupon_logic
from domain import kiosk_settings as kiosk_logic
from domain import sales as sales_logic
from domain import seasonal_theme
from domain.titles import title_name
from domain.customers import adjust_points, update_member_info
from face import FaceError
from gui import theme
from gui.order import CATEGORY_ORDER
from gui.screens.login import info_box, nav_bar
from gui.widgets import Card, Slideshow, TouchKeyboard, TrendBars, button, label, message_label, phone_field, text_field

# 왼쪽 목록 (11/02: 위쪽 탭 → 묶음별 세로 목록, 한 화면에 한 가지 일)
SECTIONS = [
    ("매장", [("sales", "매출 요약"), ("menu", "메뉴 · 재고")]),
    ("회원", [("members", "회원 목록"), ("orders", "주문 기록"), ("cards", "회원카드"), ("points", "포인트 조정")]),
    ("혜택 · 행사", [("events_add", "이벤트 생성"), ("events", "이벤트 목록·수정"),
                    ("coupons", "쿠폰"), ("perks", "혜택 설정")]),
    ("화면 · 설정", [("banners", "광고 배너"), ("login_ads", "로그인 광고"),
                    ("season", "계절 테마"), ("kiosk", "키오스크 설정")]),
    ("기록", [("log", "운영 기록")]),
]
TABS = [item for _, items in SECTIONS for item in items]
def chevron(opened, size=14):
    """묶음 이름 앞 화살표 그림 (펼침 ∨ · 접힘 >). 글꼴에 ▾ ▸가 없어 네모로 보여서 직접 그린다."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(theme.TEXT2), 2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    s = size
    points = ([QPointF(s * 0.2, s * 0.35), QPointF(s * 0.5, s * 0.65), QPointF(s * 0.8, s * 0.35)] if opened
              else [QPointF(s * 0.35, s * 0.2), QPointF(s * 0.65, s * 0.5), QPointF(s * 0.35, s * 0.8)])
    painter.drawPolyline(points)
    painter.end()
    return QIcon(pixmap)
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
    widget.horizontalHeader().setFont(theme.font(14, bold=True))     # 표 제목이 작고 흐리게 보이던 것 (11/09)
    widget.verticalHeader().setDefaultSectionSize(30)
    widget.setStyleSheet(f"QTableWidget {{ background: {theme.CARD}; border: 1px solid {theme.LINE};"
                         f" border-radius: 12px; gridline-color: {theme.LINE}; }}"
                         f" QHeaderView::section {{ background: {theme.CARAMEL_LIGHT}; border: none;"
                         " padding: 6px; font-weight: bold; }")
    return widget


LOG_KINDS = {   # 운영 기록 걸러 보기 (11/02): 이름 → 이 글자로 시작하는 기록
    "전체": (), "로그인·종료": ("admin_", "kiosk_"), "메뉴": ("menu_",), "회원카드": ("card_",),
    "포인트": ("points_",), "이벤트·혜택": ("event_", "card_perks", "coupon_"), "회원": ("member_",),
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
    """짧은 칸은 내용에 맞추고 남는 폭은 두 칸에 나눠 준다."""
    header = widget.horizontalHeader()
    for index in range(widget.columnCount()):
        header.setSectionResizeMode(index, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(stretch, QHeaderView.ResizeMode.Stretch)
    other = widget.columnCount() - 1 if stretch != widget.columnCount() - 1 else max(0, stretch - 1)
    if other != stretch:
        header.setSectionResizeMode(other, QHeaderView.ResizeMode.Stretch)


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


def align_right(widget, columns):
    """금액 · 수량 칸은 오른쪽 정렬해 자릿수를 한눈에 비교한다 (fill_table 다음에 부른다)."""
    for row in range(widget.rowCount()):
        for column in columns:
            item = widget.item(row, column)
            if item is not None:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)


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
        self.keyboard = keyboard = TouchKeyboard()
        keyboard.attach(self.admin_id, self.password)
        right.addWidget(keyboard)
        # 11/04 회의: 얼굴 확인은 큰 카메라 창 대신 이 칸 안에서 (회원 로그인처럼 라떼 얼굴 + 지금 할 일 한 줄)
        self.face_step = label("", 20, bold=True)
        self.face_step.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.face_step.setWordWrap(True)
        self.face_step.hide()
        right.addWidget(self.face_step)
        self.face_picture = QLabel()
        self.face_picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.face_picture.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.face_picture.setStyleSheet("background: rgb(250, 250, 250); border-radius: 16px;")
        self.face_picture.hide()
        right.addWidget(self.face_picture, 1)
        self.cancel_face_button = button("얼굴 확인 취소", "outline", self.cancel_face)
        self.cancel_face_button.hide()
        right.addWidget(self.cancel_face_button)
        self.face_cancelled = False
        right.addStretch()
        body.addWidget(right_card)
        layout.addLayout(body, 1)
        layout.addLayout(nav_bar(router, lambda: router.show_screen("home")))

    def on_show(self, badge=False):
        """badge=True: 관리자 카드를 대고 들어왔다 (11/04) → 바로 이 화면 안에서 운영자 얼굴 확인."""
        self.password.clear()
        self.message.setText("")
        if badge:
            self.admin_id.setText(admin_badge.ADMIN_ID)
            QTimer.singleShot(0, self, lambda: self.face_login(badge=True))

    # 화면 안 얼굴 확인 (회원 로그인 화면과 같은 방식)
    def begin_face(self, text):
        self.face_cancelled = False
        self.keyboard.hide()
        self.face_step.setText(text)
        for widget in (self.face_step, self.face_picture, self.cancel_face_button):
            widget.show()
        self.repaint()

    def end_face(self):
        for widget in (self.face_step, self.face_picture, self.cancel_face_button):
            widget.hide()
        self.face_picture.clear()
        self.keyboard.show()

    def cancel_face(self):
        self.face_cancelled = True

    def show_step(self, text):
        self.face_step.setText(text)

    def show_face(self, image, wait_ms=1):
        """얼굴 공급자가 프레임마다 부른다: 안내 그림에서 라떼 얼굴 둘레만 잘라 이 칸에 그린다."""
        cx, cy = guide_view.ROI_CENTER
        part = np.ascontiguousarray(image[cy - 190:cy + 190, cx - 190:cx + 190])
        height, width = part.shape[:2]
        frame = QImage(part.data, width, height, part.strides[0], QImage.Format.Format_BGR888).copy()
        self.face_picture.setPixmap(QPixmap.fromImage(frame).scaled(
            self.face_picture.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        clock = QElapsedTimer()
        clock.start()
        while True:
            QApplication.processEvents()
            if self.face_cancelled or clock.elapsed() >= wait_ms:
                return self.face_cancelled

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

    def face_login(self, badge=False):
        """운영자 얼굴 확인. badge=True면 관리자 카드에 같이 저장한 얼굴(data/admin_badge.bin)과 비교한다."""
        admin_id = admin_badge.ADMIN_ID if badge else self.admin_id.text().strip().lower()
        key = admin_badge.ADMIN_KEY if badge else auth.admin_face_key(admin_id)
        # 주 관리자 얼굴은 재실행해도 남는 관리자 카드 금고에 저장돼 있다.
        # 시연 모드의 회원 금고는 매번 새로 만들어지므로 여기서 읽으면 얼굴 로그인이 끊긴다.
        persistent_admin = admin_id == admin_badge.ADMIN_ID and key in admin_badge.load().get("face_profiles", {})
        face_vault = admin_badge.BadgeVault() if badge or persistent_admin else None
        scores = []
        self.message.setText("")
        self.begin_face("관리자 카드 확인 · 카메라를 켜는 중이에요…" if badge else "카메라를 켜는 중이에요…")
        try:
            matched = self.router.run_face(lambda provider: provider.identify_face(key, scores.append),
                                           viewer=self.show_face, on_step=self.show_step,
                                           vault=face_vault)
        except (FaceError, ValueError) as error:
            self.end_face()
            self.message.setText(f"{error} · 비밀번호 로그인을 사용하세요")
            return
        self.end_face()
        score = next((text for text in reversed(scores) if text.startswith("얼굴 유사도")), "")
        if matched != key:
            self.message.setText(f"얼굴이 일치하지 않습니다. 비밀번호 로그인을 사용하세요 · {score}")
            return
        if score:
            print(f"[운영자 얼굴 로그인] {admin_id} · {score}", flush=True)
        self.enter(admin_id, "관리자 카드 + 얼굴" if badge else "얼굴")

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
        tree.setContentsMargins(8, 8, 8, 8)
        tree.setSpacing(1)
        self.tab_group = QButtonGroup(self)
        # 11/04 회의 2: 색 칸 대신 굵은 묶음 이름 + 들여쓴 하위 목차. 묶음 이름을 누르면 접히고 다시 누르면 펼쳐진다
        self.section_heads, self.section_tabs = {}, {}
        for section, items in SECTIONS:
            head = QPushButton(f" {section}")
            head.setIcon(chevron(True))
            head.setObjectName("section_head")
            head.setCursor(Qt.CursorShape.PointingHandCursor)
            head.setFont(theme.font(16, bold=True))
            head.setMinimumHeight(34)
            head.setStyleSheet(f"QPushButton#section_head {{ text-align: left; padding-left: 6px; border: none;"
                               f" background: transparent; color: {theme.BROWN}; }}")
            head.clicked.connect(lambda checked=False, s=section: self.toggle_section(s))
            tree.addWidget(head)
            self.section_heads[section] = head
            self.section_tabs[section] = []
            for key, name in items:
                tab = button(name, "category", lambda checked=False, k=key: self.show_tab(k))
                tab.setCheckable(True)
                tab.setObjectName(f"tab_{key}")
                tab.setStyleSheet("text-align: left; padding-left: 26px;")      # 들여쓰기
                tab.setFont(theme.font(15))
                tab.setMinimumHeight(34)          # 큰 글자에서도 글자가 눌리지 않는 높이
                self.tab_group.addButton(tab)
                tree.addWidget(tab)
                self.section_tabs[section].append(tab)
        tree.addStretch()
        body.addWidget(nav)
        self.pages = QStackedWidget()
        self.page_of = {"sales": self.make_sales_page(), "menu": self.make_menu_page(),
                        "members": self.make_members_page(),
                        "orders": self.make_orders_page(),
                        "cards": self.make_cards_page(), "points": self.make_points_page(),
                        "events": self.make_events_page(), "events_add": self.make_event_add_page(),
                        "perks": self.make_perks_page(),
                        "coupons": self.make_coupons_page(), "banners": self.make_banners_page(),
                        "login_ads": self.make_login_ads_page(), "season": self.make_season_page(),
                        "kiosk": self.make_kiosk_page(),
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

    def toggle_section(self, section, opened=None):
        """묶음 이름을 누르면 하위 목차를 접고 펼친다 (11/04 회의 2)."""
        tabs = self.section_tabs[section]
        if opened is None:
            opened = not tabs[0].isVisibleTo(self)
        for tab in tabs:
            tab.setVisible(opened)
        self.section_heads[section].setIcon(chevron(opened))

    def show_tab(self, key):
        for section, items in SECTIONS:              # 고른 목차가 접힌 묶음 안이면 펼친다
            if any(k == key for k, _ in items) and not self.section_tabs[section][0].isVisibleTo(self):
                self.toggle_section(section, True)
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
        self.sales_top_title = label("판매 메뉴 전체", 16, bold=True)
        top.addWidget(self.sales_top_title)
        self.sales_top = table(["순위", "메뉴", "수량", "매출"])   # 디저트도 있어 "잔"이 아니라 "개"
        fit_columns(self.sales_top, 1)
        top.addWidget(self.sales_top, 1)
        body.addWidget(top_card, 1)
        hour_card = Card()
        hours = QVBoxLayout(hour_card)
        hours.setContentsMargins(16, 12, 16, 12)
        selector = QHBoxLayout()
        heading = label("분석", 19, bold=True)
        selector.addWidget(heading)
        self.sales_analysis_mode = QComboBox()
        self.sales_analysis_mode.setFont(theme.font(17, bold=True))
        self.sales_analysis_mode.setMinimumHeight(46)
        self.sales_analysis_mode.addItems(("카테고리별 판매", "시간대별 주문", "일별 매출", "주별 매출",
                                           "월별 매출", "회원가입 추이", "카드 등록 추이"))
        self.sales_analysis_mode.currentTextChanged.connect(lambda _mode: self.load_sales_analysis())
        selector.addWidget(self.sales_analysis_mode, 1)
        # 분류 선택은 같은 줄에 (11/09: 따로 한 줄을 쓰면 아래 표가 3~4줄만 보였다)
        self.sales_category_controls = QWidget()
        categories = QHBoxLayout(self.sales_category_controls)
        categories.setContentsMargins(0, 0, 0, 0)
        self.sales_category_picker = QComboBox()
        self.sales_category_picker.setFont(theme.font(16))
        self.sales_category_picker.setMinimumHeight(46)
        self.sales_category_picker.currentTextChanged.connect(lambda _name: self.load_sales_analysis())
        categories.addWidget(self.sales_category_picker, 1)
        self.sales_category_back = button("전체", "outline",
                                          lambda: self.sales_category_picker.setCurrentIndex(0))
        categories.addWidget(self.sales_category_back)
        selector.addWidget(self.sales_category_controls, 1)
        hours.addLayout(selector)
        self.sales_hour_day = date.today()
        self.sales_hour_first_open = True
        self.sales_hour_controls = QWidget()
        days = QHBoxLayout(self.sales_hour_controls)
        days.setContentsMargins(0, 0, 0, 0)
        self.sales_hour_previous = button("← 이전 날", "outline", lambda: self.move_sales_hour_day(-1))
        self.sales_hour_next = button("다음 날 →", "outline", lambda: self.move_sales_hour_day(1))
        self.sales_hour_date = label("", 19, bold=True)
        self.sales_hour_date.setAlignment(Qt.AlignmentFlag.AlignCenter)
        days.addWidget(self.sales_hour_previous)
        days.addWidget(self.sales_hour_date, 1)
        days.addWidget(self.sales_hour_next)
        hours.addWidget(self.sales_hour_controls)
        self.sales_analysis_note = label("", 14, muted=True)
        hours.addWidget(self.sales_analysis_note)
        self.sales_analysis_insight = label("", 15, bold=True)
        hours.addWidget(self.sales_analysis_insight)
        self.sales_hours = TrendBars([str(h) for h in sales_logic.HOURS], [0] * len(sales_logic.HOURS), -1,
                                     unit="건")
        hours.addWidget(self.sales_hours, 1)
        self.sales_analysis_table = table(["분류", "수량", "상품 매출"])
        fit_columns(self.sales_analysis_table, 0)
        self.sales_analysis_table.cellClicked.connect(self.open_sales_category)
        hours.addWidget(self.sales_analysis_table, 1)
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
        fill_table(self.sales_top, [[f"{rank}", name, f"{qty:,}개", f"{sales:,}원"]
                                    for rank, (name, qty, sales) in enumerate(data["top"], 1)])
        align_right(self.sales_top, (2, 3))
        self.sales_top_title.setText(f"판매 메뉴 전체 · {len(data['top'])}종")
        self.load_sales_analysis()

    def load_sales_analysis(self):
        mode = self.sales_analysis_mode.currentText()
        vault = self.vault()
        orders = vault.read("orders", default={})
        bars = self.sales_hours
        self.sales_category_controls.setVisible(mode == "카테고리별 판매")
        self.sales_hour_controls.setVisible(mode == "시간대별 주문")
        self.sales_analysis_table.setVisible(mode != "시간대별 주문")
        if mode == "시간대별 주문":                       # 표가 없으니 남는 높이를 그래프가 다 쓴다 (잘림 · 빈칸 방지)
            bars.setMinimumHeight(170)
            bars.setMaximumHeight(16777215)
            bars.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        else:
            bars.setFixedHeight(130)
            bars.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.sales_analysis_table.setColumnHidden(2, mode != "카테고리별 판매")   # 추이 표의 빈 칸 숨김
        if mode == "카테고리별 판매":
            menu = vault.read("menu", default={})
            categories = sales_logic.category_summary(orders, menu, self.sales_period)
            selected = self.sales_category_picker.currentText()
            self.sales_category_picker.blockSignals(True)
            self.sales_category_picker.clear()
            self.sales_category_picker.addItems(["전체 분류"] + [name for name, _qty, _amount in categories])
            self.sales_category_picker.setCurrentText(selected if selected in
                                                     [name for name, _qty, _amount in categories] else "전체 분류")
            self.sales_category_picker.blockSignals(False)
            selected = self.sales_category_picker.currentText()
            self.sales_category_back.setVisible(selected != "전체 분류")
            if selected == "전체 분류":
                rows = categories
                labels = [name for name, _qty, _amount in rows]
                values = [qty for _name, qty, _amount in rows]
                self.sales_analysis_table.setHorizontalHeaderLabels(["분류", "판매 수량", "상품 매출"])
                self.sales_analysis_note.setText(f"{self.sales_period} · 분류를 누르면 메뉴별 판매 순위를 볼 수 있어요")
                total = sum(amount for _name, _qty, amount in rows)
                self.sales_analysis_insight.setText(
                    f"매출 1위 {rows[0][0]} · 상품 매출의 {rows[0][2] / total:.0%}" if rows and total
                    else "판매 내역이 없어요")
            else:
                rows = sales_logic.category_menu_summary(orders, menu, selected, self.sales_period)
                labels = [name for name, _qty, _amount in rows[:6]]
                values = [qty for _name, qty, _amount in rows[:6]]
                self.sales_analysis_table.setHorizontalHeaderLabels(["메뉴", "판매 수량", "상품 매출"])
                self.sales_analysis_note.setText(f"{self.sales_period} · {selected} · 판매 수량 많은 순 · 품목 소계는 할인 전")
                self.sales_analysis_insight.setText(
                    f"{selected} 1위 {rows[0][0]} · {rows[0][1]:,}개 판매" if rows else "판매 내역이 없어요")
            fill_table(self.sales_analysis_table,
                       [[name, f"{qty:,}개", f"{amount:,}원"] for name, qty, amount in rows])
            align_right(self.sales_analysis_table, (1, 2))
            bars.unit, bars.value_format = "개", None
        elif mode == "시간대별 주문":
            if self.sales_hour_first_open:
                self.sales_hour_day = sales_logic.latest_order_day(orders)
                self.sales_hour_first_open = False
            data = sales_logic.hourly_day(orders, self.sales_hour_day)
            labels, values = data["labels"], data["hours"]
            self.sales_hour_date.setText(self.sales_hour_day.strftime("%Y년 %m월 %d일"))
            self.sales_hour_next.setEnabled(self.sales_hour_day < date.today())
            self.sales_analysis_note.setText(
                f"선택한 하루 (기간 버튼과 별개) · 주문 {data['count']:,}건 · 실결제 매출 {data['total']:,}원 · 00~23시 분포")
            self.sales_analysis_insight.setText(
                f"주문이 가장 많은 시간 {labels[values.index(max(values))]}시 · {max(values)}건"
                if any(values) else "해당 기간의 주문이 없어요")
            bars.unit, bars.value_format = "건", None
        else:
            days = 30 if self.sales_period == "최근 30일" else 7       # 일별은 위 기간 버튼을 따른다 (오늘 → 7일)
            points = sales_logic.trend(orders, vault.read("customers", default={}),
                                       vault.read("card_requests", default={}), mode, days=days)
            labels = [name for name, _value in points]
            values = [value for _name, value in points]
            money = mode in ("일별 매출", "주별 매출", "월별 매출")
            self.sales_analysis_table.setHorizontalHeaderLabels(["기간", "매출" if money else "인원", ""])
            fill_table(self.sales_analysis_table,
                       [[name, f"{value:,}{'원' if money else '명'}", ""] for name, value in points])
            align_right(self.sales_analysis_table, (1,))
            self.sales_analysis_note.setText(("주문 기록의 실결제액" if money else
                                             "회원 가입일" if mode == "회원가입 추이" else "카드 최초 등록일")
                                            + (f" · 최근 {len(points)}일 (위 기간 버튼을 따름)" if mode == "일별 매출" else
                                               f" · 최근 {len(points)}{'개월' if mode == '월별 매출' else '주'} (기간 버튼과 별개)"))
            total = sum(values)
            self.sales_analysis_insight.setText(
                f"최고 {labels[values.index(max(values))]} · {max(values):,}{'원' if money else '명'}"
                f"  |  기간 합계 {total:,}{'원' if money else '명'}" if any(values) else "기록이 없어요")
            bars.unit = "원" if money else "명"
            # 막대 위 숫자는 짧게 (10만 이상은 반올림한 '만' 단위) · 정확한 금액은 아래 표에 있다
            bars.value_format = (lambda value: f"{round(value / 10000):,}만" if value >= 100000 else
                                 f"{value / 10000:.1f}만" if value >= 10000 else f"{value:,}원") if money else None
        bars.labels = labels
        bars.values = values
        bars.current = values.index(max(values)) if any(values) else -1
        bars.update()

    def open_sales_category(self, row, _column):
        if (self.sales_analysis_mode.currentText() == "카테고리별 판매"
                and self.sales_category_picker.currentText() == "전체 분류"):
            self.sales_category_picker.setCurrentText(self.sales_analysis_table.item(row, 0).text())

    def move_sales_hour_day(self, step):
        target = self.sales_hour_day + timedelta(days=step)
        if target <= date.today():
            self.sales_hour_day = target
            self.load_sales_analysis()

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
        menu_header = self.menu_table.horizontalHeader()
        menu_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        menu_header.resizeSection(0, 32)
        menu_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        menu_header.resizeSection(1, 250)
        for index in range(2, self.menu_table.columnCount()):
            menu_header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)
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
                 if not i.get("hidden") and keyword in i["name"] and (category == "전체 분류" or i["category"] == category
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
        period = self.order_period.currentText()
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
            if period != "전체 기간" and not sales_logic.in_period(order, period, today):
                continue
            rows.append([order_id, items, f"{order['final_total']:,}원", member,
                         order["created_at"][5:16].replace("T", " ")])
            total += order["final_total"]
        fill_table(self.order_table, rows)
        align_right(self.order_table, (2,))
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
        top.addWidget(button("+ 새 이벤트", "outline", lambda: self.show_tab("events_add")))
        left.addLayout(top)
        self.event_table = table(["이벤트", "기간", "혜택", "상태 · 테마"])
        self.event_table.itemSelectionChanged.connect(self.select_event)
        left.addWidget(self.event_table, 1)
        row.addLayout(left, 5)            # 11/02: 기본 정책 글은 '혜택 설정'으로 옮기고 입력 칸을 넓게
        form_card = Card()
        form = QVBoxLayout(form_card)
        form.setContentsMargins(18, 12, 18, 12)
        form.setSpacing(10)
        self.event_form_title = label("수정할 이벤트를 선택하세요", 19, bold=True)
        form.addWidget(self.event_form_title)
        form.addSpacing(6)
        self.ev_name = text_field("이벤트 이름")
        self.ev_start = text_field("2026-10-20")
        self.ev_end = text_field("2026-10-31")
        self.ev_days = text_field("매일 / 평일 / 주말 / 월,수,금")
        self.ev_hours = text_field("하루 종일이면 비움 · 14-17")
        self.ev_rate = text_field("이벤트 적립률 %")
        self.ev_bonus = text_field("보너스 P")
        self.ev_min = text_field("보너스 최소 결제액")
        self.ev_smile = text_field("웃으면 할인 (원)")
        self.ev_message = text_field("배너 문구 (비우면 자동)")
        for title, widget in (("이름 *", self.ev_name), ("시작일 *", self.ev_start), ("종료일 *", self.ev_end),
                              ("요일", self.ev_days), ("시간", self.ev_hours), ("적립률", self.ev_rate),
                              ("보너스", self.ev_bonus), ("최소 결제", self.ev_min), ("스마일", self.ev_smile),
                              ("문구", self.ev_message)):
            widget.setMinimumHeight(40)
            form.addLayout(field_row(title, widget, 90))
            form.addStretch(1)
        category_row = QHBoxLayout()
        category_row.addWidget(label("대상", 15, bold=True))
        self.ev_categories = {}
        for name in CATEGORY_ORDER:
            box = QCheckBox(name)
            box.setFont(theme.font(14))
            self.ev_categories[name] = box
            category_row.addWidget(box)
        form.addLayout(category_row)
        form.addWidget(label("대상을 선택하지 않으면 전체 메뉴에 적용", 12, muted=True))
        form.addStretch(1)
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
        form.addStretch(1)
        self.ev_enabled = QCheckBox("켜짐")
        self.ev_enabled.setFont(theme.font(15, bold=True))
        actions = QHBoxLayout()
        actions.addWidget(self.ev_enabled)
        actions.addWidget(button("수정 저장", "primary", self.save_event), 1)
        actions.addWidget(button("선택 삭제", "outline", self.delete_event))
        form.addLayout(actions)
        scroll = QScrollArea()          # 칸이 많아 화면이 낮으면 위아래로 밀어 본다
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(form_card)
        row.addWidget(scroll, 8)
        self.editing_event = None
        return page

    def make_event_add_page(self):
        """새 이벤트 입력 전용 화면. 목록의 선택 상태와 입력값을 공유하지 않는다."""
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        card = Card()
        form = QVBoxLayout(card)
        form.setContentsMargins(24, 12, 24, 12)
        form.setSpacing(6)
        form.addWidget(label("새 이벤트", 22, bold=True))
        self.add_fields = {}
        specs = (("name", "이름 *", "이벤트 이름"), ("start", "시작일 *", "2026-11-07"),
                 ("end", "종료일 *", "2026-12-31"), ("days", "요일", "매일 / 평일 / 주말 / 월,수,금"),
                 ("hours", "시간", "하루 종일이면 비움 · 14-17"), ("rate", "적립률", "이벤트 적립률 %"),
                 ("bonus", "보너스", "보너스 P"), ("min", "최소 결제", "보너스 최소 결제액"),
                 ("smile", "스마일", "웃으면 할인 (원)"), ("message", "문구", "배너 문구 (비우면 자동)"))
        for key, title, hint in specs:
            widget = text_field(hint)
            widget.setMinimumHeight(40)
            self.add_fields[key] = widget
            form.addLayout(field_row(title, widget, 110))
        categories = QHBoxLayout()
        categories.addWidget(label("대상", 15, bold=True))
        self.add_categories = {}
        for name in CATEGORY_ORDER:
            box = QCheckBox(name)
            box.setFont(theme.font(14))
            self.add_categories[name] = box
            categories.addWidget(box)
        form.addLayout(categories)
        form.addWidget(label("대상을 선택하지 않으면 전체 메뉴에 적용", 12, muted=True))
        form.addStretch(1)
        themes = QHBoxLayout()
        themes.addWidget(label("테마", 15, bold=True))
        self.add_theme_group = QButtonGroup(self)
        for key, name in THEME_NAMES.items():
            background, foreground = theme.EVENT_THEMES[key]
            chip = button(name, "option")
            chip.setCheckable(True)
            chip.setProperty("theme", key)
            chip.setMinimumHeight(40)
            chip.setStyleSheet(f"QPushButton {{ background: {background}; color: {foreground}; }}"
                               f" QPushButton:checked {{ border: 3px solid {theme.BROWN}; }}")
            self.add_theme_group.addButton(chip)
            themes.addWidget(chip, 1)
        form.addLayout(themes)
        form.addStretch(1)
        actions = QHBoxLayout()
        self.add_enabled = QCheckBox("켜짐")
        self.add_enabled.setFont(theme.font(15, bold=True))
        actions.addWidget(self.add_enabled)
        actions.addWidget(button("이벤트 추가", "primary", lambda: self.save_event(creating=True)), 1)
        form.addLayout(actions)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(card)
        outer.addWidget(scroll)
        self.new_event()
        return page

    def load_events_add(self):
        self.new_event()

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
        if self.editing_event is not None and not any(e["id"] == self.editing_event for e in events):
            self.editing_event = None

    def new_event(self):
        for field in self.add_fields.values():
            field.clear()
        for box in self.add_categories.values():
            box.setChecked(False)
        self.add_enabled.setChecked(True)
        for chip in self.add_theme_group.buttons():
            chip.setChecked(chip.property("theme") == "basic")

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
        self.ev_days.setText(",".join(policy_logic.WEEKDAY_NAMES[d] for d in event["weekdays"]) or "매일")
        self.ev_hours.setText(f"{event['hours'][0]}-{event['hours'][1]}" if event.get("hours") else "하루 종일")
        self.ev_rate.setText(f"{event['rate']:g}")
        self.ev_bonus.setText(str(event["bonus_points"]))
        self.ev_min.setText(str(event["min_order"]))
        self.ev_smile.setText(str(event.get("smile_discount", 0)))
        self.ev_message.setText(event.get("message", ""))
        for name, box in self.ev_categories.items():
            box.setChecked(name in event["categories"])
        self.ev_enabled.setChecked(event.get("enabled", True))
        self.set_theme(event.get("theme", "basic"))

    def save_event(self, creating=False):
        if not creating and self.editing_event is None:
            self.fail("수정할 이벤트를 목록에서 선택하세요")
            return
        fields = (self.add_fields if creating else {
            "name": self.ev_name, "start": self.ev_start, "end": self.ev_end,
            "days": self.ev_days, "hours": self.ev_hours, "rate": self.ev_rate,
            "bonus": self.ev_bonus, "min": self.ev_min, "smile": self.ev_smile,
            "message": self.ev_message})
        group = self.add_theme_group if creating else self.theme_group
        categories = self.add_categories if creating else self.ev_categories
        enabled = self.add_enabled if creating else self.ev_enabled
        checked = group.checkedButton()
        try:
            policy, event = policy_logic.upsert_event(self.policy(), {
                "id": "" if creating else self.editing_event, "name": fields["name"].text(),
                "start": fields["start"].text().strip(), "end": fields["end"].text().strip(),
                "weekdays": fields["days"].text(), "hours": fields["hours"].text(),
                "categories": [n for n, box in categories.items() if box.isChecked()],
                "rate": float(fields["rate"].text() or 0), "bonus_points": as_int(fields["bonus"].text(), "보너스"),
                "min_order": as_int(fields["min"].text(), "최소 결제액"),
                "smile_discount": as_int(fields["smile"].text(), "스마일 할인"),
                "theme": checked.property("theme") if checked else "basic",
                "message": fields["message"].text(), "enabled": enabled.isChecked()})
            self.save_policy(policy)
        except ValueError as error:
            self.fail(error)
            return
        self.router.audit("event_save", event["id"])
        if creating:
            self.new_event()
        else:
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
    # ---- 회원카드 (11/03): 승인 없이 장바구니 결제 → 미사용 → 손님이 처음 대면 사용 중. 운영자는 보고 해제만
    def make_cards_page(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(10)
        self.card_table = table(["", "아이디", "이름", "칭호", "종류", "카드값", "상태", "카드 번호", "결제 시각"])
        header = self.card_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for index in range(1, self.card_table.columnCount()):
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(2, 140)
        self.card_table.verticalHeader().setDefaultSectionSize(
            round(self.card_table.verticalHeader().defaultSectionSize() * 1.02))
        self.card_table.setStyleSheet(self.card_table.styleSheet() +
                                      " QTableWidget::item:selected { background: #C88E5D; color: #2C1608; }")
        self.card_table.itemChanged.connect(lambda _item: self.update_card_buttons())
        self.card_table.itemSelectionChanged.connect(self.update_card_buttons)
        column.addWidget(self.card_table, 1)
        actions = QHBoxLayout()
        self.card_count = label("", 15, bold=True)
        actions.addWidget(self.card_count)
        actions.addStretch()
        self.card_lost_button = button("분실 처리", "outline", self.mark_cards_lost)
        self.card_unregister_button = button("등록 해제", "outline", self.unregister_cards)
        actions.addWidget(self.card_lost_button)
        actions.addWidget(self.card_unregister_button)
        column.addLayout(actions)
        return page

    # ---- 혜택 설정 (11/02): 회원카드 혜택 · 개인 컵 에코 포인트
    PERKS = (("card_price", "회원카드 값", "원", "1000"),
             ("card_first_discount", "카드 등록한 주문 할인", "%", "10"),
             ("card_point_rate", "카드 회원 적립률", "%", "3"),
             ("card_stamp_goal", "스탬프 모으면 음료 무료", "개", "10"),
             ("card_reissue_fee", "분실 재발급 카드 값", "원", "500"),
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
        scroll = QScrollArea()          # 혜택 칸이 많아 큰 글자 · 낮은 화면이면 위아래로 밀어 본다
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(form)
        column.addWidget(scroll, 1)
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
            field.setText(f"{policy[key]:g}" if key == "card_point_rate" else str(policy[key]))

    def save_perks(self):
        policy = self.policy()
        try:
            for key, field in self.perk_fields.items():
                text = field.text().strip() or field.placeholderText()
                if key == "card_point_rate":
                    try:
                        policy[key] = float(text.replace("%", ""))
                    except ValueError as exc:
                        raise ValueError("카드 회원 적립률은 숫자로 입력하세요 (예: 3 또는 2.5)") from exc
                else:
                    policy[key] = as_int(text.replace("%", ""), "혜택 값")
            self.save_policy(policy)
        except ValueError as error:
            self.fail(error)
            return
        self.router.audit("card_perks_save", " ".join(f"{k}={policy[k]}" for k in self.perk_fields))
        self.load_perks()
        self.done(f"혜택을 저장했어요 · {card_logic.perks_text(policy)}\n"
                  f"재발급 {policy['card_reissue_fee']:,}원 · 개인 컵 {policy['eco_points']}P/잔 · "
                  "무료 음료 쿠폰 금액은 '쿠폰'에서 바꿔요")

    def load_cards(self, keep=None):
        """카드 기록: 미사용(받았지만 아직 안 댐) · 사용 중 · 등록 해제. keep: 다시 그린 뒤 체크해 둘 기록들."""
        requests = card_logic.requests_of(self.vault())
        customers = self.vault().read("customers", default={})
        order = {"unused": 0, "issued": 1, "revoked": 2}
        items = sorted((r for r in requests.values() if r["status"] in order),
                       key=lambda r: (order[r["status"]], r["requested_at"]))
        rows, keys = [], []
        for request in items:
            record = customers.get(request["customer_id"], {})
            extra = record.get("extra", {})
            title = title_name(extra["title"]) if extra.get("title") else ""
            rows.append(["", extra.get("login_id", ""), record.get("name", "?"), title,
                         card_logic.KINDS[request["kind"]], f"{request['fee']:,}원" if request["fee"] else "무료",
                         card_logic.request_status_text(request), card_logic.masked_card(request["card_tail"]),
                         request["requested_at"][5:16].replace("T", " ")])
            keys.append(request["id"])
        fill_table(self.card_table, rows, keys)
        add_checks(self.card_table, keep or ())
        counts = {status: sum(r["status"] == status for r in requests.values()) for status in order}
        self.card_count.setText(f"사용 중 {counts['issued']}장 · 미사용 {counts['unused']}장")
        self.update_card_buttons()

    def checked_card_requests(self):
        """체크한 기록들. 체크가 없으면 지금 고른 줄 하나."""
        requests = card_logic.requests_of(self.vault())
        return [requests[key] for key in checked_keys(self.card_table) if key in requests]

    def update_card_buttons(self):
        """분실 처리는 사용 중 카드, 등록 해제는 목록에 보이는 카드를 골랐을 때."""
        statuses = {request["status"] for request in self.checked_card_requests()}
        live = bool(statuses & set(card_logic.LIVE))
        self.card_lost_button.setEnabled(live)
        self.card_unregister_button.setEnabled(bool(statuses))

    def mark_cards_lost(self):
        """손님이 카운터에서 분실을 알렸을 때: 예전 카드를 막는다. 손님은 My Menu에서 재발급 카드를 장바구니에 담는다."""
        targets = {r["customer_id"] for r in self.checked_card_requests() if r["status"] in card_logic.LIVE}
        for customer_id in targets:
            card_logic.report_lost(self.vault(), customer_id)
            self.router.audit("card_lost", customer_id)
        self.load_cards()
        fee = self.policy()["card_reissue_fee"]
        self.done(f"{len(targets)}명 분실 처리했어요 · 예전 카드는 이제 못 써요\n"
                  f"새 카드는 손님이 My Menu에서 재발급({fee:,}원)을 장바구니에 담아 결제해요")

    def unregister_cards(self):
        targets = [r["id"] for r in self.checked_card_requests()]
        for request_id in targets:
            card_logic.remove_card_record(self.vault(), request_id, self.router.admin_id)
            self.router.audit("card_unregistered", request_id)
        self.load_cards()
        self.done(f"{len(targets)}건 등록 해제해 목록에서 제거했어요 · 그 카드로는 더 로그인 · 적립할 수 없어요")

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

    # ---- 쿠폰 (11/02 B10): 쿠폰 종류 · 발급 · 내역
    def make_coupons_page(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(10)
        views = QHBoxLayout()
        self.coupon_view_buttons = {}
        self.coupon_stack = QStackedWidget()
        for key, name, maker in (("kinds", "쿠폰 종류", self.make_coupon_kinds), ("issue", "발급", self.make_coupon_issue),
                                 ("history", "발급 내역", self.make_coupon_history)):
            chip = button(name, "pill", lambda checked=False, k=key: self.set_coupon_view(k))
            chip.setCheckable(True)
            chip.setMinimumHeight(44)
            self.coupon_view_buttons[key] = chip
            views.addWidget(chip)
            self.coupon_stack.addWidget(maker())
        views.addStretch()
        column.addLayout(views)
        column.addWidget(self.coupon_stack, 1)
        self.coupon_view = "kinds"
        return page

    def make_coupon_kinds(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)
        self.coupon_kind_table = table(["", "쿠폰 이름", "할인", "최소 주문", "유효"])
        fit_columns(self.coupon_kind_table, 1)
        self.coupon_kind_table.itemChanged.connect(lambda _item: self.update_coupon_buttons())
        column.addWidget(self.coupon_kind_table, 1)
        form = QHBoxLayout()
        self.coupon_name = text_field("쿠폰 이름")
        self.coupon_amount = text_field("할인 원")
        self.coupon_min = text_field("최소 주문 원")
        self.coupon_days = text_field("유효 일수")
        form.addWidget(self.coupon_name, 3)
        for field in (self.coupon_amount, self.coupon_min, self.coupon_days):
            form.addWidget(field, 1)
        form.addWidget(button("+ 추가", "primary", self.add_coupon_kind))
        column.addLayout(form)
        actions = QHBoxLayout()
        actions.addStretch()
        self.coupon_kind_delete = button("삭제", "outline", self.delete_coupon_kinds)
        actions.addWidget(self.coupon_kind_delete)
        column.addLayout(actions)
        return page

    def make_coupon_issue(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        self.coupon_pick = QComboBox()
        self.coupon_pick.setFont(theme.font(15))
        self.coupon_pick.setMinimumHeight(44)
        top.addWidget(self.coupon_pick, 2)
        self.coupon_member_search = text_field("회원 ID · 닉네임")
        self.coupon_member_search.textChanged.connect(lambda _text: self.load_coupon_members())
        top.addWidget(self.coupon_member_search, 2)
        column.addLayout(top)
        self.coupon_member_table = table(["", "회원 ID", "닉네임", "보유 쿠폰", "방문"])
        fit_columns(self.coupon_member_table, 2)
        self.coupon_member_table.itemChanged.connect(lambda _item: self.update_coupon_buttons())
        column.addWidget(self.coupon_member_table, 1)
        actions = QHBoxLayout()
        actions.addWidget(button("전체 선택", "outline", lambda: check_all(self.coupon_member_table)))
        actions.addStretch()
        self.coupon_issue_button = button("발급", "primary", self.issue_coupons)
        actions.addWidget(self.coupon_issue_button)
        column.addLayout(actions)
        return page

    def make_coupon_history(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)
        self.coupon_history_table = table(["발급일", "회원", "쿠폰", "할인", "유효기간", "상태", "발급"])
        fit_columns(self.coupon_history_table, 2)
        column.addWidget(self.coupon_history_table, 1)
        self.coupon_history_total = label("", 15, bold=True)
        column.addWidget(self.coupon_history_total)
        return page

    def set_coupon_view(self, view):
        self.coupon_view = view
        self.load_coupons()

    def load_coupons(self):
        for key, chip in self.coupon_view_buttons.items():
            chip.setChecked(key == self.coupon_view)
        self.coupon_stack.setCurrentIndex(list(self.coupon_view_buttons).index(self.coupon_view))
        kinds = coupon_logic.templates(self.vault().read("settings", default={}))
        fill_table(self.coupon_kind_table, [["", k["name"], f"{k['amount']:,}원",
                                             f"{k['min_order']:,}원" if k["min_order"] else "없음", f"{k['days']}일"]
                                            for k in kinds], [k["id"] for k in kinds])
        add_checks(self.coupon_kind_table)
        current = self.coupon_pick.currentData()
        self.coupon_pick.clear()
        for kind in kinds:
            self.coupon_pick.addItem(f"{kind['name']} · {kind['amount']:,}원", kind["id"])
        if current is not None and self.coupon_pick.findData(current) >= 0:
            self.coupon_pick.setCurrentIndex(self.coupon_pick.findData(current))
        self.load_coupon_members()
        rows = coupon_logic.history(self.vault())
        fill_table(self.coupon_history_table, [[r["at"][5:10], r["nickname"], r["name"], f"{r['amount']:,}원",
                                                r["expires"][5:], r["state"], r["by"]] for r in rows])
        used = sum(r["state"] == "사용함" for r in rows)
        self.coupon_history_total.setText(f"발급 {len(rows)}장 · 사용 {used}장")
        self.update_coupon_buttons()

    def load_coupon_members(self):
        keyword = self.coupon_member_search.text().strip().lower()
        customers = self.vault().read("customers", default={})
        rows, keys = [], []
        for customer_id, record in sorted(customers.items()):
            extra = record["extra"]
            if keyword and keyword not in f"{extra.get('login_id', '')} {extra['nickname']}".lower():
                continue
            rows.append(["", extra.get("login_id", ""), extra["nickname"], f"{len(extra.get('coupons', []))}장",
                         f"{extra['visits']}회"])
            keys.append(customer_id)
        fill_table(self.coupon_member_table, rows, keys)
        add_checks(self.coupon_member_table)
        self.update_coupon_buttons()

    def update_coupon_buttons(self):
        members = [self.coupon_member_table.item(r, 0) for r in range(self.coupon_member_table.rowCount())]
        any_member = any(item is not None and item.checkState() == Qt.CheckState.Checked for item in members)
        kinds = [self.coupon_kind_table.item(r, 0) for r in range(self.coupon_kind_table.rowCount())]
        any_kind = any(item is not None and item.checkState() == Qt.CheckState.Checked for item in kinds)
        self.coupon_issue_button.setEnabled(any_member and self.coupon_pick.count() > 0)
        self.coupon_kind_delete.setEnabled(any_kind)

    def add_coupon_kind(self):
        try:
            kind = coupon_logic.add_template(self.vault(), {"name": self.coupon_name.text(),
                                                            "amount": self.coupon_amount.text(),
                                                            "min_order": self.coupon_min.text(),
                                                            "days": self.coupon_days.text()})
        except ValueError as error:
            self.fail(error)
            return
        self.router.audit("coupon_kind_add", kind["id"])
        for field in (self.coupon_name, self.coupon_amount, self.coupon_min, self.coupon_days):
            field.clear()
        self.load_coupons()
        self.done(f"'{kind['name']}' 쿠폰을 만들었어요")

    def delete_coupon_kinds(self):
        chosen = [self.coupon_kind_table.item(r, 0).data(Qt.ItemDataRole.UserRole)
                  for r in range(self.coupon_kind_table.rowCount())
                  if self.coupon_kind_table.item(r, 0).checkState() == Qt.CheckState.Checked]
        removed = coupon_logic.delete_templates(self.vault(), chosen)
        self.router.audit("coupon_kind_delete", " ".join(chosen))
        self.load_coupons()
        self.done(f"쿠폰 종류 {removed}개를 지웠어요 (이미 나눠 준 쿠폰은 그대로예요)")

    def issue_coupons(self):
        members = [self.coupon_member_table.item(r, 0).data(Qt.ItemDataRole.UserRole)
                   for r in range(self.coupon_member_table.rowCount())
                   if self.coupon_member_table.item(r, 0).checkState() == Qt.CheckState.Checked]
        template_id = self.coupon_pick.currentData()
        try:
            count = coupon_logic.issue(self.vault(), members, template_id, self.router.admin_id)
        except ValueError as error:
            self.fail(error)
            return
        self.router.audit("coupon_issue", f"{template_id} x{count}")
        self.load_coupons()
        self.done(f"{count}명에게 '{self.coupon_pick.currentText()}' 쿠폰을 발급했어요")

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
        self.banner_caption = text_field("아래에 쓸 글 (비워도 돼요)")
        add.addWidget(self.banner_caption, 1)
        add.addWidget(button("+ 이미지 추가", "primary", self.add_banner))
        left.addLayout(add)
        row.addLayout(left, 3)
        preview = Card()
        preview_box = QVBoxLayout(preview)
        preview_box.setContentsMargins(14, 12, 14, 12)
        self.banner_preview = Slideshow([])
        self.banner_preview.setMinimumSize(220, 220)
        preview_box.addWidget(self.banner_preview, 1)
        preview_box.addWidget(label("선택한 광고의 아래 문구", 15, bold=True))
        self.banner_edit_caption = text_field("문구를 비우면 글자 띠가 사라져요")
        preview_box.addWidget(self.banner_edit_caption)
        self.banner_edit_button = button("문구 수정 저장", "primary", self.save_banner_caption)
        preview_box.addWidget(self.banner_edit_button)
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
            self.banner_preview.set_slides([])
            self.banner_edit_caption.clear()
            self.banner_edit_button.setEnabled(False)
            return
        slide = slides[index]
        self.banner_preview.set_slides([(slide["file"], slide.get("caption", ""), slide.get("fit", "contain"))])
        self.banner_edit_caption.setText(slide.get("caption", ""))
        self.banner_edit_button.setEnabled(True)

    def save_banner_caption(self):
        index = selected_key(self.banner_table)
        slides = self.banners()
        if index is None or index >= len(slides):
            self.fail("문구를 수정할 광고를 목록에서 선택하세요")
            return
        slides[index]["caption"] = self.banner_edit_caption.text().strip()
        self.save_banners(slides, note="광고 문구를 수정했어요")
        self.banner_table.selectRow(index)

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
        target = self.choose_ad_image()
        if target is None:
            return
        try:
            slides = self.banners() + [{"file": target.name,
                                        "caption": self.banner_caption.text().strip(),
                                        "fit": "contain", "on": True}]
            kiosk_logic.save_slides(self.vault(), slides)
        except (OSError, ValueError) as error:
            target.unlink(missing_ok=True)
            self.fail(error)
            return
        self.router.audit("banner_save", f"{sum(bool(s.get('on')) for s in slides)}/{len(slides)}")
        self.banner_caption.clear()
        self.load_banners(keep=[len(slides) - 1])
        self.done("이미지를 광고 폴더에 복사하고 맨 뒤에 추가했어요")

    def choose_ad_image(self):
        """PNG/JPG만 읽어 광고 자산 폴더로 복사한다. 취소 또는 오류면 None."""
        source, _filter = QFileDialog.getOpenFileName(
            self, "광고 배너 이미지 선택", str(theme.ASSETS), "이미지 파일 (*.png *.jpg)")
        if not source:  # 파일 탐색기에서 취소
            return
        path = Path(source)
        suffix = path.suffix.lower()
        if suffix not in (".png", ".jpg"):
            self.fail("PNG 또는 JPG 이미지만 추가할 수 있어요")
            return
        reader = QImageReader(str(path))
        if reader.format().toLower() not in (b"png", b"jpeg") or reader.read().isNull():
            self.fail("열 수 있는 PNG 또는 JPG 이미지를 선택해 주세요")
            return
        target = theme.ASSETS / f"promo_upload_{uuid4().hex}{suffix}"
        try:
            shutil.copyfile(path, target)
        except OSError as error:
            self.fail(error)
            return None
        return target

    def make_login_ads_page(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(14)
        column.addWidget(label("로그인 화면 · 키보드 아래 광고", 22, bold=True))
        column.addWidget(label("왼쪽과 오른쪽 이미지를 각각 PNG/JPG로 교체할 수 있어요", 15, muted=True))
        row = QHBoxLayout()
        self.login_ad_previews = []
        self.login_ad_names = []
        for index, title in enumerate(("왼쪽 광고", "오른쪽 광고")):
            card = Card()
            content = QVBoxLayout(card)
            content.addWidget(label(title, 18, bold=True))
            picture = QLabel()
            picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
            picture.setMinimumSize(260, 250)
            content.addWidget(picture, 1)
            name = label("", 14, muted=True)
            content.addWidget(name)
            content.addWidget(button("이미지 변경", "primary", lambda checked=False, i=index: self.change_login_ad(i)))
            content.addWidget(button("기본 이미지로", "outline", lambda checked=False, i=index: self.reset_login_ad(i)))
            self.login_ad_previews.append(picture)
            self.login_ad_names.append(name)
            row.addWidget(card, 1)
        column.addLayout(row, 1)
        return page

    def load_login_ads(self):
        files = kiosk_logic.login_promos(self.vault().read("settings", default={}))
        for index, filename in enumerate(files):
            picture = QPixmap(str(theme.ASSETS / filename))
            self.login_ad_previews[index].setPixmap(picture.scaled(
                400, 340, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
            self.login_ad_names[index].setText(filename)

    def change_login_ad(self, index):
        target = self.choose_ad_image()
        if target is None:
            return
        try:
            settings = self.vault().read("settings", default={})
            files = list(kiosk_logic.login_promos(settings))
            files[index] = target.name
            settings["login_promos"] = files
            self.vault().write("settings", settings)
        except (OSError, ValueError) as error:
            target.unlink(missing_ok=True)
            self.fail(error)
            return
        self.router.audit("login_ad_save", str(index))
        self.load_login_ads()
        self.done(f"{index + 1}번 로그인 광고를 변경했어요")

    def reset_login_ad(self, index):
        settings = self.vault().read("settings", default={})
        files = list(kiosk_logic.login_promos(settings))
        files[index] = kiosk_logic.DEFAULT_LOGIN_PROMOS[index]
        settings["login_promos"] = files
        self.vault().write("settings", settings)
        self.router.audit("login_ad_reset", str(index))
        self.load_login_ads()
        self.done(f"{index + 1}번 로그인 광고를 기본 이미지로 돌렸어요")

    def make_season_page(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(15)
        column.addWidget(label("계절 테마", 24, bold=True))
        column.addWidget(label("원본은 유지하고 계절 신메뉴·광고·대기 배경을 함께 전환합니다.", 16, muted=True))
        self.season_group = QButtonGroup(self)
        self.season_group.setExclusive(True)
        choices = QHBoxLayout()
        for key, title, file, details in (
            ("none", "계절 테마 해제", "promo_photo.webp", "원본 대기 배경으로 복귀"),
            ("autumn", "가을", "promo_autumn_2026.png", "신메뉴 5종 · 광고 1장 · 가을 대기 배경"),
            ("winter", "겨울", "promo_christmas_2026.png", "신메뉴 10종 · 광고 1장 · 겨울 대기 배경"),
        ):
            card = Card()
            content = QVBoxLayout(card)
            choice = button(title, "option")
            choice.setCheckable(True)
            choice.setProperty("season", key)
            choice.setMinimumHeight(54)
            self.season_group.addButton(choice)
            content.addWidget(choice)
            preview = QLabel()
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview.setPixmap(QPixmap(str(theme.ASSETS / file)).scaled(
                340, 300, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
            content.addWidget(preview, 1)
            content.addWidget(label("대기 화면 미리보기", 14, muted=True))
            idle_file = seasonal_theme.IDLE_BACKGROUNDS[key][0]
            idle_preview = QLabel()
            idle_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            idle_preview.setPixmap(QPixmap(str(theme.ASSETS / idle_file)).scaled(
                340, 155, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
            content.addWidget(idle_preview)
            content.addWidget(label(details, 15, muted=True))
            choices.addWidget(card, 1)
        column.addLayout(choices, 1)
        column.addWidget(button("선택한 계절 테마 적용", "primary", self.save_season))
        return page

    def load_season(self):
        current = seasonal_theme.current_theme(self.vault().read("settings", default={}))
        for choice in self.season_group.buttons():
            choice.setChecked(choice.property("season") == current)

    def save_season(self):
        selected = self.season_group.checkedButton()
        if selected is None:
            self.fail("계절 테마를 선택해 주세요")
            return
        choice = selected.property("season")
        try:
            seasonal_theme.set_theme(self.vault(), choice)
        except ValueError as error:
            self.fail(error)
            return
        self.router.audit("season_theme", choice)
        self.done("계절 신메뉴·광고·대기 배경을 변경했어요 · 원본은 유지됩니다")

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
        font_row = QHBoxLayout()
        font_title = label("화면 글꼴", 17, bold=True)
        font_title.setFixedWidth(280 if theme.SCALE == 1 else 330)
        font_row.addWidget(font_title)
        self.font_choice = QComboBox()
        self.font_choice.setFont(theme.font(17))
        self.font_choice.setMinimumHeight(48)
        self.font_choice.setFixedWidth(300)
        for key, name in kiosk_logic.FONT_STYLES.items():
            self.font_choice.addItem(name, key)
        font_row.addWidget(self.font_choice)
        font_row.addWidget(label("키오스크 화면에 적용", 15, muted=True))
        font_row.addStretch(1)
        rows.addLayout(font_row)
        self.ticket_switch = QCheckBox("승차권 탭 보이기")
        self.ticket_switch.setFont(theme.font(17, bold=True))
        rows.addWidget(self.ticket_switch)
        self.presence_switch = QCheckBox("카메라로 사람 감지 (다가오면 시작 · 자리 비움 확인)")
        self.presence_switch.setFont(theme.font(17, bold=True))
        rows.addWidget(self.presence_switch)
        scroll = QScrollArea()          # 큰 글자 · 낮은 화면이면 위아래로 밀어 본다
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(form)
        column.addWidget(scroll, 1)
        save = QHBoxLayout()
        save.addStretch()
        save.addWidget(button("기본값으로", "outline", self.reset_kiosk))
        save.addWidget(button("설정 저장", "primary", self.save_kiosk))
        column.addLayout(save)
        return page

    def load_kiosk(self):
        settings = self.vault().read("settings", default={})
        values = kiosk_logic.load_kiosk(settings)
        for key, field in self.kiosk_fields.items():
            field.setText(str(values[key]))
        self.ticket_switch.setChecked(settings.get("ticket_sales", True) is not False)
        self.presence_switch.setChecked(kiosk_logic.presence_on(settings))
        self.font_choice.setCurrentIndex(self.font_choice.findData(kiosk_logic.font_style(settings)))

    def reset_kiosk(self):
        for key, field in self.kiosk_fields.items():
            field.setText(str(kiosk_logic.KIOSK_DEFAULTS[key]))
        self.ticket_switch.setChecked(True)
        self.presence_switch.setChecked(True)
        self.font_choice.setCurrentIndex(self.font_choice.findData("default"))

    def save_kiosk(self):
        raw = {key: field.text().strip() or field.placeholderText() for key, field in self.kiosk_fields.items()}
        prior_font = kiosk_logic.font_style(self.vault().read("settings", default={}))
        selected_font = self.font_choice.currentData()
        try:
            saved = kiosk_logic.save_kiosk(self.vault(), raw, self.ticket_switch.isChecked(),
                                           self.presence_switch.isChecked(), selected_font)
        except ValueError as error:
            self.fail(error)
            return
        self.router.apply_kiosk_settings()
        self.router.audit("kiosk_settings_save", " ".join(f"{k}={v}" for k, v in saved.items())
                          + f" font_style={selected_font}")
        self.load_kiosk()
        self.done("키오스크 설정을 저장했어요")
        if selected_font != prior_font and self.router.rebuild is not None:
            router = self.router
            def apply_font():
                router.rebuild()
                router.show_screen("admin", tab="kiosk")
            QTimer.singleShot(0, router, apply_font)

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
