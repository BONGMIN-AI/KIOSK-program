"""여러 화면에서 같이 쓰는 작은 부품."""

import math

from PySide6.QtCore import QElapsedTimer, QEvent, QPointF, QRectF, QTimer, QVariantAnimation, Qt
from PySide6.QtGui import (QBitmap, QColor, QImage, QPainter, QPainterPath, QPen, QPixmap,
                           QPolygonF, QRadialGradient, QRegion)
from PySide6.QtWidgets import (QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from gui import theme


def trimmed_pixmap(filename):
    """원본 파일은 보존하고, 그림 둘레의 투명한 여백만 잘라서 돌려준다."""
    image = QPixmap(str(theme.ASSETS / filename))
    mask = image.toImage().createAlphaMask(Qt.ImageConversionFlag.ThresholdAlphaDither)
    bounds = QRegion(QBitmap.fromImage(mask)).boundingRect()
    return image if bounds.isEmpty() else image.copy(bounds)


def button(text, kind="primary", on_click=None):
    result = QPushButton(text)
    result.setProperty("kind", kind)
    result.setFont(theme.font(theme.BUTTON_SIZE, bold=True))
    result.setMinimumHeight(theme.BUTTON_HEIGHT)
    result.setCursor(Qt.CursorShape.PointingHandCursor)
    # 터치 키오스크라 키보드 포커스 테두리를 쓰지 않는다.
    result.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    if on_click is not None:
        result.clicked.connect(on_click)
    return result


def chip(text):
    result = button(text, "chip")
    result.setFont(theme.font(theme.BODY_SIZE))
    result.setCheckable(True)
    return result


def label(text, size=theme.BODY_SIZE, title=False, muted=False, bold=False):
    result = QLabel(text)
    result.setFont(theme.font(size, title=title, bold=bold))
    if muted:
        result.setStyleSheet(f"color: {theme.TEXT2};")
    return result


class ElidedLabel(QLabel):
    """한 줄 글자. 칸보다 길면 끝을 '…'로 줄여 화면 폭을 늘리지 않는다 (예: 긴 이벤트 문구)."""

    def __init__(self, text=""):
        super().__init__()
        self.full_text = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setText(text)

    def setText(self, text):
        self.full_text = text
        self.fit()

    def fit(self):
        room = self.contentsRect().width()
        shown = self.fontMetrics().elidedText(self.full_text, Qt.TextElideMode.ElideRight, room)             if room > 0 else self.full_text
        super().setText(shown)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit()


class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("card", True)
        shadow = QGraphicsDropShadowEffect(self)
        color = QColor(theme.BROWN)
        color.setAlphaF(0.1)
        shadow.setColor(color)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 6)
        self.setGraphicsEffect(shadow)


