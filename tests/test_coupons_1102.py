"""11/02 B10 쿠폰 관리: 쿠폰 종류 만들기 · 회원 발급 · 결제에서 쓰기 · 내역 상태."""
import os
from datetime import date

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

from core.storage import MemoryVault
from domain import coupons, seed
from domain.benefits import apply_benefits


@pytest.fixture
def vault():
    result = MemoryVault()
    seed.run(result)
    return result


def test_template_rules(vault):
    assert [t["id"] for t in coupons.templates(vault.read("settings", default={}))] == ["T001", "T002", "T003", "T004"]
    added = coupons.add_template(vault, {"name": "주말 500원", "amount": "500", "min_order": "", "days": "7"})
    assert added["id"] == "T005" and added["min_order"] == 0
    with pytest.raises(ValueError, match="이름"):
        coupons.validate_template({"name": " ", "amount": 500, "days": 7})
    with pytest.raises(ValueError, match="숫자"):
        coupons.validate_template({"name": "x", "amount": "오백", "days": 7})
    with pytest.raises(ValueError, match="10~50,000"):
        coupons.validate_template({"name": "x", "amount": 5, "days": 7})
    assert coupons.delete_templates(vault, ["T005", "T001"]) == 2
    assert [t["id"] for t in coupons.templates(vault.read("settings"))] == ["T002", "T003", "T004"]


def test_issue_use_and_history(vault):
    today = date(2026, 11, 2)
    assert coupons.issue(vault, ["C0002", "C0003", "없는회원"], "T001", "admin", today=today) == 2
    customer = vault.read("customers")["C0002"]
    coupon = customer["extra"]["coupons"][-1]
    assert coupon["amount"] == 1000 and coupon["expires"] == "2026-12-02"
    with pytest.raises(ValueError, match="5,000원 이상"):
        apply_benefits(3000, customer, coupon["id"], today=today.isoformat())
    assert apply_benefits(6000, customer, coupon["id"], today=today.isoformat())["final_total"] == 5000
    customer["extra"]["coupons"].remove(coupon)       # 결제에서 쓰면 사라진다
    vault.write("customers", {**vault.read("customers"), "C0002": customer})
    states = {row["customer_id"]: row["state"] for row in coupons.history(vault, today)}
    assert states == {"C0002": "사용함", "C0003": "미사용"}
    assert coupons.history(vault, date(2027, 1, 1))[0]["state"] == "기간 지남"
    with pytest.raises(ValueError, match="찾을 수 없"):
        coupons.issue(vault, ["C0002"], "T999", "admin")


def test_admin_coupon_page(qtbot_free_window):
    from PySide6.QtCore import Qt
    window = qtbot_free_window
    admin = window.router.screens["admin"]
    admin.show_tab("coupons")
    admin.set_coupon_view("issue")
    assert not admin.coupon_issue_button.isEnabled()
    admin.coupon_member_search.setText("user01")
    assert admin.coupon_member_table.rowCount() == 1
    admin.coupon_member_table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    assert admin.coupon_issue_button.isEnabled()
    admin.coupon_pick.setCurrentIndex(admin.coupon_pick.findData("T003"))
    admin.issue_coupons()
    assert "1명에게" in admin.message.text()
    admin.set_coupon_view("history")
    assert admin.coupon_history_table.rowCount() == 1
    assert admin.coupon_history_table.item(0, 5).text() == "미사용"
    admin.set_coupon_view("kinds")
    assert not admin.coupon_kind_delete.isEnabled()
    admin.coupon_name.setText("비 오는 날 300원")
    admin.coupon_amount.setText("300")
    admin.coupon_days.setText("3")
    admin.add_coupon_kind()
    assert admin.coupon_kind_table.rowCount() == 5 and admin.coupon_pick.count() == 5


@pytest.fixture
def qtbot_free_window():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from face import FakeFace
    from gui.main import KioskWindow, demo_vault
    app = QApplication.instance() or QApplication([])
    result = KioskWindow(vault=demo_vault(random_members=True), face_factory=lambda vault: FakeFace())
    result.show()
    result.router.admin_id = "admin"
    result.router.show_screen("admin", tab="sales")
    app.processEvents()
    yield result
    result.close()
    result.deleteLater()
    app.processEvents()
