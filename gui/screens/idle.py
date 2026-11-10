"""00: 글자 없는 배경 위에 로고·시작 안내·언어 선택·이벤트를 그린다.

대기 배경에는 하단 손·화살표가 있고, 매장·포장 선택 배경에서는 하단 아이콘과 선을 지웠다.
계절 테마가 켜지면 같은 구도의 가을·겨울 배경으로 전환한다.
아래 상자 좌표는 원본 그림(1672×941) 기준이다.
"""

import math

from PySide6.QtCore import (QEasingCurve, QElapsedTimer, QParallelAnimationGroup, QPoint, QPointF,
                            QPropertyAnimation, QRectF, QTimer, Qt)
from PySide6.QtGui import (QBitmap, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPen, QPixmap,
                           QPolygonF, QRegion)
from PySide6.QtWidgets import QButtonGroup, QGraphicsOpacityEffect, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from domain import policy as policy_logic
from domain import member_cards as card_logic
from domain.seasonal_theme import idle_backgrounds
from gui import theme
from gui.widgets import EventBanner, chip, gear_path, label

IMAGE_SIZE = (1672, 941)
LOGO_BOX = (475, 30, 765, 214)            # 원래 로고 자리 (x, y, 너비, 높이)
LOGO_SCALE = 1.1                           # 원래보다 조금 크게
LOGO_SHIFT_Y = 12                          # 언어 칩과 겹치지 않게 화면에서 조금 아래로
START_BOX = (585, 786, 575, 52)            # 대기 화면: 손가락 아이콘과 화살표 사이
CHOICE_BOX = (456, 775, 760, 70)           # 매장/포장 선택 화면: 하단 가운데
# 움직임 (5단계 다듬기 D-1~D-3). 로고 조각은 tools/make_logo_parts.py로 만든다.
FRAME_MS = 40                              # 1초에 25번 다시 그린다
GEAR_CENTER = (1523, 519)                  # 원본 로고(1774×887) 기준 기어 가운데
GEAR_RADIUS = 68
GEAR_SECONDS_PER_TURN = 16                 # 차분하지만 눈에 띄게 한 바퀴 도는 시간
STEAMS = ((1500, 445, 180, 28, "#C68B52"), (1545, 440, 125, 18, "#EBCB9C"))   # (x, y, 높이, 굵기, 색)
SHADOW_SWAY = 22                           # 잎 그림자가 흔들리는 폭(px)
# 접근 안내는 그림 위가 아니라 아래 이벤트 띠에서 이벤트 문구와 번갈아 보여 준다(10/23 결정, B안).

START_TEXT = {
    "한국어": "화면을 터치하여 주문을 시작하세요",
    "English": "Touch the screen to start your order",
    "日本語": "画面をタッチしてご注文を始めてください",
    "中文": "触摸屏幕开始点单",
}
CHOICE_TEXT = {
    "한국어": "드시고 가세요? 포장해 가세요?",
    "English": "Dine in or take away?",
    "日本語": "店内でお召し上がりですか？お持ち帰りですか？",
    "中文": "堂食还是打包？",
}
APPROACH_TEXT = {
    "한국어": "가까이 오시면 자동으로 시작할 수 있어요",
    "English": "Come closer and it starts by itself",
    "日本語": "近づくと自動で始まります",
    "中文": "靠近时会自动开始",
}


def promotion_lines(policy, settings, first_event=None):
    """현재 진행 중인 행사와 실제 설정된 회원 혜택으로 대기 화면 광고를 만든다."""
    lines = []
    for event in policy_logic.active_events(policy):
        if first_event and event["id"] == first_event["id"]:
            continue
        lines.append((f"{event['name']}  ·  {policy_logic.banner_message(event)}", event.get("theme", "basic")))
    discount = int(policy.get("card_first_discount", 0))
    if discount:
        lines.append((f"회원카드 신규 등록 주문의 음료는 {discount}% 할인받을 수 있어요", "basic"))
    rate = float(policy.get("card_point_rate", 0))
    if rate:
        lines.append((f"회원카드 등록 후 매 주문 {rate:g}% 적립 혜택을 받아보세요", "basic"))
    goal = int(policy.get("card_stamp_goal", 0))
    if goal and card_logic.stamp_coupon(settings):
        lines.append((f"회원카드 주문 스탬프 {goal}개를 모으면 무료 음료 쿠폰을 드려요", "basic"))
    eco = int(policy.get("eco_points", 0))
    if eco:
        lines.append((f"회원이 개인 컵으로 음료를 주문하면 한 잔마다 {eco}P를 적립해 드려요", "basic"))
    visits = int(policy.get("visit_coupon_every", 0))
    amount = int(policy.get("visit_coupon_amount", 0))
    if visits and amount:
        lines.append((f"회원은 {visits}번째 방문마다 {amount:,}원 할인 쿠폰을 받을 수 있어요", "basic"))
    return lines