class EventBanner(QWidget):
    """대기 화면 아래 띠.

    - 이벤트 문구는 전광판처럼 오른쪽에서 왼쪽으로 흘러간다.
    - 접근 안내가 켜져 있으면, 이벤트 문구가 한 번 다 지나간 뒤 접근 안내를 가운데에 5초 보여 주고
      다시 이벤트로 돌아간다(10/23 B안). 바뀔 때는 글자가 0.4초 흐려졌다 나타난다.
    """

    SPEED = 90         # 흘러가는 속도 (초당 픽셀)
    FRAME_MS = 16      # 약 60번/초 다시 그림
    HINT_MS = 5000     # 접근 안내를 보여 주는 시간
    FADE_MS = 400      # 글자가 사라지고 나타나는 시간

    def __init__(self, event=None, parent=None):
        super().__init__(parent)
        self.setFixedHeight(theme.EVENT_HEIGHT)
        self.setFont(theme.font(theme.BODY_SIZE, bold=True))
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.event = None
        self.hint = None
        self.messages = []     # (문구, 테마 이름, 흘러가는지) 목록
        self.index = 0
        self.offset = 0.0      # 흘러가는 글자의 왼쪽 x 위치
        self.opacity = 1.0
        self.frame_timer = QTimer(self)
        self.frame_timer.setInterval(self.FRAME_MS)
        self.frame_timer.timeout.connect(self.step)
        self.switch_timer = QTimer(self)
        self.switch_timer.setSingleShot(True)
        self.switch_timer.setInterval(self.HINT_MS)
        self.switch_timer.timeout.connect(self.show_next)
        self.fade = QVariantAnimation(self)
        self.fade.setDuration(self.FADE_MS)
        self.fade.valueChanged.connect(self.set_opacity)
        self.set_event(event)

    def set_event(self, event):
        self.event = event
        self.refresh()

    def set_hint(self, text):
        """접근 안내 문구. None이면 이벤트만 보여 준다."""
        self.hint = text
        self.refresh()

    def refresh(self):
        self.messages = []
        if self.event is not None:
            text = f"{self.event['name']}  ·  {self.event['message']}"
            self.messages.append((text, self.event["theme"], True))
        if self.hint:
            self.messages.append((self.hint, "basic", False))
        self.index = 0
        self.setVisible(bool(self.messages))
        self.start_message()

    def start_message(self):
        """지금 문구를 처음부터 시작한다."""
        self.frame_timer.stop()
        self.switch_timer.stop()
        if not self.messages:
            return
        if self.is_scrolling():
            self.offset = float(self.width())      # 오른쪽 끝 밖에서 들어온다
            if self.isVisible():
                self.frame_timer.start()
        elif len(self.messages) > 1:
            self.switch_timer.start()
        self.update()

    def is_scrolling(self):
        return bool(self.messages) and self.messages[self.index][2]

    def text_width(self):
        return self.fontMetrics().horizontalAdvance(self.current_text())

    def step(self):
        self.offset -= self.SPEED * self.FRAME_MS / 1000
        if self.offset < -self.text_width():       # 왼쪽 끝으로 다 빠져나감
            if len(self.messages) > 1:
                self.frame_timer.stop()
                self.show_next()
            else:
                self.offset = float(self.width())
        self.update()

    def show_next(self, animated=True):
        if len(self.messages) < 2:
            return
        if not animated:
            self.index = (self.index + 1) % len(self.messages)
            self.start_message()
            return
        # 글자를 흐리게 → 다음 문구로 바꿈 → 다시 진하게
        self.fade.stop()
        self.fade.setStartValue(1.0)
        self.fade.setEndValue(0.0)
        self.fade.finished.connect(self.fade_in_next)
        self.fade.start()

    def fade_in_next(self):
        self.fade.finished.disconnect(self.fade_in_next)
        self.index = (self.index + 1) % len(self.messages)
        self.start_message()
        self.fade.setStartValue(0.0)
        self.fade.setEndValue(1.0)
        self.fade.start()

    def set_opacity(self, value):
        self.opacity = float(value)
        self.update()

    def current_text(self):
        return self.messages[self.index][0] if self.messages else ""

    # 화면에 보일 때만 움직인다 (다른 화면에 있을 때는 멈춤)
    def showEvent(self, event):
        super().showEvent(event)
        self.start_message()

    def hideEvent(self, event):
        self.frame_timer.stop()
        self.switch_timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        if not self.messages:
            return
        text, theme_name, scrolling = self.messages[self.index]
        background, foreground = theme.EVENT_THEMES[theme_name]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.fillRect(self.rect(), QColor(background))
        color = QColor(foreground)
        color.setAlphaF(self.opacity)
        painter.setPen(color)
        painter.setFont(self.font())
        if scrolling:
            area = QRectF(self.offset, 0, self.text_width() + 4, self.height())
            painter.drawText(area, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        else:
            painter.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter, text)


# ---------------------------------------------------------------- 컵 그림
# 메뉴 사진 대신 쓰는 위에서 본 컵 그림. 라떼 위 무늬는 로고처럼 기어(톱니) 모양.
CUP_COLORS = {
    "latte": ("#C98B57", "#8A4E22"), "dark": ("#5A2E12", "#2A1203"),
    "matcha": ("#A9C27A", "#6F8A45"), "choco": ("#8B5A3C", "#4A2614"),
    "berry": ("#E7A1AE", "#B85C6E"), "tea": ("#D9A55A", "#A8702A"),
    "ade": ("#F6D365", "#E9A23B"), "dessert": ("#D9A066", "#9A5B2C"),
}


