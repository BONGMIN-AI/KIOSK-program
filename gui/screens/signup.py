"""10 회원가입 · 정보 입력 / 10-B 얼굴 등록 (와이어프레임 v2.1).

플로차트: 01 회원가입 → 10 가입 정보·동의 → 얼굴 정보 동의?
  ○ → 10-B 얼굴 등록 → (완료·나중에) 03 My Menu      × → 03 My Menu
02-B '비밀번호 확인 후 얼굴 등록'도 같은 10-B 화면을 쓴다.
사진은 저장하지 않고 얼굴 특징값만 암호화 금고에 저장한다. D435의 깊이 영상은 입체 확인에만 쓰고 저장하지 않는다.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QGridLayout, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from domain.allergens import ALLERGENS, search
from domain.customers import register_customer, set_face_enrolled, validate_password_pair
from face import FaceError
from gui import theme
from gui.screens.login import nav_bar
from gui.widgets import Card, button, label, message_label, phone_field, text_field


def check_box(text, bold=False):
    box = QCheckBox(text)
    box.setFont(theme.font(16, bold=bold))
    box.setMinimumHeight(40)
    return box


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
        left.addWidget(label("이름은 대기 화면에 닉네임으로 보여요. 비밀번호는 ●로 가려져요.", 13, muted=True))
        left.addStretch()
        body.addWidget(info, 1)

        right_card = Card()
        right = QVBoxLayout(right_card)
        right.setContentsMargins(22, 18, 22, 18)
        right.setSpacing(6)
        self.allergy_title = label("알레르기 선택 (0개)", 18, bold=True)
        right.addWidget(self.allergy_title)
        self.allergy_search = text_field("검색 (예: 우유)")
        self.allergy_search.textChanged.connect(self.show_allergies)
        right.addWidget(self.allergy_search)
        self.allergy_area = QScrollArea()
        self.allergy_area.setWidgetResizable(True)
        self.allergy_area.setFixedHeight(170)
        right.addWidget(self.allergy_area)
        right.addWidget(label("약관 동의", 18, bold=True))
        self.privacy = check_box("[필수] 개인정보 수집·이용 동의", bold=True)
        self.marketing = check_box("[선택] 마케팅 정보 수신 동의")
        right.addWidget(self.privacy)
        right.addWidget(self.marketing)
        right.addWidget(label("얼굴 정보 등록", 18, bold=True))
        self.face_consent = check_box("[선택] 얼굴 정보(특징값) 등록 동의 → 다음 화면 10-B")
        right.addWidget(self.face_consent)
        self.message = message_label()
        right.addWidget(self.message)
        right.addWidget(button("다음 →", "primary", self.submit))
        body.addWidget(right_card, 1)
        layout.addLayout(body, 1)
        layout.addLayout(nav_bar(router, lambda: router.show_screen("home")))

    def on_show(self):
        for field in (self.name, self.login_id, self.password, self.password_again, self.phone,
                      self.allergy_search):
            field.clear()
        for box in (self.privacy, self.marketing, self.face_consent):
            box.setChecked(False)
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
        if self.face_consent.isChecked():
            self.router.session.login(customer)
            self.router.show_screen("enroll", customer=customer)
        else:
            self.router.start_member_order(customer)


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
        head.addWidget(label("얼굴 동의자만 · 회원가입 2 / 2", 16, muted=True))
        layout.addLayout(head)
        body = QHBoxLayout()
        body.setSpacing(20)
        camera = Card()
        left = QVBoxLayout(camera)
        left.setContentsMargins(24, 22, 24, 22)
        left.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.addWidget(label("카메라 화면 (거울 모드)", 24, title=True), alignment=Qt.AlignmentFlag.AlignCenter)
        left.addWidget(label("버튼을 누르면 이 화면에 카메라가 나와요.\n가운데 얼굴 타원 안 = 초록 · 벗어나면 빨강",
                             16, muted=True), alignment=Qt.AlignmentFlag.AlignCenter)
        self.camera_kind = label("", 16, bold=True)
        left.addWidget(self.camera_kind, alignment=Qt.AlignmentFlag.AlignCenter)
        body.addWidget(camera, 1)
        steps_card = Card()
        steps_card.setFixedWidth(460)
        right = QVBoxLayout(steps_card)
        right.setContentsMargins(22, 20, 22, 20)
        right.setSpacing(10)
        right.addWidget(label("등록 안내 (단계별로 하나씩)", 20, bold=True))
        self.steps = label("", 17)
        self.steps.setWordWrap(True)
        right.addWidget(self.steps)
        privacy = label("사진은 저장하지 않고 특징값만 암호화해 저장합니다 · ESC 취소", 13, muted=True)
        privacy.setWordWrap(True)
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
        self.message.setText("카메라를 켜는 중이에요…")
        self.repaint()
        try:
            self.router.run_face(lambda provider: provider.enroll_face(self.customer["id"], lambda text: None))
            set_face_enrolled(self.router.session.vault, self.customer["id"], True)
        except (FaceError, ValueError) as error:
            self.message.setText(f"{error} · 나중에 다시 등록할 수 있어요")
            return
        self.router.session.reload_customer()
        self.message.setText("")
        self.steps.setText("✓ 얼굴 등록 완료\n다음부터 회원 ID + 얼굴로 로그인할 수 있어요.")
        self.start_button.setEnabled(False)
        self.skip_button.setText("주문 시작 →")

    def go_order(self):
        self.router.start_member_order(self.router.session.reload_customer() or self.customer)
