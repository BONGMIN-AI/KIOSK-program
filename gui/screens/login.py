"""02 회원 ID · 얼굴 인증 / 02-B 비밀번호 대체 로그인 (와이어프레임 v2.1).

플로차트: 회원 ID 입력 → 얼굴 인증(정면만: 가림·품질 → 진짜 얼굴 → 5장 비교, docs/FACE_AUTH_FLOW.md)
  → 성공: 03 My Menu   → 실패·사진 거절: 02-B 비밀번호 → 성공: 03 My Menu / 실패: 회원 ID 다시 입력
02-B의 '비밀번호 확인 후 얼굴 등록'은 10-B 얼굴 등록으로 간다.
"""

import numpy as np
from PySide6.QtCore import QElapsedTimer, Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

from domain.customers import find_by_login_id, login_with_face, login_with_password, must_change_password
from domain.member_cards import perks_text
from face import FaceError, guide_view
from gui import theme
from gui.widgets import (Card, FixedWidthCard, TouchKeyboard, button, label, link_button, message_label, option_check,
                         promo_row, text_field)


def nav_bar(router, back, menu=False):
    """화면 맨 아래 공통 버튼: ← 뒤로 가기 · (메뉴로) · 처음으로 / 로그아웃 (회원이면, 한 번 묻는다)."""
    row = QHBoxLayout()
    row.addWidget(button("← 뒤로 가기", "outline", back))
    if menu:
        row.addWidget(button("메뉴로", "outline", lambda: router.show_screen("menu")))
    leave = button("처음으로", "outline", router.ask_leave)
    leave.setObjectName("leave_button")
    row.addWidget(leave)
    row.addStretch()
    return row


def info_box(title, text):
    box = QFrame()
    box.setStyleSheet(f"background: {theme.CREAM}; border-radius: 16px;")
    column = QVBoxLayout(box)
    column.setContentsMargins(18, 14, 18, 14)
    column.addWidget(label(title, 18, bold=True))
    body = label(text, 15, muted=True, guide=True)
    column.addWidget(body)
    return box, body