def cup_kind(item):
    """메뉴 이름·분류로 컵 그림 종류를 고른다."""
    name, category = item["name"], item["category"]
    if category == "디저트":
        return "dessert"
    if category == "에이드":
        return "ade"
    if category == "차":
        return "tea"
    if "말차" in name or "녹차" in name:
        return "matcha"
    if "초코" in name or "모카" in name or "흑임자" in name:
        return "choco"
    if "딸기" in name or "블루베리" in name:
        return "berry"
    if "우유" in item.get("allergens", []):
        return "latte"
    return "dark"


def gear_path(center_x, center_y, radius):
    """톱니 8개짜리 기어 모양 (가운데 구멍 포함)."""
    path = QPainterPath()
    points = []
    for i in range(8):
        base = i * 2 * math.pi / 8
        half = math.pi / 8
        for r, a in ((0.78, base - half * 0.55), (1.0, base - half * 0.38),
                     (1.0, base + half * 0.38), (0.78, base + half * 0.55)):
            points.append(QPointF(center_x + radius * r * math.cos(a),
                                  center_y + radius * r * math.sin(a)))
    path.addPolygon(QPolygonF(points))
    path.closeSubpath()
    path.addEllipse(QPointF(center_x, center_y), radius * 0.3, radius * 0.3)
    path.setFillRule(Qt.FillRule.OddEvenFill)
    return path


class CupIcon(QWidget):
    def __init__(self, kind="latte", size=100, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        d = self.width()
        painter.setPen(QPen(QColor(theme.LINE), 1))
        painter.setBrush(QColor("#F3ECE4"))
        painter.drawEllipse(QRectF(d * 0.02, d * 0.02, d * 0.94, d * 0.94))   # 받침
        if self.kind == "dessert":
            self.paint_dessert(painter, d)
            return
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRoundedRect(QRectF(d * 0.74, d * 0.42, d * 0.2, d * 0.12), d * 0.06, d * 0.06)
        painter.drawEllipse(QRectF(d * 0.14, d * 0.14, d * 0.68, d * 0.68))   # 잔
        light, dark = CUP_COLORS[self.kind]
        gradient = QRadialGradient(QPointF(d * 0.48, d * 0.48), d * 0.28)
        gradient.setColorAt(0, QColor(light))
        gradient.setColorAt(1, QColor(dark))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(QRectF(d * 0.2, d * 0.2, d * 0.56, d * 0.56))     # 음료
        if self.kind == "ade":
            painter.setBrush(QColor(255, 255, 255, 170))
            for x, y in ((0.36, 0.34), (0.5, 0.42), (0.38, 0.52)):           # 얼음
                painter.drawRoundedRect(QRectF(d * x, d * y, d * 0.12, d * 0.12), 3, 3)
        elif self.kind not in ("dark", "tea"):
            painter.setBrush(QColor(255, 248, 238, 240))
            painter.drawPath(gear_path(d * 0.48, d * 0.48, d * 0.16))          # 기어 라떼 아트

    def paint_dessert(self, painter, d):
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(QRectF(d * 0.1, d * 0.1, d * 0.76, d * 0.76))     # 접시
        light, dark = CUP_COLORS["dessert"]
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(dark))
        painter.drawRoundedRect(QRectF(d * 0.3, d * 0.32, d * 0.36, d * 0.3), d * 0.06, d * 0.06)
        painter.setBrush(QColor(light))
        painter.drawRoundedRect(QRectF(d * 0.3, d * 0.32, d * 0.36, d * 0.12), d * 0.06, d * 0.06)


MENU_PHOTOS = theme.ASSETS / "menu"     # 메뉴 사진: M001_아메리카노.png 처럼 '메뉴 번호_이름'
_photo_cache = {}


def menu_photo_path(item):
    """메뉴 번호로 사진 파일을 찾는다. 디카페인은 자기 사진이 없으면 같은 이름의 일반 메뉴 사진을 쓴다."""
    def find(menu_id):
        return next(iter(sorted(MENU_PHOTOS.glob(f"{menu_id}_*"))), None) if MENU_PHOTOS.exists() else None
    found = find(item["id"])
    if found is None and item.get("category") == "디카페인":
        plain = item["name"].replace("디카페인", "").strip()
        found = next((path for path in sorted(MENU_PHOTOS.glob("*")) if path.stem.split("_", 1)[-1] == plain), None) \
            if MENU_PHOTOS.exists() else None
    return found


