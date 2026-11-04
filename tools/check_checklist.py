"""시연 테스트 체크리스트 중 실물(카메라 · 카드 리더 · 얼굴 · 눈으로 보기)이 필요 없는 항목을 직접 해 본다.

사용: python tools/check_checklist.py   → docs/release/checklist_auto.json (항목마다 통과 / 문제 · 이유)
      python tools/build_manual.py      → 체크리스트에 '자동으로 확인한 것'과 '직접 해 볼 것'을 나눠 보여 준다
항목마다 새 창(시연 데이터 · 가짜 카메라 · 가짜 사람 감지)을 써서 앞 항목이 뒤 항목에 섞이지 않게 한다.
"""
import json
import os
import sys
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("KIOSK_CARD_PORT", "off")
os.environ["KIOSK_PRESENCE"] = "off"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from build_manual import KEYS, LEFT_OUT, MANUAL, TESTS
from domain.customers import find_login_id, login_with_password, set_face_enrolled
from domain.member_cards import purchase_card, register_first_tap
from domain.tickets import ORIGIN
from face import FakeFace
from face.presence import FakePresence
from gui.main import KioskWindow, demo_vault

OUT = ROOT / "docs" / "release" / "checklist_auto.json"


class Fail(Exception):
    pass


def need(condition, why):
    if not condition:
        raise Fail(why)


def window():
    result = KioskWindow(vault=demo_vault(random_members=True), face_factory=lambda vault: FakeFace(),
                         presence=FakePresence())
    result.router.presence_timer.stop()
    result.resize(1200, 800)
    result.show()
    QApplication.processEvents()
    return result


def member(w, login_id, takeout=False):
    router = w.router
    router.show_screen("dine")
    router.screens["dine"].choose(takeout)
    router.open_action("member")
    router.start_member_order(login_with_password(router.session.vault, login_id, "1234"))
    router.popup.hide()
    return router.screens["menu"]


def texts(widget, w):
    return " ".join(label.text() for label in widget.findChildren(QLabel) if label.isVisibleTo(w))


def pay(session, cash=20000):
    if cash:
        session.insert(cash)
    return session.pay()


# ---------------------------------------------------------------- 항목마다 해 보기 (키 → 함수)
def idle_touch(w):
    router = w.router
    router.show_screen("idle")
    QTest.mouseClick(router.screens["idle"], Qt.MouseButton.LeftButton, pos=QPoint(600, 400))
    need(router.current_name == "idle" and router.choosing_dine(), f"대기 화면을 눌렀는데 {router.current_name}")
    return "대기 화면 위에 매장 / 포장 버튼이 떠오름 (화면은 그대로)"


def takeout(w):
    router = w.router
    router.show_screen("dine")
    router.screens["dine"].choose(True)
    router.open_action("guest")
    router.session.add("M001", None, 1)
    router.show_screen("cart")
    need(router.screens["cart"].summary_title.text() == "주문 합계 · 포장", "장바구니 제목에 포장 없음")
    pay(router.session)
    router.show_screen("done")
    shown = texts(router.screens["done"], w)
    need("대기 번호 · 포장" in shown and "영수증 · 포장" in shown, "완료 화면 · 영수증에 포장 없음")
    return "장바구니 · 완료 · 영수증 모두 '포장'"


def display_reset(w):
    router = w.router
    router.show_screen("home")
    router.set_display(large=True)
    router.set_display(contrast=True)
    router.language = "English"
    router.show_screen("idle")
    need(router.display == {"contrast": False, "large": False} and router.language == "한국어", "다음 손님에게 그대로 남음")
    return "처음 화면으로 가면 글자 · 색 · 언어가 기본으로"


def away_refund(w):
    router = w.router
    router.open_action("guest")
    router.session.insert(1000)
    router.last_seen = time.monotonic() - 100
    router.check_presence()
    need(router.away_box.isVisible(), "자리 비움 질문이 안 뜸")
    router.away_box.left = 1
    router.away_box.count_down()
    need(router.current_name == "idle" and router.session.inserted == 0, "0초에 처음 화면 · 반환이 안 됨")
    need("1,000원" in router.notice.text(), "반환 안내 없음")
    return "0초 → 처음 화면 · '넣은 현금 1,000원을 반환했어요'"


