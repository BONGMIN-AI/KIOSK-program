"""Textual 화면 흐름 테스트. 화면을 띄우지 않고(headless) 실제 버튼 흐름을 따라간다.

카메라가 필요한 얼굴 로그인은 여기서 다루지 않는다(test_kiosk.py 의 FakeFace 테스트 참고).
"""
import asyncio
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as kiosk_app
import config
from core import auth, schema
from domain import seed
from textual.widgets import Input, Select, Static

TEST_PASSWORD = "test-admin-pw"


class AppFlowBase(unittest.TestCase):
    """화면 흐름 테스트 공통 준비(임시 금고·앱 실행·버튼 누르기). 테스트는 하위 클래스에 둔다."""
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kiosk-flow-"))
        self.old_paths = (config.DATA_DIR, config.KEYSTORE_PATH)
        config.DATA_DIR = self.tmp
        config.KEYSTORE_PATH = self.tmp / "keystore.json"
        auth.init_keystore(config.KEYSTORE_PATH, "admin", TEST_PASSWORD, iterations=1000)
        vault = auth.unlock(config.KEYSTORE_PATH, config.DATA_DIR, "admin", TEST_PASSWORD)
        vault.write("settings", dict(schema.DEFAULT_SETTINGS))
        seed.run(vault)

    def tearDown(self):
        config.DATA_DIR, config.KEYSTORE_PATH = self.old_paths
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_flow(self, flow):
        async def runner():
            app = kiosk_app.KioskApp()
            async with app.run_test(size=(130, 60)) as pilot:
                await self.press(app, pilot, "unlock", **{"#admin-id": "admin", "#admin-password": TEST_PASSWORD})
                self.assertPage(app, "home-page")
                await flow(app, pilot)
        asyncio.run(runner())

    async def press(self, app, pilot, button_id, **inputs):
        for selector, value in inputs.items():
            app.query_one(selector, Input).value = value
        await app.on_button_pressed(type("E", (), {"button": app.query_one(f"#{button_id}")})())
        await pilot.pause()

    def assertPage(self, app, page_id):
        self.assertTrue(app.query_one(f"#{page_id}").has_class("active"), f"{page_id} 화면이 아닙니다")

    def text(self, app, selector):
        return str(app.query_one(selector, Static).render())


