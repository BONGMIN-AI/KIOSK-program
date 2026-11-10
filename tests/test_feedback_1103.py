"""11/03 시험 의견 반영: 미소 미션(작은 카드 · 3초 · 성공 팝업 · 계정당 한 번) · 로그인 '함께 할 일' 상태별 ·
My Menu '카드 등록' · 사람이 있으면 최대 120초 · 회원가입 · 쿠폰·포인트 화면 정리."""
import os
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

from domain.customers import login_with_password, set_face_enrolled
from face.presence import FakePresence


@pytest.fixture
def window():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from face import FakeFace
    from gui.main import KioskWindow, demo_vault
    app = QApplication.instance() or QApplication([])
    result = KioskWindow(vault=demo_vault(random_members=True), face_factory=lambda vault: FakeFace(),
                         presence=FakePresence())
    result.router.presence_timer.stop()
    result.show()
    app.processEvents()
    yield result
    result.close()
    result.deleteLater()
    app.processEvents()


def login(router, login_id):
    router.start_member_order(login_with_password(router.session.vault, login_id, "1234"))
    router.popup.hide()


def test_smile_mission_small_card_success_popup_and_once_per_account(window):
    router = window.router
    session = router.session
    login(router, "jisung0642")
    session.add("M051", None, 1)
    router.show_screen("cart")
    cart = router.screens["cart"]
    states = []
    original = cart.smile_mission.update_state
    cart.smile_mission.update_state = lambda *s: states.append(s) or original(*s)
    cart.try_smile()
    assert states[-1][:3] == (True, True, 1.0) and not cart.smile_mission.isVisible()
    assert router.popup.isVisible() and router.popup.title.text() == "미소 미션 성공!"
    session.insert(10000)
    session.pay()
    assert session.customer["extra"].get("smile_used")
    session.add("M051", None, 1)
    router.show_screen("cart")
    assert session.smile_offer() == 0 and not cart.smile_button.isVisible()       # 계정당 한 번


def test_smile_cup_draws_both_faces(window):
    from gui.widgets import SmileCup
    cup = SmileCup(96)
    for state in ((True, True, 0.5), (True, False, 0.0), (False, False, 0.0)):
        cup.set_state(*state)
        cup.grab()                                         # 그리다가 오류가 나지 않는다


def test_login_options_hide_what_member_already_has(window):
    router = window.router
    vault = router.session.vault
    set_face_enrolled(vault, "C0201")
    router.open_action("member")
    page = router.screens["login"]
    page.login_id.setText("withtop77")
    page.set_mode("password")
    assert page.enroll_check.isHidden() and not page.card_check.isHidden()
    page.login_id.setText("user01")                        # 시연 회원카드 사용 중 · 얼굴 없음
    assert not page.enroll_check.isHidden() and page.card_check.isHidden()
    page.login_id.setText("user12")                        # 산 카드 '등록 전'
    assert page.card_check.isHidden()


def test_my_menu_card_register_button(window):
    from PySide6.QtWidgets import QPushButton
    router = window.router
    login(router, "user12")
    menu = router.screens["menu"]
    assert menu.card_register_button.isVisibleTo(window)
    menu.card_register_button.click()
    assert "리더기에 대 주세요" in router.notice.text()
    router.card_scanned("ABCD0001")
    assert "등록 완료" in router.popup.title.text()          # 11/03: 팝업 하나로
    window.repaint()
    from PySide6.QtWidgets import QApplication
    QApplication.processEvents()
    texts = [b.text() for b in menu.findChildren(QPushButton) if b.isVisibleTo(window)]
    assert "카드 등록" not in texts


