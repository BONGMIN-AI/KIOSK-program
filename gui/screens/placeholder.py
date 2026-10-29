"""다음 작업에서 연결할 화면의 공통 안내."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from gui import theme
from gui.widgets import button, label


class PlaceholderScreen(QWidget):
    def __init__(self, router):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(80, 80, 80, 80)
        layout.addStretch()
        text = label("준비 중입니다", theme.TITLE_SIZE, title=True)
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text)
        layout.addStretch()
        self.back_button = button("← 처음으로", "outline",
                                  lambda: router.show_screen("idle"))
        layout.addWidget(self.back_button)
