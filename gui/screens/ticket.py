"""승차권 탭(T1): 03 메뉴 가운데 칸 안에서만 바뀌는 승차권 화면들 (와이어프레임 T1-0 ~ T1-8).

T1-0 첫 화면: 예매표 출력 | 승차권 구매 (지역을 메뉴 카드처럼 늘어놓지 않는다)
예매표 출력: T1-1 조회(예매번호 / 이름 + 생년월일) → T1-2 내 예매 확인 → 바로 출력 (장바구니에 안 담김)
승차권 구매: ① 노선 → ② 시간표 → ③ 인원·좌석 → ④ 혜택·확인 → 장바구니에 승차권 줄 → 음료와 함께 05~08
계산·시연 데이터는 domain/tickets.py, 한글 키보드 조합은 domain/hangul.py.
"""

from datetime import date, datetime, timedelta

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLineEdit, QScrollArea,
                               QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from domain import hangul, tickets
from gui import theme
from gui.widgets import CategoryIcon, button, label, message_label, text_field

NOTICE = "승차권은 키오스크 아래 출력구에서 나와요. 잊지 말고 꼭 챙겨 주세요!"
STEPS = ["① 노선", "② 시간", "③ 인원·좌석", "④ 혜택·확인"]
TIME_COLUMNS = (("출발", 2), ("등급", 2), ("회사", 2), ("남은 좌석", 3), ("요금(어른)", 3))
SEAT_WIDTH, SEAT_HEIGHT = 46, 34


def clear(layout):
    """줄을 비운다. 누른 버튼이 자기 줄을 다시 만들 수도 있어서 바로 지우지 않고 나중에 지운다."""
    while layout.count():
        entry = layout.takeAt(0)
        if entry.widget():
            entry.widget().hide()
            entry.widget().deleteLater()
        elif entry.layout():
            clear(entry.layout())


def seconds_text(seconds):
    return f"{seconds // 60}:{seconds % 60:02d}"


def notice_label(size=17):
    """승차권 챙기기 안내: 진한 띠에 밝은 글자 (와이어프레임 T1-8)."""
    # 자동 줄바꿈 글자는 칸이 높이를 덜 잡아 글자가 눌려서, 큰 글자에서는 직접 두 줄로 나눈다
    text = NOTICE.replace(" 잊지", "\n잊지") if theme.SCALE > 1 else NOTICE
    result = label(text, size, bold=True)
    result.setAlignment(Qt.AlignmentFlag.AlignCenter)
    result.setStyleSheet(f"background: {theme.BROWN}; color: {theme.CARD}; border-radius: 12px; padding: 10px;")
    return result


def box_frame(color=None):
    box = QFrame()
    box.setStyleSheet(f"QFrame {{ background: {color or theme.CREAM}; border-radius: 16px; }}")
    return box


def wrapped(text, size, **style):
    result = label(text, size, **style)
    result.setWordWrap(True)
    return result


class BusIcon(CategoryIcon):
    """카테고리 줄의 '승차권' 아이콘: 버스 선 그림 (다른 아이콘과 같은 한 가지 색 선)."""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        d = self.width()
        pen = QPen(QColor(self.color or theme.BROWN), max(1.6, d * 0.07))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(d * 0.14, d * 0.12, d * 0.72, d * 0.62), d * 0.1, d * 0.1)
        painter.drawLine(QPointF(d * 0.14, d * 0.44), QPointF(d * 0.86, d * 0.44))     # 창 아래
        painter.drawLine(QPointF(d * 0.5, d * 0.12), QPointF(d * 0.5, d * 0.44))       # 창 사이
        for x in (0.3, 0.7):                                                           # 바퀴
            painter.drawEllipse(QPointF(d * x, d * 0.8), d * 0.07, d * 0.07)


class HangulKeyboard(QWidget):
    """두벌식 한글 + 숫자 화면 키보드. 마지막으로 누른 입력 칸에 넣는다. digits 칸에는 숫자만 들어간다."""

    ROWS = ["1234567890", "ㅂㅈㄷㄱㅅㅛㅕㅑㅐㅔ", "ㅁㄴㅇㄹㅎㅗㅓㅏㅣ", "ㅋㅌㅊㅍㅠㅜㅡ"]
    KEY_HEIGHT = 48

    def __init__(self, parent=None):
        super().__init__(parent)
        self.target = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        for index, keys in enumerate(self.ROWS):
            row = QHBoxLayout()
            row.setSpacing(6)
            margin = {0: 0, 1: 0, 2: 1, 3: 2}[index]      # 실제 키보드처럼 아래 줄을 엇갈리게
            row.addStretch(margin)
            for key in keys:
                row.addWidget(self.key_button(key, lambda checked=False, k=key: self.type(k)), 2)
            if index == len(self.ROWS) - 1:
                row.addWidget(self.key_button("지우기", self.backspace), 3)   # ⌫는 글꼴에 없어 네모로 보인다
            row.addStretch(margin if index < 3 else 0)
            layout.addLayout(row)

    def key_button(self, text, on_click):
        key = button(text, "outline", on_click)
        key.setFixedHeight(round(self.KEY_HEIGHT * theme.SCALE))
        key.setMinimumWidth(34)
        key.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        key.setFont(theme.font(20, bold=True))
        key.setStyleSheet("padding: 0;")
        return key

    def attach(self, *fields):
        for field in fields:
            field.installEventFilter(self)
        if fields and self.target is None:
            self.target = fields[0]

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.FocusIn and isinstance(watched, QLineEdit):
            self.target = watched
        return False

    def type(self, key):
        field = self.target
        if field is None:
            return
        if key.isdigit():
            field.insert(key)
        elif not field.property("digits"):
            text = hangul.type_jamo(field.text(), key)
            if len(text) <= field.maxLength():
                field.setText(text)

    def backspace(self):
        if self.target is not None:
            self.target.setText(hangul.erase(self.target.text()))


