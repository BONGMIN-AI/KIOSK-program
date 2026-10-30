"""10/31: 최근 주문 · 온도 규칙(메가MGC커피 조사 반영)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from domain.my_menu import recent_order
from domain.options import available_options, normalize_options


MENU = {"M001": {"id": "M001", "name": "아메리카노", "category": "커피"},
        "M012": {"id": "M012", "name": "딸기라떼", "category": "논커피"},
        "M041": {"id": "M041", "name": "크루아상", "category": "디저트"}}


def order(number, lines, customer="C0001"):
    return {"id": f"O{number:04d}", "created_at": f"2026-10-{number:02d}T10:00:00",
            "customer": {"id": customer}, "lines": lines}


def line(menu_id, quantity=1, temperature="ICE"):
    options = {} if menu_id == "M041" else {"temperature": temperature, "size": "M", "extras": []}
    return {"menu_id": menu_id, "quantity": quantity, "options": options,
            "option_label": f"{temperature} / M" if options else ""}


def test_recent_order_keeps_every_line():
    orders = {"a": order(1, [line("M001")]),
              "b": order(2, [line("M001", 2), line("M012"), line("M041", 3)]),
              "c": order(3, [line("M001")], customer="C0002")}
    recent = recent_order(orders, "C0001", MENU)
    assert [(l["name"], l["quantity"]) for l in recent["lines"]] == [("아메리카노", 2), ("딸기라떼", 1), ("크루아상", 3)]
    assert recent["count"] == 6
    assert recent_order({}, "C0001", MENU) is None


def test_fruit_lattes_are_ice_only_even_in_old_data():
    """예전에 만든 메뉴 데이터(온도 값 없음)에도 이름별 규칙이 적용된다."""
    assert available_options(MENU["M012"])["temperatures"] == ["ICE"]
    assert available_options({"name": "에스프레소", "category": "커피"})["temperatures"] == ["HOT"]
    assert available_options(MENU["M001"])["temperatures"] == ["HOT", "ICE"]
    try:
        normalize_options(MENU["M012"], {"temperature": "HOT"})
    except ValueError as error:
        assert "HOT" in str(error)
    else:
        raise AssertionError("딸기라떼 HOT이 통과됨")
