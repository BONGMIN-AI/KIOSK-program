"""04 옵션 팝업: 온도·사이즈·추가·수량을 고르고 장바구니에 담는다. 메뉴 화면 위에 덮어 띄운다.

회원이면 오른쪽 위 ♡ 좋아요 토글(My Menu 좋아요 목록)이 있고,
회원 알레르기와 겹치는 메뉴를 담으려 하면 04-A 알레르기 경고(취소 · 다른 메뉴 / 그래도 담기)를 먼저 보여 준다.
카페인 알리미 제한을 넘으면 '그래도 담을까요?'(아니요 / 예, 담기)를 묻는다.
비회원은 메뉴의 알레르기 성분 표시만 본다.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QVBoxLayout, QWidget

from domain.options import EXTRA_LABELS, EXTRA_PRICES, SIZE_PRICES
from gui import theme
from gui.widgets import Card, button, label, menu_icon, menu_photo_path, message_label

MAX_QUANTITY = 10


class OptionPopup(QWidget):
    def __init__(self, parent, session, on_added):
        super().__init__(parent)
        self.session = session
        self.on_added = on_added
        self.menu_id = None
        self.quantity = 1
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 디자인 템플릿(10/28)처럼 왼쪽에 큰 잔, 오른쪽에 이름·옵션·담기 버튼
        self.card = Card()
        self.card.setFixedWidth(900 if theme.SCALE == 1 else 820)
        outer.addWidget(self.card, alignment=Qt.AlignmentFlag.AlignCenter)
        columns = QHBoxLayout(self.card)
        columns.setContentsMargins(0, 0, 28, 0)
        columns.setSpacing(24)
        self.photo = QFrame()
        self.photo.setObjectName("option_photo")
        self.photo.setStyleSheet(f"QFrame#option_photo {{ background: {theme.CREAM};"
                                 f" border-top-left-radius: {theme.CARD_RADIUS}px;"
                                 f" border-bottom-left-radius: {theme.CARD_RADIUS}px; }}")
        self.photo.setFixedWidth(270 if theme.SCALE == 1 else 200)
        self.photo_layout = QVBoxLayout(self.photo)
        self.photo_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        columns.addWidget(self.photo)
        right = QWidget()
        self.body = QVBoxLayout(right)
        self.body.setContentsMargins(0, 24, 0, 24)
        self.body.setSpacing(12)
        columns.addWidget(right, 1)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(40, 20, 5, 110))   # 뒤 화면을 어둡게

    def mousePressEvent(self, event):
        event.accept()   # 뒤에 있는 메뉴 카드가 눌리지 않게 막는다

    # 팝업 내용 만들기
    def open_for(self, menu_id):
        self.menu_id = menu_id
        self.quantity = 1
        self.item = self.session.menu()[menu_id]
        self.rules = self.session.options_for(menu_id)
        self.clear_body()
        self.build()
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.card.layout().activate()           # 첫 그림부터 다 배치된 팝업이 보이게 (한 장면 납작해지지 않게)
        self.layout().activate()
        self.raise_()
        self.update_total()

    def clear_body(self):
        while self.photo_layout.count():
            entry = self.photo_layout.takeAt(0)
            if entry.widget():
                entry.widget().setParent(None)
        while self.body.count():
            entry = self.body.takeAt(0)
            if entry.widget():
                entry.widget().setParent(None)
            elif entry.layout():
                remove_layout(entry.layout())

    def build(self):
        size = (250 if menu_photo_path(self.item) else 230) if theme.SCALE == 1 else 170
        self.photo_layout.addWidget(menu_icon(self.item, size),
                                    alignment=Qt.AlignmentFlag.AlignCenter)
        head = QHBoxLayout()
        title = QVBoxLayout()
        title.addWidget(label(self.item["name"], 32, title=True))
        title.addWidget(label(f"기본 {theme.won(self.item['price'])}", 16, muted=True))
        allergens = self.item.get("allergens") or []
        allergy_text = "알레르기: " + ", ".join(allergens) if allergens else "알레르기 성분 없음"
        self.allergy_label = label(allergy_text, 15, muted=True)
        title.addWidget(self.allergy_label)
        head.addLayout(title, 1)
        self.like_button = None
        if self.session.is_member():
            self.like_button = button("", "pill", self.toggle_like)
            self.like_button.setCheckable(True)
            self.like_button.setFixedWidth(130)
            self.update_like()
            head.addWidget(self.like_button, alignment=Qt.AlignmentFlag.AlignTop)
        self.body.addLayout(head)

        self.temperature_group = self.option_row(
            "온도", [(t, t) for t in self.rules["temperatures"]], exclusive=True)
        self.size_group = self.option_row(
            "사이즈", [(s, f"{s} +{SIZE_PRICES[s]:,}원") for s in self.rules["sizes"]], exclusive=True)
        self.extra_group = self.option_row(
            "추가", [(e, f"{EXTRA_LABELS[e]} +{EXTRA_PRICES[e]:,}원") for e in self.rules["extras"]],
            exclusive=False)

        count_row = QHBoxLayout()
        count_row.addWidget(label("수량", 18, bold=True))
        count_row.addStretch()
        self.minus_button = button("−", "outline", lambda: self.change_quantity(-1))
        self.quantity_label = label("1", 22, bold=True)
        self.plus_button = button("+", "outline", lambda: self.change_quantity(1))
        for widget in (self.minus_button, self.quantity_label, self.plus_button):
            count_row.addWidget(widget)
        self.minus_button.setFixedWidth(64)
        self.plus_button.setFixedWidth(64)
        self.body.addLayout(count_row)

        self.message = message_label()
        self.body.addWidget(self.message)
        self.warning = self.make_warning()
        self.body.addWidget(self.warning)
        self.actions = QWidget()
        actions = QHBoxLayout(self.actions)
        actions.setContentsMargins(0, 0, 0, 0)
        cancel = button("취소", "outline", self.hide)
        cancel.setStyleSheet("border-radius: 28px;")
        actions.addWidget(cancel)
        self.add_button = button("장바구니 담기", "accent", self.add_to_cart)
        actions.addWidget(self.add_button, 1)
        self.body.addWidget(self.actions)

    def make_warning(self):
        """04-A 알레르기 경고 · 카페인 알리미 질문 (같은 상자를 같이 쓴다). 처음에는 숨겨 둔다."""
        box = QWidget()
        box.setObjectName("allergy_warning")
        box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # 이름을 붙여 이 상자에만 색을 칠한다 (안의 버튼 색은 그대로)
        box.setStyleSheet(f"QWidget#allergy_warning {{ background: {theme.WARN_BG}; border-radius: 16px; }}")
        column = QVBoxLayout(box)
        column.setContentsMargins(18, 14, 18, 14)
        self.warning_title = label("", 24, bold=True)
        column.addWidget(self.warning_title)
        self.warning_text = label("", 17)
        self.warning_text.setWordWrap(True)
        column.addWidget(self.warning_text)
        row = QHBoxLayout()
        self.warning_cancel = button("", "outline", self.hide)
        row.addWidget(self.warning_cancel)
        self.confirm_button = button("", "primary", lambda: self.warning_action())
        row.addWidget(self.confirm_button, 1)
        column.addLayout(row)
        box.hide()
        return box

    def ask(self, title, text, cancel, confirm, action):
        """담기 전에 한 번 묻는다. 아니요 = 팝업 닫기, 예 = action()."""
        self.warning_title.setText(title)
        self.warning_text.setText(text)
        self.warning_cancel.setText(cancel)
        self.confirm_button.setText(confirm)
        self.warning_action = action
        self.warning.show()
        self.actions.hide()

    def option_row(self, title, choices, exclusive):
        group = QButtonGroup(self)
        group.setExclusive(exclusive)
        if not choices:
            return group
        row = QHBoxLayout()
        name = label(title, 17, bold=True)
        name.setFixedWidth(70)
        row.addWidget(name)
        for index, (value, text) in enumerate(choices):
            item = button(text, "pill", self.update_total)      # 템플릿의 둥근 칩
            item.setCheckable(True)
            item.setProperty("value", value)
            item.setFont(theme.font(15, bold=True))
            item.setMinimumHeight(46)
            # 기본값: 온도는 마지막(ICE), 사이즈는 첫 번째(M), 추가는 없음
            if exclusive:
                item.setChecked(index == (len(choices) - 1 if title == "온도" else 0))
            group.addButton(item)
            row.addWidget(item, 1)
        self.body.addLayout(row)
        return group

    # 선택값
    def chosen_options(self):
        if not self.rules["temperatures"]:
            return {}
        temperature = self.temperature_group.checkedButton()
        size = self.size_group.checkedButton()
        return {
            "temperature": temperature.property("value") if temperature else None,
            "size": size.property("value") if size else None,
            "extras": [b.property("value") for b in self.extra_group.buttons() if b.isChecked()],
        }

    def change_quantity(self, delta):
        self.quantity = min(MAX_QUANTITY, max(1, self.quantity + delta))
        self.quantity_label.setText(str(self.quantity))
        self.update_total()

    def update_total(self):
        if self.menu_id is None:
            return
        total = self.session.unit_price(self.menu_id, self.chosen_options()) * self.quantity
        self.add_button.setText(f"장바구니 담기 · {theme.won(total)}")

    def toggle_like(self):
        self.session.toggle_like(self.menu_id)
        self.update_like()
        self.on_added()          # 뒤의 My Menu 좋아요 목록도 다시 그린다

    def update_like(self):
        liked = self.session.is_liked(self.menu_id)
        self.like_button.setText("♥ 좋아요" if liked else "♡ 좋아요")
        self.like_button.setChecked(liked)

    def add_to_cart(self, confirmed=False, caffeine_ok=False):
        found = self.session.allergy_warning(self.menu_id)
        if found and not confirmed:
            self.ask("!  알레르기 주의",
                     f"{self.item['name']}에 {', '.join(found)}이(가) 들어 있어요.\n"
                     f"회원 카드에 등록된 알레르기: {', '.join(found)}",
                     "취소 · 다른 메뉴", "그래도 담기", lambda: self.add_to_cart(confirmed=True))
            return
        line = {"menu_id": self.menu_id, "options": self.chosen_options(), "quantity": self.quantity}
        note = None if caffeine_ok else self.session.caffeine_warning([line])
        if note:                                 # 카페인 알리미 (10/31): 예 = 담기, 아니요 = 나가기
            self.ask("카페인 알리미", note + "\n그래도 담을까요?", "아니요", "예, 담기",
                     lambda: self.add_to_cart(confirmed=True, caffeine_ok=True))
            return
        try:
            self.session.add(self.menu_id, line["options"], self.quantity)
        except ValueError as error:
            self.message.setText(str(error))
            return
        self.hide()
        self.on_added()

    def hideEvent(self, event):
        if hasattr(self, "warning"):
            self.warning.hide()
            self.actions.show()
        super().hideEvent(event)


def remove_layout(layout):
    while layout.count():
        entry = layout.takeAt(0)
        if entry.widget():
            entry.widget().setParent(None)
        elif entry.layout():
            remove_layout(entry.layout())