CHOICE_SECONDS = 20               # 매장 / 포장 버튼이 떠 있는 시간 (아무것도 안 고르면 다시 대기 화면)
CHOICE_PROMPT_SECONDS = 0.55       # 하단 질문이 아래에서 올라오며 선명해지는 시간


class DineChoice(QWidget):
    """11/03: 대기 화면 가운데에 '스윽' 떠오르는 매장 / 포장 버튼 두 개 (화면 전체를 바꾸지 않는다)."""

    def __init__(self, idle):
        super().__init__(idle)
        from gui.screens.dine import TEXT, MugIcon, PaperCupIcon
        self.idle = idle
        self.then = None
        self.texts = TEXT
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(16)
        self.title = label("", 30, title=True)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setStyleSheet(f"background: rgba(255, 250, 244, 225); border-radius: 18px; padding: 8px 24px;")
        column.addWidget(self.title, alignment=Qt.AlignmentFlag.AlignCenter)
        self.title.hide()                     # 선택 질문은 버튼 위가 아닌 화면 하단에 표시한다
        row = QHBoxLayout()
        row.setSpacing(28)                  # 두 칸 사이를 확실히 띄운다
        self.buttons, self.tile_texts = {}, {}
        tiles = ((False, "here", MugIcon(118), theme.CARD, theme.BROWN, theme.CARAMEL, theme.TEXT2),
                 (True, "togo", PaperCupIcon(118, ink="#FFFFFF", sleeve=theme.CARAMEL), theme.BROWN, "#FFFFFF",
                  theme.BROWN, "#EBD9C6"))
        for takeout, key, icon, fill, ink, edge, sub in tiles:
            tile = QPushButton()
            tile.setObjectName(f"{key}_button")
            tile.setCursor(Qt.CursorShape.PointingHandCursor)
            tile.setMinimumSize(300, 270)
            tile.setStyleSheet(f"QPushButton#{key}_button {{ background: {fill}; border: 4px solid {edge};"
                               f" border-radius: 26px; }} QPushButton#{key}_button:pressed {{ background: {theme.CARAMEL_LIGHT}; }}")
            tile.clicked.connect(lambda checked=False, t=takeout: self.choose(t))
            inner = QVBoxLayout(tile)
            inner.setContentsMargins(18, 22, 18, 20)
            inner.setSpacing(8)
            inner.addWidget(icon, alignment=Qt.AlignmentFlag.AlignCenter)
            name = label("", 30, bold=True)
            name.setStyleSheet(f"color: {ink}; background: transparent;")
            detail = label("", 16)
            detail.setStyleSheet(f"color: {sub}; background: transparent;")
            for part in (icon, name, detail):
                part.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            for part in (name, detail):
                part.setAlignment(Qt.AlignmentFlag.AlignCenter)
                inner.addWidget(part)
            self.buttons[key] = tile
            self.tile_texts[key] = (name, detail)
            row.addWidget(tile, 1)
        column.addLayout(row)
        self.opacity = None                 # 움직이는 동안만 흐림 효과를 단다 (카드 그림자와 겹치면 안 그려진다)
        self.fade = QPropertyAnimation(self)
        self.fade.setPropertyName(b"opacity")
        self.slide = QPropertyAnimation(self, b"pos", self)
        for animation in (self.fade, self.slide):
            animation.setDuration(380)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.group = QParallelAnimationGroup(self)
        self.group.addAnimation(self.fade)
        self.group.addAnimation(self.slide)
        self.group.finished.connect(self.after_animation)
        self.closing = False
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(self.close_choice)
        self.hide()

    def place(self):
        width = min(720, self.idle.width() - 80)
        self.resize(width, self.sizeHint().height())
        return QPoint((self.idle.width() - width) // 2, int(self.idle.height() * 0.52) - self.height() // 2)

    def open_choice(self, then=None):
        """대기 화면 터치 · 다가옴 · 카드: 버튼이 아래에서 살짝 올라오며 나타난다. 이미 떠 있으면 그대로."""
        if then is not None:
            self.then = then
        from gui.screens.home import LANGUAGES
        index = LANGUAGES.index(self.idle.router.language)
        for key in ("here", "togo"):
            name, detail = self.tile_texts[key]
            name.setText(self.texts[key][index])
            detail.setText(self.texts[f"{key}_detail"][index])
        self.timeout.start(CHOICE_SECONDS * 1000)
        self.idle.show_admin_button(True)       # 11/10: 매장 / 포장과 함께 오른쪽 위 운영자 버튼
        if self.isVisible() and not self.closing:
            return
        end = self.place()
        self.idle.choice_prompt_started = self.idle.seconds()
        self.closing = False
        self.group.stop()
        self.use_fade_effect()
        self.fade.setStartValue(0.0)
        self.fade.setEndValue(1.0)
        self.slide.setStartValue(end + QPoint(0, 40))
        self.slide.setEndValue(end)
        self.move(end + QPoint(0, 40))
        self.show()
        self.raise_()
        self.group.start()
        self.idle.update()

    def close_choice(self):
        """아무것도 안 고르면 다시 흐려지며 들어간다."""
        if not self.isVisible():
            return
        self.then = None
        self.closing = True
        self.idle.show_admin_button(False)
        self.group.stop()
        self.use_fade_effect()
        self.fade.setStartValue(1.0)
        self.fade.setEndValue(0.0)
        self.slide.setStartValue(self.pos())
        self.slide.setEndValue(self.pos() + QPoint(0, 30))
        self.group.start()

    def use_fade_effect(self):
        self.opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity)
        self.fade.setTargetObject(self.opacity)

    def after_animation(self):
        self.setGraphicsEffect(None)        # 다 나타났으면(또는 사라졌으면) 효과를 뗀다
        self.opacity = None
        if self.closing:
            self.hide()
            self.closing = False
            self.idle.update()

    def reset(self):
        self.group.stop()
        self.setGraphicsEffect(None)
        self.opacity = None
        self.timeout.stop()
        self.closing = False
        self.then = None
        self.hide()
        self.idle.show_admin_button(False)

    def choose(self, takeout):
        router = self.idle.router
        router.session.takeout = takeout
        then = self.then
        self.reset()
        if then is not None:
            then()
        else:
            router.show_screen("home")