def menu_icon(item, size):
    """메뉴 사진이 있으면 둥근 사진, 없으면 그린 잔(CupIcon)."""
    path = menu_photo_path(item)
    if path is None:
        return CupIcon(cup_kind(item), size)
    key = (str(path), size)
    if key not in _photo_cache:
        source = QPixmap(str(path)).scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                           Qt.TransformationMode.SmoothTransformation)
        rounded = QPixmap(size, size)
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, size, size), size * 0.08, size * 0.08)
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, source)
        painter.end()
        _photo_cache[key] = rounded
    photo = QLabel()
    photo.setPixmap(_photo_cache[key])
    photo.setFixedSize(size, size)
    photo.setObjectName("menu_photo")
    return photo


class CategoryIcon(QWidget):
    """카테고리 줄의 선 그림 아이콘 (디자인 템플릿처럼 한 가지 색 선). 이모지는 PC마다 네모로 나와서 직접 그린다."""

    def __init__(self, name, size=30, parent=None):
        super().__init__(parent)
        self.name = name
        self.color = None            # None이면 theme.BROWN
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        d = self.width()
        pen = QPen(QColor(self.color or theme.BROWN), max(1.6, d * 0.07))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        draw = getattr(self, f"draw_{CATEGORY_SHAPES.get(self.name, 'cup')}")
        draw(painter, d)

    @staticmethod
    def cup_body(painter, d, top=0.42):
        path = QPainterPath()
        path.moveTo(d * 0.16, d * top)
        path.lineTo(d * 0.7, d * top)
        path.lineTo(d * 0.64, d * 0.84)
        path.lineTo(d * 0.22, d * 0.84)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawArc(QRectF(d * 0.6, d * (top + 0.06), d * 0.24, d * 0.22), -90 * 16, 180 * 16)   # 손잡이

    def draw_cup(self, painter, d):
        self.cup_body(painter, d)
        for x in (0.32, 0.46):                                   # 김
            path = QPainterPath(QPointF(d * x, d * 0.32))
            path.cubicTo(d * (x - 0.06), d * 0.24, d * (x + 0.06), d * 0.18, d * x, d * 0.1)
            painter.drawPath(path)

    def draw_decaf(self, painter, d):
        self.cup_body(painter, d)
        moon = QPainterPath()
        moon.addEllipse(QRectF(d * 0.5, d * 0.06, d * 0.3, d * 0.3))
        cut = QPainterPath()
        cut.addEllipse(QRectF(d * 0.58, d * 0.02, d * 0.3, d * 0.3))
        painter.drawPath(moon.subtracted(cut))

    def draw_milk(self, painter, d):
        path = QPainterPath()
        path.moveTo(d * 0.38, d * 0.08)
        path.lineTo(d * 0.62, d * 0.08)
        path.lineTo(d * 0.62, d * 0.24)
        path.lineTo(d * 0.74, d * 0.4)
        path.lineTo(d * 0.74, d * 0.9)
        path.lineTo(d * 0.26, d * 0.9)
        path.lineTo(d * 0.26, d * 0.4)
        path.lineTo(d * 0.38, d * 0.24)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(d * 0.26, d * 0.56), QPointF(d * 0.74, d * 0.56))

    def draw_tea(self, painter, d):
        painter.drawArc(QRectF(d * 0.12, d * 0.2, d * 0.62, d * 0.62), 180 * 16, 180 * 16)
        painter.drawLine(QPointF(d * 0.12, d * 0.51), QPointF(d * 0.74, d * 0.51))
        painter.drawArc(QRectF(d * 0.66, d * 0.5, d * 0.2, d * 0.18), -90 * 16, 180 * 16)
        painter.drawLine(QPointF(d * 0.43, d * 0.51), QPointF(d * 0.43, d * 0.16))   # 티백 줄
        painter.drawRect(QRectF(d * 0.36, d * 0.06, d * 0.14, d * 0.12))

    def draw_ade(self, painter, d):
        path = QPainterPath()
        path.moveTo(d * 0.22, d * 0.26)
        path.lineTo(d * 0.66, d * 0.26)
        path.lineTo(d * 0.6, d * 0.92)
        path.lineTo(d * 0.28, d * 0.92)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(d * 0.5, d * 0.5), QPointF(d * 0.62, d * 0.06))       # 빨대
        painter.drawEllipse(QRectF(d * 0.6, d * 0.2, d * 0.28, d * 0.28))              # 레몬

    def draw_cake(self, painter, d):
        path = QPainterPath()
        path.moveTo(d * 0.12, d * 0.82)
        path.lineTo(d * 0.88, d * 0.82)
        path.lineTo(d * 0.88, d * 0.46)
        path.lineTo(d * 0.12, d * 0.62)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(d * 0.12, d * 0.7), QPointF(d * 0.88, d * 0.62))
        painter.drawEllipse(QRectF(d * 0.66, d * 0.26, d * 0.14, d * 0.14))           # 딸기

    def draw_star(self, painter, d):
        points = []
        for i in range(10):
            radius = d * (0.42 if i % 2 == 0 else 0.18)
            angle = math.radians(-90 + i * 36)
            points.append(QPointF(d * 0.5 + radius * math.cos(angle), d * 0.52 + radius * math.sin(angle)))
        painter.drawPolygon(QPolygonF(points))


