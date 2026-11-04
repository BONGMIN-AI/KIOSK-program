"""00-B 매장 / 포장 고르기 (11/03): 대기 화면을 누르거나 다가오면 가장 먼저 묻는다. 고르면 01 시작 화면으로.

대기 화면에서 회원카드를 대면 여기를 먼저 지나고 카드 로그인으로 간다 (then).
고른 값은 주문(session.takeout)에 남아 완료 화면 · 영수증에 '매장' / '포장'으로 보인다.
"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from gui import theme
from gui.screens.home import LANGUAGES
from gui.widgets import Card, button, label

TEXT = {
    "heading": ("드시고 가세요? 포장해 가세요?", "For here or to go?", "店内でお召し上がりですか？お持ち帰りですか？",
                "堂食还是外带？"),
    "here": ("매장에서 먹어요", "For here", "店内で", "堂食"),
    "here_detail": ("머그잔 · 매장 자리에서", "In a mug, at a table", "マグカップで店内で", "用马克杯在店内享用"),
    "togo": ("포장해 갈게요", "To go", "お持ち帰り", "外带"),
    "togo_detail": ("테이크아웃 컵 · 들고 가기", "Takeout cup", "テイクアウトカップで", "外带杯带走"),
    "back": ("← 처음으로", "← Start over", "← 最初に戻る", "← 返回首页"),
}


class MugIcon(QWidget):
    """매장: 손잡이 달린 머그잔 옆모습 + 김 (이모지는 PC마다 네모로 보여서 직접 그린다)."""

    def __init__(self, size=100, ink=None):
        super().__init__()
        self.ink = ink
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        d = self.width()
        ink = QColor(self.ink or theme.BROWN)
        pen = QPen(ink, d * 0.045)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for x in (0.36, 0.5):                                   # 김 두 줄
            path = QPainterPath(QPointF(d * x, d * 0.3))
            path.cubicTo(QPointF(d * (x - 0.06), d * 0.22), QPointF(d * (x + 0.06), d * 0.16), QPointF(d * x, d * 0.08))
            painter.drawPath(path)
        painter.drawArc(QRectF(d * 0.6, d * 0.44, d * 0.24, d * 0.26), 90 * 16, -180 * 16)   # 손잡이
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ink)
        painter.drawRoundedRect(QRectF(d * 0.18, d * 0.36, d * 0.48, d * 0.46), d * 0.08, d * 0.08)   # 몸통
        painter.drawRoundedRect(QRectF(d * 0.12, d * 0.84, d * 0.6, d * 0.06), d * 0.03, d * 0.03)    # 받침
        painter.setBrush(QColor(theme.CARAMEL))
        painter.drawRect(QRectF(d * 0.18, d * 0.42, d * 0.48, d * 0.07))                             # 무늬 띠


class PaperCupIcon(QWidget):
    """포장: 뚜껑 덮인 테이크아웃 종이컵 (아래로 좁아지는 몸통 + 슬리브)."""

    def __init__(self, size=100, ink=None, sleeve=None):
        super().__init__()
        self.ink, self.sleeve = ink, sleeve
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        d = self.width()
        ink = QColor(self.ink or theme.BROWN)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ink)
        body = QPolygonF([QPointF(d * 0.26, d * 0.28), QPointF(d * 0.74, d * 0.28),
                          QPointF(d * 0.66, d * 0.92), QPointF(d * 0.34, d * 0.92)])
        painter.drawPolygon(body)                                                                   # 컵
        painter.drawRoundedRect(QRectF(d * 0.2, d * 0.16, d * 0.6, d * 0.1), d * 0.04, d * 0.04)     # 뚜껑
        painter.drawRoundedRect(QRectF(d * 0.32, d * 0.08, d * 0.36, d * 0.08), d * 0.03, d * 0.03)  # 뚜껑 윗단
        painter.setBrush(QColor(self.sleeve or theme.CARAMEL))
        sleeve = QPolygonF([QPointF(d * 0.285, d * 0.46), QPointF(d * 0.715, d * 0.46),
                            QPointF(d * 0.69, d * 0.68), QPointF(d * 0.31, d * 0.68)])
        painter.drawPolygon(sleeve)                                                                 # 슬리브


class DineScreen(QWidget):
    def __init__(self, router):
        super().__init__()
        self.router = router
        self.then = None
        self.texts = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(60, 40, 60, 28)
        layout.setSpacing(24)
        heading = self.text(label("", 34 if theme.SCALE == 1 else 28, title=True), "heading")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)
        row = QHBoxLayout()
        row.setSpacing(32)
        row.addWidget(self.make_choice(False, MugIcon(150 if theme.SCALE == 1 else 120)), 1)
        row.addWidget(self.make_choice(True, PaperCupIcon(150 if theme.SCALE == 1 else 120)), 1)
        layout.addLayout(row, 1)
        bottom = QHBoxLayout()
        self.back_button = self.text(button("", "outline", lambda: self.router.show_screen("idle")), "back")
        bottom.addWidget(self.back_button)
        bottom.addStretch()
        layout.addLayout(bottom)

    def text(self, widget, key):
        self.texts.append((widget, key))
        return widget

    def make_choice(self, takeout, icon):
        card = Card()
        column = QVBoxLayout(card)
        column.setContentsMargins(28, 24, 28, 24)
        column.setSpacing(10)
        column.addStretch()
        column.addWidget(icon, alignment=Qt.AlignmentFlag.AlignCenter)
        key = "togo" if takeout else "here"
        detail = self.text(label("", 18, muted=True), f"{key}_detail")
        detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addWidget(detail)
        column.addStretch()
        choose = self.text(button("", "primary" if takeout else "secondary", lambda: self.choose(takeout)), key)
        choose.setObjectName(f"{key}_button")
        choose.setMinimumHeight(72)
        choose.setFont(theme.font(26, bold=True))
        column.addWidget(choose)
        return card

    def on_show(self, then=None):
        self.then = then
        index = LANGUAGES.index(self.router.language)
        for widget, key in self.texts:
            widget.setText(TEXT[key][index])

    def choose(self, takeout):
        self.router.session.takeout = takeout
        then, self.then = self.then, None
        if then is not None:
            then()
        else:
            self.router.show_screen("home")
