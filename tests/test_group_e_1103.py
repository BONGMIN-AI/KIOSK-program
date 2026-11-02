"""11/03 E묶음: 14 방문 간격 인사 · 19 생일·가입 기념 쿠폰 · 21 칭호 진행 현황 · 22 로고 이스터에그."""
import os
from datetime import date, datetime

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

from core.storage import MemoryVault
from domain import seed
from domain.visits import celebrate, easter_egg, visit_greeting


def orders_at(*times):
    return {f"O{i}": {"created_at": t, "customer": {"id": "C0002"}} for i, t in enumerate(times)}


def test_visit_greeting():
    now = datetime(2026, 11, 3, 15)
    assert visit_greeting({}, "C0002", now) == "첫 주문을 환영해요!"
    assert visit_greeting(orders_at("2026-10-31T10:00:00"), "C0002", now) == "3일 만이에요!"
    assert visit_greeting(orders_at("2026-11-02T10:00:00"), "C0002", now) == "어제도 와 주셨네요!"
    assert visit_greeting(orders_at("2026-11-03T09:00:00"), "C0002", now) == "오늘 두 번째 방문이에요!"
    assert visit_greeting(orders_at("2026-08-01T09:00:00"), "C0002", now).startswith("오랜만이에요! 94일")


def member_vault(birthday="", joined="2026-10-01T09:00:00"):
    vault = MemoryVault()
    seed.run(vault)
    customers = vault.read("customers")
    customers["C0002"]["extra"]["birthday"] = birthday
    customers["C0002"]["created_at"] = joined
    vault.write("customers", customers)
    return vault


def test_birthday_and_anniversary_coupons_once_a_year():
    vault = member_vault(birthday="1999-11-05", joined="2025-11-01T09:00:00")
    gifts = celebrate(vault, "C0002", date(2026, 11, 3))
    assert [g["title"] for g in gifts] == ["생일 축하해요!", "가입 1주년이에요!"]
    names = [c["name"] for c in vault.read("customers")["C0002"]["extra"]["coupons"]]
    assert "생일 축하 2,000원" in names and "가입 기념 1,000원" in names
    assert celebrate(vault, "C0002", date(2026, 11, 4)) == []          # 같은 해에는 한 번
    assert celebrate(member_vault(birthday="1999-12-25"), "C0002", date(2026, 11, 3)) == []


def test_easter_egg_once_per_member():
    vault = member_vault()
    assert easter_egg(vault, "C0002")["amount"] == 100
    assert easter_egg(vault, "C0002") is None


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


def test_login_greets_and_birthday_popup(window):
    router = window.router
    vault = router.session.vault
    customers = vault.read("customers")
    customers["C0003"]["extra"]["birthday"] = date.today().replace(year=2000).isoformat() \
        if (date.today().month, date.today().day) != (2, 29) else "2000-02-28"
    vault.write("customers", customers)
    router.start_member_order(customers["C0003"])
    assert router.current_name == "menu"
    assert "님," in router.notice.text()
    assert router.popup.isVisible() and router.popup.title.text() == "생일 축하해요!"
    assert router.popup.no_button.isHidden()
    assert any(c["name"] == "생일 축하 2,000원" for c in router.session.coupons())


def test_title_progress_sheet_and_logo_easter_egg(window):
    router = window.router
    router.start_member_order(router.session.vault.read("customers")["C0002"])
    router.popup.hide()
    menu = router.screens["menu"]
    assert menu.member_name.text().endswith("님 ›")
    menu.member_name.on_tap()
    assert menu.titles_sheet.isVisible() and menu.title_rows.count() == 2 * 7
    menu.titles_sheet.hide()
    before = len(router.session.coupons())
    for _ in range(4):
        menu.logo_tap()
    assert not router.popup.isVisible()
    menu.logo_tap()                                  # 다섯 번째
    assert router.popup.isVisible() and router.popup.title.text() == "숨은 쿠폰을 찾았어요!"
    assert len(router.session.coupons()) == before + 1
    router.popup.hide()
    menu.last_tap -= 2                               # 1초가 지나면 처음부터 센다
    for _ in range(5):
        menu.logo_tap()
    assert router.popup.title.text() == "이미 찾으셨네요!"
