"""관리자 분석의 분류 및 시간 집계가 원본 기록을 따르는지 확인."""

from datetime import date

from domain.sales import category_menu_summary, category_summary, hourly_day, trend


def test_category_sales_and_time_series_use_source_records():
    today = date(2026, 11, 7)
    menu = {"M1": {"category": "커피"}, "M2": {"category": "차"}}
    orders = {
        "O1": {"created_at": "2026-11-07T10:00:00", "final_total": 8500,
               "lines": [{"menu_id": "M1", "quantity": 2, "subtotal": 6000},
                         {"menu_id": "M2", "quantity": 1, "subtotal": 3000}]},
        "O2": {"created_at": "2026-10-30T14:00:00", "final_total": 4000,
               "lines": [{"menu_id": "M2", "quantity": 1, "subtotal": 4000}]},
    }
    assert category_summary(orders, menu, "오늘", today) == [("커피", 2, 6000), ("차", 1, 3000)]
    assert category_summary(orders, menu, "최근 30일", today) == [("차", 2, 7000), ("커피", 2, 6000)]
    assert category_menu_summary(orders, menu, "차", "최근 30일", today) == [("메뉴", 2, 7000)]
    assert hourly_day(orders, today)["hours"][10] == 1
    assert hourly_day(orders, date(2026, 10, 30))["count"] == 1
    assert trend(orders, {}, {}, "일별 매출", today)[-1] == ("11/7", 8500)
    assert sum(amount for _label, amount in trend(orders, {}, {}, "월별 매출", today)) == 12500

    customers = {"C1": {"created_at": "2026-11-05T09:00:00"}}
    cards = {"R1": {"issued_at": "2026-11-06T11:00:00"}, "R2": {"issued_at": ""}}
    assert sum(value for _label, value in trend({}, customers, cards, "회원가입 추이", today)) == 1
    assert sum(value for _label, value in trend({}, customers, cards, "카드 등록 추이", today)) == 1


def test_category_drilldown_sorts_quantity_before_revenue():
    today = date(2026, 11, 8)
    menu = {"M1": {"category": "논커피"}, "M2": {"category": "논커피"},
            "M3": {"category": "차"}}
    orders = {"O1": {"created_at": "2026-11-08T09:00:00", "lines": [
        {"menu_id": "M1", "name": "초코라떼", "quantity": 3, "subtotal": 12000},
        {"menu_id": "M2", "name": "말차라떼", "quantity": 2, "subtotal": 14000},
        {"menu_id": "M3", "name": "유자차", "quantity": 5, "subtotal": 20000}]}}
    assert category_menu_summary(orders, menu, "논커피", "오늘", today) == [
        ("초코라떼", 3, 12000), ("말차라떼", 2, 14000)]
