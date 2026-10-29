"""KIOSK 도메인 테스트."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.storage import MemoryVault
from domain.benefits import apply_benefits, max_usable_points
from domain.cart import add_item, cart_lines, change_quantity, total_price
from domain.customers import (
    allergy_warnings, find_by_phone, login_with_face, login_with_password,
    register_customer, set_face_enrolled,
)
from face import FakeFace
from domain.orders import complete_order
from domain.payment import breakdown_text, insert_cash, payment_status
from domain.seed import make_menu, run


class CartAndPaymentTest(unittest.TestCase):
    def setUp(self):
        self.menu = make_menu()

    def test_add_change_and_total(self):
        cart = add_item({}, "M001", 2)
        cart = add_item(cart, "M002")
        self.assertEqual(total_price(cart, self.menu), 10000)
        self.assertEqual(list(change_quantity(cart, "M001", 0)), ["M002"])

    def test_options_change_price_and_split_lines(self):
        cart = add_item({}, "M003", 2, {"temperature": "ICE", "size": "L", "extras": ["shot"]}, self.menu)
        cart = add_item(cart, "M003", 1, None, self.menu)
        lines = cart_lines(cart, self.menu)
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["unit_price"], 6000)  # 4,500 + L 1,000 + 샷 500 (와이어프레임 예시)
        self.assertEqual(lines[0]["option_label"], "ICE / L / 샷 1회 추가")
        self.assertEqual(total_price(cart, self.menu), 12000 + 4500)

    def test_invalid_options_rejected(self):
        with self.assertRaises(ValueError):
            add_item({}, "M031", 1, {"temperature": "HOT"}, self.menu)  # 에이드는 ICE만
        with self.assertRaises(ValueError):
            add_item({}, "M011", 1, {"extras": ["shot"]}, self.menu)  # 논커피에는 샷 없음
        with self.assertRaises(ValueError):
            add_item({}, "M041", 1, {"size": "L"}, self.menu)  # 디저트는 옵션 없음

    def test_stock_counts_all_option_lines(self):
        self.menu["M003"]["stock"] = 2
        cart = add_item({}, "M003", 2, {"temperature": "ICE"}, self.menu)
        cart = add_item(cart, "M003", 1, {"temperature": "HOT"}, self.menu)
        with self.assertRaises(ValueError):
            cart_lines(cart, self.menu)

    def test_cash_can_be_inserted_several_times(self):
        inserted = insert_cash(0, 3000)
        self.assertFalse(payment_status(5000, inserted)["paid"])
        inserted = insert_cash(inserted, 5000)
        status = payment_status(5000, inserted)
        self.assertTrue(status["paid"])
        self.assertEqual(breakdown_text(status["breakdown"]), "천원권 3장")
        with self.assertRaises(ValueError):
            insert_cash(0, 0)
        with self.assertRaises(ValueError):
            insert_cash(0, 1005)

    def test_cash_shortage_and_change(self):
        self.assertEqual(payment_status(5000, 3000)["shortage"], 2000)
        paid = payment_status(5300, 10000)
        self.assertTrue(paid["paid"])
        self.assertEqual(paid["change"], 4700)
        self.assertEqual(paid["breakdown"], {1000: 4, 500: 1, 100: 2})

    def test_stock_blocks_order(self):
        self.menu["M001"]["stock"] = 1
        with self.assertRaises(ValueError):
            total_price({"M001": 2}, self.menu)


class CustomerAndOrderTest(unittest.TestCase):
    def setUp(self):
        self.vault = MemoryVault()
        run(self.vault)
        self.vault.write("settings", {"next_order_number": 1})

    def test_register_and_find(self):
        record = register_customer(
            self.vault, "홍길동", "길동", "01012345678",
            "gildong", "pass1234",
            allergies=["우유"], privacy_agreed=True,
        )
        self.assertEqual(find_by_phone(self.vault, "010 1234 5678")["id"], record["id"])

    def test_required_consent(self):
        with self.assertRaises(ValueError):
            register_customer(
                self.vault, "홍길동", "길동", "01012345678",
                "gildong", "pass1234",
            )

    def test_member_face_and_password_login(self):
        set_face_enrolled(self.vault, "C0001", True)
        self.assertEqual(login_with_face(self.vault, "bomin", FakeFace())["id"], "C0001")
        self.assertEqual(login_with_password(self.vault, "bomin", "1234")["id"], "C0001")
        with self.assertRaises(ValueError):
            login_with_password(self.vault, "bomin", "wrong")

    def test_allergy_warning(self):
        customer = self.vault.read("customers")["C0001"]
        warnings = allergy_warnings(customer, [{"menu_id": "M002", "name": "카페라떼"}], self.vault.read("menu"))
        self.assertTrue(warnings)

    def test_complete_member_order(self):
        order = complete_order(self.vault, {"M001": 2}, 10000, "C0001")
        self.assertEqual(order["id"], "O0001")
        self.assertEqual(order["change"], 4000)
        self.assertEqual(self.vault.read("menu")["M001"]["stock"], 18)
        self.assertEqual(self.vault.read("customers")["C0001"]["extra"]["points"], 1460)

    def test_insufficient_cash_changes_nothing(self):
        before = self.vault.read("menu")["M001"]["stock"]
        with self.assertRaisesRegex(ValueError, "부족"):
            complete_order(self.vault, {"M001": 1}, 1000)
        self.assertEqual(self.vault.read("menu")["M001"]["stock"], before)

    def test_fifth_visit_issues_coupon(self):
        order = complete_order(self.vault, {"M001": 1}, 3000, "C0002")
        self.assertIn("5회", order["issued_coupon"])
        coupons = self.vault.read("customers")["C0002"]["extra"]["coupons"]
        self.assertEqual(len(coupons), 1)
        self.assertEqual(coupons[0]["amount"], 1000)

    def test_wireframe_benefit_example(self):
        """와이어프레임 06~08: 12,000원 - 쿠폰 1,000원 - 500P = 10,500원, 적립 105P."""
        cart = add_item({}, "M003", 2, {"temperature": "ICE", "size": "L", "extras": ["shot"]},
                        self.vault.read("menu"))
        order = complete_order(self.vault, cart, 20000, "C0001", "WELCOME1", 500)
        self.assertEqual(order["final_total"], 10500)
        self.assertEqual(order["change"], 9500)
        self.assertEqual(order["earned_points"], 105)
        customer = self.vault.read("customers")["C0001"]["extra"]
        self.assertEqual(customer["points"], 1400 - 500 + 105)
        self.assertEqual([c["id"] for c in customer["coupons"]], ["WELCOME2"])

    def test_benefit_rules(self):
        customer = self.vault.read("customers")["C0001"]
        with self.assertRaisesRegex(ValueError, "100P"):
            apply_benefits(12000, customer, None, 150)
        with self.assertRaisesRegex(ValueError, "보유"):
            apply_benefits(12000, customer, None, 2000)
        with self.assertRaisesRegex(ValueError, "이상"):
            apply_benefits(4000, customer, "WELCOME1")
        with self.assertRaises(ValueError):
            apply_benefits(4000, None, None, 100)
        self.assertEqual(max_usable_points(1250, 1400), 1200)

    def test_shortage_after_discount_changes_nothing(self):
        before = self.vault.read("customers")["C0001"]["extra"]["points"]
        with self.assertRaisesRegex(ValueError, "부족"):
            complete_order(self.vault, {"M001": 4}, 10000, "C0001", "WELCOME1", 500)
        self.assertEqual(self.vault.read("customers")["C0001"]["extra"]["points"], before)

    def test_legacy_string_coupon_still_usable(self):
        customers = self.vault.read("customers")
        customers["C0002"]["extra"]["coupons"] = ["방문 5회 축하 1,000원 쿠폰"]
        self.vault.write("customers", customers)
        order = complete_order(self.vault, {"M001": 1}, 2000, "C0002", "LEGACY1")
        self.assertEqual(order["final_total"], 2000)


class SeedTest(unittest.TestCase):
    def test_menu_has_at_least_fifty_items_with_caffeine(self):
        menu = make_menu()
        self.assertGreaterEqual(len(menu), 50)
        decaf = [m for m in menu.values() if m["category"] == "디카페인"]
        self.assertEqual(len(decaf), 10)
        self.assertTrue(all(m["decaf"] and m["caffeine_mg"] == 0 for m in decaf))
        americano = next(m for m in menu.values() if m["name"] == "아메리카노")
        self.assertEqual(americano["caffeine_mg"], 150)
        self.assertEqual(menu["M001"]["name"], "아메리카노")   # 기존 메뉴 ID는 그대로

    def test_seed_faces_require_real_registration(self):
        vault = MemoryVault()
        run(vault)
        self.assertFalse(vault.read("customers")["C0001"]["extra"]["face_enrolled"])
        self.assertEqual(vault.read("face_profiles"), {})


if __name__ == "__main__":
    unittest.main()
