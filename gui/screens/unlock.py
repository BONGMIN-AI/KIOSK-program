"""키오스크를 켤 때 운영자가 한 번 금고(암호화 데이터)를 여는 화면. 손님 흐름에는 나오지 않는다."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

import config
from core import auth
from gui import theme
from gui.widgets import Card, button, label


class UnlockScreen(QWidget):
    def __init__(self, router):
        super().__init__()
        self.router = router
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = Card()
        card.setFixedWidth(480)
        column = QVBoxLayout(card)
        column.setContentsMargins(32, 28, 32, 28)
        column.setSpacing(12)
        column.addWidget(label("KIOSK 준비 · 운영자", 26, title=True))
        column.addWidget(label("데이터 금고를 열면 대기 화면이 시작됩니다.", 15, muted=True))
        self.admin_id = QLineEdit("admin")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("관리자 비밀번호")
        self.password.returnPressed.connect(self.open_vault)
        for field in (self.admin_id, self.password):
            field.setFont(theme.font(18))
            field.setMinimumHeight(52)
            field.setStyleSheet(f"background: {theme.CARD}; border: 1px solid {theme.LINE};"
                                " border-radius: 12px; padding: 0 12px;")
            column.addWidget(field)
        self.message = label("", 15)
        self.message.setStyleSheet(f"color: {theme.ERROR};")
        self.message.setWordWrap(True)
        column.addWidget(self.message)
        column.addWidget(button("금고 열기", "primary", self.open_vault))
        outer.addWidget(card)

    def open_vault(self):
        if not config.KEYSTORE_PATH.exists():
            self.message.setText("데이터가 없습니다. 먼저 tools/reset_data.py --yes 로 만드세요.")
            return
        try:
            vault = auth.unlock(config.KEYSTORE_PATH, config.DATA_DIR,
                                self.admin_id.text().strip(), self.password.text())
        except auth.AuthError as error:
            self.message.setText(str(error))
            return
        finally:
            self.password.clear()
        self.router.set_vault(vault)
