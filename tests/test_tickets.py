"""승차권 탭(T1): 한글 키보드 · 시간표·좌석·요금 · 예매표 출력 · 음료와 같은 장바구니·결제 · 화면 연결."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from datetime import date, datetime, timedelta

import pytest

from domain import hangul, tickets
from domain.orders import complete_order
from domain.tickets import TicketOffice

NOW = datetime(2026, 10, 29, 17, 0)
TOMORROW = date(2026, 10, 30)


# ---------------------------------------------------------------- 한글 키보드
def type_all(keys, text=""):
    for key in keys:
        text = hangul.type_jamo(text, key)
    return text


def test_hangul_typing_builds_syllables():
    assert type_all("ㄱㅣㅁㅂㅗㅁㅣㄴ") == "김보민"
    assert type_all("ㄷㅐㅈㅓㄴ") == "대전"
    assert type_all("ㄱㅣㅁㅏ") == "기마"            # 받침이 다음 글자로 넘어감
    assert type_all("ㄷㅏㄹㄱㅏ") == "달가"          # 겹받침은 뒤 자음만 넘어감
    assert type_all("ㄱㅗㅏ") == "과"
    assert hangul.erase("김") == "기"
    assert hangul.erase("기") == "ㄱ"
    assert hangul.erase("ㄱ") == ""


def test_destination_search_by_initials_and_unfinished_syllable():
    assert tickets.search_destinations("ㄷㅈ") == ["대전복합", "대전청사", "대전도룡"]
    assert tickets.search_destinations("댖") == ["대전복합", "대전청사", "대전도룡"]   # 대 + ㅈ 조합 중
    assert tickets.search_destinations("부산") == ["부산"]
    assert tickets.search_destinations("ㅋ") == []
    assert len(tickets.search_destinations("")) == len(tickets.DESTINATIONS)


# ---------------------------------------------------------------- 좌석·요금
def test_seat_layouts_match_wireframe():
    assert len(tickets.all_seats("우등")) == 28
    assert len(tickets.all_seats("일반")) == 45
    assert tickets.seat_rows("우등")[0] == [1, 2, None, None, 3]
    assert tickets.seat_rows("우등")[-1] == [25, 26, 27, None, 28]
    assert tickets.seat_rows("일반")[0] == [1, 2, None, 3, 4]
    assert tickets.seat_rows("일반")[-1] == [41, 42, 43, 44, 45]


def test_fares_take_the_bigger_discount_and_cut_below_100():
    assert tickets.fare(13700) == 13700
    assert tickets.fare(13700, "중고생") == 10900
    assert tickets.fare(13700, "초등생") == 6800
    assert tickets.fare(13700, "어른", "경로") == 9500
    assert tickets.fare(13700, "초등생", "군인") == 6800      # 학생 할인과 겹치지 않음
    with pytest.raises(ValueError):
        tickets.fare(13700, "어른", "VIP")


def test_passengers_follow_seat_order_adults_first():
    passengers = tickets.assign_passengers({"어른": 1, "초등생": 1}, [8, 7])
    assert [(p["seat"], p["type"]) for p in passengers] == [(7, "어른"), (8, "초등생")]
    passengers[1]["benefit"] = "장애인"
    priced, total = tickets.quote(13700, passengers)
    assert [p["price"] for p in priced] == [13700, 6800] and total == 20500
    with pytest.raises(ValueError):
        tickets.assign_passengers({"어른": 2}, [7])


# ---------------------------------------------------------------- 시간표
def test_timetable_marks_closed_and_hides_departed():
    office = TicketOffice(NOW)
    buses = office.timetable("대전복합", NOW.date(), NOW + timedelta(minutes=55))
    assert all(datetime.fromisoformat(b["depart"]) >= NOW + timedelta(minutes=55) for b in buses)
    first = buses[0]
    assert first["depart"].endswith("18:00") and first["status"] == "closed"    # 5분 뒤 출발 = 마감
    assert office.timetable("대전복합", NOW.date(), NOW) == office.timetable("대전복합", NOW.date(), NOW)
    assert {b["grade"] for b in buses} == {"우등", "일반"}
    with pytest.raises(ValueError):
        office.timetable("평양", NOW.date(), NOW)


def open_bus(office, now=NOW, day=TOMORROW, destination="대전복합"):
    return next(b for b in office.timetable(destination, day, now) if b["status"] == "ok")


def free_seats(office, bus, count, now=NOW):
    taken = office.taken(bus["id"], now)
    return [s for s in tickets.all_seats(bus["grade"]) if s not in taken][:count]


# ---------------------------------------------------------------- 좌석 잡아 두기
def test_hold_blocks_seats_for_five_minutes_then_releases():
    office = TicketOffice(NOW)
    bus = open_bus(office)
    seats = free_seats(office, bus, 2)
    hold = office.hold(bus["id"], seats, NOW)
    with pytest.raises(ValueError, match="방금 팔렸어요"):
        office.hold(bus["id"], seats[:1], NOW + timedelta(minutes=1))
    assert office.hold_seconds(hold, NOW + timedelta(minutes=1)) == 240
    later = NOW + timedelta(seconds=tickets.HOLD_SECONDS + 1)
    assert office.hold_seconds(hold, later) == 0
    assert not set(seats) & office.taken(bus["id"], later)          # 5분이 지나면 풀림
    with pytest.raises(ValueError, match="5분이 지났어요"):
        office.confirm(hold, later)


def test_confirm_sells_seats_and_closed_bus_cannot_be_held():
    office = TicketOffice(NOW)
    bus = open_bus(office)
    seats = free_seats(office, bus, 1)
    hold = office.hold(bus["id"], seats, NOW)
    office.confirm(hold, NOW + timedelta(minutes=2))
    assert set(seats) <= office.taken(bus["id"], NOW + timedelta(hours=1))
    closing = datetime.fromisoformat(bus["depart"]) - timedelta(minutes=5)
    with pytest.raises(ValueError, match="마감"):
        office.hold(bus["id"], free_seats(office, bus, 1, closing), closing)


# ---------------------------------------------------------------- 예매표 출력
def test_lookup_by_name_or_number_and_print_once():
    office = TicketOffice(NOW)
    found = office.lookup(name="홍길동", birth="900101", now=NOW)
    assert [r["number"] for r in found] == ["12345678", "23456789"]
    assert office.lookup(number="1234-5678", now=NOW)[0]["seats"] == [7, 8]
    office.print_reservations(["12345678"], NOW)
    with pytest.raises(ValueError, match="이미 출력한 표"):
        office.lookup(number="12345678", now=NOW)
    assert [r["number"] for r in office.lookup(name="홍길동", birth="900101", now=NOW)] == ["23456789"]


def test_lookup_explains_why_nothing_can_be_printed():
    office = TicketOffice(NOW)
    with pytest.raises(ValueError, match="조회된 예매가 없어요"):
        office.lookup(name="없는사람", birth="000101", now=NOW)
    with pytest.raises(ValueError, match="6자리"):
        office.lookup(name="홍길동", birth="9001", now=NOW)
    with pytest.raises(ValueError, match="출발 시간이 지났어요"):
        office.lookup(number="45678901", now=NOW)
    with pytest.raises(ValueError, match="이미 출력한 표예요 · 출발 시간이 지났어요"):
        office.lookup(name="김공학", birth="010315", now=NOW)
    soon = office.reservations["12345678"]
    near = datetime.fromisoformat(soon["depart"]) - timedelta(minutes=5)
    with pytest.raises(ValueError, match="출발 시간이 지났어요"):
        office.lookup(number="12345678", now=near)                    # 출발 10분 전부터는 출력 마감


# ---------------------------------------------------------------- 음료와 같은 결제
@pytest.fixture
def vault():
    from gui.main import demo_vault
    return demo_vault()


def ticket_item(office, count=1):
    now = datetime.now()                                    # 장바구니·결제는 지금 시각으로 잡아 둔다
    bus = open_bus(office, now, date.today() + timedelta(days=2))
    seats = free_seats(office, bus, count, now)
    hold = office.hold(bus["id"], seats)
    passengers = tickets.assign_passengers({"어른": count}, seats)
    return office.make_item(bus, passengers, hold)


def test_order_adds_tickets_without_discount_or_points(vault):
    office = TicketOffice()
    item = ticket_item(office)
    item.pop("hold_id")
    menu = vault.read("menu")
    drink = menu["M001"]["price"] * 2                         # 6,000원: 500원 쿠폰(5천 이상)만 맞음
    before = complete_order(vault, {"M001": 2}, 100000, customer_id="C0001")
    with_ticket = complete_order(vault, {"M001": 2}, 100000, customer_id="C0001", coupon_id="WELCOME2",
                                 tickets=[item])
    assert with_ticket["final_total"] == drink - 500 + item["total"]
    assert with_ticket["total"] == drink + item["total"] and with_ticket["ticket_total"] == item["total"]
    assert with_ticket["earned_points"] <= before["earned_points"]   # 적립은 음료 금액으로만 (승차권은 더 안 쌓임)
    assert vault.read("orders")[with_ticket["id"]]["tickets"][0]["destination"] == item["destination"]
    with pytest.raises(ValueError, match="10,000원 이상"):          # 승차권 금액으로 쿠폰 조건을 채울 수 없다
        complete_order(vault, {"M001": 2}, 100000, customer_id="C0001", coupon_id="WELCOME1", tickets=[item])
    with pytest.raises(ValueError, match="부족"):
        complete_order(vault, {"M001": 2}, drink, tickets=[item])


def test_ticket_only_order_and_travel_record_for_consenting_member(vault):
    office = TicketOffice()
    item = ticket_item(office, 2)
    item.pop("hold_id")
    order = complete_order(vault, {}, item["total"], customer_id="C0002", tickets=[item])
    assert order["lines"] == [] and order["final_total"] == item["total"] and order["change"] == 0
    assert "trips" not in vault.read("customers")["C0002"]["extra"]          # 동의 안 한 회원은 기록 없음
    customers = vault.read("customers")
    customers["C0002"]["extra"]["travel_consent"] = True
    vault.write("customers", customers)
    complete_order(vault, {}, item["total"], customer_id="C0002", tickets=[item])
    trips = vault.read("customers")["C0002"]["extra"]["trips"]
    assert trips[0]["destination"] == item["destination"] and trips[0]["count"] == 2
    with pytest.raises(ValueError, match="비어"):
        complete_order(vault, {}, 0)


def test_session_keeps_ticket_out_of_coupon_and_points(vault):
    from gui.order import OrderSession
    session = OrderSession(vault)
    session.login(vault.read("customers")["C0001"])
    session.add("M001", None, 2)
    item = ticket_item(session.office)
    session.add_ticket(item)
    drink = session.drink_total()
    assert session.total() == drink + item["total"] and session.count() == 3
    with pytest.raises(ValueError, match="10,000원 이상"):
        session.set_benefit("WELCOME1", 0)
    session.set_benefit("WELCOME2", 0)
    assert session.final_total() == drink - 500 + item["total"]
    assert session.max_points() <= drink
    session.insert(50000)
    order = session.pay()
    assert order["tickets"][0]["count"] == 1 and session.tickets == []
    seats = {p["seat"] for p in item["passengers"]}
    assert seats <= session.office.taken(item["bus_id"])
    assert not session.office.holds


def test_session_refuses_expired_seat_hold_and_reset_releases(vault):
    from gui.order import OrderSession
    session = OrderSession(vault)
    item = ticket_item(session.office)
    session.add_ticket(item)
    session.office.holds[item["hold_id"]]["until"] = datetime.now() - timedelta(seconds=1)
    session.insert(item["total"])
    with pytest.raises(ValueError, match="5분이 지났어요"):
        session.pay()
    assert session.expire_tickets() == [item] and session.tickets == []
    session.add_ticket(ticket_item(session.office))
    session.reset()
    assert session.tickets == [] and not session.office.holds


# ---------------------------------------------------------------- 화면
pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app):
    from face import FakeFace
    from gui.main import KioskWindow, demo_vault
    result = KioskWindow(vault=demo_vault(), face_factory=lambda v: FakeFace())
    result.show()
    app.processEvents()
    yield result
    result.close()
    result.deleteLater()
    app.processEvents()


def ticket_tab(window):
    router = window.router
    router.open_action("guest")
    menu = router.screens["menu"]
    tab = next(b for b in menu.category_buttons.buttons() if b.objectName() == "category_승차권")
    tab.click()
    return router, menu, menu.ticket_panel


def buy_to_confirm(panel, keys="ㄷㅐㅈㅓㄴ", seats=1):
    panel.buy_choice.click()
    assert panel.page_name() == "route"
    for key in keys:
        panel.route_keyboard.type(key)
    assert panel.dest_field.text() == "대전"
    panel.dest_field.setText("대전복합")                    # 후보 칩을 누른 것과 같다
    panel.day_buttons[1].click()                           # 내일
    panel.search()
    assert panel.page_name() == "timetable"
    next(b for b in panel.time_buttons if b.isEnabled()).click()
    panel.time_next.click()
    assert panel.page_name() == "seats" and not panel.seat_next.isEnabled()
    if seats > 1:
        panel.change_count("어른", seats - 1)
    free = [b for b in panel.seat_buttons.values() if b.isEnabled()][:seats]
    for item in free:
        item.click()
    assert panel.seat_next.isEnabled()
    panel.seat_next.click()
    assert panel.page_name() == "confirm" and panel.hold_id


def test_ticket_tab_sits_after_my_menu_and_keeps_coffee_first(window):
    router, menu, panel = ticket_tab(window)
    names = [b.objectName() for b in menu.category_buttons.buttons()]
    assert names[:3] == ["category_My Menu", "category_승차권", "category_커피"]
    assert menu.middle_stack.currentWidget() is panel and panel.page_name() == "home"
    menu.show_category("커피")
    assert menu.middle_stack.currentWidget() is menu.grid_area
    router.show_screen("idle")
    router.open_action("guest")
    assert menu.category == "커피"                           # 처음 열리는 탭은 그대로


def test_ticket_tab_hidden_when_store_turns_it_off(window):
    router = window.router
    settings = router.session.vault.read("settings")
    settings["ticket_sales"] = False
    router.session.vault.write("settings", settings)
    router.open_action("guest")
    tab = next(b for b in router.screens["menu"].category_buttons.buttons()
               if b.objectName() == "category_승차권")
    assert not tab.isVisible()


def test_buy_ticket_then_drink_and_pay_together(window):
    router, menu, panel = ticket_tab(window)
    buy_to_confirm(panel, seats=2)
    panel.findChild(type(panel.buy_choice), f"benefit_{panel.passengers[1]['seat']}_경로").click()
    assert panel.passengers[1]["benefit"] == "경로"
    panel.with_drinks_button.click()
    session = router.session
    assert menu.category == "커피" and len(session.tickets) == 1 and panel.page_name() == "home"
    assert len(menu.ticket_lines) == 1 and "좌석 유지" in menu.ticket_lines[0].time_label.text()
    session.add("M001", None, 1)
    menu.refresh()
    menu.check_button.click()
    assert router.current_name == "cart"
    router.screens["cart"].go_pay()
    assert router.current_name == "cash"
    cash = router.screens["cash"]
    cash.insert(50000)
    cash.finish()
    assert router.current_name == "done"
    done = router.screens["done"]
    assert done.ticket_box.isVisibleTo(done) and done.number.isVisibleTo(done)
    texts = [w.text() for w in done.findChildren(type(done.number)) if w.isVisibleTo(done)]
    assert any("잊지 말고 꼭 챙겨 주세요" in t for t in texts)
    assert any("쿠폰·포인트" in t for t in texts)


def test_ticket_only_skips_benefit_for_member(window):
    router = window.router
    member = next(iter(router.session.vault.read("customers").values()))
    router.start_member_order(member)
    menu = router.screens["menu"]
    menu.show_category("승차권")
    buy_to_confirm(menu.ticket_panel)
    menu.ticket_panel.pay_now_button.click()
    assert router.current_name == "cart"
    router.screens["cart"].go_pay()
    assert router.current_name == "cash"                     # 음료가 없으면 06 쿠폰·포인트는 건너뜀
    cash = router.screens["cash"]
    cash.insert(50000)
    cash.finish()
    done = router.screens["done"]
    assert done.ticket_box.isVisibleTo(done) and not done.number.isVisibleTo(done)


def test_going_back_from_confirm_releases_seats(window):
    router, menu, panel = ticket_tab(window)
    buy_to_confirm(panel)
    office = router.session.office
    assert len(office.holds) == 1
    panel.show_seats()
    assert not office.holds and panel.page_name() == "seats"
    panel.reset()
    assert panel.page_name() == "home"


def test_print_reservation_by_name_and_birth(window):
    router, menu, panel = ticket_tab(window)
    panel.print_choice.click()
    for key in "ㅎㅗㅇㄱㅣㄹㄷㅗㅇ":
        panel.lookup_keyboard.type(key)
    assert panel.name_field.text() == "홍길동"
    panel.lookup_keyboard.target = panel.birth_field
    for key in "900101ㄱ":
        panel.lookup_keyboard.type(key)                     # 생년월일 칸에는 숫자만
    assert panel.birth_field.text() == "900101"
    panel.lookup()
    assert panel.page_name() == "result" and len(panel.reservation_buttons) == 2
    panel.reservation_buttons[1].click()                    # 하나만 출력
    assert panel.print_button.text() == "선택한 표 출력 (2매)"
    panel.print_button.click()
    assert panel.printed_box.isVisibleTo(panel) and "출력됐어요" in panel.printed_title.text()
    assert router.session.is_empty()                        # 예매표는 장바구니에 안 담김
    assert router.session.office.reservations["12345678"]["printed"]
    assert not router.session.office.reservations["23456789"]["printed"]


def test_lookup_error_stays_on_lookup(window):
    router, menu, panel = ticket_tab(window)
    panel.print_choice.click()
    panel.set_lookup_mode("number")
    panel.number_field.setText("99999999")
    panel.lookup()
    assert panel.page_name() == "lookup" and "조회된 예매가 없어요" in panel.lookup_message.text()