class IdleScreen(QWidget):
    def __init__(self, router, event=theme.FROM_POLICY):
        super().__init__()
        self.router = router
        self.show_approach_hint = False    # D10 접근 감지를 연결하면 True
        self.background = QPixmap()
        self.choice_background = QPixmap()
        self.background_files = None
        self.logo, self.logo_front, self.logo_offset = self.logo_layers()
        self.scaled_background = None
        self.scaled_choice_background = None
        self.choice_prompt_started = 0.0
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
        # 11/10: 매장 / 포장이 떠 있을 때 오른쪽 위에 운영자 버튼 (둘 중 하나를 고르지 않아도 운영자 로그인)
        self.admin_button = chip("운영자")
        self.admin_button.setObjectName("idle_admin_button")
        self.admin_button.setCheckable(False)
        self.admin_button.setParent(self)
        self.admin_button.clicked.connect(self.open_admin)
        self.admin_button.hide()
        self.dine_choice = DineChoice(self)   # 11/03: 매장 / 포장은 이 화면 위에서 고른다

    def show_admin_button(self, on):
        self.admin_button.setVisible(on)
        if on:
            self.place_admin_button()
            self.admin_button.raise_()

    def place_admin_button(self):
        width = max(96, self.admin_button.fontMetrics().horizontalAdvance("운영자") + 48)
        self.admin_button.setGeometry(self.width() - width - 24, 24, width, theme.BUTTON_HEIGHT)

    def open_admin(self):
        self.dine_choice.reset()
        self.router.open_action("admin")

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
        settings = self.router.session.vault.read("settings", default={}) if self.router.session.vault else {}
        self.load_backgrounds(settings)
        self.dine_choice.reset()                # 새 손님: 떠 있던 버튼은 내린다
        for item in self.languages.buttons():   # 새 손님이면 한국어로 돌아와 있다
            item.setChecked(item.text() == self.language)
        self.set_approach_hint(self.show_approach_hint)
        if self.fixed_event == theme.FROM_POLICY:
            policy = self.router.session.policy()
            event = self.router.session.current_event()
            self.banner.set_promotions(promotion_lines(policy, settings, event))
            self.banner.set_event(event)

    def load_backgrounds(self, settings):
        files = idle_backgrounds(settings)
        if files == self.background_files:
            return
        backgrounds = [QPixmap(str(theme.ASSETS / filename)) for filename in files]
        if any(picture.isNull() for picture in backgrounds):
            files = idle_backgrounds({})
            backgrounds = [QPixmap(str(theme.ASSETS / filename)) for filename in files]
        self.background_files = files
        self.background, self.choice_background = backgrounds
        if not self.size().isEmpty():
            self.scaled_background = self.background.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            self.scaled_choice_background = self.choice_background.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
        self.update()

    def set_language(self, name):
        self.router.language = name
        self.set_approach_hint(self.show_approach_hint)
        if self.dine_choice.isVisible():
            self.dine_choice.open_choice()           # 버튼 글자도 고른 언어로
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
        self.scaled_choice_background = self.choice_background.scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation)
        self.shadow_layer = self.make_shadow_layer()
        if self.dine_choice.isVisible() and not self.dine_choice.closing:
            self.dine_choice.move(self.dine_choice.place())
        self.place_admin_button()
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
            band.setColorAt(0.5, QColor(70, 40, 15, 38))
            band.setColorAt(1, QColor(70, 40, 15, 0))
            painter.fillRect(QRectF(offset, -length / 2, width, length), band)
        painter.end()
        return layer

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), theme.BG)
        picture = (self.scaled_choice_background if self.dine_choice.isVisible()
                   else self.scaled_background)
        if picture is not None:
            painter.drawPixmap((self.width() - picture.width()) // 2,
                               (self.height() - picture.height()) // 2, picture)
        self.draw_shadow(painter)
        self.draw_logo(painter)
        if self.dine_choice.isVisible():
            elapsed = max(0.0, self.seconds() - self.choice_prompt_started)
            progress = min(1.0, elapsed / CHOICE_PROMPT_SECONDS)
            eased = 1.0 - (1.0 - progress) ** 3
            box = self.to_screen(CHOICE_BOX).translated(0, (1.0 - eased) * 24)
            painter.save()
            painter.setOpacity(eased)
            self.draw_fitted_text(painter, CHOICE_TEXT[self.language], box,
                                  theme.BROWN, 44, family="Jua")
            painter.restore()
        else:
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
        painter.setOpacity(0.62 + 0.38 * math.sin(t * 2 * math.pi / 9))
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
                wave = math.sin(part * 5.5 - t * 2.0 + number * 1.7) * 18 * (0.3 + part)
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

    def draw_fitted_text(self, painter, text, box, color, size, bold=False, family=None):
        # 언어마다 길이가 달라서 상자에 들어갈 때까지 글자를 줄인다.
        font = QFont(family) if family else theme.font(size, bold=bold)
        if family:
            font.setFamilies([family, *theme.GLYPH_FALLBACKS])
            font.setPixelSize(round(size * theme.SCALE))
            font.setBold(bold)
        while size > 14 and QFontMetrics(font).horizontalAdvance(text) > box.width():
            size -= 1
            if family:
                font.setPixelSize(round(size * theme.SCALE))
            else:
                font = theme.font(size, bold=bold)
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, text)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.router.ask_dine()                   # 11/03: 이 화면 위에 매장 / 포장 버튼이 떠오른다
        super().mousePressEvent(event)