class LoginScreen(QWidget):
    CAMERA_HELP = ("정면을 보고 잠시 멈추면 돼요 (마스크·선글라스는 벗기).\n"
                   "회원 카드를 리더기에 대면 ID 입력 없이 바로 시작해요.")

    def __init__(self, router):
        super().__init__()
        self.router = router
        self.mode = "face"           # "face" = 02, "password" = 02-B
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 24, 40, 20)
        layout.setSpacing(14)
        head = QHBoxLayout()
        self.title = label("", 32, title=True)
        head.addWidget(self.title)
        head.addStretch()
        head.addWidget(label("회원 로그인 · 1 / 6", 16, muted=True))
        layout.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(20)
        left_card = Card()
        left = QVBoxLayout(left_card)
        left.setContentsMargins(24, 20, 24, 20)
        left.setSpacing(10)
        left.addWidget(label("회원 ID를 입력해 주세요.", 22, bold=True))
        self.login_id = text_field("회원 ID")
        self.login_id.textChanged.connect(lambda _text: getattr(self, "mode", "face") != "face" and self.update_options())
        left.addWidget(self.login_id)
        self.password = text_field("비밀번호 (화면에 보이지 않아요)", password=True)
        left.addWidget(self.password)
        self.keyboard = TouchKeyboard()
        self.keyboard.attach(self.login_id, self.password)
        left.addWidget(self.keyboard)
        self.promo = promo_row("promo_photo.webp", "promo_smile.webp")   # 키보드 아래 남는 자리는 홍보 배너
        left.addWidget(self.promo, 1)
        # 얼굴 인증 중에는 키보드·배너 자리에 얼굴 기호를 그린다 (창 전체를 덮지 않는다, 10/29)
        self.face_picture = QLabel()
        self.face_picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.face_picture.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.face_picture.setStyleSheet("background: rgb(250, 250, 250); border-radius: 16px;")   # 얼굴 기호 바탕색
        self.face_picture.hide()
        left.addWidget(self.face_picture, 1)
        self.face_cancelled = False
        body.addWidget(left_card, 1)

        right_card = self.right_card = FixedWidthCard(470)
        right = QVBoxLayout(right_card)
        right.setContentsMargins(22, 20, 22, 20)
        right.setSpacing(12)
        self.camera_box, self.camera_text = info_box("카메라 얼굴 인증", self.CAMERA_HELP)
        right.addWidget(self.camera_box)
        self.fail_box, self.fail_text = info_box("인증 실패", "")
        self.fail_box.setStyleSheet(f"background: {theme.WARN_BG}; border-radius: 16px;")
        right.addWidget(self.fail_box)
        self.message = message_label()
        right.addWidget(self.message)
        right.addStretch(1)                    # 버튼은 아래쪽에 붙인다 (홍보는 키보드 아래 배너만)
        # 비밀번호 로그인(02-B): 로그인하면서 함께 할 일을 혜택과 함께 체크 상자로 고른다 (11/02)
        self.options_box = QFrame()
        self.options_box.setObjectName("login_options")
        self.options_box.setStyleSheet(f"QFrame#login_options {{ background: {theme.CREAM}; border-radius: 16px; }}")
        options = QVBoxLayout(self.options_box)
        options.setContentsMargins(16, 12, 16, 12)
        options.setSpacing(2)
        options.addWidget(label("로그인하면서 함께 할까요? (선택)", 15, bold=True))
        self.enroll_check = option_check("얼굴도 등록할게요")
        options.addWidget(self.enroll_check)
        self.enroll_note = label("다음부터 카메라만 보면 바로 로그인돼요", 14, muted=True)
        self.enroll_note.setContentsMargins(28, 0, 0, 4)
        options.addWidget(self.enroll_note)
        self.card_check = option_check("회원카드 신청 (장바구니에 담겨요)")
        options.addWidget(self.card_check)
        self.card_note = label("", 14, muted=True, guide=True)
        self.card_note.setStyleSheet(f"color: {theme.CARAMEL};")
        self.card_note.setContentsMargins(28, 0, 0, 0)
        options.addWidget(self.card_note)
        right.addWidget(self.options_box)
        self.cancel_face_button = button("얼굴 인증 취소", "outline", self.cancel_face)
        self.cancel_face_button.hide()
        right.addWidget(self.cancel_face_button)
        self.face_button = button("얼굴 인증", "primary", self.face_login)
        self.password_mode_button = button("비밀번호로 로그인", "outline",
                                           lambda: self.set_mode("password"))
        self.password_button = button("로그인 →", "primary", self.password_login)
        for widget in (self.face_button, self.password_mode_button, self.password_button):
            right.addWidget(widget)
        # 작은 밑줄 링크: 회원가입 · 아이디/비밀번호 찾기 (회원카드 분실은 My Menu · 운영자 화면)
        links = QVBoxLayout()                    # 한 줄에 하나씩, 오른쪽에 붙여 (큰 글자에서도 겹치지 않게)
        links.setSpacing(0)
        self.signup_link = link_button("처음 오셨나요? 회원가입", lambda: self.router.open_action("signup"),
                                       strong=True)
        self.signup_link.setObjectName("signup_link")
        self.find_button = link_button("아이디·비밀번호를 잊었어요", self.find_account)
        for widget in (self.signup_link, self.find_button):
            links.addWidget(widget, alignment=Qt.AlignmentFlag.AlignRight)
        right.addLayout(links)
        body.addWidget(right_card)
        layout.addLayout(body, 1)
        layout.addLayout(nav_bar(router, self.go_back))
        self.set_mode("face")      # 처음부터 02 모양으로 (02-B 버튼은 숨김)

    def on_show(self, mode="face", message="", keep_id=False, login_id=""):
        if not keep_id:
            self.login_id.clear()
        if login_id:
            self.login_id.setText(login_id)
        self.password.clear()
        self.enroll_check.setChecked(False)       # 새 손님마다 체크는 비운다
        self.card_check.setChecked(False)
        self.set_mode(mode, message)

    def set_mode(self, mode, message=""):
        self.mode = mode
        face = mode == "face"
        self.title.setText("회원 ID · 얼굴 인증" if face else "비밀번호로 로그인")
        self.password.setVisible(not face)
        self.camera_box.setVisible(face)
        self.signup_link.setVisible(face)
        self.face_button.setVisible(face)
        self.password_mode_button.setVisible(face)
        for widget in (self.password_button, self.options_box):
            widget.setVisible(not face)
        if not face:
            self.card_note.setText(perks_text(self.router.session.policy()))
            self.update_options()
        self.fail_box.setVisible(False)
        self.face_button.setText("얼굴 인증")     # 다음 손님에게는 '재시도'가 아니라 처음 상태로
        self.say(message, ok=False)
        self.keyboard.target = self.login_id if face or not self.login_id.text() else self.password
        # 11/04: 아이디를 넣고 '비밀번호로 로그인'을 누르면 바로 비밀번호 칸에 커서 (한 번 더 누르지 않게).
        # 화면이 막 바뀌는 중이면 아직 안 보여서 포커스가 안 들어가니 한 박자 뒤에 넣는다.
        target = self.keyboard.target
        QTimer.singleShot(0, target, lambda: target.setFocus(Qt.FocusReason.OtherFocusReason))
        self.right_card.updateGeometry()        # 버튼이 바뀐 오른쪽 칸 높이를 다시 재게 (큰 글자에서 창이 커지던 문제)

    def find_account(self):
        """02-C 아이디 찾기 · 비밀번호 재설정. 아이디를 넣어 두었으면 비밀번호 재설정부터."""
        login_id = self.login_id.text().strip()
        self.router.show_screen("find", mode="password" if login_id else "id", login_id=login_id)

    def go_back(self):
        if self.mode == "password":
            self.set_mode("face")
        else:
            self.router.show_screen("home")

    def vault(self):
        return self.router.session.vault

    # 02: 얼굴
    def face_login(self):
        login_id = self.login_id.text().strip()
        if not login_id:
            self.say("회원 ID를 먼저 입력해 주세요", ok=False)
            return
        self.say("", ok=False)
        scores = []     # "얼굴 유사도 0.612 (기준 0.50)" — 기준값을 맞출 때 보려고 남긴다
        self.begin_face()
        try:
            customer = self.router.run_face(
                lambda provider: login_with_face(self.vault(), login_id, provider, scores.append),
                viewer=self.show_face, on_step=self.show_step)
        except (FaceError, ValueError) as error:
            self.end_face()
            reason = str(error)
            score = next((text for text in reversed(scores) if text.startswith("얼굴 유사도")), "")
            self.show_face_failure(f"{reason}\n{score}" if score else reason)
            return
        self.end_face()
        for text in scores:
            if text.startswith("얼굴 유사도"):
                print(f"[얼굴 로그인] {login_id} · {text}")
        self.router.start_member_order(customer)

    # 화면 안 얼굴 표시 (왼쪽: 얼굴 기호 · 오른쪽: 지금 할 일 한 줄)
    def begin_face(self):
        self.face_cancelled = False
        self.keyboard.hide()
        self.promo.hide()
        self.face_picture.clear()
        self.face_picture.show()
        self.fail_box.hide()
        self.camera_box.show()
        self.camera_box.findChild(QLabel).setText("얼굴 인증 중")
        self.camera_text.setText("카메라를 켜는 중이에요…")
        self.camera_text.setFont(theme.font(20, bold=True))      # 지금 할 일은 크게 한 줄
        for widget in (self.face_button, self.password_mode_button, self.signup_link, self.find_button):
            widget.hide()
        self.cancel_face_button.show()
        self.repaint()

    def end_face(self):
        self.face_picture.hide()
        self.keyboard.show()
        self.promo.show()
        self.cancel_face_button.hide()
        self.camera_box.findChild(QLabel).setText("카메라 얼굴 인증")
        self.camera_text.setText(self.CAMERA_HELP)
        self.camera_text.setFont(theme.font(15))
        self.set_mode(self.mode, self.message.text())
        self.find_button.show()

    def cancel_face(self):
        self.face_cancelled = True

    def show_step(self, text):
        self.camera_text.setText(text)

    def show_face(self, image, wait_ms=1):
        """얼굴 공급자가 프레임마다 부른다: 1280x720 안내 그림에서 얼굴 기호 둘레만 잘라 왼쪽 칸에 그린다."""
        cx, cy = guide_view.ROI_CENTER
        left = np.ascontiguousarray(image[cy - 250:cy + 250, cx - 250:cx + 250])
        height, width = left.shape[:2]
        frame = QImage(left.data, width, height, left.strides[0], QImage.Format.Format_BGR888).copy()
        self.face_picture.setPixmap(QPixmap.fromImage(frame).scaled(
            self.face_picture.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        clock = QElapsedTimer()
        clock.start()
        while True:
            QApplication.processEvents()
            if self.face_cancelled or clock.elapsed() >= wait_ms:
                return self.face_cancelled

    def show_face_failure(self, reason):
        """실패·사진 거절: 이유를 보여 주고 '얼굴 인증 재시도'·'비밀번호로 로그인'을 남긴다."""
        self.say("", ok=False)
        self.fail_text.setText(f"{reason}\n밝은 곳에서 다시 시도하거나 비밀번호를 사용하세요.")
        self.fail_box.setVisible(True)
        self.camera_box.setVisible(False)       # 실패 안내가 대신 그 자리를 쓴다 (큰 글자에서도 들어가게)
        self.face_button.setText("얼굴 인증 재시도")

    # 02-B: 비밀번호
    def check_password(self):
        login_id = self.login_id.text().strip()
        try:
            return login_with_password(self.vault(), login_id, self.password.text())
        except ValueError:
            # 플로차트: 비밀번호 실패 → 회원 ID 다시 입력
            self.on_show("face", "아이디 또는 비밀번호를 확인해 주세요")
            return None

    def password_login(self):
        customer = self.check_password()
        if not customer:
            return
        if must_change_password(customer):                  # 임시 비밀번호 → 새 비밀번호부터 정한다
            self.router.show_screen("find", mode="change", customer=customer)
            return
        session = self.router.session
        note = ""
        if self.card_check.isChecked():                    # 회원카드 → 장바구니 (음료와 함께 결제)
            session.login(customer)
            try:
                session.add_card("new")
                self.router.audit("card_in_cart", customer["id"])
                note = "회원카드를 장바구니에 담았어요.\n음료와 함께 결제하면 음료 나올 때 드려요."
            except ValueError as error:
                note = str(error)
        if self.enroll_check.isChecked():                  # 얼굴 등록 화면 → 끝나면 주문으로
            session.login(customer)
            self.router.show_screen("enroll", customer=customer)
        else:
            self.router.start_member_order(customer)
        if note:
            self.router.notify(note, 7)

    def update_options(self):
        """입력한 아이디의 회원을 보고 '함께 할 일' 중 필요한 것만 보여 준다 (11/03)."""
        from domain.member_cards import check_can_buy
        customer = None
        try:
            customer = find_by_login_id(self.vault(), self.login_id.text().strip())
        except ValueError:
            pass
        need_face = customer is None or not customer["extra"].get("face_enrolled")
        need_card = True
        if customer is not None:
            try:
                check_can_buy(self.vault(), customer, "new")
            except ValueError:
                need_card = False
        for widget in (self.enroll_check, self.enroll_note):
            widget.setVisible(need_face)
        for widget in (self.card_check, self.card_note):
            widget.setVisible(need_card)
        if not need_face:
            self.enroll_check.setChecked(False)
        if not need_card:
            self.card_check.setChecked(False)
        self.options_box.setVisible(self.mode != "face" and (need_face or need_card))

    def say(self, text, ok=True):
        """오른쪽 안내 한 줄: ok면 갈색(안내), 아니면 빨강(오류)."""
        self.message.setStyleSheet(f"color: {theme.BROWN if ok else theme.ERROR};")
        self.message.setText(text)

    def customer_exists(self, login_id):
        return find_by_login_id(self.vault(), login_id) is not None
