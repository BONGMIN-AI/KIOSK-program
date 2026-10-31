"""디자인 기준 표와 데이터 연결 전 예시 이벤트."""

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette

ASSETS = Path(__file__).parent / "assets"
BROWN = "#3C1B03"
CARAMEL = "#B66B2E"
CARAMEL_LIGHT = "#F1DFCB"
BG = "#F7EEE3"
CARD = "#FFFFFF"
TEXT2 = "#7A6252"
LINE = "#E6D6C4"
EVENT_THEMES = {
    "basic": ("#F1DFCB", "#3C1B03"),
    "season": ("#FBE3D0", "#B5561B"),
    "festival": ("#FFF0B3", "#B4236B"),
}
TITLE_FONT = "Noto Serif KR"
BODY_FONT = "Noto Sans KR"
FALLBACK_FONT = "Malgun Gothic"
TITLE_SIZE = 36
MENU_SIZE = 28
BUTTON_SIZE = 20
BODY_SIZE = 17
SMALL_SIZE = 13
CARD_RADIUS = 24
BUTTON_RADIUS = 16
CHIP_RADIUS = 28
BUTTON_HEIGHT = 56
EVENT_HEIGHT = 56  # 대기 그림의 손가락 아이콘을 가리지 않는 높이
FROM_POLICY = "from_policy"   # 이벤트를 운영자 정책(settings)에서 읽으라는 표시
EXAMPLE_EVENT = {
    "name": "가을 더블 포인트",
    "theme": "season",
    "message": "회원은 커피 3% 적립 + 1만원 이상 200P · 10/31까지",
}
CREAM = "#FBF5EE"   # 사진 자리·장바구니 줄 바탕
WARN_BG = "#FBE3D0"   # 실패·알레르기 안내 상자
ERROR = "#B4236B"     # 오류 문구
DISABLED_BG = "#E6D6C4"
DISABLED_TEXT = "#7A6252"
LOGO_PLATE = "transparent"   # 고대비에서는 갈색 로고가 보이도록 밝은 받침을 깐다
ACCENT = "#D4573C"   # 10/29 디자인 템플릿의 코랄: 담기 · + · 주문 버튼
SCALE = 1.0           # 큰 글자면 1.25
LARGE_SCALE = 1.25
# 고대비: 검은 바탕에 흰 글자, 강조와 누르는 버튼은 노랑 (손님 한 명에게만 적용, 대기 화면으로 가면 기본으로)
PALETTES = {
    "basic": {"BROWN": "#3C1B03", "CARAMEL": "#B66B2E", "CARAMEL_LIGHT": "#F1DFCB", "BG": "#F7EEE3",
              "CARD": "#FFFFFF", "TEXT2": "#7A6252", "LINE": "#E6D6C4", "CREAM": "#FBF5EE",
              "WARN_BG": "#FBE3D0", "ERROR": "#B4236B", "DISABLED_BG": "#E6D6C4",
              "DISABLED_TEXT": "#7A6252", "LOGO_PLATE": "transparent", "ACCENT": "#D4573C"},
    "contrast": {"BROWN": "#FFE45C", "CARAMEL": "#FFE45C", "CARAMEL_LIGHT": "#3A3300", "BG": "#000000",
                 "CARD": "#111111", "TEXT2": "#FFFFFF", "LINE": "#FFFFFF", "CREAM": "#1E1E1E",
                 "WARN_BG": "#4A1E00", "ERROR": "#FF9C9C", "DISABLED_BG": "#333333",
                 "DISABLED_TEXT": "#BBBBBB", "LOGO_PLATE": "#F7EEE3", "ACCENT": "#FFE45C"},
}
_loaded_families = set()


def set_display(contrast=False, large=False):
    """고대비·큰 글자 설정을 바꾼다. 화면은 새로 만들어야 반영된다 (KioskWindow.build_screens)."""
    global SCALE
    globals().update(PALETTES["contrast" if contrast else "basic"])
    SCALE = LARGE_SCALE if large else 1.0


def won(amount):
    """12000 -> '12,000원'"""
    return f"{amount:,}원"


GLYPH_FALLBACKS = ["Malgun Gothic", "Microsoft YaHei", "Segoe UI Symbol"]