CATEGORY_SHAPES = {"My Menu": "star", "커피": "cup", "디카페인": "decaf", "논커피": "milk", "차": "tea",
                   "에이드": "ade", "디저트": "cake"}


# ---------------------------------------------------------------- 입력
def text_field(placeholder="", password=False, text=""):
    """둥근 입력 칸. password=True면 글자를 ●로 가린다."""
    field = QLineEdit(text)
    field.setPlaceholderText(placeholder)
    if password:
        field.setEchoMode(QLineEdit.EchoMode.Password)
    field.setFont(theme.font(18))
    field.setMinimumHeight(52)
    field.setStyleSheet(f"background: {theme.CARD}; border: 1px solid {theme.LINE};"
                        " border-radius: 12px; padding: 0 12px;")
    return field


def message_label():
    """오류·안내 한 줄 (빨간 글자)."""
    result = label("", 15, bold=True)
    result.setStyleSheet(f"color: {theme.ERROR};")
    result.setWordWrap(True)
    return result


class TouchKeyboard(QWidget):
    """와이어프레임 02·02-B·09-A의 화면 키보드 (영문·숫자). 마지막으로 누른 입력 칸에 글자를 넣는다."""

    ROWS = ["1234567890", "qwertyuiop", "asdfghjkl", "zxcvbnm"]
    KEY_HEIGHT = 54

    def __init__(self, parent=None):
        super().__init__(parent)
        self.target = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        for index, keys in enumerate(self.ROWS):
            row = QHBoxLayout()
            row.setSpacing(8)
            # 아래 줄일수록 키가 적으니 양옆을 반 칸씩 비워 실제 키보드처럼 엇갈리게 한다
            margin = {0: 0, 1: 0, 2: 1, 3: 2}[index]
            row.addStretch(margin)
            for key in keys:
                row.addWidget(self.key_button(key, lambda checked=False, k=key: self.type(k)), 2)
            if index == len(self.ROWS) - 1:
                row.addWidget(self.key_button("⌫", self.backspace), 3)
            row.addStretch(margin if index < 3 else 0)
            layout.addLayout(row)

    def key_button(self, text, on_click):
        key = button(text, "outline", on_click)
        key.setFixedHeight(self.KEY_HEIGHT)
        key.setMinimumWidth(36)
        key.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        key.setFont(theme.font(22, bold=True))
        key.setStyleSheet("padding: 0;")
        return key

    def attach(self, *fields):
        """이 입력 칸들을 누르면 키보드가 그 칸에 글자를 넣는다."""
        for field in fields:
            field.installEventFilter(self)
        if fields and self.target is None:
            self.target = fields[0]

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.FocusIn and isinstance(watched, QLineEdit):
            self.target = watched
        return False

    def type(self, key):
        if self.target is not None:
            self.target.insert(key)

    def backspace(self):
        if self.target is not None:
            self.target.backspace()


class WeekBars(QWidget):
    """카페인 리포트의 요일별 막대 그래프 (오늘은 카라멜색)."""

    def __init__(self, values, today_index, parent=None):
        super().__init__(parent)
        self.values = values
        self.today_index = today_index
        self.setFixedSize(240, 120)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        top = max(max(self.values), 1)
        painter.setFont(theme.font(12))
        for index, (day, value) in enumerate(zip("월화수목금토일", self.values)):
            x = 8 + index * 33
            height = 0 if value == 0 else max(6, value / top * 80)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(theme.CARAMEL if index == self.today_index else "#D9BFA3"))
            painter.drawRoundedRect(QRectF(x, 92 - height, 22, height), 6, 6)
            painter.setPen(QColor(theme.TEXT2))
            painter.drawText(QRectF(x - 4, 96, 30, 20), Qt.AlignmentFlag.AlignCenter, day)


