"""11/02 B묶음: 회원 정보 수정 · 매출 요약 · 광고 배너 · 키오스크 설정 · 스마일 할인 · 쿠폰 관리."""
import os
from datetime import date

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

from core.storage import MemoryVault
from domain import seed
from domain.customers import update_member_info
from domain.kiosk_settings import DEFAULT_SLIDES, save_slides, shown_slides, validate_kiosk
from domain.sales import summary


def test_update_member_info_checks_phone_and_allergies():
    vault = MemoryVault()
    seed.run(vault)
    record = update_member_info(vault, "C0002", "새닉네임", "01099998888", "2001-02-03", ["우유", "땅콩"], True)
    assert record["phone"] == "010-9999-8888" and record["extra"]["allergies"] == ["우유", "땅콩"]
    with pytest.raises(ValueError, match="다른 회원"):
        update_member_info(vault, "C0003", "닉", "010-9999-8888")
    with pytest.raises(ValueError, match="목록에 없는"):
        update_member_info(vault, "C0003", "닉", "010-1000-0003", allergies=["초콜릿"])
    with pytest.raises(ValueError, match="생일"):
        update_member_info(vault, "C0003", "닉", "010-1000-0003", birthday="2001/2/3")


def test_sales_summary_by_period():
    orders = {
        "a": {"created_at": "2026-11-02T09:10:00", "final_total": 6000,
              "lines": [{"name": "아메리카노", "quantity": 2, "subtotal": 6000}]},
        "b": {"created_at": "2026-11-02T14:30:00", "final_total": 4500,
              "lines": [{"name": "바닐라라떼", "quantity": 1, "subtotal": 4500}],
              "tickets": [{"count": 2}]},
        "c": {"created_at": "2026-10-28T09:00:00", "final_total": 3000,
              "lines": [{"name": "아메리카노", "quantity": 1, "subtotal": 3000}]},
    }
    today = summary(orders, "오늘", date(2026, 11, 2))
    assert (today["count"], today["total"], today["average"], today["tickets"]) == (2, 10500, 5250, 2)
    assert today["top"][0] == ("아메리카노", 2, 6000)
    week = summary(orders, "최근 7일", date(2026, 11, 2))
    assert week["count"] == 3 and week["top"][0] == ("아메리카노", 3, 9000)
    assert week["hours"][week["hour_labels"].index("9")] == 2


def test_slides_and_kiosk_settings_rules():
    vault = MemoryVault()
    vault.write("settings", {})
    slides = [dict(s) for s in DEFAULT_SLIDES]
    for slide in slides:
        slide["on"] = False
    with pytest.raises(ValueError, match="한 장"):
        save_slides(vault, slides)
    slides[2]["on"] = True
    save_slides(vault, slides)
    assert shown_slides(vault.read("settings")) == [("promo_smile.webp", "", "contain")]
    assert validate_kiosk({"idle_seconds": "90"})["idle_seconds"] == 90
    with pytest.raises(ValueError, match="경고"):
        validate_kiosk({"idle_seconds": 30, "warn_seconds": 30})
    with pytest.raises(ValueError, match="사이"):
        validate_kiosk({"idle_seconds": 5})


@pytest.fixture
def window():
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


def test_admin_pages_edit_member_sales_banners_and_settings(window):
    from PySide6.QtCore import Qt
    router = window.router
    admin = router.screens["admin"]
    admin.set_sales_period("최근 30일")
    assert admin.sales_top.rowCount() > 5 and admin.sales_tiles["total"].text().endswith("원")
    admin.show_tab("members")
    assert not admin.member_edit_button.isEnabled()
    admin.member_table.selectRow(1)
    admin.edit_member()
    admin.edit_nickname.setText("딸기왕")
    admin.save_member()
    assert router.session.vault.read("customers")["C0002"]["extra"]["nickname"] == "딸기왕"
    admin.show_tab("banners")
    original_slide_count = len(admin.banners())
    admin.banner_table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    admin.show_banners(False)
    router.show_screen("home")
    assert len(router.screens["home"].slideshow.slides) == original_slide_count - 1
    router.show_screen("admin", tab="kiosk")
    admin.kiosk_fields["idle_seconds"].setText("90")
    admin.ticket_switch.setChecked(False)
    admin.save_kiosk()
    assert router.timer.interval() == 90_000 and router.warn_timer.interval() == 75_000
    assert not router.session.ticket_sales_on()
