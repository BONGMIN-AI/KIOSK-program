"""01: 회원 또는 비회원 주문 경로를 고르는 화면.

아래 줄의 언어·고대비·큰 글자는 지금 손님에게만 적용되고, 00 대기 화면으로 가면 기본으로 돌아온다.
언어는 00 대기·01 시작 화면 문구를 바꾼다 (다음 화면들은 아직 한국어).
"""

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (QGraphicsOpacityEffect, QHBoxLayout, QLabel, QMenu, QSizePolicy, QVBoxLayout,
                               QWidget)

from domain.kiosk_settings import load_kiosk, shown_slides
from gui import theme
from gui.widgets import Card, Slideshow, button, label, trimmed_pixmap

LANGUAGES = ("한국어", "English", "日本語", "中文")
TEXT = {
    "heading": ("어떤 방식으로 주문하시겠어요?", "How would you like to order?",
                "ご注文方法をお選びください", "请选择点单方式"),
    "intro": ("회원은 나만의 혜택으로, 비회원은 간편하게 주문하세요.",
              "Members get their own benefits; guests can order right away.",
              "会員は特典付きで、非会員はそのまま簡単にご注文いただけます。", "会员享受专属优惠，非会员可直接点单。"),
    "member": ("회원 주문", "Member order", "会員注文", "会员点单"),
    "guest": ("비회원 주문", "Guest order", "非会員注文", "非会员点单"),
    "member_detail": ("아이디 + 얼굴 인증으로 로그인", "Sign in with ID + face", "ID + 顔認証でログイン",
                      "ID + 人脸登录"),
    "guest_detail": ("로그인 없이 바로 메뉴 선택", "Choose a menu without signing in",
                     "ログインせずにメニューを選択", "无需登录直接选菜单"),
    "member_benefit": ("쿠폰 · 포인트 · My Menu", "Coupons · Points · My Menu", "クーポン · ポイント · My Menu",
                       "优惠券 · 积分 · My Menu"),
    "guest_benefit": ("회원 혜택·적립은 없어요", "No member benefits or points", "会員特典・ポイントはありません",
                      "无会员优惠和积分"),
    "start": ("시작 →", "Start →", "開始 →", "开始 →"),
    "signup": ("처음이신가요?  회원가입 →", "First time?  Sign up →", "初めてですか？  会員登録 →",
               "第一次来？  注册会员 →"),
    "admin": ("운영자 메뉴", "Staff menu", "スタッフメニュー", "管理员菜单"),
    "back": ("← 처음으로", "← Start over", "← 最初に戻る", "← 返回首页"),
    "contrast": ("고대비", "High contrast", "ハイコントラスト", "高对比度"),
    "large": ("큰 글자", "Large text", "大きな文字", "大字体"),
}


def logo(filename, width, height):
    image = trimmed_pixmap(filename)
    result = QLabel()
    result.setPixmap(image.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation))
    result.setAlignment(Qt.AlignmentFlag.AlignCenter)
    result.setStyleSheet(f"background: {theme.LOGO_PLATE}; border-radius: 16px;")
    return result


