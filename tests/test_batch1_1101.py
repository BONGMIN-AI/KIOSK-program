"""11/01 1묶음: 동전 최소화 안내 · 에코 포인트 · 옵션 습관 · 임시 비밀번호 · 무작위 회원 · 칭호 이름 변경."""
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

from core.storage import MemoryVault
from domain import seed
from domain.customers import (
    issue_temp_password, login_with_password, must_change_password, register_customer, reset_member_password,
)
from domain.my_menu import option_habit
from domain.orders import complete_order
from domain.payment import coin_tip
from domain.random_members import make_random_members
from domain.titles import title_name, update_titles


def make_vault():
    vault = MemoryVault()
    seed.run(vault)
    return vault


def test_coin_tip_only_when_change_would_have_coins():
    assert coin_tip(4500) == "500원을 동전으로 같이 넣으면 거스름돈에 동전이 없어요"
    assert coin_tip(3700).startswith("700원")
    assert coin_tip(4000) is None and coin_tip(0) is None


def test_eco_cup_points_count_drinks_only():
    vault = make_vault()
    cart = {}
    from domain.cart import add_item
    cart = add_item(cart, "M001", 2, {"temperature": "ICE", "size": "M", "extras": []}, vault.read("menu"))
    cart = add_item(cart, "M041", 1, None, vault.read("menu"))          # 디저트는 세지 않는다
    order = complete_order(vault, cart, 20000, customer_id="C0001", eco_cup=True)
    assert order["eco_points"] == 200
    history = vault.read("customers")["C0001"]["extra"]["point_history"]
    assert any("에코" in h["reason"] and h["delta"] == 200 for h in history)
    guest = complete_order(vault, add_item({}, "M001", 1, None, vault.read("menu")), 5000, eco_cup=True)
    assert guest["eco_points"] == 0


def order(number, menu_id, options, quantity=1):
    return {"id": f"O{number}", "created_at": f"2026-10-{number:02d}T10:00:00", "customer": {"id": "C1"},
            "lines": [{"menu_id": menu_id, "quantity": quantity, "options": options}]}


def test_option_habit_picks_most_common_then_latest():
    ice_l = {"temperature": "ICE", "size": "L", "extras": ["shot"]}
    hot_m = {"temperature": "HOT", "size": "M", "extras": []}
    orders = {"a": order(1, "M001", hot_m), "b": order(2, "M001", ice_l, 2), "c": order(3, "M001", hot_m),
              "d": order(4, "M002", hot_m)}
    assert option_habit(orders, "C1", "M001") == hot_m                  # 2잔 vs 2잔 → 더 최근(10/03)
    orders["e"] = order(5, "M001", ice_l)
    assert option_habit(orders, "C1", "M001") == ice_l
    assert option_habit(orders, "C1", "M041") is None


def test_temp_password_then_change():
    vault = MemoryVault()
    customer = register_customer(vault, "가나다", "", "010-1234-5678", "tempuser", "pass1234", privacy_agreed=True)
    temp = issue_temp_password(vault, customer["id"])
    assert len(temp) == 6 and not set(temp) & set("ilo01")
    with pytest.raises(ValueError):
        login_with_password(vault, "tempuser", "pass1234")
    record = login_with_password(vault, "tempuser", temp)
    assert must_change_password(record)
    record = reset_member_password(vault, customer["id"], "newpass", "newpass")
    assert not must_change_password(record)


def test_random_members_are_varied_and_repeatable():
    vault = make_vault()
    made = make_random_members(vault, count=12, seed=7)
    customers = vault.read("customers")
    orders = vault.read("orders")
    assert len(made) == 12 and all(customers[c]["extra"]["visits"] >= 1 for c in made)
    assert {customers[c]["extra"]["random_profile"] for c in made} >= {"얼죽아", "라떼파", "디카페인"}
    assert all(len(set(customers[c]["extra"]["likes"])) == len(customers[c]["extra"]["likes"]) for c in made)
    assert all(order_id.startswith("H") for order_id in orders)        # 대기 번호(O0001…)는 그대로
    again = make_vault()
    make_random_members(again, count=12, seed=7)
    assert [again.read("customers")[c]["name"] for c in made] == [customers[c]["name"] for c in made]
    assert login_with_password(vault, "user01", "1234")["id"] == made[0]


def test_titles_renamed_and_old_names_shown_new():
    assert title_name("아아수호자") == "얼죽아" and title_name("라떼 장인") == "라떼조아"
    assert title_name("새내기") == "새내기"
    customer = {"extra": {"titles": ["새내기", "아아수호자"], "title": "아아수호자"}}
    update_titles(customer, [], {})
    assert customer["extra"]["titles"] == ["새내기", "얼죽아"] and customer["extra"]["title"] == "얼죽아"


@pytest.fixture
def window():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from face import FakeFace
    from gui.main import KioskWindow, demo_vault
    app = QApplication.instance() or QApplication([])
    result = KioskWindow(vault=demo_vault(), face_factory=lambda vault: FakeFace())
    result.show()
    app.processEvents()
    yield result
    result.close()
    result.deleteLater()
    app.processEvents()


def bomin(router):
    return next(c for c in router.session.vault.read("customers").values() if c["extra"]["login_id"] == "bomin")


def test_screens_show_eco_coin_tip_and_habit(window):
    from PySide6.QtWidgets import QPushButton
    router = window.router
    session = router.session
    session.login(bomin(router))
    session.add("M001", {"temperature": "ICE", "size": "L", "extras": ["shot"]}, 1)
    session.insert(10000)
    session.pay()
    router.start_member_order(session.customer)
    menu = router.screens["menu"]
    menu.show_category("커피")
    menu.open_option("M001")                                            # 지난번 ICE · L · 샷 추가가 골라져 있다
    popup = menu.popup
    assert popup.chosen_options() == {"temperature": "ICE", "size": "L", "extras": ["shot"]}
    assert popup.habit_note.isVisible()
    popup.add_to_cart()
    session.add("M047", None, 1)                                       # 4,500 + 소금빵 3,200 = 7,700원
    router.show_screen("cart")
    cart = router.screens["cart"]
    assert cart.eco_box.isVisible() and "+100P" in cart.eco_note.text()   # 음료 1잔 (디저트 제외)
    cart.eco_check.setChecked(True)
    router.show_screen("cash")
    cash = router.screens["cash"]
    assert cash.coin_tip.text() == "동전 줄이기 팁 · 700원을 동전으로 같이 넣으면 거스름돈에 동전이 없어요"
    cash.findChild(QPushButton, "cash_10000").click()
    assert not cash.coin_tip.isVisible()                               # 충분해지면 사라진다
    cash.pay_button.click()
    assert session.last_order["eco_points"] == 100


def test_guest_sees_no_eco_or_habit(window):
    router = window.router
    router.open_action("guest")
    menu = router.screens["menu"]
    menu.show_category("커피")
    menu.open_option("M001")
    assert not menu.popup.habit_note.isVisible()
    menu.popup.add_to_cart()
    router.show_screen("cart")
    assert not router.screens["cart"].eco_box.isVisible()
