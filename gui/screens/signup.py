"""10 회원가입 · 정보 입력 / 10-B 얼굴 등록 (와이어프레임 v2.1).

플로차트: 01 회원가입 → 10 가입 정보·동의 → 얼굴 정보 동의?
  ○ → 10-B 얼굴 등록 → (완료·나중에) 03 My Menu      × → 03 My Menu
02-B '비밀번호 확인 후 얼굴 등록'도 같은 10-B 화면을 쓴다.
사진은 저장하지 않고 얼굴 특징값만 암호화 금고에 저장한다. D435의 깊이 영상은 입체 확인에만 쓰고 저장하지 않는다.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QFrame, QGridLayout, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from domain.allergens import ALLERGENS, search
from domain.customers import register_customer, set_face_enrolled, validate_password_pair
from domain.member_cards import perks_text
from face import FaceError
from gui import theme
from gui.screens.login import nav_bar
from gui.screens.ticket import HangulKeyboard
from gui.widgets import FixedWidthCard, Card, FacePanel, TouchKeyboard, button, label, message_label, phone_field, text_field


def check_box(text, bold=False):
    box = QCheckBox(text)
    box.setFont(theme.font(16, bold=bold))
    box.setMinimumHeight(40)
    return box


def option_box(title, detail):
    """회원가입 오른쪽 아래의 눈에 띄는 선택 칸 (회원카드 신청 · 얼굴 등록): 테두리 상자 + 큰 체크 + 혜택 한 줄.
    상자 어디를 눌러도 체크가 바뀐다."""
    box = ClickFrame()
    box.setObjectName("option_box")
    box.setStyleSheet(f"QFrame#option_box {{ background: {theme.CREAM}; border: 2px solid {theme.CARAMEL};"
                      " border-radius: 14px; }")
    column = QVBoxLayout(box)
    column.setContentsMargins(12, 6, 12, 6)
    column.setSpacing(2)
    check = check_box(title, bold=True)
    check.setFont(theme.font(18, bold=True))
    side = round(26 * theme.SCALE)
    check.setStyleSheet(f"QCheckBox {{ border: none; }} QCheckBox::indicator {{ width: {side}px; height: {side}px; }}")
    column.addWidget(check)
    perks = label(detail, 14, bold=True)
    perks.setStyleSheet(f"border: none; color: {theme.CARAMEL};")
    column.addWidget(perks)
    box.clicked = check.toggle
    return box, check, perks


class ClickFrame(QFrame):
    clicked = None

    def mousePressEvent(self, event):
        if self.clicked is not None:
            self.clicked()


class SignupScreen(QWidget):
    def __init__(self, router):
        super().__init__()
        self.router = router
        self.checked_allergies = set()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 16)
        layout.setSpacing(12)
        head = QHBoxLayout()
        head.addWidget(label("회원가입 · 정보 입력", 32, title=True))
        head.addStretch()
        head.addWidget(label("회원가입 1 / 2", 16, muted=True))
        layout.addLayout(head)
        body = QHBoxLayout()
        body.setSpacing(20)

        info = Card()
        left = QVBoxLayout(info)
        left.setContentsMargins(22, 18, 22, 18)
        left.setSpacing(6)
        self.name = text_field("이름 *")
        self.login_id = text_field("아이디 * (영문·숫자)")
        self.password = text_field("비밀번호 * (4자 이상)", password=True)
        self.password_again = text_field("비밀번호 재입력 *", password=True)
        self.phone = phone_field("전화번호 * (숫자만 치면 010-0000-0000 모양으로)")
        for field in (self.name, self.login_id, self.password, self.password_again, self.phone):
            left.addWidget(field)
        self.keyboard_switch = button("한글 / 영문 전환", "outline", self.switch_keyboard)
        left.addWidget(self.keyboard_switch)
        self.korean_keyboard = HangulKeyboard()
        self.english_keyboard = TouchKeyboard()
        fields = (self.name, self.login_id, self.password, self.password_again, self.phone)
        self.korean_keyboard.attach(*fields)
        self.english_keyboard.attach(*fields)
        left.addWidget(self.korean_keyboard)
        left.addWidget(self.english_keyboard)
        self.english_keyboard.hide()
        left.addStretch()
        body.addWidget(info, 1)

        right_card = Card()
        right = QVBoxLayout(right_card)
        right.setContentsMargins(22, 18, 22, 18)
        right.setSpacing(12 if theme.SCALE == 1 else 8)   # 묶음과 묶음 사이 (큰 글자는 창 높이에 맞춰 좁게)

        def section(title_widget, *widgets):
            """제목과 그 선택 칸을 한 묶음으로 붙여 둔다 (10/31: 창이 크면 제목과 칸이 벌어졌다)."""
            box = QVBoxLayout()
            box.setSpacing(4)
            box.addWidget(title_widget)
            for widget in widgets:
                box.addWidget(widget)
            right.addLayout(box)

        self.allergy_title = label("알레르기 선택 (0개)", 18, bold=True)
        self.allergy_search = text_field("검색 (예: 우유)")
        self.allergy_search.textChanged.connect(self.show_allergies)
        self.allergy_area = QScrollArea()
        self.allergy_area.setWidgetResizable(True)
        self.allergy_area.setMinimumHeight(104)   # 11/03: 남는 높이를 알레르기 칸이 쓴다 (아래 빈 곳 없이)
        section(self.allergy_title, self.allergy_search, self.allergy_area)
        right.setStretch(right.count() - 1, 1)
        self.privacy = check_box("[필수] 개인정보 수집·이용 동의", bold=True)
        self.marketing = check_box("[선택] 마케팅 정보 수신 동의")
        section(label("약관 동의", 18, bold=True), self.privacy, self.marketing)
        # 11/09: 얼굴 등록도 회원카드처럼 눈에 띄는 칸으로 (작은 체크 줄이라 못 보고 지나쳤다)
        self.face_box, self.face_consent, self.face_perks = option_box(
            "[선택] 얼굴 등록", "다음부터 카메라만 보면 바로 로그인 · 사진은 저장하지 않아요")
        right.addWidget(self.face_box)
        # 11/01 회원카드 신청 (선택): 혜택을 보여 주고 고르게 한다 → 운영자 승인 → 카운터에서 받기
        self.card_box, self.card_request, self.card_perks = option_box("[선택] 회원카드 신청", "")
        card = self.card_box.layout()                          # 혜택 글은 운영자 정책 값으로 on_show에서 채운다
        self.card_how = how = label("", 13, muted=True)
        how.setStyleSheet(f"border: none; color: {theme.TEXT2};")
        how.setVisible(theme.SCALE == 1)         # 큰 글자에서는 칸 높이에 맞춰 뺀다
        card.addWidget(how)
        right.addWidget(self.card_box)
        self.message = message_label()
        right.addWidget(self.message)
        right.addWidget(button("다음 →", "primary", self.submit))
        body.addWidget(right_card, 1)
        layout.addLayout(body, 1)
        layout.addLayout(nav_bar(router, lambda: router.show_screen("home")))

    def switch_keyboard(self):
        korean = self.korean_keyboard.isVisible()
        target = self.korean_keyboard.target if korean else self.english_keyboard.target
        self.korean_keyboard.target = target
        self.english_keyboard.target = target
        self.korean_keyboard.setVisible(not korean)
        self.english_keyboard.setVisible(korean)

    def on_show(self):
        for field in (self.name, self.login_id, self.password, self.password_again, self.phone,
                      self.allergy_search):
            field.clear()
        for box in (self.privacy, self.marketing, self.face_consent, self.card_request):
            box.setChecked(False)
        policy = self.router.session.policy()
        self.card_perks.setText(f"{perks_text(policy)}\n카드만 대면 바로 로그인")
        self.card_how.setText(f"카드값 {policy['card_price']:,}원 · 장바구니에 담겨 음료와 함께 결제 · 음료 나올 때 받아요")
        self.checked_allergies = set()
        self.message.setText("")
        self.show_allergies()

    def show_allergies(self):
        """검색어에 맞는 알레르기만 보여 준다. 검색어를 바꿔도 체크는 그대로 남는다."""
        names = search(self.allergy_search.text(), ALLERGENS) if self.allergy_search.text() else ALLERGENS
        page = QWidget()
        grid = QGridLayout(page)
        grid.setContentsMargins(0, 0, 0, 0)
        for index, name in enumerate(names):
            box = check_box(name)
            box.setChecked(name in self.checked_allergies)
            box.toggled.connect(lambda checked, n=name: self.toggle_allergy(n, checked))
            grid.addWidget(box, index // 2, index % 2)
        self.allergy_area.setWidget(page)

    def toggle_allergy(self, name, checked):
        if checked:
            self.checked_allergies.add(name)
        else:
            self.checked_allergies.discard(name)
        self.allergy_title.setText(f"알레르기 선택 ({len(self.checked_allergies)}개)")

    def submit(self):
        try:
            if not self.name.text().strip():          # 위 칸부터 차례로 알려 준다
                raise ValueError("이름을 입력하세요")
            validate_password_pair(self.password.text(), self.password_again.text())
            customer = register_customer(
                self.router.session.vault, self.name.text(), "", self.phone.text(),
                self.login_id.text(), self.password.text(),
                allergies=sorted(self.checked_allergies),
                privacy_agreed=self.privacy.isChecked(),
                marketing_agreed=self.marketing.isChecked())
        except ValueError as error:
            self.message.setText(str(error))
            return
        session = self.router.session
        session.login(customer)
        if self.card_request.isChecked():             # 회원카드 → 장바구니 (음료와 함께 결제)
            session.add_card("new")
            self.router.audit("card_in_cart", customer["id"])
        if self.face_consent.isChecked():
            self.router.show_screen("enroll", customer=customer)
        else:
            self.router.start_member_order(customer)
        if session.card_kind:
            self.router.notify("회원카드를 장바구니에 담았어요.\n음료와 함께 결제하면 음료 나올 때 드려요.", 7)


class EnrollScreen(QWidget):
    """10-B 얼굴 등록. 카메라 창은 버튼을 누르면 열린다."""

    def __init__(self, router):
        super().__init__()
        self.router = router
        self.customer = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 24, 40, 20)
        layout.setSpacing(14)
        head = QHBoxLayout()
        head.addWidget(label("얼굴 등록", 32, title=True))
        head.addStretch()
        head.addWidget(label("회원가입 2 / 2", 16, muted=True))
        layout.addLayout(head)
        body = QHBoxLayout()
        body.setSpacing(20)
        camera = Card()
        left = QVBoxLayout(camera)
        left.setContentsMargins(24, 22, 24, 22)
        # 10/31: 창 전체를 덮는 카메라 화면 대신, 이 왼쪽 칸 안에 얼굴 기호를 그린다 (로그인과 같은 방식)
        self.idle_text = QWidget()
        idle = QVBoxLayout(self.idle_text)
        idle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        idle.addWidget(label("얼굴 등록", 24, title=True), alignment=Qt.AlignmentFlag.AlignCenter)
        idle.addWidget(label("버튼을 누르면 이 칸에 얼굴 기호가 나와요.\n카메라 앞 50cm 안에서 정면을 보면 돼요.",
                             16, muted=True), alignment=Qt.AlignmentFlag.AlignCenter)
        self.camera_kind = label("", 16, bold=True)
        idle.addWidget(self.camera_kind, alignment=Qt.AlignmentFlag.AlignCenter)
        left.addWidget(self.idle_text, 1)
        self.face_panel = FacePanel()
        self.face_panel.hide()
        left.addWidget(self.face_panel, 1)
        body.addWidget(camera, 1)
        steps_card = FixedWidthCard(460)
        right = QVBoxLayout(steps_card)
        right.setContentsMargins(22, 20, 22, 20)
        right.setSpacing(10)
        right.addWidget(label("등록 안내 (단계별로 하나씩)", 20, bold=True))
        self.steps = label("", 17, guide=True)
        right.addWidget(self.steps)
        self.now_box = QFrame()                  # 등록하는 동안 '지금 할 일' 한 줄을 크게
        self.now_box.setStyleSheet(f"background: {theme.CREAM}; border-radius: 16px;")
        now = QVBoxLayout(self.now_box)
        now.setContentsMargins(16, 12, 16, 12)
        now.addWidget(label("지금 할 일", 14, muted=True))
        self.now_text = label("", 22, bold=True, guide=True)
        now.addWidget(self.now_text)
        self.now_box.hide()
        right.addWidget(self.now_box)
        privacy = label("사진은 저장하지 않고 특징값만 암호화해 저장합니다 · ESC 취소", 13, muted=True, guide=True)
        right.addWidget(privacy)
        self.message = message_label()
        right.addWidget(self.message)
        right.addStretch()
        self.start_button = button("카메라 켜고 등록 시작", "primary", self.enroll)
        right.addWidget(self.start_button)
        self.skip_button = button("나중에 하기 · 바로 주문", "outline", self.go_order)
        right.addWidget(self.skip_button)
        body.addWidget(steps_card)
        layout.addLayout(body, 1)
        layout.addLayout(nav_bar(router, lambda: router.show_screen("idle")))

    def on_show(self, customer=None):
        self.customer = customer or self.router.session.customer
        self.message.setText("")
        self.start_button.setText("카메라 켜고 등록 시작")
        self.start_button.setEnabled(True)
        self.skip_button.setText("나중에 하기 · 바로 주문")
        self.camera_kind.setText("정면을 보고 잠시 멈추면 돼요 · 사진은 저장하지 않아요")
        self.steps.setText("1  카메라 앞 50cm 안에 서기 (마스크·선글라스 벗기)\n2  정면을 보고 잠시 멈추기\n"
                           "3  확인되면 등록 완료")

    def enroll(self):
        if self.face_panel.isVisible():          # 등록 중에 누르면 '취소'
            self.face_panel.cancel()
            return
        self.message.setText("")
        self.show_running(True)
        try:
            self.router.run_face(lambda provider: provider.enroll_face(self.customer["id"], lambda text: None),
                                 viewer=self.face_panel.show_frame, on_step=self.now_text.setText)
            set_face_enrolled(self.router.session.vault, self.customer["id"], True)
        except (FaceError, ValueError) as error:
            self.show_running(False)
            self.message.setText(f"{error} · 나중에 다시 등록할 수 있어요")
            return
        self.show_running(False)
        self.router.session.reload_customer()
        self.message.setText("")
        # 11/09: 등록이 끝나면 '주문 시작'을 누를 필요 없이 바로 My Menu로
        self.go_order()
        self.router.notify("얼굴 등록 완료!\n다음부터 회원 ID + 얼굴로 로그인할 수 있어요.", 5)

    def show_running(self, running):
        """등록 중: 왼쪽은 얼굴 기호, 오른쪽은 '지금 할 일' 크게 · 시작 버튼은 '취소'로."""
        self.idle_text.setVisible(not running)
        self.face_panel.setVisible(running)
        self.now_box.setVisible(running)
        self.now_text.setText("카메라를 켜는 중이에요…" if running else "")
        self.start_button.setText("등록 취소" if running else "카메라 켜고 등록 시작")
        self.skip_button.setEnabled(not running)
        if running:
            self.face_panel.reset()
        self.repaint()

    def go_order(self):
        self.router.start_member_order(self.router.session.reload_customer() or self.customer)