def login_fail(w):
    router = w.router
    router.open_action("member")
    page = router.screens["login"]
    page.login_id.setText("bomin")
    page.set_mode("password")
    page.password.setText("9999")
    page.password_login()
    need(router.current_name == "login" and router.session.customer is None, "틀린 비밀번호로 로그인됨")
    return "틀린 비밀번호 → 로그인 안 되고 아이디부터 다시"


def no_card_option(w):
    router = w.router
    router.open_action("member")
    page = router.screens["login"]
    page.login_id.setText("user01")
    page.set_mode("password")
    need(page.card_check.isHidden(), "카드가 있는데 '회원카드 신청' 칸이 보임")
    return "user01 (카드 있음) → '회원카드 신청' 칸 없음"


def no_face_option(w):
    router = w.router
    set_face_enrolled(router.session.vault, "C0001")
    router.open_action("member")
    page = router.screens["login"]
    page.login_id.setText("bomin")
    page.set_mode("password")
    need(page.enroll_check.isHidden(), "얼굴이 있는데 '얼굴도 등록할게요' 칸이 보임")
    return "얼굴 등록된 bomin → '얼굴도 등록할게요' 칸 없음"


def find_id(w):
    router = w.router
    router.show_screen("find")
    page = router.screens["find"]
    page.phone.setText("01010000001")
    page.find_id()
    need("bo***" in page.result_text.text(), f"찾은 아이디: {page.result_text.text()!r}")
    return f"결과 '{page.result_text.text().splitlines()[0]}'"


def greet(login_id, expected):
    def check(w):
        member(w, login_id)
        need(expected in w.router.notice.text(), f"인사: {w.router.notice.text()!r}")
        return f"'{expected}'"
    return check


def title_sheet(w):
    menu = member(w, "bomin")
    need(menu.member_name.text().startswith("[디카페인 지킴이]"), "이름 앞 칭호가 다름")
    menu.member_name.on_tap()
    need(menu.titles_sheet.isVisible() and menu.title_rows.count() == 14, "칭호 진행 현황이 안 뜸")
    return "칭호 7개 진행 막대"


def new_title(w):
    member(w, "jisung0642")
    session = w.router.session
    session.add("M051", None, 1)
    order = pay(session)
    w.router.show_screen("done")
    done = w.router.screens["done"]
    need("단골손님" in order["new_titles"] and done.title_badge.isVisibleTo(w), "새 칭호 띠가 안 보임")
    need("[단골손님] 김지성" in done.waiting.text(), f"대기자: {done.waiting.text()!r}")
    return done.title_badge.text()


def easter_egg(w):
    menu = member(w, "bomin")
    for _ in range(5):
        menu.logo_tap()
    need(w.router.popup.title.text() == "숨은 쿠폰을 찾았어요!", "첫 번째에 숨은 쿠폰이 안 나옴")
    w.router.popup.hide()
    menu.last_tap -= 2
    for _ in range(5):
        menu.logo_tap()
    need(w.router.popup.title.text() == "이미 찾으셨네요!", "두 번째에도 쿠폰이 나옴")
    return "첫 번째 100원 쿠폰 · 두 번째 '이미 찾으셨네요!'"


def quick_reorder(w):
    menu = member(w, "withtop77")
    menu.quick_button.click()
    need(menu.confirm_box.isVisible() and "카페인" in menu.confirm_box.title.text(), "카페인 질문이 안 뜸")
    menu.confirm_box.yes()
    need(len(w.router.session.lines()) == 2, "두 잔이 안 담김")
    return "다시 담기 → '그래도 담을까요?' → 예 → 2잔"


def caffeine_gear(w):
    menu = member(w, "withtop77")
    menu.change_limit(unit="mg")
    menu.change_limit(step=1)
    limit = w.router.session.caffeine_limit()
    need(limit and limit["unit"] == "mg", f"제한: {limit}")
    return f"제한 → {limit['amount']}mg"


def caffeine_views(w):
    menu = member(w, "withtop77")
    for view in ("주별", "월별", "이번 주"):
        menu.set_caffeine_view(view)
        need(menu.caffeine_view == view, f"{view} 보기로 안 바뀜")
    return "이번 주 · 주별 · 월별"


