"""11/03 시연 계정 네 부분: withtop77(My Menu) · asd1625(예매표 + 회원카드) · jisung0642(버스표 구매 · 포장 · 혜택)
· bomin(접근 · 얼굴 · 인사 · 생일 · 알레르기 · 칭호). 비밀번호는 모두 1234."""
import os
from datetime import datetime

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

from domain.customers import allergy_warnings, login_with_password
from domain.member_cards import card_status_text, unused_card
from domain.my_menu import week_caffeine
from domain.tickets import saved_routes
from domain.titles import count_stats, customer_lines, progress
from domain.visits import celebrate, visit_greeting


@pytest.fixture
def vault():
    pytest.importorskip("PySide6")
    from gui.main import demo_vault
    return demo_vault(random_members=True)


@pytest.mark.parametrize("login_id", ["withtop77", "jisung0642", "bomin"])
def test_demo_accounts_log_in_with_1234(vault, login_id):
    assert login_with_password(vault, login_id, "1234")["extra"]["login_id"] == login_id


def test_part1_withtop77_my_menu(vault):
    customer = vault.read("customers")["C0201"]
    orders = vault.read("orders")
    assert customer["extra"]["title"] == "얼죽아"
    assert visit_greeting(orders, "C0201") == "2일 만이에요!"
    assert [r["destination"] for r in saved_routes(customer)] == ["대전복합", "동대구"]    # 최근에 간 곳 먼저
    used = week_caffeine(orders, "C0201", vault.read("menu"))["잔"]
    assert customer["extra"]["caffeine_limit"] == {"unit": "잔", "amount": used + 1}


def test_team_real_names_11_04(vault):
    """11/04 회의 2: 미리 만드는 계정은 김휘원 · 김지성뿐 (조민기는 시연 때 가입, 임예찬은 비회원)."""
    customers = vault.read("customers")
    names = {c["extra"]["login_id"]: c["name"] for c in customers.values()}
    assert (names["withtop77"], names["jisung0642"], names["bomin"]) == ("김휘원", "김지성", "김보민")
    assert "asd1625" not in names and "yeachan2007" not in names
    withtop = next(c for c in customers.values() if c["extra"]["login_id"] == "withtop77")
    assert withtop["extra"]["allergies"] == ["우유"] and celebrate(vault, withtop["id"])    # 생일 쿠폰


def test_guest_reservation_by_name_and_phone():
    from domain.tickets import BOOKER_NAME, BOOKER_PHONE, TicketOffice
    assert len(TicketOffice().lookup(name=BOOKER_NAME, phone=BOOKER_PHONE)) == 2      # 임예찬 · 비회원 시연


def test_part3_jisung0642_one_order_from_regular_title(vault):
    orders = vault.read("orders")
    assert visit_greeting(orders, "C0203", datetime.now()) == "오늘 두 번째 방문이에요!"
    rows = {row["title"]: row for row in progress(count_stats(customer_lines(orders, "C0203"), vault.read("menu")))}
    assert (rows["단골손님"]["count"], rows["단골손님"]["goal"]) == (9, 10)


def test_part4_bomin_greeting_birthday_allergy(vault):
    customer = vault.read("customers")["C0001"]
    assert customer["extra"]["title"] == "디카페인 지킴이"
    assert visit_greeting(vault.read("orders"), "C0001") == "3일 만이에요!"
    latte = [{"menu_id": next(k for k, v in vault.read("menu").items() if v["name"] == "카페라떼"), "name": "카페라떼", "quantity": 1}]
    assert allergy_warnings(customer, latte, vault.read("menu"))
    assert celebrate(vault, "C0001") == []                     # 11/04: 생일은 withtop77로 옮김
