"""시연 데이터(--demo와 같음)로 화면을 차례로 열어 PNG로 저장한다. 카메라는 쓰지 않는다(FakeFace).

사용: python tools/capture_gui.py [저장 폴더]   (기본: docs/gui_screens)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication, QRadioButton

from face import FakeFace
from gui.main import KioskWindow, demo_vault


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/gui_screens")
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv[:1])
    window = KioskWindow(vault=demo_vault(), face_factory=lambda vault: FakeFace())
    window.resize(1200, 800)
    router, session = window.router, window.router.session

    def shot(name):
        app.processEvents()
        window.grab().save(str(out / f"{name}.png"))

    # 회원 주문 기록을 몇 개 만들어 My Menu가 채워지게 한다
    router.open_action("member")
    login = router.screens["login"]
    login.login_id.setText("bomin")
    shot("02_login")
    login.show_face_failure("입체 얼굴이 확인되지 않았어요 (사진·화면으로 보여요)")
    shot("02_login_fail")
    login.set_mode("password")
    shot("02B_password")
    customer = [c for c in session.vault.read("customers").values() if c["extra"]["login_id"] == "bomin"][0]
    session.login(customer)
    for _ in range(3):
        session.add("M001", {"temperature": "ICE", "size": "L", "extras": ["shot"]}, 1)
        session.insert(5000)
        session.pay()
    session.toggle_like("M003")
    session.toggle_like("M014")
    router.start_member_order(session.customer)
    shot("03_my_menu")
    menu = router.screens["menu"]
    menu.show_category("커피")
    menu.open_option("M002")
    shot("04_option_member")
    menu.popup.add_to_cart()
    shot("04A_allergy")
    menu.popup.add_to_cart(confirmed=True)
    menu.popup.change_quantity(0)
    session.add("M002", {"temperature": "HOT"}, 2)
    router.show_screen("benefit")
    benefit = router.screens["benefit"]
    [r for r in benefit.findChildren(QRadioButton) if r.property("coupon_id") == "WELCOME1"][0].setChecked(True)
    benefit.set_points(500)
    shot("06_benefit")
    router.show_screen("cash")
    cash = router.screens["cash"]
    cash.insert(10000)
    cash.insert(5000)
    cash.change_check.setChecked(True)
    shot("07_cash_member")
    cash.finish()
    shot("08_done_member")

    router.show_screen("idle")
    router.open_action("signup")
    shot("10_signup")
    router.show_screen("enroll", customer=customer)
    shot("10B_enroll")

    router.show_screen("idle")
    router.open_action("admin")
    shot("09A_admin_login")
    router.admin_id = "admin"
    router.show_screen("admin")
    shot("09B_menu")
    for tab in ("members", "events", "points"):
        router.screens["admin"].show_tab(tab)
        shot(f"09_{tab}")
    print("저장:", out)


if __name__ == "__main__":
    main()