def option_habit(w):
    menu = member(w, "withtop77")
    menu.show_category("커피")
    menu.open_option("M001")
    chosen = menu.popup.chosen_options()
    need(chosen.get("temperature") == "ICE" and chosen.get("size") == "L" and "shot" in chosen.get("extras", []),
         f"미리 고른 옵션: {chosen}")
    return "ICE · L · 샷 추가가 미리 골라짐"


def like(w):
    menu = member(w, "bomin")
    menu.show_category("논커피")
    menu.open_option("M012")
    menu.popup.toggle_like()
    need("M012" in w.router.session.customer["extra"].get("likes", []), "좋아요가 저장 안 됨")
    return "♡ → My Menu 좋아요한 음료"


def like_max(w):
    menu = member(w, "jisung0642")
    for menu_id in list(w.router.session.menu())[:6]:
        w.router.session.toggle_like(menu_id)
    menu.show_category("디저트")
    menu.open_option("M044")
    menu.popup.toggle_like()
    need("최대 6잔" in w.router.notice.text(), f"안내: {w.router.notice.text()!r}")
    return "'즐겨찾기는 최대 6잔만 가능해요'"


def allergy(w):
    menu = member(w, "bomin")
    menu.show_category("커피")
    menu.open_option("M002")
    menu.popup.add_to_cart()
    shown = texts(menu.popup, w)
    need("알레르기 주의" in shown and "우유" in shown, "알레르기 주의가 안 뜸")
    return "'알레르기 주의 · 우유' → 취소 / 그래도 담기"


def saved_route(w):
    menu = member(w, "withtop77")
    menu.open_saved_route(ORIGIN, "대전복합")
    need(menu.category == "승차권" and menu.ticket_panel.page_name() == "timetable", "시간표로 안 감")
    return "저장한 노선 → 바로 시간표"


def buy_ticket(w, with_drink):
    menu = member(w, "jisung0642")
    menu.show_category("승차권")
    panel = menu.ticket_panel
    panel.open_route()
    panel.dest_field.setText("대전복합")
    panel.day_buttons[1].setChecked(True)
    panel.search()
    next(b for b in panel.time_buttons if b.isEnabled() and b.bus["grade"] == "우등").setChecked(True)
    panel.open_seats()
    panel.change_count("어른", 1)
    for seat in [s for s, b in panel.seat_buttons.items() if b.isEnabled()][:2]:
        panel.toggle_seat(seat, True)
    panel.confirm_seats()
    adult = panel.passengers[0].copy()
    panel.set_benefit(0, "경로")
    panel.add_to_cart(panel.on_drinks)
    session = w.router.session
    return session, adult


def ticket_discount(w):
    session, _adult = buy_ticket(w, False)
    ticket = session.tickets[0]
    need(ticket["passengers"][0]["benefit"] == "경로", "경로 할인이 안 붙음")
    full = ticket["passengers"][0]["price"]
    return f"경로 할인 적용 · {full:,}원"


def ticket_with_drink(w):
    session, _adult = buy_ticket(w, True)
    session.add("M001", None, 1)
    order = pay(session, 60000)
    w.router.show_screen("done")
    need(order["tickets"] and order["lines"], "승차권과 음료가 같이 결제 안 됨")
    need(w.router.screens["done"].ticket_box.isVisibleTo(w), "완료 화면에 승차권 안내 없음")
    return "승차권 + 음료 한 번에 결제 · 완료 화면 승차장"


def reservation_cart(w):
    menu = member(w, "user12")
    menu.show_category("승차권")
    panel = menu.ticket_panel
    panel.open_lookup()
    panel.name_field.setText("임예찬")
    panel.phone_field.setText("01020072007")
    panel.lookup()
    panel.print_selected()
    session = w.router.session
    need(session.tickets and session.total() == 0, "예매표가 0원으로 안 담김")
    return f"예매표 {len(session.tickets)}장 · 0원"


def reservation_pay(w):
    reservation_cart(w)
    session = w.router.session
    order = pay(session, 0)
    need(all(session.office.reservations[t["reservation"]]["printed"] for t in order["tickets"]), "출력 표시가 안 됨")
    return "0원 결제 → 출력"