class AppFlowTest(AppFlowBase):
    def test_guest_order_cash_shortage_then_change(self):
        async def flow(app, pilot):
            await self.press(app, pilot, "guest-order")
            await self.press(app, pilot, "menu-M001")          # 아메리카노 3,000원
            self.assertPage(app, "option-page")
            await self.press(app, pilot, "option-add", **{"#opt-quantity": "2"})
            self.assertPage(app, "order-page")
            await self.press(app, pilot, "go-checkout")
            self.assertPage(app, "payment-page")            # 비회원은 혜택 화면을 건너뛴다
            await self.press(app, pilot, "insert-cash", **{"#cash": "3000"})
            await self.press(app, pilot, "pay")
            self.assertPage(app, "payment-page")            # 3,000원 부족 → 결제가 끝나지 않는다
            self.assertIn("부족", self.text(app, "#status"))
            await self.press(app, pilot, "cash-5000")
            await self.press(app, pilot, "pay")
            self.assertPage(app, "receipt-page")
            receipt = self.text(app, "#receipt")
            self.assertIn("비회원", receipt)
            self.assertIn("거스름돈 2,000원", receipt)
            self.assertIn("천원권 2장", receipt)
        self.run_flow(flow)

    def test_member_options_benefits_and_receipt(self):
        async def flow(app, pilot):
            await self.press(app, pilot, "member-order")
            await self.press(app, pilot, "member-password-login",
                             **{"#member-login-id": "bomin", "#member-login-password": "1234"})
            self.assertPage(app, "order-page")
            self.assertIn("MVP보민", self.text(app, "#member-card"))
            await self.press(app, pilot, "menu-M003")          # 바닐라라떼: 우유 알레르기 경고
            self.assertIn("알레르기", self.text(app, "#option-warning"))
            app.query_one("#opt-temperature", Select).value = "ICE"
            app.query_one("#opt-size", Select).value = "L"
            app.query_one("#opt-shot").value = True
            await self.press(app, pilot, "option-add", **{"#opt-quantity": "2"})
            await self.press(app, pilot, "go-checkout")
            self.assertPage(app, "benefit-page")
            app.query_one("#benefit-coupon", Select).value = "WELCOME1"
            await self.press(app, pilot, "benefit-pay", **{"#benefit-points": "500"})
            self.assertPage(app, "payment-page")
            self.assertIn("10,500원", self.text(app, "#payment-total"))
            await self.press(app, pilot, "cash-10000")
            await self.press(app, pilot, "cash-1000")
            await self.press(app, pilot, "pay")
            receipt = self.text(app, "#receipt")
            self.assertIn("MVP보민", receipt)
            self.assertIn("+105P", receipt)
            self.assertIn("500원 1개", receipt)
        self.run_flow(flow)

    def test_admin_requires_login_and_kiosk_cannot_quit_from_home(self):
        async def flow(app, pilot):
            await pilot.press("ctrl+q")
            self.assertTrue(app.is_running)                 # 손님 화면에서는 종료되지 않는다
            await self.press(app, pilot, "admin")
            self.assertPage(app, "admin-login-page")
            await self.press(app, pilot, "op-password-login", **{"#op-id": "admin", "#op-password": "wrong"})
            self.assertPage(app, "admin-login-page")
            self.assertIsNone(app.admin_id)
            await self.press(app, pilot, "op-password-login", **{"#op-id": "admin", "#op-password": TEST_PASSWORD})
            self.assertPage(app, "admin-page")
            app.query_one("#admin-menu-id", Select).value = "M001"
            await pilot.pause()
            await self.press(app, pilot, "toggle-sold-out")
            self.assertTrue(app.vault.read("menu")["M001"]["sold_out"])
            await self.press(app, pilot, "delete-menu")     # 첫 번째는 확인만
            self.assertIn("M001", app.vault.read("menu"))
            await self.press(app, pilot, "admin-logout")
            self.assertPage(app, "home-page")
            self.assertIsNone(app.admin_id)
        self.run_flow(flow)

    def test_new_menu_can_be_added(self):
        async def flow(app, pilot):
            await self.press(app, pilot, "admin")
            await self.press(app, pilot, "op-password-login", **{"#op-id": "admin", "#op-password": TEST_PASSWORD})
            await self.press(app, pilot, "save-menu", **{"#admin-menu-name": "시즌 라떼", "#admin-category": "커피",
                                                        "#admin-price": "5200", "#admin-stock": "5"})
            menu = app.vault.read("menu")
            self.assertEqual(len(menu), 51)
            self.assertEqual(menu["M051"]["name"], "시즌 라떼")
        self.run_flow(flow)


    def test_language_switch_translates_customer_screens(self):
        async def flow(app, pilot):
            app.query_one("#pref-language", Select).value = "en"
            await pilot.pause()
            self.assertEqual(app.lang, "en")
            self.assertIn("How would you like to order", self.text(app, "#home-title"))
            await self.press(app, pilot, "guest-order")
            self.assertIn("Americano", str(app.query_one("#menu-M001").label))
            await self.press(app, pilot, "menu-M001")
            await self.press(app, pilot, "option-add")
            await self.press(app, pilot, "go-checkout")
            await self.press(app, pilot, "cash-5000")
            await self.press(app, pilot, "pay")
            receipt = self.text(app, "#receipt")
            self.assertIn("Guest", receipt)
            self.assertIn("₩2,000", receipt)
            self.assertIn("2 × ₩1,000 bill", receipt)
            await self.press(app, pilot, "next-customer")
            self.assertEqual(app.lang, "ko")                   # 다음 손님은 기본 언어로 돌아간다
        self.run_flow(flow)

    def test_accessibility_modes_and_member_preferences(self):
        async def flow(app, pilot):
            await self.press(app, pilot, "member-order")
            await self.press(app, pilot, "member-password-login",
                             **{"#member-login-id": "bomin", "#member-login-password": "1234"})
            app.query_one("#pref-contrast").value = True
            app.query_one("#pref-large").value = True
            await pilot.pause()
            self.assertTrue(app.screen.has_class("high-contrast"))
            self.assertTrue(app.screen.has_class("large"))
            prefs = app.vault.read("customers")["C0001"]["extra"]["preferences"]
            self.assertTrue(prefs["high_contrast"] and prefs["large_mode"])
            await self.press(app, pilot, "home")
            self.assertFalse(app.screen.has_class("high-contrast"))  # 다음 손님은 기본값
            await self.press(app, pilot, "member-order")
            await self.press(app, pilot, "member-password-login",
                             **{"#member-login-id": "bomin", "#member-login-password": "1234"})
            await pilot.pause()
            self.assertTrue(app.screen.has_class("high-contrast"))   # 회원 카드 설정 자동 적용
            self.assertTrue(app.screen.has_class("large"))
        self.run_flow(flow)

    def test_admin_policy_event_and_point_adjustment(self):
        async def flow(app, pilot):
            await self.press(app, pilot, "admin")
            await self.press(app, pilot, "op-password-login", **{"#op-id": "admin", "#op-password": TEST_PASSWORD})
            await self.press(app, pilot, "view-policy")
            await self.press(app, pilot, "save-policy", **{"#pol-base-rate": "5"})
            self.assertEqual(app.policy()["base_rate"], 5.0)
            today = __import__("datetime").date.today().isoformat()
            await self.press(app, pilot, "save-event", **{
                "#ev-name": "오늘 보너스", "#ev-start": today, "#ev-end": today, "#ev-weekdays": "",
                "#ev-hours": "", "#ev-categories": "", "#ev-rate": "", "#ev-bonus": "200", "#ev-min-order": "0"})
            self.assertEqual(app.policy()["events"][0]["id"], "EV001")
            await self.press(app, pilot, "view-customers")
            app.query_one("#admin-customer-id", Select).value = "C0002"
            await pilot.pause()
            await self.press(app, pilot, "adjust-points", **{"#adjust-delta": "-400", "#adjust-reason": "중복 적립 정정"})
            self.assertEqual(app.vault.read("customers")["C0002"]["extra"]["points"], 500)
            await self.press(app, pilot, "view-audit")
            self.assertIn("정상", self.text(app, "#status"))
            await self.press(app, pilot, "admin-logout")
            # 회원 주문: 3,000원 × 5% = 150P + 이벤트 보너스 200P
            await self.press(app, pilot, "member-order")
            await self.press(app, pilot, "member-password-login",
                             **{"#member-login-id": "member1", "#member-login-password": "1234"})
            self.assertIn("오늘 보너스", self.text(app, "#event-banner"))
            await self.press(app, pilot, "menu-M001")
            await self.press(app, pilot, "option-add")
            await self.press(app, pilot, "go-checkout")
            await self.press(app, pilot, "benefit-skip")
            await self.press(app, pilot, "cash-5000")
            await self.press(app, pilot, "pay")
            receipt = self.text(app, "#receipt")
            self.assertIn("+350P", receipt)
            self.assertIn("오늘 보너스", receipt)
        self.run_flow(flow)


if __name__ == "__main__":
    unittest.main()
