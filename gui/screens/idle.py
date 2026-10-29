"""00: 글자 없는 배경 위에 로고·시작 안내·언어 선택·이벤트를 그린다.

배경 idle_bg_clean.png는 tools/make_idle_background.py로 원본 그림에서
로고와 안내 글자만 지운 것이다. 아래 상자 좌표는 원본 그림(1672×941) 기준이다.
"""

import math

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import (QBitmap, QColor, QFontMetrics, QLinearGradient, QPainter, QPen, QPixmap,
                           QPolygonF, QRegion)
from PySide6.QtWidgets import QButtonGroup, QWidget

from gui import theme
from gui.widgets import EventBanner, chip, gear_path

IMAGE_SIZE = (1672, 941)
LOGO_BOX = (475, 30, 765, 214)            # 원래 로고 자리 (x, y, 너비, 높이)
LOGO_SCALE = 1.1                           # 원래보다 조금 크게
LOGO_SHIFT_Y = 12                          # 언어 칩과 겹치지 않게 화면에서 조금 아래로
START_BOX = (585, 786, 575, 52)            # 손가락 아이콘과 화살표 사이
# 움직임 (5단계 다듬기 D-1~D-3). 로고 조각은 tools/make_logo_parts.py로 만든다.
FRAME_MS = 40                              # 1초에 25번 다시 그린다
GEAR_CENTER = (1523, 519)                  # 원본 로고(1774×887) 기준 기어 가운데
GEAR_RADIUS = 68
GEAR_SECONDS_PER_TURN = 24                 # 기어가 아주 천천히 돈다
STEAMS = ((1500, 445, 180, 28, "#C68B52"), (1545, 440, 125, 18, "#EBCB9C"))   # (x, y, 높이, 굵기, 색)
SHADOW_SWAY = 14                           # 잎 그림자가 흔들리는 폭(px)
# 접근 안내는 그림 위가 아니라 아래 이벤트 띠에서 이벤트 문구와 번갈아 보여 준다(10/23 결정, B안).

START_TEXT = {
    "한국어": "화면을 터치하여 주문을 시작하세요",
    "English": "Touch the screen to start your order",
    "日本語": "画面をタッチしてご注文を始めてください",
    "中文": "触摸屏幕开始点单",
}
APPROACH_TEXT = {
    "한국어": "가까이 오시면 자동으로 시작할 수 있어요",
    "English": "Come closer and it starts by itself",
    "日本語": "近づくと自動で始まります",
    "中文": "靠近时会自动开始",
}