def step_bar(now):
    """승차권 구매 단계 표시 (가운데 칸 맨 위)."""
    row = QHBoxLayout()
    row.setSpacing(8)
    for index, name in enumerate(STEPS, 1):
        part = label(name, 15, bold=True)
        part.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if index == now:
            colors = f"background: {theme.BROWN}; color: {theme.CARD};"
        elif index < now:
            colors = f"background: {theme.CARAMEL_LIGHT}; color: {theme.BROWN};"
        else:
            colors = f"background: {theme.CARD}; color: {theme.TEXT2}; border: 1px solid {theme.LINE};"
        part.setStyleSheet(colors + " border-radius: 16px; padding: 6px 8px;")
        row.addWidget(part, 1)
    return row


def row_button(parts, height=56):
    """누르면 골라지는 한 줄 (시간표·내 예매). parts = [(글자, 늘어나는 비율, 크기, 굵게)]."""
    item = button("", "option")
    item.setCheckable(True)
    item.setMinimumHeight(round(height * theme.SCALE))
    inner = QHBoxLayout(item)
    inner.setContentsMargins(16, 6, 16, 6)
    item.parts = []
    for text, stretch, size, bold in parts:
        part = label(text, size, bold=bold)
        part.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        inner.addWidget(part, stretch)
        item.parts.append(part)
    return item


class TicketCartLine(QFrame):
    """장바구니의 승차권 줄. 좌석을 잡아 둔 남은 시간이 줄어든다 (와이어프레임 T1-7)."""

    def __init__(self, session, ticket, on_remove, big=False):
        super().__init__()
        self.session, self.ticket = session, ticket
        self.setStyleSheet(f"QFrame {{ background: {theme.CARAMEL_LIGHT}; border-radius: {16 if big else 14}px; }}")
        row = QHBoxLayout(self)
        row.setContentsMargins(14 if big else 10, 8, 14 if big else 10, 8)
        row.setSpacing(12 if big else 6)
        if big:
            row.addWidget(BusIcon("승차권", 48))
        text = QVBoxLayout()
        text.setSpacing(0)
        route = f"{ticket['origin']} → {ticket['destination']}"
        if big:
            text.addWidget(wrapped(f"승차권 {route}", 20, title=True))
            text.addWidget(wrapped(f"{tickets.ticket_summary(ticket)} · {ticket['count']}매", 14, muted=True))
        else:                                    # 좁은 메뉴 장바구니: 자동 줄바꿈 대신 줄을 나눠 둔다
            seats = "·".join(str(p["seat"]) for p in ticket["passengers"])
            text.addWidget(label(f"승차권 {ticket['count']}매", 15, title=True))
            text.addWidget(label(route, 13, bold=True))
            text.addWidget(label(f"{tickets.depart_text(ticket['depart'])}\n{ticket['grade']} · {seats}번", 12,
                                 muted=True))
        self.time_label = label("", 14 if big else 12, bold=True)
        self.time_label.setStyleSheet(f"color: {theme.ACCENT};")
        text.addWidget(self.time_label)
        price = label(theme.won(ticket["total"]), 18 if big else 14, bold=True)
        if not big:
            price.setStyleSheet(f"color: {theme.CARAMEL};")
            text.addWidget(price)
        row.addLayout(text, 1)
        if big:
            row.addWidget(price)
            row.addWidget(button("삭제", "outline", lambda: on_remove(ticket["hold_id"])))
        else:
            remove = button("×", "outline", lambda: on_remove(ticket["hold_id"]))
            side = 34 if theme.SCALE == 1 else 40
            remove.setFixedSize(side, side)
            remove.setStyleSheet("padding: 0;")
            row.addWidget(remove, alignment=Qt.AlignmentFlag.AlignTop)
        self.update_time()

    def update_time(self):
        self.time_label.setText(f"좌석 유지 {seconds_text(self.session.ticket_seconds(self.ticket))}")


