"""02-C 아이디 찾기 · 비밀번호 재설정 (10/28 회의 6번).

비밀번호는 원래 글자를 저장하지 않으므로 '찾기'가 아니라 새로 정한다.
  아이디 찾기:      전화번호 → 가린 아이디 (kbm****08)
  비밀번호 재설정:  ① 아이디 + 전화번호 (또는 얼굴)로 본인 확인 → ② 새 비밀번호 두 번 → 02-B 로그인으로
본인 확인을 5번 틀리면 잠기고 직원을 부르게 한다. 재설정은 감사 로그에 남는다(개인정보 없이 회원 번호만).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from domain.customers import (
    find_login_id, login_with_face, reset_member_password, verify_identity,
)
from face import FaceError
from gui import theme
from gui.screens.login import info_box, nav_bar
from gui.widgets import FixedWidthCard, Card, TouchKeyboard, button, label, message_label, phone_field, text_field


class FindAccountScreen(QWidget):
    def __init__(self, router):
        super().__init__()
        self.router = router
        self.customer = None          # 본인 확인을 마친 회원 (②단계)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 24, 40, 20)
        layout.setSpacing(14)
        head = QHBoxLayout()
        self.title = label("", 32, title=True)
        head.addWidget(self.title)
        head.addStretch()
        head.addWidget(label("회원 로그인 · 도움", 16, muted=True))
        layout.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(20)
        left_card = Card()
        left = QVBoxLayout(left_card)
        left.setContentsMargins(24, 20, 24, 20)
        left.setSpacing(10)
        tabs = QHBoxLayout()
        self.id_tab = button("아이디 찾기", "outline", lambda: self.set_mode("id"))
        self.pw_tab = button("비밀번호 재설정", "outline", lambda: self.set_mode("password"))
        tabs.addWidget(self.id_tab)
        tabs.addWidget(self.pw_tab)
        left.addLayout(tabs)
        self.login_id = text_field("회원 ID")
        self.phone = phone_field("가입한 전화번호 (숫자만 치면 010-0000-0000 모양으로)")
        self.new_password = text_field("새 비밀번호 (4자 이상)", password=True)
        self.confirm = text_field("새 비밀번호 다시", password=True)
        for field in (self.login_id, self.phone, self.new_password, self.confirm):
            left.addWidget(field)
        self.keyboard = TouchKeyboard()
        self.keyboard.attach(self.login_id, self.phone, self.new_password, self.confirm)
        left.addWidget(self.keyboard)
        left.addStretch(1)
        body.addWidget(left_card, 1)

        right_card = FixedWidthCard(470)
        right = QVBoxLayout(right_card)
        right.setContentsMargins(22, 20, 22, 20)
        right.setSpacing(12)
        self.help_box, self.help_text = info_box("안내", "")
        right.addWidget(self.help_box)
        self.result_box, self.result_text = info_box("결과", "")
        self.result_box.setStyleSheet(f"background: {theme.WARN_BG}; border-radius: 16px;")
        right.addWidget(self.result_box)
        self.message = message_label()
        right.addWidget(self.message)
        right.addStretch(1)
        self.find_button = button("아이디 찾기", "primary", self.find_id)
        self.verify_button = button("전화번호로 본인 확인", "primary", self.verify_phone)
        self.face_button = button("얼굴로 본인 확인", "outline", self.verify_face)
        self.save_button = button("새 비밀번호 저장", "primary", self.save_password)
        self.to_login_button = button("로그인하러 가기", "outline", self.go_login)
        for widget in (self.find_button, self.verify_button, self.face_button, self.save_button,
                       self.to_login_button):
            right.addWidget(widget)
        body.addWidget(right_card)
        layout.addLayout(body, 1)
        layout.addLayout(nav_bar(router, self.go_back))
        self.set_mode("id")

    def vault(self):
        return self.router.session.vault

    def on_show(self, mode="id", login_id=""):
        for field in (self.login_id, self.phone, self.new_password, self.confirm):
            field.clear()
        self.login_id.setText(login_id)
        self.set_mode(mode)

    def set_mode(self, mode, step=1):
        """mode: 'id' 아이디 찾기 / 'password' 비밀번호 재설정. step 2 = 본인 확인 끝, 새 비밀번호 입력."""
        self.mode, self.step = mode, step
        if step == 1:
            self.customer = None
        finding = mode == "id"
        setting = mode == "password" and step == 2
        self.title.setText("아이디 찾기" if finding else "비밀번호 재설정")
        self.id_tab.setProperty("kind", "primary" if finding else "outline")
        self.pw_tab.setProperty("kind", "outline" if finding else "primary")
        for tab in (self.id_tab, self.pw_tab):
            tab.style().unpolish(tab)
            tab.style().polish(tab)
        self.login_id.setVisible(mode == "password" and not setting)
        self.phone.setVisible(not setting)
        self.new_password.setVisible(setting)
        self.confirm.setVisible(setting)
        self.find_button.setVisible(finding)
        self.verify_button.setVisible(mode == "password" and not setting)
        self.face_button.setVisible(mode == "password" and not setting)
        self.save_button.setVisible(setting)
        self.to_login_button.setVisible(True)
        self.result_box.setVisible(False)
        self.message.setText("")
        if finding:
            self.help_text.setText("가입할 때 쓴 전화번호를 넣으면 아이디 일부를 보여 드려요.\n"
                                   "예) kbm****08")
            self.keyboard.target = self.phone
        elif setting:
            self.help_text.setText("본인 확인이 끝났어요. 새 비밀번호를 두 번 넣어 주세요.\n"
                                   "얼굴 로그인 잠금도 함께 풀려요.")
            self.keyboard.target = self.new_password
        else:
            self.help_text.setText("비밀번호는 저장하지 않아서 알려 드릴 수 없어요. 대신 새로 정해요.\n"
                                   "아이디 + 가입 전화번호, 또는 얼굴로 본인 확인을 해 주세요.\n"
                                   "5번 틀리면 잠겨요.")
            self.keyboard.target = self.login_id if not self.login_id.text() else self.phone

    def show_result(self, text):
        self.result_text.setText(text)
        self.result_box.setVisible(True)
        self.message.setText("")

    def find_id(self):
        try:
            masked = find_login_id(self.vault(), self.phone.text())
        except ValueError as error:
            self.message.setText(str(error))
            return
        self.show_result(f"회원 ID: {masked}\n가린 부분이 기억나지 않으면 직원을 불러 주세요.")

    def verify_phone(self):
        try:
            customer = verify_identity(self.vault(), self.login_id.text(), self.phone.text())
        except ValueError as error:
            self.message.setText(str(error))
            return
        self.passed(customer, "전화번호")

    def verify_face(self):
        login_id = self.login_id.text().strip()
        if not login_id:
            self.message.setText("회원 ID를 먼저 입력해 주세요")
            return
        self.message.setText("카메라를 켜는 중이에요…")
        self.repaint()
        try:
            customer = self.router.run_face(
                lambda provider: login_with_face(self.vault(), login_id, provider, lambda text: None))
        except (FaceError, ValueError) as error:
            self.message.setText(f"{error}\n전화번호로 본인 확인을 해 주세요.")
            return
        self.passed(customer, "얼굴")

    def passed(self, customer, how):
        self.set_mode("password", step=2)
        self.customer = customer
        self.router.audit("member_identity_checked", f"{customer['id']} {how}")

    def save_password(self):
        if self.customer is None:
            self.set_mode("password")
            return
        try:
            reset_member_password(self.vault(), self.customer["id"], self.new_password.text(), self.confirm.text())
        except ValueError as error:
            self.message.setText(str(error))
            self.new_password.clear()
            self.confirm.clear()
            return
        self.router.audit("member_password_reset", self.customer["id"])
        login_id = self.customer["extra"]["login_id"]
        self.customer = None
        self.router.show_screen("login", mode="password", message="새 비밀번호로 로그인해 주세요",
                                keep_id=True, login_id=login_id)

    def go_login(self):
        self.router.show_screen("login", mode="password")

    def go_back(self):
        if self.mode == "password" and self.step == 2:
            self.set_mode("password")
        else:
            self.go_login()
