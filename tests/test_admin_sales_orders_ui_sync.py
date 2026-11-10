"""관리자 매출 요약과 주문 기록의 화면 값이 같은 주문을 반영하는지 확인."""

import os
from datetime import date

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from domain.sales import summary
from face import FakeFace
from gui.main import KioskWindow, demo_vault


def test_admin_sales_and_order_tables_match_all_periods():
    app = QApplication.instance() or QApplication([])
    vault = demo_vault(random_members=True)
    window = KioskWindow(vault=vault, face_factory=lambda current: FakeFace())
    window.show()
    window.router.admin_id = "admin"
    window.router.show_screen("admin", tab="sales")
    app.processEvents()
    admin = window.router.screens["admin"]
    try:
        for period in ("오늘", "최근 7일", "최근 30일"):
            admin.set_sales_period(period)
            expected = summary(vault.read("orders"), period)
            assert admin.sales_tiles["count"].text() == f"{expected['count']:,}건"
            assert admin.sales_tiles["total"].text() == f"{expected['total']:,}원"
            assert admin.sales_top.rowCount() == len(expected["top"])
            for row, (name, quantity, sales) in enumerate(expected["top"]):
                assert [admin.sales_top.item(row, col).text() for col in range(4)] == [
                    str(row + 1), name, f"{quantity:,}개", f"{sales:,}원"]
            admin.show_tab("orders")
            admin.order_period.setCurrentText(period)
            assert admin.order_table.rowCount() == expected["count"]
            assert admin.order_total.text() == f"{expected['count']}건 · 합계 {expected['total']:,}원"
            admin.show_tab("sales")
        assert admin.sales_top.rowCount() > 5
        for mode in ("카테고리별 판매", "시간대별 주문", "일별 매출", "주별 매출",
                     "월별 매출", "회원가입 추이", "카드 등록 추이"):
            admin.sales_analysis_mode.setCurrentText(mode)
            if mode != "시간대별 주문":
                assert admin.sales_analysis_table.rowCount() == len(admin.sales_hours.values)
            else:
                assert admin.sales_analysis_table.isHidden()
            if mode not in ("카테고리별 판매", "시간대별 주문"):
                assert any(admin.sales_hours.values)
            if mode == "월별 매출":
                assert sum(value > 0 for value in admin.sales_hours.values) >= 8
            assert admin.sales_analysis_insight.text()
        admin.sales_analysis_mode.setCurrentText("시간대별 주문")
        assert admin.sales_hours.unit == "건"
        assert admin.sales_hour_next.isEnabled() == (admin.sales_hour_day < date.today())
        today_values = list(admin.sales_hours.values)
        admin.move_sales_hour_day(-1)
        assert admin.sales_hour_next.isEnabled()
        assert admin.sales_hour_day.isoformat() in admin.sales_hour_date.text().replace("년 ", "-").replace("월 ", "-").replace("일", "")
        admin.move_sales_hour_day(1)
        assert admin.sales_hours.values == today_values
        admin.sales_analysis_mode.setCurrentText("카테고리별 판매")
        admin.sales_analysis_table.cellClicked.emit(0, 0)
        assert admin.sales_category_picker.currentText() != "전체 분류"
        assert admin.sales_analysis_table.rowCount() >= 1
        quantities = [int(admin.sales_analysis_table.item(row, 1).text().removesuffix("개").replace(",", ""))
                      for row in range(admin.sales_analysis_table.rowCount())]
        assert quantities == sorted(quantities, reverse=True)
        admin.sales_category_back.click()
        assert admin.sales_category_picker.currentText() == "전체 분류"
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()