class PromoBanner(QWidget):
    """홍보 배너 그림 한 장. 칸을 꽉 채우고 넘치는 부분은 가운데 기준으로 자른다 (둥근 모서리)."""

    def __init__(self, filename, parent=None):
        super().__init__(parent)
        self.picture = QPixmap(str(theme.ASSETS / filename))
        self.setMinimumSize(200, 140)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        target = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(target, 18, 18)
        painter.setClipPath(path)
        if self.picture.isNull():          # 그림 파일이 없어도 멈추지 않고 빈 칸으로 둔다
            painter.fillRect(target, QColor(theme.CARAMEL_LIGHT))
            return
        scale = max(target.width() / self.picture.width(), target.height() / self.picture.height())
        width, height = target.width() / scale, target.height() / scale
        source = QRectF((self.picture.width() - width) / 2, (self.picture.height() - height) / 2,
                        width, height)
        painter.drawPixmap(target, self.picture, source)


def promo_row(*filenames):
    """홍보 배너 여러 장을 같은 크기로 나란히 놓는다 (예: 사진 찍기 · 스마일 할인)."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(12)
    for filename in filenames:
        layout.addWidget(PromoBanner(filename), 1)
    return row


class CameraView(QFrame):
    """얼굴 인증 카메라 화면을 키오스크 창 위에 덮어 보여 준다 (별도 창 없음).

    얼굴 공급자가 프레임마다 show_frame을 부르고, 그 사이에 화면 이벤트를 처리해
    '취소' 버튼과 ESC가 눌리게 한다. 덮개가 창 전체를 가려 다른 버튼은 눌리지 않는다.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("camera_view")
        self.setStyleSheet("QFrame#camera_view { background: rgba(20, 10, 4, 225); }")
        column = QVBoxLayout(self)
        column.setContentsMargins(40, 30, 40, 30)
        column.setSpacing(16)
        self.picture = QLabel()
        self.picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.picture.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        column.addWidget(self.picture, 1)
        self.cancel_button = button("취소 (ESC)", "outline", self.cancel)
        self.cancel_button.setFixedWidth(260)
        column.addWidget(self.cancel_button, alignment=Qt.AlignmentFlag.AlignCenter)
        self.cancelled = False
        self.hide()

    def open_view(self):
        self.cancelled = False
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self.setFocus()

    def close_view(self):
        self.picture.clear()
        self.hide()

    def cancel(self):
        self.cancelled = True

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
        else:
            super().keyPressEvent(event)

    def show_frame(self, image, wait_ms=1):
        """OpenCV(BGR) 그림 한 장을 보여 주고 wait_ms 동안 화면 이벤트를 처리한다. 취소했으면 True."""
        if not self.isVisible():
            self.open_view()
        if not image.flags["C_CONTIGUOUS"]:
            image = image.copy()
        height, width = image.shape[:2]
        frame = QImage(image.data, width, height, image.strides[0], QImage.Format.Format_BGR888).copy()
        self.picture.setPixmap(QPixmap.fromImage(frame).scaled(
            self.picture.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        clock = QElapsedTimer()
        clock.start()
        while True:
            QApplication.processEvents()
            if self.cancelled or clock.elapsed() >= wait_ms:
                return self.cancelled


class Notice(QLabel):
    """창 위쪽 가운데에 몇 초 동안 뜨는 안내 (예: 현금 반환, 잠시 문제가 생겼어요)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("notice")
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(theme.font(19, bold=True))
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)
        self.hide()

    def show_message(self, text, seconds=6):
        self.setStyleSheet(f"QLabel#notice {{ background: {theme.BROWN}; color: {theme.CARD};"
                           " border-radius: 18px; padding: 16px 28px; }")
        self.setText(text)
        width = min(760, self.parentWidget().width() - 80)
        self.setFixedWidth(width)
        self.adjustSize()
        self.move((self.parentWidget().width() - width) // 2, 24)
        self.show()
        self.raise_()
        self.timer.start(seconds * 1000)
