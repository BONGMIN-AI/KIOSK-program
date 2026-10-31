"""모든 화면·상태를 여러 창 크기로 열어 글자가 잘리거나 눌리거나 칸 밖으로 나가는지 자동 점검한다.

사용: python tools/check_layout.py            (카메라 없이 FakeFace, 메모리 시연 데이터)
      python tools/check_layout.py --basic    (큰 글자 점검은 빼고 기본 글자만)
결과: 문제마다 [화면/상태 @ 크기] 위젯 종류 · 글자 · 이유. 문제가 없으면 '문제 없음'.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import (QAbstractButton, QApplication, QLabel, QLineEdit, QRadioButton,
                               QScrollArea, QWidget)

from face import FakeFace
from core.storage import MemoryVault
from gui.main import KioskWindow, demo_vault

SIZES = [(1200, 800), (1280, 800), (1440, 900), (1920, 1080), (2560, 1440)]
DISPLAYS = {"기본": {}, "큰 글자": {"large": True}}   # 고대비는 색만 바뀌어 배치가 같다


def text_of(widget):
    if isinstance(widget, (QLabel, QAbstractButton)):
        return widget.text()
    if isinstance(widget, QLineEdit):
        return widget.text() or widget.placeholderText()
    return ""


def inside_scroll(widget):
    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QScrollArea):
            return True
        parent = parent.parentWidget()
    return False


def visible_to_user(widget, top):
    """화면에 실제로 보이는지 (숨김·팝업 뒤 제외는 하지 않음)."""
    return widget.isVisibleTo(top) and widget.width() > 0


def check(window, screen, where):
    problems = []
    widgets = screen.findChildren(QLabel) + screen.findChildren(QAbstractButton) + screen.findChildren(QLineEdit)
    for widget in widgets:
        if not visible_to_user(widget, window):
            continue
        text = text_of(widget).replace("\n", " / ")
        if not text.strip():
            continue
        hint = widget.minimumSizeHint()
        need_height = hint.height()
        if isinstance(widget, QLabel) and widget.wordWrap():
            # 줄바꿈 글자는 지금 너비에서 몇 줄이 되는지로 필요한 높이를 계산한다
            need_height = widget.heightForWidth(widget.contentsRect().width()) or need_height
        if widget.height() < need_height - 2:
            problems.append((where, type(widget).__name__, text, f"높이 눌림 {widget.height()} < {need_height}"))
        if isinstance(widget, (QLabel, QAbstractButton)) and not (
                isinstance(widget, QLabel) and widget.wordWrap()):
            lines = widget.text().split("\n")
            need = max(widget.fontMetrics().horizontalAdvance(line) for line in lines)
            extra = 24 if isinstance(widget, QRadioButton) else 0
            room = widget.contentsRect().width() - extra
            if isinstance(widget, QAbstractButton) and not isinstance(widget, QRadioButton):
                room = widget.width() - 8
            if need > room + 2:
                problems.append((where, type(widget).__name__, text, f"글자 잘림 {need} > {room}"))
        parent = widget.parentWidget()
        if parent is not None and not inside_scroll(widget):
            g = widget.geometry()
            r = parent.rect()
            if g.right() > r.right() + 2 or g.bottom() > r.bottom() + 2 or g.left() < -2 or g.top() < -2:
                problems.append((where, type(widget).__name__, text, "부모 칸 밖으로 나감"))
    # 칸(카드) 자체가 안쪽 내용이 필요로 하는 높이보다 작게 눌렸는지
    for box in screen.findChildren(QWidget):
        layout = box.layout()
        if layout is None or not visible_to_user(box, window) or inside_scroll(box):
            continue
        need = layout.totalMinimumSize().height() if hasattr(layout, "totalMinimumSize") else layout.minimumSize().height()
        if box.height() < need - 2:
            problems.append((where, type(box).__name__, box.objectName() or first_text(box),
                             f"칸 눌림 {box.height()} < {need}"))
    # 같은 칸 안의 글자끼리 겹치는지
    texts = [w for w in widgets if visible_to_user(w, window) and text_of(w).strip()]
    by_parent = {}
    for widget in texts:
        by_parent.setdefault(id(widget.parentWidget()), []).append(widget)
    for group in by_parent.values():
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                overlap = a.geometry().intersected(b.geometry())
                if overlap.height() > 4 and overlap.width() > 4:
                    problems.append((where, "겹침", f"{text_of(a)[:15]} ↔ {text_of(b)[:15]}", "글자끼리 겹침"))
    return problems


def first_text(box):
    for widget in box.findChildren(QLabel):
        if widget.text().strip():
            return widget.text()
    return ""


def states(window):
    """(이름, 준비 함수) 목록. 화면 흐름은 플로차트 순서를 따른다."""
    router, session = window.router, window.router.session
    customers = session.vault.read("customers")
    bomin = next(c for c in customers.values() if c["extra"]["login_id"] == "bomin")
    member2 = next(c for c in customers.values() if c["extra"]["login_id"] == "member2")

    def login_fail():
        router.open_action("member")
        login = router.screens["login"]
        login.login_id.setText("kbm000608")
        login.show_face_failure("등록된 회원 ID가 없습니다")

    def face_running():
        router.open_action("member")
        login = router.screens["login"]
        login.login_id.setText("bomin")
        login.begin_face()
        login.show_step("한 사람만 카메라 앞에 서 주세요")

    def login_fail_long():
        login_fail()
        router.screens["login"].show_face_failure("입체 얼굴이 확인되지 않았어요 (사진·화면으로 보여요). 비밀번호로 로그인하세요")

    def password_mode():
        router.open_action("member")
        router.screens["login"].set_mode("password", "아이디 또는 비밀번호를 확인해 주세요")

    def member_menu(customer):
        def run():
            router.start_member_order(customer)
        return run

    def filled_member():
        session.login(bomin)
        for _ in range(3):                        # 최근 주문에 4가지가 담긴다
            session.add("M001", {"temperature": "ICE", "size": "L", "extras": ["shot", "syrup"]}, 1)
            session.add("M044", None, 1)
            session.add("M014", {"temperature": "HOT"}, 2)
            session.add("M031", None, 1)
            session.insert(50000)
            session.pay()
        session.toggle_like("M003")
        session.toggle_like("M014")
        session.toggle_like("M047")
        router.start_member_order(session.customer)

    def option(menu_id, allergy=False, error=False):
        def run():
            router.start_member_order(bomin)
            router.screens["menu"].show_category("커피")
            popup = router.screens["menu"].popup
            popup.open_for(menu_id)
            if allergy:
                popup.add_to_cart()
            if error:
                popup.message.setText("재고가 부족합니다: 카라멜마키아토 (남은 수량 0개)")
        return run

    def big_cart():
        router.open_action("guest")
        for menu_id in ("M001", "M002", "M003", "M004", "M005", "M006", "M041", "M055"):
            session.add(menu_id, None, 3)
        router.screens["menu"].refresh()

    def cart_screen():
        big_cart()
        router.show_screen("cart")

    def benefit_error():
        session.login(bomin)
        session.add("M002", {"temperature": "HOT"}, 4)
        router.show_screen("benefit")
        router.screens["benefit"].set_points(999999)

    def cash_member():
        session.login(bomin)
        session.add("M002", {"temperature": "HOT"}, 4)
        router.show_screen("cash")
        router.screens["cash"].insert(50000)
        router.screens["cash"].change_check.setChecked(True)

    def cash_refund():
        router.open_action("guest")
        session.add("M001", None, 1)
        router.show_screen("cash")
        router.screens["cash"].insert(1000)
        router.screens["cash"].refund()

    def done_member():
        session.login(member2)
        for menu_id in ("M001", "M002", "M003", "M004", "M051", "M052"):
            session.add(menu_id, {"temperature": "ICE", "size": "L", "extras": ["shot"]}, 2)
        session.insert(100000)
        session.change_to_points = True
        session.pay()
        router.show_screen("done")

    def signup_error():
        router.open_action("signup")
        signup = router.screens["signup"]
        signup.allergy_search.setText("류")
        signup.submit()

    def enroll_running():
        router.show_screen("enroll", customer=bomin)
        enroll = router.screens["enroll"]
        enroll.show_running(True)
        enroll.now_text.setText("한 사람만 카메라 앞에 서 주세요")

    def admin(tab, error=""):
        def run():
            router.admin_id = "admin"
            router.show_screen("admin", tab=tab)
            if error:
                router.screens["admin"].fail(error)
        return run

    def admin_login_error():
        router.open_action("admin")
        login = router.screens["admin_login"]
        login.password.setText("x")
        login.password_login()

    def find_id():
        router.open_action("member")
        router.show_screen("find", mode="id")
        find = router.screens["find"]
        find.phone.setText(bomin["phone"])
        find.find_id()

    def find_reset():
        router.show_screen("find", mode="password", login_id="bomin")
        find = router.screens["find"]
        find.phone.setText(bomin["phone"])
        find.verify_phone()

    def card_wait():
        password_mode()
        login = router.screens["login"]
        login.login_id.setText("bomin")
        login.password.setText("1234")
        login.password_then_card()

    def cash_zero():
        customers = session.vault.read("customers")
        customers[bomin["id"]]["extra"]["points"] = 10000
        session.vault.write("customers", customers)
        session.login(customers[bomin["id"]])
        session.add("M001", None, 1)
        session.set_benefit(None, 3000)
        router.show_screen("cash")

    # 카페인 알리미 (10/31)
    def caffeine_limit(view="주별", ask=None):
        def run():
            filled_member()
            menu = router.screens["menu"]
            menu.change_limit(unit="잔")
            menu.change_limit(step=-1)
            menu.set_caffeine_view(view)
            if ask == "popup":
                menu.show_category("커피")
                menu.popup.open_for("M001")
                menu.popup.add_to_cart()
            elif ask == "settings":
                menu.gear_button.click()
            elif ask == "reorder":
                menu.reorder(session.recent()["lines"])
        return run

    # 인기 탭 (10/31)
    def popular(sort, member=None):
        def run():
            if member:
                router.start_member_order(member)
            else:
                router.open_action("guest")
            menu = router.screens["menu"]
            menu.popular_sort = sort
            menu.show_category("인기")
        return run

    # 승차권 탭(T1)
    def ticket_tab(member=None):
        if member:
            router.start_member_order(member)
        else:
            router.open_action("guest")
        menu = router.screens["menu"]
        menu.show_category("승차권")
        return menu.ticket_panel

    def ticket_lookup_error():
        panel = ticket_tab()
        panel.open_lookup()
        panel.name_field.setText("홍길동")
        panel.birth_field.setText("9001")
        panel.lookup()

    def ticket_printed():
        panel = ticket_tab(bomin)
        panel.open_lookup()
        panel.name_field.setText("홍길동")
        panel.birth_field.setText("900101")
        panel.lookup()
        panel.print_selected()

    def ticket_route():
        panel = ticket_tab()
        panel.open_route()
        panel.dest_field.setText("대")

    def ticket_other_origin():
        panel = ticket_tab()
        panel.open_route()
        panel.origin_field.setText("대전복합")
        panel.choose_field(panel.origin_field)
        panel.day_buttons[5].setChecked(True)

    def my_menu_routes():
        customers = session.vault.read("customers")
        customers[bomin["id"]]["extra"]["saved_routes"] = [
            {"origin": "서울경부", "destination": "대전복합", "times": 12, "last": "2026-10-30"},
            {"origin": "서울경부", "destination": "동대구", "times": 3, "last": "2026-10-21"},
            {"origin": "대전복합", "destination": "서울경부", "times": 9, "last": "2026-10-29"}]
        session.vault.write("customers", customers)
        router.start_member_order(customers[bomin["id"]])

    def ticket_timetable(member=None):
        panel = ticket_tab(member)
        panel.open_route()
        panel.dest_field.setText("대전복합")
        panel.day_buttons[1].setChecked(True)
        panel.search()
        return panel

    def ticket_seats(grade, adults=2):
        def run():
            panel = ticket_timetable(bomin)
            item = next(b for b in panel.time_buttons if b.isEnabled() and b.bus["grade"] == grade)
            item.setChecked(True)
            panel.open_seats()
            for _ in range(adults - 1):
                panel.change_count("어른", 1)
            panel.change_count("초등생", 1)
            for seat in [s for s, b in panel.seat_buttons.items() if b.isEnabled()][:adults + 1]:
                panel.toggle_seat(seat, True)
            return panel
        return run

    def ticket_confirm():
        panel = ticket_seats("우등")()
        panel.confirm_seats()
        panel.set_benefit(1, "장애인")

    def ticket_with_drink(member=None):
        def run():
            panel = ticket_seats("일반")() if member else None
            if panel is None:
                panel = ticket_timetable()
                next(b for b in panel.time_buttons if b.isEnabled()).setChecked(True)
                panel.open_seats()
                panel.toggle_seat(next(s for s, b in panel.seat_buttons.items() if b.isEnabled()), True)
            panel.confirm_seats()
            panel.add_to_cart(panel.on_drinks)
            session.add("M001", {"temperature": "ICE", "size": "L"}, 1)
            router.screens["menu"].refresh()
        return run

    def ticket_cart():
        ticket_with_drink(bomin)()
        router.show_screen("cart")

    def ticket_done(drinks=True):
        def run():
            panel = ticket_seats("우등")()
            panel.confirm_seats()
            panel.set_benefit(0, "경로")
            panel.add_to_cart(panel.on_drinks)
            if drinks:
                session.add("M001", {"temperature": "ICE", "size": "L"}, 2)
            session.insert(100000)
            session.pay()
            router.show_screen("done")
        return run

    return [
        ("00 대기", lambda: router.show_screen("idle")),
        ("01 시작", lambda: router.show_screen("home")),
        ("02 로그인", lambda: router.open_action("member")),
        ("02 얼굴 인증 중", face_running),
        ("02 로그인 실패", login_fail),
        ("02 로그인 실패(긴 문구)", login_fail_long),
        ("02-B 비밀번호", password_mode),
        ("02-B 카드 연결 대기", card_wait),
        ("02-C 아이디 찾기", find_id),
        ("02-C 비밀번호 재설정", find_reset),
        ("03 비회원 메뉴", lambda: router.open_action("guest")),
        ("03 비회원 장바구니 많음", big_cart),
        ("03 My Menu 빈 회원", member_menu(member2)),
        ("03 My Menu 채운 회원", filled_member),
        ("03 카페인 알리미 주별", caffeine_limit()),
        ("03 카페인 월별", caffeine_limit("월별")),
        ("03 카페인 알리미 설정 창", caffeine_limit(ask="settings")),
        ("04 카페인 알리미 질문", caffeine_limit(ask="popup")),
        ("03 카페인 알리미 다시 담기 질문", caffeine_limit(ask="reorder")),
        ("03 인기 좋아요순 비회원", popular("좋아요순")),
        ("03 인기 판매순 회원", popular("판매순", bomin)),
        ("03 인기 계절 인기순 회원", popular("계절 인기순", bomin)),
        ("T1-0 승차권 비회원", ticket_tab),
        ("T1-0 승차권 회원", lambda: ticket_tab(bomin)),
        ("T1-1 예매표 조회 오류", ticket_lookup_error),
        ("T1-2 예매표 출력됨", ticket_printed),
        ("T1-3 노선 입력", ticket_route),
        ("T1-3 다른 출발지", ticket_other_origin),
        ("03 My Menu 저장한 노선", my_menu_routes),
        ("T1-4 시간표", lambda: ticket_timetable(bomin)),
        ("T1-5 좌석 우등", ticket_seats("우등")),
        ("T1-5B 좌석 일반", ticket_seats("일반")),
        ("T1-6 혜택·확인", ticket_confirm),
        ("T1-7 음료와 같은 장바구니", ticket_with_drink()),
        ("T1 05 장바구니 승차권", ticket_cart),
        ("T1-8 완료 승차권+음료", ticket_done()),
        ("T1-8 완료 승차권만", ticket_done(drinks=False)),
        ("04 옵션", option("M001")),
        ("04-A 알레르기", option("M002", allergy=True)),
        ("04 옵션 오류문구", option("M006", error=True)),
        ("05 장바구니 많음", cart_screen),
        ("06 쿠폰·포인트 오류", benefit_error),
        ("07 현금 회원 잔돈", cash_member),
        ("07 현금 반환", cash_refund),
        ("07 현금 0원 결제", cash_zero),
        ("08 완료 회원", done_member),
        ("10 회원가입 오류", signup_error),
        ("10-B 얼굴 등록", lambda: router.show_screen("enroll", customer=bomin)),
        ("10-B 얼굴 등록 중", enroll_running),
        ("09-A 운영자 로그인 오류", admin_login_error),
        ("09-B 메뉴", admin("menu", "재고가 0개입니다. 재고를 먼저 채우고 저장하세요")),
        ("09-C 회원·주문", admin("members")),
        ("09-D 이벤트", admin("events", "이벤트 적립률이나 보너스 포인트 중 하나는 입력하세요")),
        ("09-E 포인트·로그", admin("points")),
    ]


def fresh_vault(template):
    """시연 데이터를 매번 새로 만들면 비밀번호 해시 때문에 느려서, 한 번 만든 것을 복사해 쓴다."""
    vault = MemoryVault()
    vault._store = dict(template._store)
    return vault


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    app = QApplication(sys.argv[:1])
    template = demo_vault()
    all_problems = []
    grown = []
    count = 0
    first = KioskWindow(vault=fresh_vault(template), face_factory=lambda v: FakeFace())
    names = [name for name, _ in states(first)]
    first.close()
    displays = {"기본": {}} if "--basic" in sys.argv else DISPLAYS
    cases = [(display, size) for display in displays for size in SIZES]
    for display, size in cases:
        print(f"{display} · 크기 {size[0]}x{size[1]} 점검 중…", flush=True)
        for name in names:
            window = KioskWindow(vault=fresh_vault(template), face_factory=lambda v: FakeFace())
            window.resize(*size)
            window.show()
            app.processEvents()
            if displays[display]:       # 실제처럼 창이 보이는 상태에서 바꾼다
                window.router.apply_display({"contrast": False, "large": False, **displays[display]})
                app.processEvents()
            # 같은 이름의 상태를 새 창에서 다시 만든다
            print("  -", name, flush=True)
            prepare_fn = dict(states(window))[name]
            prepare_fn()
            app.processEvents()
            app.processEvents()
            where = f"{name} @ {size[0]}x{size[1]}" + ("" if display == "기본" else f" ({display})")
            if window.width() > size[0] + 1 or window.height() > size[1] + 1:
                grown.append(f"{where}: 창이 {window.width()}x{window.height()}로 커짐 (내용이 창보다 큼)")
            screen = window.router.currentWidget()
            all_problems += check(window, screen, where)
            count += 1
            window.close()
            window.deleteLater()
            # 창을 바로 지운다. processEvents만으로는 안 지워져 창마다 앱 전체 이벤트 필터가 쌓이다가 멈췄다
            app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents()
    print(f"점검한 경우: {count}개 (화면·상태 {len(names)}개 × 크기 {len(SIZES)}개 × 글자 {len(displays)}가지)")
    for line in grown:
        print("[창 커짐]", line)
    seen = set()
    for where, kind, text, why in all_problems:
        key = (where.split(" @ ")[0], where.endswith(")"), kind, text, why.split(" ")[0])
        if key in seen:
            continue
        seen.add(key)
        print(f"[{where}] {kind} '{text[:40]}' — {why}")
    if not grown and not all_problems:
        print("문제 없음")
    return 1 if grown or all_problems else 0


if __name__ == "__main__":
    sys.exit(main())
