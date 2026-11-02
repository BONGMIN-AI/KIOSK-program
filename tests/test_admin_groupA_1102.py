"""11/02 A묶음: 운영자 화면 정리 — 메뉴 체크 일괄 처리 · 회원 목록/주문 기록 · 포인트 저장 조건 · 운영 기록 걸러 보기."""
import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from face import FakeFace
from gui.main import KioskWindow, demo_vault


@pytest.fixture
def admin():
    app = QApplication.instance() or QApplication([])
    window = KioskWindow(vault=demo_vault(random_members=True), face_factory=lambda vault: FakeFace())
    window.show()
    window.router.admin_id = "admin"
    window.router.show_screen("admin", tab="menu")
    app.processEvents()
    yield window.router.screens["admin"]
    window.close()
    window.deleteLater()
    app.processEvents()


def check_rows(table, rows):
    for row in rows:
        table.item(row, 0).setCheckState(Qt.CheckState.Checked)


def test_menu_batch_sold_out_and_buttons_follow_state(admin):
    table = admin.menu_table
    assert not admin.sold_out_button.isEnabled() and not admin.menu_delete_button.isEnabled()
    check_rows(table, (0, 1, 2))
    assert admin.sold_out_button.isEnabled() and not admin.on_sale_button.isEnabled()
    admin.set_sold_out(True)
    menu = admin.vault().read("menu")
    assert all(menu[key]["sold_out"] for key in ("M001", "M002", "M003"))
    check_rows(table, (0, 1))
    assert admin.on_sale_button.isEnabled() and not admin.sold_out_button.isEnabled()
    admin.menu_filter.setCurrentText("품절만")
    assert table.rowCount() == 3


def test_members_and_orders_are_separate_pages(admin):
    admin.show_tab("members")
    admin.member_table.selectRow(4)
    assert "최근 주문" in admin.member_detail_text.text()
    admin.member_search.setText("user05")
    assert admin.member_table.rowCount() == 1
    admin.show_tab("orders")
    total = admin.order_table.rowCount()
    assert total > 50 and "합계" in admin.order_total.text()
    admin.order_search.setText("아메리카노")
    assert 0 < admin.order_table.rowCount() < total


def test_point_save_needs_member_amount_and_reason(admin):
    admin.show_tab("points")
    assert not admin.adjust_button.isEnabled()
    admin.point_table.selectRow(0)
    admin.adjust_delta.setText("+300")
    assert not admin.adjust_button.isEnabled()
    admin.adjust_reason.setText("시연 보상")
    assert admin.adjust_button.isEnabled()
    admin.point_search.setText("member2")
    assert admin.point_table.rowCount() == 1


def test_log_filters_by_kind(admin):
    admin.router.audit("admin_login", "password")        # 메뉴가 아닌 기록도 하나
    admin.menu_table.selectRow(0)
    admin.toggle_sold_out()
    admin.show_tab("log")
    everything = admin.audit_table.rowCount()
    admin.log_kind.setCurrentText("메뉴")
    assert 0 < admin.audit_table.rowCount() < everything
    admin.log_period.setCurrentText("오늘")
    assert admin.audit_table.rowCount() >= 1              # 시연 기록도 시각을 남긴다
