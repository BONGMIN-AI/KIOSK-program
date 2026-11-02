"""11/03 팀원 시연 계정: withtop77 · asd1625 · jisung0642 (비밀번호 1234), 각자 대표 시연 기능이 바로 보이게."""
import os
from datetime import datetime

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

from domain.customers import login_with_password
from domain.member_cards import check_can_buy
from domain.my_menu import week_caffeine
from domain.titles import count_stats, customer_lines, progress
from domain.visits import celebrate, visit_greeting


@pytest.fixture
def vault():
    pytest.importorskip("PySide6")
    from gui.main import demo_vault
    return demo_vault(random_members=True)


@pytest.mark.parametrize("login_id", ["withtop77", "asd1625", "jisung0642"])
def test_team_accounts_log_in_with_1234(vault, login_id):
    assert login_with_password(vault, login_id, "1234")["extra"]["login_id"] == login_id


def test_withtop77_remembered_customer(vault):
    customer = vault.read("customers")["C0201"]
    orders = vault.read("orders")
    assert customer["extra"]["title"] == "얼죽아"
    assert visit_greeting(orders, "C0201") == "2일 만이에요!"
    limit = customer["extra"]["caffeine_limit"]
    used = week_caffeine(orders, "C0201", vault.read("menu"))["잔"]
    assert limit == {"unit": "잔", "amount": used + 1}      # 두 잔을 담으면 알리미가 묻는다


def test_asd1625_birthday_anniversary_and_can_buy_card(vault):
    gifts = celebrate(vault, "C0202")
    assert [g["title"] for g in gifts] == ["생일 축하해요!", "가입 1주년이에요!"]
    customer = vault.read("customers")["C0202"]
    assert customer["extra"]["points"] == 3000
    check_can_buy(vault, customer, "new")          # 회원카드 신청 체크 → 장바구니 시연


def test_jisung0642_one_order_from_regular_title(vault):
    orders = vault.read("orders")
    assert visit_greeting(orders, "C0203", datetime.now()) == "오늘 두 번째 방문이에요!"
    rows = {row["title"]: row for row in progress(count_stats(customer_lines(orders, "C0203"), vault.read("menu")))}
    assert (rows["단골손님"]["count"], rows["단골손님"]["goal"]) == (9, 10)
    assert not vault.read("customers")["C0203"]["extra"].get("easter_egg")