class TicketPanel(QStackedWidget):
    """승차권 탭의 가운데 칸. 화면 등록 없이 메뉴 화면 안에서 단계만 바꾼다."""

    def __init__(self, session, on_drinks, on_pay):
        super().__init__()
        self.session = session
        self.office = session.office
        self.on_drinks = on_drinks       # 장바구니에 담고 음료 고르기 (메뉴의 커피 탭으로)
        self.on_pay = on_pay             # 바로 결제 (05 장바구니로)
        self.destination = None
        self.day = None
        self.bus = None
        self.counts = {}
        self.picked = []
        self.hold_id = None              # 아직 장바구니에 담지 않은, 이 화면이 잡아 둔 좌석
        self.passengers = []
        self.available = 0
        self.lookup_mode = "person"
        self.reservation_buttons = []
        self.seat_buttons = {}
        self.time_buttons = []
        self.time_group = QButtonGroup(self)
        self.benefit_groups = []
        self.home_page = self.make_home()
        self.lookup_page = self.make_lookup()
        self.result_page = self.make_result()
        self.route_page = self.make_route()
        self.time_page = self.make_timetable()
        self.seat_page = self.make_seats()
        self.confirm_page = self.make_confirm()
        self.clock = QTimer(self)
        self.clock.setInterval(1000)
        self.clock.timeout.connect(self.tick)
        self.clock.start()
        self.reset()

    # 공통
    def new_page(self, scroll=True):
        """한 단계 화면. 보통은 통째로 위아래로 밀리고, scroll=False면 안쪽 목록만 밀린다."""
        if not scroll:
            page = QWidget()
            column = QVBoxLayout(page)
            column.setContentsMargins(4, 4, 8, 4)
            column.setSpacing(12)
            self.addWidget(page)
            return page, column
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(4, 4, 8, 4)
        column.setSpacing(12)
        area.setWidget(page)
        self.addWidget(area)
        return area, column

    def go(self, page):
        self.setCurrentWidget(page)
        if isinstance(page, QScrollArea):
            page.verticalScrollBar().setValue(0)

    def page_name(self):
        pages = {self.home_page: "home", self.lookup_page: "lookup", self.result_page: "result",
                 self.route_page: "route", self.time_page: "timetable", self.seat_page: "seats",
                 self.confirm_page: "confirm"}
        return pages.get(self.currentWidget())

    def reset(self):
        """승차권 탭 첫 화면으로. 담지 않은 좌석은 풀어 준다."""
        self.release_hold()
        self.destination = self.day = self.bus = None
        self.picked = []
        for field in (self.name_field, self.birth_field, self.number_field, self.dest_field):
            field.clear()
        self.go(self.home_page)

    def release_hold(self):
        if self.hold_id:
            self.office.release(self.hold_id)
            self.hold_id = None

    @staticmethod
    def back_row(text, on_click, right=None):
        row = QHBoxLayout()
        row.addWidget(button(text, "outline", on_click))
        row.addStretch()
        if right is not None:
            row.addWidget(right)
        return row

    # T1-0 첫 화면
    def make_home(self):
        area, column = self.new_page()
        top = QHBoxLayout()
        top.addWidget(label("승차권", 26, title=True))
        top.addWidget(label("터미널 안 승차권 위탁 판매소", 15, muted=True))
        top.addStretch()
        column.addLayout(top)
        choices = QHBoxLayout()
        choices.setSpacing(14)
        self.print_choice = self.choice_button("예매표 출력", "인터넷·앱으로 예매한 표 받기", self.open_lookup)
        self.buy_choice = self.choice_button("승차권 구매", "지금 출발하는 표 사기", self.open_route)
        choices.addWidget(self.print_choice)
        choices.addWidget(self.buy_choice)
        column.addLayout(choices)
        rules = box_frame()
        inner = QVBoxLayout(rules)
        inner.setContentsMargins(18, 14, 18, 14)
        for text in (f"· 이 터미널({tickets.ORIGIN}) 출발 표만 · 출발 {tickets.SALES_CLOSE_MINUTES}분 전까지 판매·출력",
                     "· 할인(경로·보훈·군인·장애인)은 승차 때 증명서 확인",
                     "· 취소·환불은 터미널 매표소 · 승차권은 카페 쿠폰·포인트 할인 제외",
                     "· 시연용 시간표·좌석이에요 (실제 버스 회사와 연결되지 않음)"):
            inner.addWidget(wrapped(text, 15))
        column.addWidget(rules)
        column.addStretch()
        return area

    @staticmethod
    def choice_button(title, sub, on_click):
        item = button("", "outline", on_click)
        item.setMinimumHeight(round(190 * theme.SCALE))
        item.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        inner = QVBoxLayout(item)
        inner.setContentsMargins(12, 16, 12, 16)
        inner.setSpacing(8)
        inner.addStretch()
        inner.addWidget(BusIcon("승차권", 48), alignment=Qt.AlignmentFlag.AlignCenter)
        for text, size, muted in ((title, 26, False), (sub, 15, True)):
            part = wrapped(text, size, title=not muted, muted=muted)
            part.setAlignment(Qt.AlignmentFlag.AlignCenter)
            part.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            inner.addWidget(part)
        inner.addStretch()
        return item

    # T1-1 예매표 조회
    def make_lookup(self):
        area, column = self.new_page()
        column.addWidget(label("예매표 출력 · 조회", 24, title=True))
        modes = QHBoxLayout()
        self.mode_group = QButtonGroup(self)
        self.mode_buttons = {}
        for key, text in (("person", "이름 + 생년월일"), ("number", "예매번호")):
            chip = button(text, "pill", lambda checked=False, k=key: self.set_lookup_mode(k))
            chip.setCheckable(True)
            chip.setFont(theme.font(17, bold=True))
            self.mode_group.addButton(chip)
            self.mode_buttons[key] = chip
            modes.addWidget(chip)
        modes.addStretch()
        column.addLayout(modes)
        fields = QHBoxLayout()
        self.name_field = text_field("이름")
        self.name_field.setMaxLength(10)
        self.birth_field = text_field("생년월일 6자리")
        self.birth_field.setMaxLength(6)
        self.number_field = text_field("예매번호 8자리")
        self.number_field.setMaxLength(8)
        for field in (self.birth_field, self.number_field):
            field.setProperty("digits", True)
        for field in (self.name_field, self.birth_field, self.number_field):
            field.returnPressed.connect(self.lookup)
            fields.addWidget(field)
        column.addLayout(fields)
        column.addWidget(button("조회", "primary", self.lookup))
        self.lookup_message = message_label()
        column.addWidget(self.lookup_message)
        column.addWidget(wrapped("시연용 예매: 홍길동 · 900101  /  예매번호 12345678", 14, muted=True))
        self.lookup_keyboard = HangulKeyboard()
        self.lookup_keyboard.attach(self.name_field, self.birth_field, self.number_field)
        column.addWidget(self.lookup_keyboard)
        column.addLayout(self.back_row("← 승차권", self.reset))
        column.addStretch()
        return area

    def open_lookup(self):
        self.set_lookup_mode("person")
        self.go(self.lookup_page)

    def set_lookup_mode(self, mode):
        self.lookup_mode = mode
        self.mode_buttons[mode].setChecked(True)
        self.name_field.setVisible(mode == "person")
        self.birth_field.setVisible(mode == "person")
        self.number_field.setVisible(mode == "number")
        self.lookup_keyboard.target = self.name_field if mode == "person" else self.number_field
        self.lookup_message.setText("")

    def lookup(self):
        try:
            if self.lookup_mode == "number":
                found = self.office.lookup(number=self.number_field.text())
            else:
                found = self.office.lookup(name=self.name_field.text(), birth=self.birth_field.text())
        except ValueError as error:
            self.lookup_message.setText(str(error))     # 못 찾음·출발 지남·이미 출력: 알리고 다시 입력
            return
        self.show_reservations(found)

    # T1-2 내 예매 확인·출력
    def make_result(self):
        area, column = self.new_page()
        column.addWidget(label("예매표 출력 · 내 예매", 24, title=True))
        self.reservation_list = QVBoxLayout()
        self.reservation_list.setSpacing(10)
        column.addLayout(self.reservation_list)
        self.print_button = button("선택한 표 출력", "accent", self.print_selected)
        column.addWidget(self.print_button)
        self.print_message = message_label()
        column.addWidget(self.print_message)
        self.printed_box = box_frame()
        inner = QVBoxLayout(self.printed_box)
        inner.setContentsMargins(18, 14, 18, 14)
        inner.setSpacing(10)
        self.printed_title = wrapped("", 18, bold=True)
        inner.addWidget(self.printed_title)
        inner.addWidget(notice_label())
        inner.addWidget(wrapped("음료도 고르시겠어요? 왼쪽 탭에서 바로 고를 수 있어요", 15, muted=True))
        after = QHBoxLayout()
        after.addWidget(button("음료 고르기 →", "secondary", lambda: (self.reset(), self.on_drinks())))
        after.addWidget(button("승차권 처음으로", "outline", self.reset))
        inner.addLayout(after)
        column.addWidget(self.printed_box)
        column.addLayout(self.back_row("← 다시 조회", lambda: self.go(self.lookup_page)))
        column.addStretch()
        return area

    def show_reservations(self, found):
        clear(self.reservation_list)
        self.reservation_buttons = []
        now = datetime.now()
        for reservation in found:
            depart = datetime.fromisoformat(reservation["depart"])
            seats = ", ".join(map(str, reservation["seats"]))
            item = button("", "option")
            item.setCheckable(True)
            item.setMinimumHeight(round(92 * theme.SCALE))
            inner = QHBoxLayout(item)
            inner.setContentsMargins(16, 8, 16, 8)
            text = QVBoxLayout()                       # 노선 아래에 자세한 내용, 오른쪽에 남은 시간
            parts = [label(f"{reservation['origin']} → {reservation['destination']}", 19, bold=True),
                     wrapped(f"{tickets.depart_text(reservation['depart'])} · {reservation['grade']} · "
                             f"{reservation['company']} · 좌석 {seats} · {len(reservation['seats'])}매", 14,
                             muted=True),
                     label(tickets.until_text(depart, now), 15, bold=True)]
            for part in parts:
                part.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            text.addWidget(parts[0])
            text.addWidget(parts[1])
            inner.addLayout(text, 1)
            inner.addWidget(parts[2])
            item.setProperty("number", reservation["number"])
            item.setChecked(True)
            item.toggled.connect(self.update_print_button)
            self.reservation_list.addWidget(item)
            self.reservation_buttons.append(item)
        self.print_message.setText("")
        self.printed_box.hide()
        self.print_button.show()
        self.update_print_button()
        self.go(self.result_page)

    def selected_reservations(self):
        return [item.property("number") for item in self.reservation_buttons if item.isChecked()]

    def update_print_button(self):
        count = sum(len(self.office.reservations[number]["seats"]) for number in self.selected_reservations())
        self.print_button.setText(f"선택한 표 출력 ({count}매)")
        self.print_button.setEnabled(count > 0)

    def print_selected(self):
        try:
            printed = self.office.print_reservations(self.selected_reservations())
        except ValueError as error:
            self.print_message.setText(str(error))
            return
        for item in self.reservation_buttons:
            item.setEnabled(False)
        first = printed[0]
        depart = datetime.fromisoformat(first["depart"])
        self.printed_title.setText(f"출력됐어요 · {first['platform']}번 승차장 · {depart:%H:%M} 출발 "
                                   f"({tickets.until_text(depart, datetime.now())})")
        self.print_button.hide()
        self.printed_box.show()

    # ① 노선
    def make_route(self):
        area, column = self.new_page()
        column.addLayout(step_bar(1))
        fields = QHBoxLayout()
        fields.setSpacing(14)
        for title, field in (("출발지", text_field(text=f"{tickets.ORIGIN} (이 터미널)")),
                             ("도착지", text_field("글자나 초성 (예: ㄷㅈ)"))):
            part = QVBoxLayout()
            part.addWidget(label(title, 14, bold=True, muted=True))
            part.addWidget(field)
            fields.addLayout(part, 1)
            if title == "출발지":
                field.setReadOnly(True)
            else:
                self.dest_field = field
        self.dest_field.setMaxLength(8)
        self.dest_field.textChanged.connect(self.update_candidates)
        column.addLayout(fields)
        self.candidates = QGridLayout()
        self.candidates.setSpacing(8)
        column.addLayout(self.candidates)
        column.addWidget(label("날짜", 14, bold=True, muted=True))
        days = QHBoxLayout()
        self.day_group = QButtonGroup(self)
        self.day_buttons = []
        for offset in range(tickets.DAYS_AHEAD):
            chip = button("", "pill")
            chip.setCheckable(True)
            chip.setFont(theme.font(17, bold=True))
            chip.setProperty("offset", offset)
            self.day_group.addButton(chip)
            self.day_buttons.append(chip)
            days.addWidget(chip)
        days.addStretch()
        column.addLayout(days)
        actions = QHBoxLayout()
        actions.addWidget(button("← 승차권", "outline", self.reset))
        actions.addWidget(button("검색 →", "primary", self.search), 1)
        column.addLayout(actions)
        self.route_message = message_label()
        column.addWidget(self.route_message)
        self.route_keyboard = HangulKeyboard()
        self.route_keyboard.attach(self.dest_field)
        column.addWidget(self.route_keyboard)
        column.addStretch()
        return area

    def open_route(self):
        today = date.today()
        for chip in self.day_buttons:
            chip.setText(tickets.day_text(today + timedelta(days=chip.property("offset")), today))
        if self.day_group.checkedButton() is None:
            self.day_buttons[0].setChecked(True)
        self.route_message.setText("")
        self.update_candidates(self.dest_field.text())
        self.go(self.route_page)

    def update_candidates(self, text):
        """입력한 글자·초성에 맞는 도착지 후보 (그림 카드 없이 글자 칩만)."""
        clear(self.candidates)
        names = tickets.search_destinations(text)[:8]
        columns = 4 if theme.SCALE == 1 else 3
        for index, name in enumerate(names):
            chip = button(name, "pill", lambda checked=False, n=name: self.dest_field.setText(n))
            chip.setCheckable(True)
            chip.setChecked(name == text)
            chip.setFont(theme.font(17, bold=True))
            chip.setMinimumHeight(46)
            self.candidates.addWidget(chip, index // columns, index % columns)
        if not names:
            self.candidates.addWidget(label("맞는 도착지가 없어요 · 다시 입력해 주세요", 15, muted=True), 0, 0, 1, columns)

    def search(self):
        text = self.dest_field.text().strip()
        names = tickets.search_destinations(text)
        if text not in tickets.DESTINATION_NAMES:
            if len(names) != 1 or not text:
                self.route_message.setText("도착지를 입력하고 아래 목록에서 골라 주세요")
                return
            text = names[0]
            self.dest_field.setText(text)
        self.destination = text
        checked = self.day_group.checkedButton()
        self.day = date.today() + timedelta(days=checked.property("offset") if checked else 0)
        self.show_timetable()

    # ② 시간표
    def make_timetable(self):
        page, column = self.new_page(scroll=False)
        column.addLayout(step_bar(2))
        self.time_title = wrapped("", 20, bold=True)
        column.addWidget(self.time_title)
        head = box_frame(theme.CARAMEL_LIGHT)
        inner = QHBoxLayout(head)
        inner.setContentsMargins(16, 6, 16, 6)
        for text, stretch in TIME_COLUMNS:
            inner.addWidget(label(text, 14, bold=True, muted=True), stretch)
        column.addWidget(head)
        self.time_area = QScrollArea()          # 차가 많아도 '다음'은 늘 아래에 보이도록 목록만 민다
        self.time_area.setWidgetResizable(True)
        self.time_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        rows = QWidget()
        self.time_list = QVBoxLayout(rows)
        self.time_list.setContentsMargins(0, 0, 6, 0)
        self.time_list.setSpacing(8)
        self.time_list.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.time_area.setWidget(rows)
        column.addWidget(self.time_area, 1)
        column.addWidget(label("매진·마감(출발 10분 전) 차는 흐리게 보이고 고를 수 없어요", 13, muted=True))
        self.time_message = message_label()
        column.addWidget(self.time_message)
        self.time_next = button("다음 →", "primary", self.open_seats)
        column.addLayout(self.back_row("← 노선", self.open_route, self.time_next))
        return page

    def show_timetable(self, message=""):
        clear(self.time_list)
        self.time_group.deleteLater()
        self.time_group = QButtonGroup(self)
        self.time_buttons = []
        today = date.today()
        self.time_title.setText(f"{tickets.ORIGIN} → {self.destination} · {tickets.day_text(self.day, today)}"
                                f"({tickets.WEEKDAYS[self.day.weekday()]})")
        buses = self.office.timetable(self.destination, self.day)
        for bus in buses:
            seats = {"ok": f"{bus['seats_left']} / {bus['seats_total']}", "sold_out": "매진",
                     "closed": "마감"}[bus["status"]]
            values = [bus["depart"][11:], bus["grade"], bus["company"], seats, theme.won(bus["fare"])]
            item = row_button([(value, stretch, 16, False) for value, (_, stretch) in zip(values, TIME_COLUMNS)])
            item.bus = bus
            item.setEnabled(bus["status"] == "ok")
            if bus["status"] != "ok":
                for part in item.parts:
                    part.setStyleSheet(f"color: {theme.DISABLED_TEXT};")
            if self.bus and bus["id"] == self.bus["id"] and bus["status"] == "ok":
                item.setChecked(True)
            item.toggled.connect(self.update_time_next)
            self.time_group.addButton(item)
            self.time_list.addWidget(item)
            self.time_buttons.append(item)
        if not buses:
            self.time_list.addWidget(label("이 날은 남은 차가 없어요 · 다른 날짜를 골라 주세요", 16, muted=True))
        self.time_message.setText(message)
        self.update_time_next()
        self.time_area.verticalScrollBar().setValue(0)
        self.go(self.time_page)

    def update_time_next(self):
        self.time_next.setEnabled(self.time_group.checkedButton() is not None)

    # ③ 인원·좌석
    def make_seats(self):
        area, column = self.new_page()
        column.addLayout(step_bar(3))
        self.seat_title = label("", 20, bold=True)
        column.addWidget(self.seat_title)
        body = QHBoxLayout()
        body.setSpacing(18)
        left = QVBoxLayout()
        left.setSpacing(10)
        self.count_labels = {}
        for kind in tickets.PASSENGER_TYPES:
            row = QHBoxLayout()
            row.addWidget(label(kind, 17, bold=True))
            row.addStretch()
            for symbol, delta in (("−", -1), ("+", 1)):
                step = button(symbol, "outline", lambda checked=False, k=kind, d=delta: self.change_count(k, d))
                side = 44 if theme.SCALE == 1 else 50
                step.setFixedSize(side, side)
                step.setStyleSheet("padding: 0;")
                row.addWidget(step)
                if delta < 0:
                    count = label("0", 20, bold=True)
                    count.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    count.setMinimumWidth(32)
                    self.count_labels[kind] = count
                    row.addWidget(count)
            left.addLayout(row)
        hint = box_frame()
        inner = QVBoxLayout(hint)
        inner.setContentsMargins(14, 10, 14, 10)
        self.seat_need = wrapped("", 15, bold=True)
        inner.addWidget(self.seat_need)
        inner.addWidget(wrapped("'다음'을 누르면 고른 좌석을 5분 동안 잡아 둬요", 13, muted=True))
        inner.addWidget(wrapped("× = 이미 팔린 좌석 · 중고생 80% · 초등생 50% 요금 (시연 값)", 13, muted=True))
        left.addWidget(hint)
        self.seat_message = message_label()
        left.addWidget(self.seat_message)
        left.addStretch()
        self.seat_next = button("다음 →", "primary", self.confirm_seats)
        nav = QHBoxLayout()                       # 좌석표가 길어도 버튼이 보이도록 왼쪽 칸 아래에 둔다
        nav.addWidget(button("← 시간", "outline", self.back_to_timetable))
        nav.addWidget(self.seat_next, 1)
        left.addLayout(nav)
        body.addLayout(left, 1)
        self.seat_frame = QFrame()
        self.seat_frame.setObjectName("seat_map")
        self.seat_frame.setStyleSheet(f"QFrame#seat_map {{ background: {theme.CARD}; border: 2px solid {theme.LINE};"
                                      " border-radius: 16px; }")
        self.seat_grid = QGridLayout(self.seat_frame)
        self.seat_grid.setContentsMargins(14, 10, 14, 14)
        self.seat_grid.setHorizontalSpacing(6)
        self.seat_grid.setVerticalSpacing(5)
        body.addWidget(self.seat_frame, alignment=Qt.AlignmentFlag.AlignTop)
        column.addLayout(body)
        column.addStretch()
        return area

    def open_seats(self):
        chosen = self.time_group.checkedButton()
        if chosen is None:
            return
        self.release_hold()
        bus = self.office.bus(chosen.bus["id"])
        if bus["status"] != "ok":
            self.show_timetable("방금 매진·마감됐어요 · 다른 시간을 골라 주세요")
            return
        if self.bus is None or self.bus["id"] != bus["id"]:
            self.counts = {kind: 0 for kind in tickets.PASSENGER_TYPES}
            self.counts["어른"] = 1
            self.picked = []
        self.bus = bus
        self.show_seats()

    def back_to_timetable(self):
        self.show_timetable()

    def show_seats(self, message=""):
        self.release_hold()
        bus = self.bus
        self.seat_title.setText(f"인원수 · 좌석 · {bus['grade']} {bus['seats_total']}석 · {bus['depart'][11:]} 출발")
        taken = self.office.taken(bus["id"], grade=bus["grade"])
        self.available = bus["seats_total"] - len(taken)
        self.picked = [seat for seat in self.picked if seat not in taken]
        clear(self.seat_grid)
        self.seat_buttons = {}
        driver = label("운전석", 13, bold=True, muted=True)
        door = label("출입구 ↓", 13, bold=True, muted=True)
        door.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.seat_grid.addWidget(driver, 0, 0, 1, 2)
        self.seat_grid.addWidget(door, 0, 3, 1, 2)
        for col in range(5):
            self.seat_grid.setColumnMinimumWidth(col, 0)
        aisle = [2, 3] if bus["grade"] == "우등" else [2]
        for col in aisle:
            self.seat_grid.setColumnMinimumWidth(col, 20)
        for r, seats in enumerate(tickets.seat_rows(bus["grade"]), 1):
            for c, seat in enumerate(seats):
                if seat is None:
                    continue
                item = button("×" if seat in taken else str(seat), "option")
                item.setCheckable(True)
                item.setFixedSize(SEAT_WIDTH, SEAT_HEIGHT)
                item.setFont(theme.font(14, bold=True))
                item.setStyleSheet(f"QPushButton {{ padding: 0; border-radius: 8px; }}"
                                   f" QPushButton:checked {{ background: {theme.ACCENT}; color: {theme.CARD};"
                                   " border: none; }")
                item.setEnabled(seat not in taken)
                item.setObjectName(f"seat_{seat}")
                item.clicked.connect(lambda checked=False, s=seat: self.toggle_seat(s, checked))
                if bus["grade"] == "우등" and seat == 27:      # 맨 뒷줄 27번은 통로 자리
                    self.seat_grid.addWidget(item, r, 2, 1, 2, Qt.AlignmentFlag.AlignCenter)
                else:
                    self.seat_grid.addWidget(item, r, c)
                self.seat_buttons[seat] = item
        self.seat_message.setText(message)
        self.update_seat_state()
        if self.currentWidget() is not self.seat_page:
            self.go(self.seat_page)

    def need(self):
        return sum(self.counts.values())

    def change_count(self, kind, delta):
        value = self.counts[kind] + delta
        if value < 0:
            return
        limit = min(tickets.MAX_PASSENGERS, self.available)
        if self.need() + delta > limit:
            self.seat_message.setText(f"한 번에 {limit}명까지 살 수 있어요")
            return
        self.counts[kind] = value
        self.picked = self.picked[:self.need()]
        self.seat_message.setText("")
        self.update_seat_state()

    def toggle_seat(self, seat, checked):
        if checked and len(self.picked) >= self.need():
            self.seat_message.setText(f"인원수만큼({self.need()}석) 이미 골랐어요 · 고른 좌석을 다시 누르면 풀려요")
        elif checked:
            self.picked.append(seat)
            self.seat_message.setText("")
        elif seat in self.picked:
            self.picked.remove(seat)
        self.update_seat_state()

    def update_seat_state(self):
        for kind, count in self.count_labels.items():
            count.setText(str(self.counts.get(kind, 0)))
        for seat, item in self.seat_buttons.items():
            item.setChecked(seat in self.picked)
        need, picked = self.need(), sorted(self.picked)
        chosen = f" · 고른 좌석 {', '.join(map(str, picked))}" if picked else ""
        if need == 0:
            self.seat_need.setText("인원수를 먼저 골라 주세요")
        elif len(picked) < need:
            self.seat_need.setText(f"좌석 {need - len(picked)}개를 더 골라 주세요{chosen}")
        else:
            self.seat_need.setText(f"좌석을 다 골랐어요{chosen}")
        self.seat_next.setEnabled(need > 0 and len(picked) == need)

    def confirm_seats(self):
        try:
            self.hold_id = self.office.hold(self.bus["id"], self.picked)
        except ValueError as error:
            self.show_seats(str(error))
            return
        self.passengers = tickets.assign_passengers(self.counts, self.picked)
        self.open_confirm()

    # ④ 혜택·확인
    def make_confirm(self):
        area, column = self.new_page()
        column.addLayout(step_bar(4))
        column.addWidget(label("혜택 (승객마다)", 20, bold=True))
        self.benefit_rows = QVBoxLayout()
        self.benefit_rows.setSpacing(8)
        column.addLayout(self.benefit_rows)
        column.addWidget(wrapped("할인 승차권은 승차할 때 증명서를 보여 주세요 · 할인율은 시연 값이에요 "
                                 "(학생 요금과 겹치지 않고 더 싼 쪽)", 13, muted=True))
        summary = box_frame()
        grid = QGridLayout(summary)
        grid.setContentsMargins(18, 14, 18, 14)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        self.summary_values = {}
        for row, key in enumerate(("노선", "출발", "좌석", "금액")):
            grid.addWidget(label(key, 15, bold=True, muted=True), row, 0, Qt.AlignmentFlag.AlignTop)
            value = wrapped("", 15, bold=True)
            grid.addWidget(value, row, 1)
            self.summary_values[key] = value
        grid.setColumnStretch(1, 1)
        column.addWidget(summary)
        self.hold_label = label("", 15, bold=True)
        self.hold_label.setStyleSheet(f"color: {theme.ACCENT};")
        column.addWidget(self.hold_label)
        self.confirm_message = message_label()
        column.addWidget(self.confirm_message)
        actions = QHBoxLayout() if theme.SCALE == 1 else QVBoxLayout()   # 큰 글자는 위아래로
        actions.setSpacing(12)
        self.with_drinks_button = button("장바구니 담고 음료 고르기", "outline",
                                         lambda: self.add_to_cart(self.on_drinks))
        self.pay_now_button = button("바로 결제 →", "accent", lambda: self.add_to_cart(self.on_pay))
        actions.addWidget(self.with_drinks_button, 1)
        actions.addWidget(self.pay_now_button, 1)
        column.addLayout(actions)
        column.addWidget(wrapped("바로 결제도 장바구니 → (회원) 쿠폰·포인트 → 현금 순서예요 · 쿠폰·포인트는 음료에만", 13,
                                 muted=True))
        column.addLayout(self.back_row("← 좌석", lambda: self.show_seats()))
        column.addStretch()
        return area

    def open_confirm(self):
        clear(self.benefit_rows)
        for group in self.benefit_groups:
            group.deleteLater()
        self.benefit_groups = []
        for index, passenger in enumerate(self.passengers):
            who = label(f"좌석 {passenger['seat']} · {passenger['type']}", 16, bold=True)
            row = QHBoxLayout()
            row.setSpacing(8)
            if theme.SCALE == 1:                  # 큰 글자는 이름 아래 줄에 칩
                who.setMinimumWidth(120)
                row.addWidget(who)
            else:
                self.benefit_rows.addWidget(who)
            group = QButtonGroup(self)
            self.benefit_groups.append(group)
            for name in tickets.BENEFITS:
                chip = button(name, "pill", lambda checked=False, i=index, n=name: self.set_benefit(i, n))
                chip.setCheckable(True)
                chip.setChecked(name == passenger["benefit"])
                chip.setFont(theme.font(16, bold=True))
                chip.setMinimumHeight(44)
                chip.setObjectName(f"benefit_{passenger['seat']}_{name}")
                group.addButton(chip)
                row.addWidget(chip)
            row.addStretch()
            self.benefit_rows.addLayout(row)
        self.confirm_message.setText("")
        self.update_summary()
        self.go(self.confirm_page)
        self.tick()

    def set_benefit(self, index, name):
        self.passengers[index]["benefit"] = name
        self.update_summary()

    def update_summary(self):
        bus = self.bus
        priced, total = tickets.quote(bus["fare"], self.passengers)
        values = self.summary_values
        values["노선"].setText(f"{bus['origin']} → {bus['destination']}")
        values["출발"].setText(f"{tickets.depart_text(bus['depart'])} · {bus['grade']} · {bus['company']}"
                             f" · {bus['platform']}번 승차장")
        values["좌석"].setText(" / ".join(f"{p['seat']} ({p['type']} · {p['benefit']})" for p in priced))
        values["금액"].setText(" + ".join(f"{p['price']:,}" for p in priced) + f" = {theme.won(total)}")
        self.pay_now_button.setText(f"{theme.won(total)} 바로 결제 →")

    def tick(self):
        """좌석 잡아 둔 남은 시간. 다 지나면 좌석을 풀고 좌석 고르기로 돌아간다."""
        if self.currentWidget() is not self.confirm_page or not self.hold_id:
            return
        seconds = self.office.hold_seconds(self.hold_id)
        if not seconds:
            self.show_seats("좌석을 잡아 둔 5분이 지났어요 · 좌석을 다시 골라 주세요")
            return
        self.hold_label.setText(f"고른 좌석 {seconds_text(seconds)} 동안 잡아 둬요")

    def add_to_cart(self, then):
        """승차권을 장바구니에 담는다 (좌석은 장바구니에서 계속 잡아 둔다). 그다음 음료 고르기 또는 결제."""
        try:
            self.office.check_hold(self.hold_id)
        except ValueError as error:
            self.show_seats(str(error))
            return
        self.session.add_ticket(self.office.make_item(self.bus, self.passengers, self.hold_id))
        self.hold_id = None              # 이제 장바구니가 들고 있다
        self.reset()
        then()