def test_idle_waits_up_to_120_seconds_when_someone_is_there(window):
    router = window.router
    sensor = router.presence
    router.show_screen("home")
    sensor.distance = 0.6
    router.input_at = time.monotonic() - 50
    router.warn_time_out()                                 # 사람이 있으니 경고를 미룬다
    assert not router.warning_shown and router.warn_timer.isActive()
    assert 50_000 <= router.warn_timer.remainingTime() <= 56_000      # 120 - 15 - 50 = 55초 뒤
    router.input_at = time.monotonic() - 110
    router.warn_time_out()                                 # 최대 시간이 지나면 평소처럼
    assert router.warning_shown
    router.restart_timer()
    sensor.distance = None
    router.warn_time_out()                                 # 아무도 없으면 바로 경고
    assert router.warning_shown


def test_signup_and_benefit_screen_cleanup(window):
    from PySide6.QtWidgets import QPushButton
    router = window.router
    router.open_action("signup")
    assert "무료" not in router.screens["signup"].card_request.text()
    login(router, "bomin")
    router.session.add("M051", None, 2)
    router.show_screen("benefit")
    benefit = router.screens["benefit"]
    assert "혜택 적용 · 금액 갱신" not in [b.text() for b in benefit.findChildren(QPushButton)]
    before = router.session.final_total()
    benefit.points_field.setText("1000")                  # 치는 대로 적용
    assert router.session.final_total() == before - 1000


def test_smile_mission_is_a_checkbox_with_note(window):
    router = window.router
    session = router.session
    login(router, "jisung0642")
    session.add("M051", None, 1)
    router.show_screen("cart")
    cart = router.screens["cart"]
    assert cart.smile_check.text() == "미소 미션" and "웃으면 500원 할인" in cart.smile_note.text()
    cart.smile_check.setChecked(True)                      # 체크 = 미션 시작 (가짜 카메라는 바로 성공)
    assert session.smiled and cart.smile_check.isChecked() and not cart.smile_check.isEnabled()
    assert "적용됨" in cart.smile_note.text()


def test_card_tap_before_dine_choice_asks_dine_first_even_on_home(window):
    from domain.member_cards import purchase_card, register_first_tap
    router = window.router
    vault = router.session.vault
    purchase_card(vault, "C0201", "new", "", 1000)
    register_first_tap(vault, "C0201", "HOME0001")
    router.show_screen("idle")
    router.show_screen("home")                             # 매장 / 포장을 건너뛰고 시작 화면에 있어도
    router.card_scanned("HOME0001")
    assert router.current_name == "dine"                   # 시작 화면에서는 00-B 화면
    router.screens["dine"].choose(True)
    assert router.current_name == "login" and router.session.takeout is True


def test_serial_reader_takes_held_card_once_and_retap_again(window):
    """카드를 받은 직후 3초는 어떤 카드 · '못 읽음'도 넘긴다 · 같은 화면 같은 카드는 6초 · 화면이 바뀌면 3초 뒤 바로."""
    import time as clock
    from gui.serial_card import SerialCardReader
    got, seen, notes = [], [], []
    screen = {"name": "menu"}
    reader = SerialCardReader(lambda: True, screen=lambda: screen["name"])
    reader.scanned.connect(got.append)
    reader.seen.connect(seen.append)
    reader.notice.connect(notes.append)
    reader.deliver("AAAA1111")
    reader.relay.misread.emit()                            # 성공 직후 '못 읽음'이 와도
    reader.deliver("AAAA1111")
    reader.deliver("BBBB2222")                             # 다른 카드도 3초 안에는
    assert got == ["AAAA1111"] and notes == [] and "직후라 넘김" in seen[-1]
    reader.last_at = clock.monotonic() - 4                 # 3초 뒤 같은 화면 같은 카드(대고 있는 중)는 아직 넘김
    reader.deliver("AAAA1111")
    assert got == ["AAAA1111"]
    screen["name"] = "idle"                                # 화면이 바뀌면 같은 카드도 받는다
    reader.deliver("AAAA1111")
    assert got == ["AAAA1111", "AAAA1111"]
    reader.last_at = clock.monotonic() - 7                 # 6초가 지나면 같은 화면이라도 다시
    reader.deliver("AAAA1111")
    assert len(got) == 3
    reader.last_at = clock.monotonic() - 4
    reader.relay.misread.emit()                            # 한참 뒤의 '못 읽음'은 알려 준다
    assert notes and "읽지 못했어요" in notes[-1]