class IdleScreen(QWidget):
    def __init__(self, router, event=theme.FROM_POLICY):
        super().__init__()
        self.router = router
        self.show_approach_hint = False    # D10 접근 감지를 연결하면 True
        self.background = QPixmap(str(theme.ASSETS / "idle_bg_clean.png"))
        self.logo, self.logo_front, self.logo_offset = self.logo_layers()
        self.scaled_background = None
        self.shadow_layer = None
        self.clock = QElapsedTimer()
        self.clock.start()
        self.frame_timer = QTimer(self)
        self.frame_timer.setInterval(FRAME_MS)
        self.frame_timer.timeout.connect(self.update)
        self.languages = QButtonGroup(self)
        left = 24
        for name in START_TEXT:
            item = chip(name)
            item.setParent(self)
            width = max(88, item.fontMetrics().horizontalAdvance(name) + 40)
            item.setGeometry(left, 24, width, theme.BUTTON_HEIGHT)
            left += item.width() + 8
            self.languages.addButton(item)
            item.setChecked(name == router.language)
            item.clicked.connect(lambda checked, name=name: self.set_language(name))
        self.fixed_event = event          # FROM_POLICY면 화면에 올 때마다 운영자 이벤트를 읽는다
        self.banner = EventBanner(None if event == theme.FROM_POLICY else event, self)

    @staticmethod
    def logo_layers():
        """김·기어를 지운 로고와 기어 앞 숟가락 테두리. 자리는 원본 로고의 여백을 자른 기준으로 맞춘다."""
        original = QPixmap(str(theme.ASSETS / "logo_main.png"))
        mask = original.toImage().createAlphaMask(Qt.ImageConversionFlag.ThresholdAlphaDither)
        bounds = QRegion(QBitmap.fromImage(mask)).boundingRect()
        base = QPixmap(str(theme.ASSETS / "logo_idle_base.png")).copy(bounds)
        front = QPixmap(str(theme.ASSETS / "logo_idle_front.png")).copy(bounds)
        return base, front, QPointF(bounds.topLeft())

    def seconds(self):
        return self.clock.elapsed() / 1000

    def showEvent(self, event):
        self.frame_timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.frame_timer.stop()
        super().hideEvent(event)

    @property
    def language(self):
        return self.router.language        # 01 시작 화면과 같이 쓴다

    def on_show(self):
        for item in self.languages.buttons():   # 새 손님이면 한국어로 돌아와 있다
            item.setChecked(item.text() == self.language)
        self.set_approach_hint(self.show_approach_hint)
        if self.fixed_event == theme.FROM_POLICY:
            self.banner.set_event(self.router.session.current_event())

    def set_language(self, name):
        self.router.language = name
        self.set_approach_hint(self.show_approach_hint)
        self.update()

    def set_approach_hint(self, on):
        """D10 접근 감지를 연결하면 True로 켠다. 켜면 아래 띠에서 이벤트와 번갈아 나온다."""
        self.show_approach_hint = on
        self.banner.set_hint(APPROACH_TEXT[self.language] if on else None)

    def start_text(self):
        return START_TEXT[self.language]

    # 원본 그림 좌표를 화면 좌표로 바꾸기 (cover: 꽉 채우고 가운데 기준으로 자름)
    def image_scale(self):
        return max(self.width() / IMAGE_SIZE[0], self.height() / IMAGE_SIZE[1])

    def to_screen(self, box):
        scale = self.image_scale()
        offset_x = (self.width() - IMAGE_SIZE[0] * scale) / 2
        offset_y = (self.height() - IMAGE_SIZE[1] * scale) / 2
        x, y, width, height = box
        return QRectF(offset_x + x * scale, offset_y + y * scale, width * scale, height * scale)

    def resizeEvent(self, event):
        self.banner.setGeometry(0, self.height() - theme.EVENT_HEIGHT,
                                self.width(), theme.EVENT_HEIGHT)
        self.scaled_background = self.background.scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation)
        self.shadow_layer = self.make_shadow_layer()
        super().resizeEvent(event)

    def make_shadow_layer(self):
        """D-1: 그림의 잎 그림자 방향(왼쪽 위 → 오른쪽 아래)으로 옅은 그림자 줄을 한 장 그려 둔다."""
        margin = SHADOW_SWAY * 2
        layer = QPixmap(self.width() + margin * 2, self.height() + margin * 2)
        layer.fill(Qt.GlobalColor.transparent)
        painter = QPainter(layer)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(layer.width() * 0.3, -layer.height() * 0.1)
        painter.rotate(35)
        length = (layer.width() + layer.height()) * 1.5
        for offset, width in ((0, 70), (130, 40), (220, 90), (380, 50), (470, 30), (600, 80)):
            band = QLinearGradient(offset, 0, offset + width, 0)
            band.setColorAt(0, QColor(70, 40, 15, 0))
            band.setColorAt(0.5, QColor(70, 40, 15, 26))
            band.setColorAt(1, QColor(70, 40, 15, 0))
            painter.fillRect(QRectF(offset, -length / 2, width, length), band)
        painter.end()
        return layer

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), theme.BG)
        if self.scaled_background is not None:
            picture = self.scaled_background
            painter.drawPixmap((self.width() - picture.width()) // 2,
                               (self.height() - picture.height()) // 2, picture)
        self.draw_shadow(painter)
        self.draw_logo(painter)
        self.draw_fitted_text(painter, self.start_text(), self.to_screen(START_BOX),
                              theme.BROWN, 40, bold=True)

    def draw_logo(self, painter):
        if self.logo.isNull():               # 그림 파일이 없어도 멈추지 않는다
            return
        box = self.to_screen(LOGO_BOX)
        width = box.width() * LOGO_SCALE
        height = width * self.logo.height() / self.logo.width()
        target = QRectF(box.center().x() - width / 2,
                        box.center().y() - height / 2 + LOGO_SHIFT_Y, width, height)
        painter.drawPixmap(target, self.logo, QRectF(self.logo.rect()))
        # 여기부터는 원본 로고 좌표로 그린다
        painter.save()
        painter.translate(target.topLeft())
        painter.scale(width / self.logo.width(), height / self.logo.height())
        painter.translate(-self.logo_offset)
        self.draw_gear(painter)
        painter.drawPixmap(self.logo_offset, self.logo_front)
        self.draw_steam(painter)
        painter.restore()

    def draw_shadow(self, painter):
        """D-1: 그림자 줄이 바람에 흔들리듯 천천히 오가고 진해졌다 옅어진다."""
        if self.shadow_layer is None:
            return
        t = self.seconds()
        shift = SHADOW_SWAY * math.sin(t * 2 * math.pi / 7)
        painter.save()
        painter.setOpacity(0.65 + 0.35 * math.sin(t * 2 * math.pi / 11))
        painter.drawPixmap(QPointF(-SHADOW_SWAY * 2 + shift, -SHADOW_SWAY * 2 + shift * 0.4),
                           self.shadow_layer)
        painter.restore()

    def draw_gear(self, painter):
        """D-2: 숟가락 위 기어가 조금씩 돈다."""
        x, y = GEAR_CENTER
        painter.save()
        painter.translate(x, y)
        painter.rotate(self.seconds() * 360 / GEAR_SECONDS_PER_TURN)
        fill = QLinearGradient(0, -GEAR_RADIUS, 0, GEAR_RADIUS)
        fill.setColorAt(0, QColor("#D49A5C"))
        fill.setColorAt(1, QColor("#A9682F"))
        painter.setPen(QPen(QColor("#F3D2A2"), 3))
        painter.setBrush(fill)
        painter.drawPath(gear_path(0, 0, GEAR_RADIUS))
        painter.restore()

    def draw_steam(self, painter):
        """D-3: 김 두 줄이 흔들리며 피어오르고 위로 갈수록 흐려진다."""
        t = self.seconds()
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        for number, (x, y, rise, thick, color) in enumerate(STEAMS):
            left, right = [], []
            steps = 30
            for i in range(steps + 1):
                part = i / steps
                wave = math.sin(part * 5.5 - t * 1.6 + number * 1.7) * 12 * (0.3 + part)
                half = thick / 2 * (1 - part * 0.7)            # 위로 갈수록 가늘게
                left.append(QPointF(x + wave - half, y - part * rise))
                right.append(QPointF(x + wave + half, y - part * rise))
            fade = QLinearGradient(0, y, 0, y - rise)                # 위로 갈수록 흐리게
            bottom, top = QColor(color), QColor(color)
            bottom.setAlphaF(0.9)
            top.setAlphaF(0.0)
            fade.setColorAt(0, bottom)
            fade.setColorAt(1, top)
            painter.setBrush(fade)
            painter.drawPolygon(QPolygonF(left + right[::-1]))
        painter.restore()

    def draw_fitted_text(self, painter, text, box, color, size, bold=False):
        # 언어마다 길이가 달라서 상자에 들어갈 때까지 글자를 줄인다.
        font = theme.font(size, bold=bold)
        while size > 14 and QFontMetrics(font).horizontalAdvance(text) > box.width():
            size -= 1
            font = theme.font(size, bold=bold)
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.router.show_screen("home")
        super().mousePressEvent(event)
