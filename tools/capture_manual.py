"""사용 설명서·최종 보고서에 넣을 화면 그림을 만든다 (시연 데이터 · 카메라 없이).

사용: python tools/capture_manual.py      → docs/release/images/*.jpg (1440×900 화면을 1200px 너비로 줄여 저장)
"""
import copy
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KIOSK_CARD_PORT", "off")      # 꽂혀 있는 아두이노 카드 리더는 열지 않는다
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton

from core.storage import MemoryVault
from face import FakeFace
from gui.main import KioskWindow, demo_vault

OUT = ROOT / "docs" / "release" / "images"


def shots(make_window):
    """(파일 이름, 화면 만들기) 목록. 화면마다 새 창을 써서 앞 화면의 상태가 섞이지 않게 한다."""

    def guest_menu(w):
        w.router.open_action("guest")

    def option(w):
        guest_menu(w)
        menu = w.router.screens["menu"]
        menu.show_category("커피")
        menu.open_option("M003")

    def cart(w):
        guest_menu(w)
        w.router.session.add("M003", {"temperature": "HOT", "size": "L", "extras": []}, 2)
        w.router.session.add("M041", None, 1)
        w.router.show_screen("cart")

    def cash(w):
        cart(w)
        w.router.show_screen("cash")
        w.router.screens["cash"].insert(10000)

    def done(w):
        cart(w)
        w.router.session.insert(20000)
        w.router.session.pay()
        w.router.show_screen("done")

    def login(w):
        w.router.open_action("member")
        w.router.screens["login"].login_id.setText("bomin")

    def password(w):
        login(w)
        w.router.screens["login"].set_mode("password")

    def member(w):
        s = w.router.session
        bomin = next(c for c in s.vault.read("customers").values() if c["extra"]["login_id"] == "bomin")
        s.login(bomin)
        s.add("M001", {"temperature": "ICE", "size": "L", "extras": []}, 2)
        s.add("M044", None, 1)
        s.insert(20000)
        s.pay()
        s.toggle_like("M012")
        s.toggle_like("M006")
        w.router.start_member_order(s.customer)
        return w.router.screens["menu"]

    def my_menu_bottom(w):
        menu = member(w)
        menu.change_limit(unit="잔")
        bar = menu.grid_area.verticalScrollBar()
        bar.setValue(bar.maximum())

    def caffeine_settings(w):
        my_menu_bottom(w)
        w.router.screens["menu"].gear_button.click()

    def popular(w):
        member(w).show_category("인기")

    def ticket(w):
        guest_menu(w)
        w.router.screens["menu"].show_category("승차권")

    def ticket_seats(w):
        member(w)
        menu = w.router.screens["menu"]
        menu.show_category("승차권")
        panel = menu.ticket_panel
        panel.open_route()
        panel.dest_field.setText("대전복합")
        panel.day_buttons[1].setChecked(True)
        panel.search()
        next(b for b in panel.time_buttons if b.isEnabled() and b.bus["grade"] == "우등").setChecked(True)
        panel.open_seats()
        panel.toggle_seat(next(s for s, b in panel.seat_buttons.items() if b.isEnabled()), True)

    def signup(w):
        w.router.open_action("signup")

    def admin(w):
        w.router.admin_id = "admin"
        w.router.show_screen("admin", tab="menu")

    def admin_login(w):
        w.router.open_action("admin")

    return [
        ("00_대기화면", lambda w: w.router.show_screen("idle")),
        ("01_시작화면", lambda w: w.router.show_screen("home")),
        ("02_회원로그인", login),
        ("02_비밀번호로그인", password),
        ("03_비회원메뉴", guest_menu),
        ("04_옵션선택", option),
        ("05_장바구니", cart),
        ("07_현금결제", cash),
        ("08_주문완료", done),
        ("10_회원가입", signup),
        ("03_MyMenu", member),
        ("03_MyMenu_카페인리포트", my_menu_bottom),
        ("03_카페인알리미_설정", caffeine_settings),
        ("03_인기탭", popular),
        ("T1_승차권탭", ticket),
        ("T1_좌석고르기", ticket_seats),
        ("09_운영자로그인", admin_login),
        ("09_운영자화면", admin),
    ]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    app = QApplication(sys.argv[:1])
    OUT.mkdir(parents=True, exist_ok=True)
    template = demo_vault()

    def make_window():
        vault = MemoryVault()
        vault._store = copy.deepcopy(template._store)
        window = KioskWindow(vault=vault, face_factory=lambda v: FakeFace())
        window.resize(1440, 900)
        window.show()
        return window

    for name, setup in shots(make_window):
        window = make_window()
        setup(window)
        for _ in range(10):
            QTest.qWait(30)
        picture = window.grab().scaledToWidth(1200, Qt.TransformationMode.SmoothTransformation)
        picture.save(str(OUT / f"{name}.jpg"), "JPG", 82)
        window.close()
        window.deleteLater()
        app.processEvents()
        print("저장", name)


if __name__ == "__main__":
    main()
