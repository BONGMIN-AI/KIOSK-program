"""11/03 시연 네 부분을 화면에서 처음부터 끝까지 (시연 모드 데이터 · 가짜 카메라)."""
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest


@pytest.fixture
def window():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from face import FakeFace
    from gui.main import KioskWindow, demo_vault
    app = QApplication.instance() or QApplication([])
    result = KioskWindow(vault=demo_vault(random_members=True), face_factory=lambda vault: FakeFace())
    result.show()
    app.processEvents()
    yield result
    result.close()
    result.deleteLater()
    app.processEvents()


def start(router, login_id, takeout=False):
    from domain.customers import login_with_password
    router.show_screen("dine")
    router.screens["dine"].choose(takeout)
    router.open_action("member")
    router.start_member_order(login_with_password(router.session.vault, login_id, "1234"))
    router.popup.hide()
    return router.screens["menu"]


@pytest.mark.parametrize("login_id,width", [("bomin", 1200), ("bomin", 1900),
                                          ("withtop77", 1900), ("user01", 1900)])
def test_my_menu_uses_side_by_side_cards_on_first_show(window, login_id, width):
    from PySide6.QtWidgets import QFrame

    window.resize(width, 1050)
    menu = start(window.router, login_id)
    from PySide6.QtWidgets import QApplication
    QApplication.processEvents()
    page = menu.grid_area.widget()
    divider = page.findChild(QFrame, "my_menu_vertical_divider")
    assert divider is not None
    column = divider.parentWidget().layout()          # 맨 위에 얼굴 등록 · 카드 등록 줄이 올 수 있다
    pair = next(column.itemAt(i).layout() for i in range(column.count())
                if column.itemAt(i).layout() is not None and column.itemAt(i).layout().indexOf(divider) >= 0)
    assert pair.itemAt(0).widget().x() < divider.x() < pair.itemAt(2).widget().x()
    assert pair.itemAt(0).widget().y() == pair.itemAt(2).widget().y()


def test_part1_my_menu_route_quick_and_caffeine(window):
    from domain.tickets import ORIGIN
    router = window.router
    menu = start(router, "withtop77")
    assert "[얼죽아] 김휘원 님, 2일 만이에요!" in router.notice.text() and menu.member_name.text().startswith("[얼죽아]")
    menu.open_saved_route(ORIGIN, "대전복합")                      # ★ 저장한 노선 → 바로 시간표
    assert menu.category == "승차권" and menu.ticket_panel.page_name() == "timetable"
    menu.show_category("My Menu")
    menu.quick_button.click()                                       # 최근 주문 다시 담기 (커피 2잔)
    assert menu.confirm_box.isVisible() and "카페인" in menu.confirm_box.title.text()
    menu.confirm_box.yes()
    assert len(router.session.lines()) == 2


def test_reservation_zero_won_and_first_card_tap(window):
    router = window.router
    session = router.session
    menu = start(router, "user12")                                    # 11/04: asd1625는 시연 때 새로 가입
    assert "리더기에 대면 등록" in router.notice.text()
    menu.show_category("승차권")
    panel = menu.ticket_panel
    panel.open_lookup()
    panel.name_field.setText("임예찬")
    panel.phone_field.setText("01020072007")
    panel.lookup()
    panel.print_selected()
    assert session.tickets and session.total() == 0
    router.card_scanned("84E3D273")                                 # 지난번에 받은 카드를 처음 대기
    assert "10% 할인" in router.popup.title.text() + router.popup.text.text()
    session.add("M002", None, 1)
    assert session.benefit()["card_discount"] > 0
    session.insert(10000)
    order = session.pay()
    assert order["card_stamp"]["stamps"] == 2 and order["card_stamp"]["earned"] == 2   # 새 카드 첫 주문은 도장 2개
    assert session.office.reservations[order["tickets"][0]["reservation"]]["printed"]


def test_part3_takeout_smile_change_points_title(window):
    router = window.router
    session = router.session
    start(router, "jisung0642", takeout=True)
    assert "오늘 두 번째 방문이에요!" in router.notice.text()
    session.add("M051", None, 1)                                    # 처음 먹어 보는 메뉴
    router.show_screen("cart")
    router.screens["cart"].try_smile()                              # 웃고 500원
    assert session.smiled
    session.insert(10000)
    session.change_to_points = True
    order = session.pay()
    assert order["takeout"] is True and order["smile_discount"] == 500 and order["change_points"] > 0
    assert "단골손님" in order["new_titles"]


def test_part1_withtop77_birthday_allergy_titles_easter_egg(window):
    """11/04 회의: 생일 · 우유 알레르기 · 숨은 쿠폰은 withtop77(김휘원)이 보여 준다. 인사는 '[칭호] 이름 님'."""
    from domain.customers import login_with_password
    router = window.router
    router.show_screen("dine")
    router.screens["dine"].choose(False)
    router.start_member_order(login_with_password(router.session.vault, "withtop77", "1234"))
    assert router.popup.isVisible() and router.popup.title.text() == "생일 축하해요!"
    assert "[얼죽아] 김휘원 님, 2일 만이에요!" in router.notice.text()
    router.popup.hide()
    menu = router.screens["menu"]
    assert menu.member_name.text() == "[얼죽아] 김휘원 님 ›"
    latte = next(k for k, v in router.session.menu().items() if v["name"] == "카페라떼")
    assert "우유" in router.session.allergy_warning(latte)                  # 알레르기 경고
    menu.member_name.on_tap()
    assert menu.titles_sheet.isVisible()
    menu.titles_sheet.hide()
    for _ in range(5):
        menu.logo_tap()
    assert router.popup.title.text() == "숨은 쿠폰을 찾았어요!"