def load_fonts():
    """동봉된 글꼴만 등록하고 없으면 맑은 고딕을 쓴다. 글꼴 파일이 커서 한 번만 등록한다."""
    if _loaded_families:
        return
    for path in sorted((ASSETS / "fonts").glob("*")):
        if path.suffix.lower() in (".ttf", ".otf"):
            font_id = QFontDatabase.addApplicationFont(str(path))
            _loaded_families.update(QFontDatabase.applicationFontFamilies(font_id))


def font(size=BODY_SIZE, title=False, bold=False):
    name = TITLE_FONT if title else BODY_FONT
    if name not in _loaded_families:
        name = FALLBACK_FONT
    result = QFont(name)
    # 동봉 글꼴에 없는 글자(중국어 간체·기호)는 Windows 글꼴로 이어 그린다 (없으면 네모로 보였다, 10/31 점검)
    result.setFamilies([name, *GLYPH_FALLBACKS])
    result.setPixelSize(round(size * SCALE))
    result.setBold(bold or title)
    return result


def palette():
    """글상자·표·스크롤 칸처럼 스타일시트가 닿지 않는 바탕색도 지금 색 구성(기본·고대비)에 맞춘다."""
    result = QPalette()
    roles = QPalette.ColorRole
    for role, color in ((roles.Window, BG), (roles.Base, CARD), (roles.AlternateBase, CREAM),
                        (roles.WindowText, BROWN), (roles.Text, BROWN), (roles.ButtonText, BROWN),
                        (roles.Button, CARD), (roles.PlaceholderText, TEXT2),
                        (roles.Highlight, CARAMEL), (roles.HighlightedText, CARD)):
        result.setColor(role, QColor(color))
    return result


def stylesheet():
    return f"""
        QWidget {{ color: {BROWN}; }}
        QStackedWidget {{ background: {BG}; }}
        QLabel, QCheckBox, QRadioButton, QLineEdit {{ color: {BROWN}; }}
        QLabel {{ background: transparent; }}
        QPushButton {{ padding: 0 20px; border-radius: {BUTTON_RADIUS}px;
                       border: 1px solid {LINE}; }}
        QPushButton:focus {{ border: 3px solid {CARAMEL}; }}
        QPushButton:pressed {{ padding-top: 2px; }}
        QPushButton[kind="primary"] {{ background: {BROWN}; color: {CARD}; }}
        QPushButton[kind="secondary"] {{ background: {CARAMEL}; color: {CARD}; }}
        QPushButton[kind="outline"], QPushButton[kind="chip"] {{
            background: {CARD}; color: {TEXT2}; }}
        QPushButton[kind="chip"] {{ border-radius: {CHIP_RADIUS}px; padding: 0 16px; }}
        QPushButton[kind="chip"]:checked {{ background: {BROWN}; color: {CARD}; }}
        QFrame[card="true"] {{ background: {CARD}; border-radius: {CARD_RADIUS}px; }}
        QFrame[card="selected"] {{ background: {CARD}; border-radius: {CARD_RADIUS}px;
                                   border: 2px solid {CARAMEL}; }}
        QPushButton[kind="category"] {{ background: transparent; border: 2px solid transparent;
                                        color: {TEXT2}; padding: 4px; }}
        QPushButton[kind="category"]:checked {{ background: {CARAMEL_LIGHT};
                                                border: 2px solid {CARAMEL}; color: {BROWN}; }}
        QPushButton[kind="option"] {{ background: {CARD}; color: {TEXT2}; }}
        QPushButton[kind="option"]:checked {{ background: {CARAMEL_LIGHT};
                                              border: 2px solid {CARAMEL}; color: {BROWN}; }}
        QPushButton[kind="plus"] {{ background: {ACCENT}; color: {CARD}; border: none;
                                    padding: 0; border-radius: 12px; }}
        QPushButton[kind="accent"] {{ background: {ACCENT}; color: {CARD}; border: none;
                                      border-radius: 28px; }}
        QPushButton[kind="pill"] {{ background: {CARD}; color: {TEXT2}; border-radius: 22px; padding: 0 14px; }}
        QPushButton[kind="pill"]:checked {{ background: {CARAMEL_LIGHT}; border: 2px solid {BROWN};
                                            color: {BROWN}; }}
        QPushButton:disabled {{ background: {DISABLED_BG}; color: {DISABLED_TEXT}; border: none; }}
        QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
        QScrollArea > QWidget > QFrame[card="true"] {{ background: {CARD}; border-radius: {CARD_RADIUS}px; }}
    """