class FitLogo(QWidget):
    """남는 높이만큼 커지는 로고 (비율 유지, 화면 너비의 MAX_WIDTH 비율까지). 전체 화면에서 위쪽 빈 곳을 채운다."""

    MAX_WIDTH = 0.42     # 너무 크면 촌스럽다 (10/29 의견) → 화면 너비의 절반 아래로

    def __init__(self, filename, min_height, plate=True):
        super().__init__()
        self.image = trimmed_pixmap(filename)
        self.plate = plate                   # 크림 글자 로고(고대비)는 받침 없이 검은 바탕에 바로
        self.setMinimumHeight(min_height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def paintEvent(self, event):
        if self.image.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        box = self.rect().adjusted(0, 8, 0, -8)
        size = self.image.size().scaled(min(box.width(), int(self.window().width() * self.MAX_WIDTH)),
                                        box.height(), Qt.AspectRatioMode.KeepAspectRatio)
        x = box.x() + (box.width() - size.width()) // 2
        y = box.y() + (box.height() - size.height()) // 2
        if self.plate and theme.LOGO_PLATE != "transparent":   # 고대비: 어두운 바탕에서도 로고가 보이게 밝은 받침
            painter.setBrush(QColor(theme.LOGO_PLATE))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(x - 16, y - 8, size.width() + 32, size.height() + 16, 16, 16)
        painter.drawPixmap(x, y, size.width(), size.height(), self.image)


class HomeScreen(QWidget):
    FADE_MS = 600

    def __init__(self, router):
        super().__init__()
        self.router = router
        self.texts = []          # (위젯, TEXT 키, 앞에 붙일 글자) — 언어를 바꾸면 다시 쓴다
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.content = QWidget()                 # 들어올 때 흐릿하게 나타나는(fade in) 부분
        outer.addWidget(self.content)
        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(48, 20, 48, 20)
        layout.setSpacing(14)
        # 10/31: 맨 위 가운데 큰 로고 → 아래 왼쪽은 돌아가는 광고·사진, 오른쪽은 회원/비회원 버튼을 위아래로
        layout.addLayout(self.make_header(), 2)
        body = QHBoxLayout()
        body.setSpacing(28)
        settings = self.router.session.vault.read("settings", default={}) if self.router.session.vault else {}
        self.slideshow = Slideshow(shown_slides(settings))     # 광고는 운영자 '광고 배너'에서 고친다
        big = theme.SCALE > 1
        if big:                                  # 11/03: 큰 글자에서는 광고 대신 큰 버튼 (변화가 확 보이게)
            self.slideshow.hide()
        else:
            body.addWidget(self.slideshow, 3)
        right = QVBoxLayout()
        right.setSpacing(10)
        heading = self.text(label("", 34 if big else 28, title=True, guide=True), "heading")
        right.addWidget(heading)
        intro = self.text(label("", muted=True, guide=True), "intro")
        intro.setFont(theme.font(20 if big else theme.BODY_SIZE))
        right.addWidget(intro)
        right.addSpacing(6)
        if big:                                  # 11/03: 큰 글자는 매장/포장 화면처럼 좌우 두 칸 (버튼이 잘리지 않게)
            cards = QHBoxLayout()
            cards.setSpacing(24)
            cards.addWidget(self.make_order_card(True), 1)
            cards.addWidget(self.make_order_card(False), 1)
            right.addLayout(cards, 1)
        else:
            right.addWidget(self.make_order_card(True), 1)
            right.addWidget(self.make_order_card(False), 1)
        self.signup_button = self.text(self.action_button("", "signup"), "signup")
        right.addWidget(self.signup_button)
        body.addLayout(right, 2 if not big else 1)
        layout.addLayout(body, 7)
        layout.addSpacing(6)
        layout.addLayout(self.make_footer())
        self.fade = QPropertyAnimation(self)
        self.fade.setPropertyName(b"opacity")
        self.fade.setDuration(self.FADE_MS)
        self.fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade.finished.connect(lambda: self.content.setGraphicsEffect(None))   # 다 보이면 효과를 뗀다
        self.apply_language()

    def paintEvent(self, event):
        """배경: 위는 밝은 크림, 아래로 갈수록 살짝 카라멜빛 + 커피 잔 자국 같은 큰 원 두 개 (고대비는 단색)."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if theme.BG == "#000000":
            painter.fillRect(self.rect(), QColor(theme.BG))
            return
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor("#FBF6EF"))
        gradient.setColorAt(1, QColor("#EFDDC6"))
        painter.fillRect(self.rect(), gradient)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        w, h = self.width(), self.height()
        for cx, cy, r, alpha in ((w * 0.08, h * 0.22, h * 0.32, 26), (w * 0.93, h * 0.12, h * 0.22, 20)):
            painter.setPen(QPen(QColor(182, 107, 46, alpha), max(6, h * 0.012)))
            painter.drawEllipse(QPointF(cx, cy), r, r)

    def fade_in(self):
        effect = QGraphicsOpacityEffect(self.content)
        effect.setOpacity(0.0)
        self.content.setGraphicsEffect(effect)
        self.fade.stop()
        self.fade.setTargetObject(effect)
        self.fade.setStartValue(0.0)
        self.fade.setEndValue(1.0)
        self.fade.start()

    def text(self, widget, key, suffix_key=None):
        self.texts.append((widget, key, suffix_key))
        return widget

    def apply_language(self):
        index = LANGUAGES.index(self.router.language)
        for widget, key, suffix_key in self.texts:
            words = TEXT[key][index]
            if suffix_key:
                words += " " + TEXT[suffix_key][index]
            widget.setText(words)
        self.language_button.setText(f"언어 · {self.router.language} ▼")

    def on_show(self):
        self.apply_language()
        vault = self.router.session.vault
        if vault is not None:
            settings = vault.read("settings", default={})
            self.slideshow.set_slides(shown_slides(settings), load_kiosk(settings)["slide_seconds"])
        self.fade_in()

    def action_button(self, text, action, kind="outline"):
        return button(text, kind, lambda: self.router.open_action(action))

    def make_header(self):
        """맨 위 줄: 가운데 큰 로고(남는 높이만큼 커짐) · 오른쪽 위 운영자 메뉴."""
        row = QHBoxLayout()
        self.admin_button = self.text(self.action_button("", "admin"), "admin")
        self.admin_button.setFont(theme.font(theme.SMALL_SIZE))
        spacer = QWidget()                       # 왼쪽도 같은 폭을 비워 로고가 정가운데
        spacer.setFixedWidth(self.admin_button.sizeHint().width() + 40)
        row.addWidget(spacer)
        contrast = theme.BG == "#000000"                 # 고대비: 크림 글자 로고 (받침 없이)
        self.logo = FitLogo("logo_contrast.png" if contrast else "logo_main.png", 76 if theme.SCALE == 1 else 70,
                            plate=not contrast)            # 최소 높이 (창이 크면 더 커짐)
        row.addWidget(self.logo, 1)
        row.addWidget(self.admin_button, alignment=Qt.AlignmentFlag.AlignTop)
        return row

    def make_order_card(self, member):
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 12, 24, 12)
        layout.setSpacing(6)
        layout.addStretch()                      # 카드가 커져도 글자는 가운데쯤, 버튼은 아래
        kind = "member" if member else "guest"
        # 글자는 가운데 정렬로 크게
        big = theme.SCALE > 1                    # 큰 글자: 광고 자리까지 넓게 쓰고 글자를 확 키운다
        lines = [(kind, 40 if big else 30, True, False), (f"{kind}_detail", 22 if big else 18, False, True),
                 (f"{kind}_benefit", 22 if big else 18, False, True)]
        for key, size, title_font, muted in lines:
            line = self.text(label("", size, title=title_font, muted=muted, guide=True), key)
            line.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(line)
        layout.addStretch()
        action = "member" if member else "guest"
        start = self.text(self.action_button("", action, "primary" if member else "secondary"),
                          kind, "start")
        start.setObjectName(f"{action}_button")
        start.setMinimumHeight(64 if big else 54)
        start.setFont(theme.font(26 if big else 22, bold=True))
        layout.addWidget(start)
        return card

    def make_footer(self):
        row = QHBoxLayout()
        self.back_button = self.text(button("", "outline", lambda: self.router.show_screen("idle")), "back")
        row.addWidget(self.back_button)
        row.addStretch()
        self.language_button = button("", "outline", self.choose_language)
        self.language_button.setFont(theme.font(theme.BODY_SIZE))
        row.addWidget(self.language_button)
        self.contrast_button = self.toggle("contrast")
        self.large_button = self.toggle("large")
        row.addWidget(self.contrast_button)
        row.addWidget(self.large_button)
        return row

    def toggle(self, key):
        item = button("", "chip", lambda: QTimer.singleShot(
            30, self, lambda: self.router.set_display(**{key: not self.router.display[key]})))
        item.setCheckable(True)
        item.setChecked(self.router.display[key])
        item.setFont(theme.font(theme.BODY_SIZE))
        return self.text(item, key)

    def choose_language(self):
        menu = QMenu(self)
        menu.setFont(theme.font(theme.BUTTON_SIZE))
        for name in LANGUAGES:
            action = menu.addAction(name)
            action.triggered.connect(lambda checked=False, name=name: self.set_language(name))
        menu.exec(self.language_button.mapToGlobal(self.language_button.rect().topLeft()))

    def set_language(self, name):
        self.router.language = name
        self.apply_language()