def test_notice_fades_out_and_clears_on_start_screen(window):
    from PySide6.QtTest import QTest
    router = window.router
    router.notify("안내 시험", 1)
    assert router.notice.isVisible()
    for _ in range(60):                                    # 1초 + 천천히 흐려지기 (0.45초) — 바쁠 때는 조금 더
        if not router.notice.isVisible():
            break
        QTest.qWait(100)
    assert not router.notice.isVisible()
    router.show_screen("home")
    router.notify("안내 시험", 6)
    router.show_screen("idle")
    assert not router.notice.isVisible()                   # 처음 화면으로 가면 바로 내린다


def test_likes_are_limited_to_six(window):
    from domain.my_menu import toggle_like
    router = window.router
    vault = router.session.vault
    menu_ids = list(vault.read("menu"))[:7]
    for menu_id in menu_ids[:6]:
        toggle_like(vault, "C0203", menu_id)
    with pytest.raises(ValueError, match="최대 6잔"):
        toggle_like(vault, "C0203", menu_ids[6])
    assert toggle_like(vault, "C0203", menu_ids[0]) is False      # 하나 풀면
    assert toggle_like(vault, "C0203", menu_ids[6]) is True       # 다시 담을 수 있다


def test_done_screen_highlights_new_title_and_stamp_card(window):
    from domain.member_cards import purchase_card, register_first_tap
    router = window.router
    session = router.session
    purchase_card(session.vault, "C0203", "new", "", 1000)
    register_first_tap(session.vault, "C0203", "STAMP777")
    login(router, "jisung0642")
    session.add("M051", None, 1)
    session.insert(10000)
    session.pay()
    router.show_screen("done")
    done = router.screens["done"]
    assert done.title_badge.isVisibleTo(window) and "★ 새 칭호 획득!" in done.title_badge.text()
    assert done.stamp_card.isVisibleTo(window) and done.stamp_card.stamps == 2   # 새 카드 첫 주문은 도장 2개
    assert "2 / 10" in done.stamp_title.text()
    done.stamp_card.grab()


def test_admin_card_table_shows_id_name_title_columns(window):
    from domain.member_cards import purchase_card
    router = window.router
    purchase_card(router.session.vault, "C0203", "new", "", 1000)
    router.admin_id = "admin"
    router.show_screen("admin", tab="cards")
    table = router.screens["admin"].card_table
    headers = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
    assert headers[1:4] == ["아이디", "이름", "칭호"]
    row = next(r for r in range(table.rowCount()) if table.item(r, 1).text() == "jisung0642")
    assert table.item(row, 2).text() == "김지성" and table.item(row, 3).text() == "새내기"


def test_idle_card_tap_greets_by_name(window):
    from domain.member_cards import purchase_card, register_first_tap
    router = window.router
    vault = router.session.vault
    purchase_card(vault, "C0203", "new", "", 1000)
    register_first_tap(vault, "C0203", "NAME0001")
    router.show_screen("idle")
    router.card_scanned("NAME0001")
    assert "김지성 님 카드 확인" in router.notice.text() and "칭호수집가" not in router.notice.text()


def test_dine_choice_slides_in_on_idle_and_fades_away(window):
    from PySide6.QtTest import QTest
    router = window.router
    router.show_screen("idle")
    router.ask_dine()
    choice = router.screens["idle"].dine_choice
    assert router.current_name == "idle" and choice.isVisible()      # 화면은 그대로, 버튼만 떠오른다
    router.ask_dine()                                                # 이미 떠 있으면 그대로
    assert choice.isVisible()
    choice.close_choice()                                            # 아무것도 안 고르면 흐려지며 들어간다
    for _ in range(30):
        if not choice.isVisible():
            break
        QTest.qWait(50)
    assert not choice.isVisible() and router.current_name == "idle"
    router.ask_dine()
    choice.buttons["here"].click()
    assert router.current_name == "home" and router.session.takeout is False