def reservation_printed(w):
    w.router.open_action("guest")
    panel = w.router.screens["menu"].ticket_panel
    w.router.screens["menu"].show_category("승차권")
    panel.open_lookup()
    panel.set_lookup_mode("number")
    panel.number_field.setText("34567890")
    panel.lookup()
    need("이미 출력한" in panel.lookup_message.text(), f"안내: {panel.lookup_message.text()!r}")
    return "'이미 출력한 표예요'"


def seat_hold_expires(w):
    session, _adult = buy_ticket(w, False)
    gone = session.expire_tickets(datetime.now() + timedelta(minutes=6))
    need(gone and not session.tickets, "5분이 지나도 승차권이 남음")
    return "5분 뒤 장바구니에서 빠짐"


def card_login_notice(w):
    member(w, "user12")
    need("리더기에 대면 등록" in w.router.notice.text(), f"안내: {w.router.notice.text()!r}")
    need("카드 등록 전" in w.router.screens["menu"].member_detail.text(), "회원 줄에 '카드 등록 전' 없음")
    return "'받으신 회원카드를 리더기에 대면 등록돼요'"


def card_button(w):
    menu = member(w, "user12")
    menu.card_register_button.click()
    need("리더기에 대 주세요" in w.router.notice.text(), f"안내: {w.router.notice.text()!r}")
    return "'받으신 회원카드를 리더기에 대 주세요 · 20초'"


def card_pay(w):
    member(w, "user12")
    w.router.card_scanned("84E3D273")                     # 실물 대신 카드 번호를 넣어 본다
    need(w.router.popup.title.text() == "회원카드 등록 완료!", "등록 팝업이 안 뜸")
    session = w.router.session
    session.add("M003", {"temperature": "ICE", "size": "M", "extras": []}, 1)
    need(session.benefit()["card_discount"] > 0, "첫 주문 할인이 없음")
    order = pay(session)
    need(order["card_stamp"]["stamps"] == 1, "스탬프가 안 찍힘")
    w.router.show_screen("done")
    need(w.router.screens["done"].stamp_card.isVisibleTo(w), "스탬프 칸이 안 보임")
    return f"할인 {order['card_discount']:,}원 · 스탬프 1 / 10"


def notice_fade(w):
    router = w.router
    router.notify("시험", 1)
    for _ in range(60):
        if not router.notice.isVisible():
            break
        QTest.qWait(100)
    need(not router.notice.isVisible(), "안내가 사라지지 않음")
    router.show_screen("home")
    router.notify("시험", 8)
    router.show_screen("idle")
    need(not router.notice.isVisible(), "처음 화면으로 가도 안내가 남음")
    return "흐려지며 사라짐 · 처음 화면에서 바로 사라짐"


def lost_card(w):
    menu = member(w, "user01")
    menu.ask_lost_card()
    need(menu.confirm_box.isVisible() and "500원" in menu.confirm_box.text.text(), "분실 질문이 안 뜸")
    menu.confirm_box.yes()
    session = w.router.session
    need(session.card_kind == "reissue" and session.card_total() == 500, "재발급 카드가 안 담김")
    return "예전 카드 정지 · 재발급 500원 장바구니"


def card_apply(w):
    router = w.router
    router.show_screen("dine")
    router.screens["dine"].choose(False)
    router.open_action("member")
    page = router.screens["login"]
    page.login_id.setText("jisung0642")
    page.set_mode("password")
    page.password.setText("1234")
    page.card_check.setChecked(True)
    page.password_login()
    router.popup.hide()
    session = router.session
    need(session.card_kind == "new" and session.card_total() == 1000, "장바구니에 회원카드 1,000원이 없음")
    session.add("M001", None, 1)
    pay(session)
    router.show_screen("done")
    need("음료와 함께 받아" in texts(router.screens["done"], w), "'음료와 함께 받아 가세요'가 없음")
    return "장바구니 1,000원 · 완료 '음료와 함께 받아 가세요'"


def smile_once(w):
    member(w, "jisung0642")
    session = w.router.session
    session.add("M051", None, 1)
    w.router.show_screen("cart")
    w.router.screens["cart"].smile_check.setChecked(True)
    need(session.smiled, "미소 미션이 적용 안 됨 (가짜 카메라)")
    pay(session)
    session.add("M051", None, 1)
    w.router.show_screen("cart")
    need(session.smile_offer() == 0 and not w.router.screens["cart"].smile_box.isVisible(), "두 번째에도 미소 미션이 보임")
    return "한 번 쓰면 다음부터 안 보임"


