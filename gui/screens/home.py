"""01: 회원 또는 비회원 주문 경로를 고르는 화면.

아래 줄의 언어·고대비·큰 글자는 지금 손님에게만 적용되고, 00 대기 화면으로 가면 기본으로 돌아온다.
언어는 00 대기·01 시작 화면 문구를 바꾼다 (다음 화면들은 아직 한국어).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QVBoxLayout, QWidget

from gui import theme
from gui.widgets import Card, button, label, trimmed_pixmap

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


class HomeScreen(QWidget):
    def __init__(self, router):
        super().__init__()
        self.router = router
        self.texts = []          # (위젯, TEXT 키, 앞에 붙일 글자) — 언어를 바꾸면 다시 쓴다
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 20, 48, 20)
        layout.setSpacing(14)
        layout.addLayout(self.make_header())
        # 10/29: 로고·제목이 너무 커서 아래 카드에 붙어 보였다 → 조금 줄이고, 위아래에 같은 여백을 두어 가운데로
        layout.addStretch(1)
        layout.addWidget(logo("logo_main.png", 470, 124 if theme.SCALE == 1 else 90))
        heading = self.text(label("", 30, title=True), "heading")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(heading)
        intro = self.text(label("", muted=True), "intro")
        intro.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(intro)
        layout.addSpacing(26)                    # 제목 묶음과 주문 카드 사이 숨 쉴 자리
        cards = QHBoxLayout()
        cards.setSpacing(24)
        cards.addWidget(self.make_order_card(True))
        cards.addWidget(self.make_order_card(False))
        layout.addLayout(cards)
        self.signup_button = self.text(self.action_button("", "signup"), "signup")
        layout.addWidget(self.signup_button)
        layout.addStretch(1)
        layout.addLayout(self.make_footer())
        self.apply_language()

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

    def action_button(self, text, action, kind="outline"):
        return button(text, kind, lambda: self.router.open_action(action))

    def make_header(self):
        row = QHBoxLayout()
        row.addWidget(logo("logo_sub.png", 56, 64))
        row.addStretch()
        self.admin_button = self.text(self.action_button("", "admin"), "admin")
        self.admin_button.setFont(theme.font(theme.SMALL_SIZE))
        row.addWidget(self.admin_button)
        return row

    def make_order_card(self, member):
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(10)
        kind = "member" if member else "guest"
        # 글자는 가운데 정렬로 크게
        for key, size, title_font, muted in ((kind, 36, True, False), (f"{kind}_detail", 22, False, True),
                                             (f"{kind}_benefit", 22, False, True)):
            line = self.text(label("", size, title=title_font, muted=muted), key)
            line.setAlignment(Qt.AlignmentFlag.AlignCenter)
            line.setWordWrap(True)
            layout.addWidget(line)
        layout.addStretch()
        action = "member" if member else "guest"
        start = self.text(self.action_button("", action, "primary" if member else "secondary"),
                          kind, "start")
        start.setObjectName(f"{action}_button")
        start.setMinimumHeight(64)
        start.setFont(theme.font(22, bold=True))
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
        item = button("", "chip", lambda: self.router.set_display(**{key: not self.router.display[key]}))
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
