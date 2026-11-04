"""사용 설명서·최종 보고서에 넣을 화면 그림을 만든다 (시연 데이터 · 카메라 없이).

사용: python tools/capture_manual.py      → docs/release/images/*.jpg (1440×900 화면을 1200px 너비로 줄여 저장)
11/03: 시연 계정 4부분(withtop77 · asd1625 · jisung0642 · bomin) 화면과 매장/포장 · 팝업 · 운영자 화면을 더했다.
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
from PySide6.QtWidgets import QApplication

from core.storage import MemoryVault
from domain.customers import login_with_password
from domain.tickets import ORIGIN
from face import FakeFace
from gui.main import KioskWindow, demo_vault

OUT = ROOT / "docs" / "release" / "images"


def shots():
    """(파일 이름, 화면 만들기) 목록. 화면마다 새 창을 써서 앞 화면의 상태가 섞이지 않게 한다."""

    def member(w, login_id, takeout=False, keep_popup=False, keep_notice=False):
        router = w.router
        router.show_screen("dine")
        router.screens["dine"].choose(takeout)
        router.open_action("member")
        router.start_member_order(login_with_password(router.session.vault, login_id, "1234"))
        if not keep_popup:
            router.popup.hide()
        if not keep_notice:
            router.notice.hide()
        return router.screens["menu"]

    def dine_on_idle(w):
        w.router.show_screen("idle")
        w.router.ask_dine()
        QTest.qWait(600)                               # 떠오르는 움직임이 끝난 뒤

    def guest_menu(w):
        w.router.open_action("guest")

    def option(w):
        guest_menu(w)
        menu = w.router.screens["menu"]
        menu.show_category("커피")
        menu.open_option("M003")

    def allergy(w):
        menu = member(w, "bomin")
        menu.show_category("커피")
        menu.open_option("M002")                     # 카페라떼 · 우유 알레르기
        menu.popup.add_to_cart()                     # 담기 → 04-A 알레르기 주의

    def cart(w):
        menu = member(w, "user12")
        menu.show_category("승차권")
        panel = menu.ticket_panel
        panel.open_lookup()
        panel.name_field.setText("임예찬")
        panel.phone_field.setText("01020072007")
        panel.lookup()
        panel.print_selected()
        w.router.session.add("M003", {"temperature": "ICE", "size": "M", "extras": []}, 1)
        w.router.show_screen("cart")

    def reservation(w):
        menu = member(w, "user12")
        menu.show_category("승차권")
        panel = menu.ticket_panel
        panel.open_lookup()
        panel.name_field.setText("임예찬")
        panel.phone_field.setText("01020072007")
        panel.lookup()

    def card_tap(w):
        member(w, "user12")
        w.router.card_scanned("84E3D273")
        w.router.session.add("M003", {"temperature": "ICE", "size": "M", "extras": []}, 1)
        w.router.screens["menu"].refresh()

    def card_button(w):
        member(w, "user12")

    def smile_mission(w):
        member(w, "jisung0642")
        w.router.session.add("M051", None, 1)
        w.router.show_screen("cart")
        mission = w.router.screens["cart"].smile_mission
        mission.open()
        mission.update_state(True, True, 0.55, "좋아요! 그대로 웃어 주세요")

    def benefit(w):
        card_tap(w)
        w.router.notice.hide()
        w.router.show_screen("benefit")

    def cash(w):
        guest_menu(w)
        w.router.session.add("M003", {"temperature": "HOT", "size": "L", "extras": []}, 2)
        w.router.show_screen("cash")
        w.router.screens["cash"].insert(10000)

    def done(w):
        member(w, "jisung0642", takeout=True)
        session = w.router.session
        session.add("M051", None, 1)
        session.insert(10000)
        session.change_to_points = True
        session.pay()
        w.router.show_screen("done")

    def login(w):
        w.router.open_action("member")
        w.router.screens["login"].login_id.setText("bomin")

    def password(w):
        login(w)
        w.router.screens["login"].set_mode("password")

    def my_menu(w):
        member(w, "withtop77", keep_notice=True)

    def my_menu_bottom(w):
        menu = member(w, "withtop77")
        bar = menu.grid_area.verticalScrollBar()
        bar.setValue(bar.maximum())

    def caffeine_settings(w):
        my_menu_bottom(w)
        w.router.screens["menu"].gear_button.click()

    def caffeine_warning(w):
        member(w, "withtop77").quick_button.click()

    def saved_route(w):
        member(w, "withtop77").open_saved_route(ORIGIN, "대전복합")

    def popular(w):
        member(w, "withtop77").show_category("인기")

    def titles(w):
        member(w, "withtop77").open_titles()

    def birthday(w):
        member(w, "withtop77", keep_popup=True, keep_notice=True)

    def easter_egg(w):
        menu = member(w, "bomin")
        for _ in range(5):
            menu.logo_tap()

    def ticket(w):
        guest_menu(w)
        w.router.screens["menu"].show_category("승차권")

    def ticket_seats(w):
        menu = member(w, "jisung0642")
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

    def admin(tab):
        def setup(w):
            w.router.admin_id = "admin"
            w.router.show_screen("admin", tab=tab)
        return setup

    def admin_login(w):
        w.router.open_action("admin")

    return [
        ("00_대기화면", lambda w: w.router.show_screen("idle")),
        ("00B_매장포장", dine_on_idle),
        ("01_시작화면", lambda w: w.router.show_screen("home")),
        ("02_회원로그인", login),
        ("02_비밀번호로그인", password),
        ("03_비회원메뉴", guest_menu),
        ("04_옵션선택", option),
        ("04_알레르기경고", allergy),
        ("05_장바구니", cart),
        ("05_미소미션", smile_mission),
        ("06_쿠폰포인트", benefit),
        ("07_현금결제", cash),
        ("08_주문완료", done),
        ("10_회원가입", signup),
        ("03_MyMenu", my_menu),
        ("03_MyMenu_카페인리포트", my_menu_bottom),
        ("03_카페인알리미_설정", caffeine_settings),
        ("03_카페인경고", caffeine_warning),
        ("03_인기탭", popular),
        ("03_칭호현황", titles),
        ("03_생일팝업", birthday),
        ("03_이스터에그", easter_egg),
        ("03_카드등록버튼", card_button),
        ("03_회원카드등록", card_tap),
        ("T1_승차권탭", ticket),
        ("T1_저장노선시간표", saved_route),
        ("T1_좌석고르기", ticket_seats),
        ("T1_예매표조회", reservation),
        ("09_운영자로그인", admin_login),
        ("09_운영자화면", admin("sales")),
        ("09_회원카드", admin("cards")),
        ("09_쿠폰", admin("coupons")),
        ("09_혜택설정", admin("perks")),
        ("09_키오스크설정", admin("kiosk")),
    ]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    app = QApplication(sys.argv[:1])
    OUT.mkdir(parents=True, exist_ok=True)
    template = demo_vault(random_members=True)

    def make_window():
        vault = MemoryVault()
        vault._store = copy.deepcopy(template._store)
        window = KioskWindow(vault=vault, face_factory=lambda v: FakeFace())
        window.resize(1440, 900)
        window.show()
        return window

    for name, setup in shots():
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