def change_points(w):
    member(w, "jisung0642")
    session = w.router.session
    session.add("M051", None, 1)
    session.change_to_points = True
    order = pay(session, 10000)
    need(order["change_points"] > 0, "잔돈 포인트가 없음")
    return f"잔돈 포인트 +{order['change_points']:,}P"


def coupon_points(w):
    member(w, "bomin")
    session = w.router.session
    session.add("M051", None, 3)
    w.router.show_screen("benefit")
    benefit = w.router.screens["benefit"]
    before = session.final_total()
    benefit.coupon_group.buttons()[0].setChecked(True)
    benefit.points_field.setText("500")
    need(session.final_total() < before, "금액이 안 줄어듦")
    return f"{before:,}원 → {session.final_total():,}원"


def eco_cup(w):
    member(w, "bomin")
    session = w.router.session
    session.add("M051", None, 1)
    w.router.show_screen("cart")
    w.router.screens["cart"].eco_check.setChecked(True)
    order = pay(session)
    need(order["eco_points"] == 100, f"에코 포인트 {order['eco_points']}")
    return "에코 포인트 +100P"


def coin_tip(w):
    w.router.open_action("guest")
    w.router.session.add("M003", {"temperature": "HOT", "size": "M", "extras": []}, 1)
    w.router.show_screen("cash")
    shown = texts(w.router.screens["cash"], w)
    need("동전으로 같이 넣으면" in shown, "동전 줄이기 팁이 없음")
    return "'500원을 동전으로 같이 넣으면 거스름돈에 동전이 없어요'"


def short_refund(w):
    w.router.open_action("guest")
    session = w.router.session
    session.add("M001", None, 2)
    w.router.show_screen("cash")
    cash = w.router.screens["cash"]
    cash.insert(1000)
    need("더 넣어 주세요" in cash.status.text(), "부족 안내 없음")
    cash.refund()
    need(session.inserted == 0, "반환이 안 됨")
    return "부족 금액 안내 → 반환"


def zero_won(w):
    member(w, "bomin")
    session = w.router.session
    customers = session.vault.read("customers")
    customers["C0001"]["extra"]["points"] = 10000
    session.vault.write("customers", customers)
    session.reload_customer()
    session.add("M051", None, 1)
    session.set_benefit(None, session.max_points())
    need(session.final_total() == 0, f"남은 금액 {session.final_total()}")
    order = pay(session, 0)
    need(order["final_total"] == 0, "0원 결제가 안 됨")
    return "포인트 전액 → 0원 결제"


def admin(w, tab):
    w.router.admin_id = "admin"
    w.router.show_screen("admin", tab=tab)
    return w.router.screens["admin"]


def admin_sales(w):
    page = admin(w, "sales")
    page.set_sales_period("최근 30일")
    need(page.sales_tiles["total"].text().endswith("원"), "매출이 안 나옴")
    return f"30일 매출 {page.sales_tiles['total'].text()}"


def admin_sold_out(w):
    page = admin(w, "menu")
    row = next(r for r in range(page.menu_table.rowCount()) if "아메리카노" == page.menu_table.item(r, 1).text())
    page.menu_table.item(row, 0).setCheckState(Qt.CheckState.Checked)
    page.set_sold_out(True)
    need(w.router.session.menu()["M001"]["sold_out"], "품절이 안 됨")
    return "아메리카노 → 품절"


def admin_card_columns(w):
    page = admin(w, "cards")
    table = page.card_table
    headers = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
    need(headers[1:4] == ["아이디", "이름", "칭호"], f"열: {headers}")
    return " · ".join(headers[1:4])


def admin_lost(w):
    page = admin(w, "cards")
    table = page.card_table
    row = next(r for r in range(table.rowCount()) if table.item(r, 6).text() == "사용 중")
    customer_id_text = table.item(row, 1).text()
    table.item(row, 0).setCheckState(Qt.CheckState.Checked)
    page.mark_cards_lost()
    need("분실 처리" in page.message.text(), f"안내: {page.message.text()!r}")
    return f"{customer_id_text} 분실 처리"


