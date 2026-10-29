"""seed(시연용 샘플 데이터)가 올바르게 만들어지는지 점검한다."""
import unittest

from domain.allergens import ALLERGENS
from domain.options import available_options, normalize_options
from domain.seed import make_demo_customers, make_menu

CATEGORIES = {"커피", "디카페인", "논커피", "차", "에이드", "디저트"}


class SeedMenuTest(unittest.TestCase):
    def setUp(self):
        self.menu = make_menu()
        self.by_name = {item["name"]: item for item in self.menu.values()}

    def test_sixty_items_with_unique_ids_and_names(self):
        self.assertEqual(len(self.menu), 60)
        self.assertEqual(len(self.by_name), 60)
        self.assertEqual(sorted(self.menu)[0], "M001")
        self.assertEqual(sorted(self.menu)[-1], "M060")
        self.assertEqual(self.menu["M001"]["name"], "아메리카노")   # 예전 ID 유지

    def test_every_category_has_ten_items(self):
        for category in CATEGORIES:
            items = [i for i in self.menu.values() if i["category"] == category]
            self.assertEqual(len(items), 10, category)

    def test_prices_and_stock(self):
        for item in self.menu.values():
            self.assertGreater(item["price"], 0)
            self.assertEqual(item["price"] % 100, 0, item["name"])
            self.assertEqual(item["stock"], 20)
            self.assertFalse(item["sold_out"])

    def test_allergen_names_are_standard(self):
        for item in self.menu.values():
            for name in item["allergens"]:
                self.assertIn(name, ALLERGENS, item["name"])
        self.assertIn("복숭아", self.by_name["복숭아 아이스티"]["allergens"])

    def test_decaf_has_no_caffeine(self):
        for item in self.menu.values():
            if item["category"] == "디카페인":
                self.assertTrue(item["decaf"])
                self.assertEqual(item["caffeine_mg"], 0)
        self.assertEqual(self.by_name["아메리카노"]["caffeine_mg"], 150)

    def test_drinks_have_options_and_desserts_do_not(self):
        for item in self.menu.values():
            options = available_options(item)
            if item["category"] == "디저트":
                self.assertEqual(options["temperatures"], [])
            else:
                self.assertTrue(options["temperatures"], item["name"])
                normalize_options(item, None)   # 기본값으로 고를 수 있어야 한다

    def test_special_temperatures_and_sizes(self):
        for name in ("콜드브루", "디카페인 콜드브루", "복숭아 아이스티"):
            self.assertEqual(available_options(self.by_name[name])["temperatures"], ["ICE"])
        espresso = self.by_name["에스프레소"]
        self.assertEqual(available_options(espresso)["temperatures"], ["HOT"])
        self.assertEqual(normalize_options(espresso, None)["size"], "M")
        with self.assertRaises(ValueError):
            normalize_options(espresso, {"size": "L"})


class SeedCustomerTest(unittest.TestCase):
    def test_demo_customers(self):
        customers = make_demo_customers()
        self.assertEqual([c["extra"]["login_id"] for c in customers.values()],
                         ["bomin", "member1", "member2", "member3"])
        for customer in customers.values():
            for name in customer["extra"]["allergies"]:
                self.assertIn(name, ALLERGENS)


if __name__ == "__main__":
    unittest.main()