def admin_coupon(w):
    page = admin(w, "coupons")
    page.set_coupon_view("issue")
    page.coupon_member_search.setText("user02")
    page.coupon_member_table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    page.issue_coupons()
    page.set_coupon_view("history")
    need(page.coupon_history_table.item(0, 5).text() == "미사용", "발급 내역에 없음")
    return "발급 → 내역 '미사용'"


def admin_perks(w):
    page = admin(w, "perks")
    page.perk_fields["card_point_rate"].setText("5")
    page.save_perks()
    page.logout()
    w.router.open_action("signup")
    need("매 주문 5% 적립" in w.router.screens["signup"].card_perks.text(), "가입 화면에 안 바뀜")
    return "가입 화면 '매 주문 5% 적립'"


def admin_presence_off(w):
    page = admin(w, "kiosk")
    page.presence_switch.setChecked(False)
    page.save_kiosk()
    page.logout()
    w.router.show_screen("idle")
    w.router.presence.distance = 0.5
    w.router.approach_armed = True
    for _ in range(3):
        w.router.check_presence()
    need(w.router.current_name == "idle" and not w.router.screens["idle"].show_approach_hint, "꺼도 다가오면 시작함")
    return "끄면 안내도 사라지고 다가와도 시작 안 함"


CHECKS = {
    "idle_touch": idle_touch, "takeout": takeout, "display_reset": display_reset, "away_refund": away_refund,
    "login_fail": login_fail, "no_card_option": no_card_option, "no_face_option": no_face_option, "find_id": find_id,
    "greet_withtop": greet("withtop77", "[얼죽아] 김휘원 님, 2일 만이에요!"),
    "greet_jisung": greet("jisung0642", "김지성 님, 오늘 두 번째 방문이에요!"),
    "title_sheet": title_sheet, "new_title": new_title, "easter_egg": easter_egg, "quick": quick_reorder,
    "caffeine_gear": caffeine_gear, "caffeine_views": caffeine_views, "habit": option_habit, "like": like,
    "like_max": like_max, "allergy": allergy, "saved_route": saved_route, "ticket_discount": ticket_discount,
    "ticket_drink": ticket_with_drink, "reservation_cart": reservation_cart, "reservation_pay": reservation_pay,
    "reservation_printed": reservation_printed, "seat_hold": seat_hold_expires, "card_login_notice": card_login_notice,
    "card_button": card_button, "card_pay": card_pay, "notice_fade": notice_fade, "lost_card": lost_card,
    "card_apply": card_apply, "smile_once": smile_once, "change_points": change_points, "coupon_points": coupon_points,
    "eco": eco_cup, "coin_tip": coin_tip, "short_refund": short_refund, "zero_won": zero_won,
    "admin_sales": admin_sales, "admin_sold_out": admin_sold_out, "admin_card_columns": admin_card_columns,
    "admin_lost": admin_lost, "admin_coupon": admin_coupon, "admin_perks": admin_perks,
    "admin_presence_off": admin_presence_off,
}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    app = QApplication(sys.argv[:1])
    results = {}
    for key, (group, _account, todo, _expect) in zip(KEYS, TESTS):
        if key in MANUAL or key in LEFT_OUT:
            continue
        check = CHECKS.get(key)
        if check is None:
            results[key] = {"ok": False, "detail": "자동 확인 함수가 없어요"}
            continue
        w = window()
        try:
            detail = check(w)
            results[key] = {"ok": True, "detail": detail}
        except Fail as error:
            results[key] = {"ok": False, "detail": str(error)}
        except Exception as error:                        # 예상 못 한 오류도 '문제'로 남긴다
            results[key] = {"ok": False, "detail": f"{type(error).__name__}: {error}",
                            "trace": traceback.format_exc()[-600:]}
        finally:
            w.close()
            w.deleteLater()
            app.processEvents()
        mark = "통과" if results[key]["ok"] else "문제"
        print(f"[{mark}] {group} · {todo} → {results[key]['detail']}", flush=True)
    OUT.write_text(json.dumps({"at": datetime.now().isoformat(timespec="minutes"), "results": results},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    failed = [k for k, r in results.items() if not r["ok"]]
    print(f"자동 확인 {len(results)}개 · 통과 {len(results) - len(failed)} · 문제 {len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
