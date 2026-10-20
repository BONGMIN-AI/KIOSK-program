"""포인트 정책·기간 이벤트·포인트 조정·다국어 문구 테스트."""
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.storage import MemoryVault
from domain import policy as P
from domain.benefits import apply_benefits, max_usable_points
from domain.cart import add_item, cart_lines
from domain.customers import adjust_points, save_preferences
from domain.orders import complete_order
from domain.seed import make_menu, run
from ui import i18n

WED_15 = datetime(2026, 10, 21, 15, 0)   # 수요일 오후 3시
SAT_10 = datetime(2026, 10, 24, 10, 0)   # 토요일 오전 10시

COFFEE_EVENT = {"name": "커피 트리플", "start": "2026-10-20", "end": "2026-10-31",
                "weekdays": "평일", "hours": "14-17", "categories": "커피", "rate": 3}


class EventRuleTest(unittest.TestCase):
    def test_event_window_by_date_weekday_and_hour(self):
        event = P.validate_event(COFFEE_EVENT)
        self.assertTrue(P.event_is_active(event, WED_15))
        self.assertFalse(P.event_is_active(event, SAT_10))                    # 주말
        self.assertFalse(P.event_is_active(event, datetime(2026, 10, 21, 17)))  # 17시는 제외
        self.assertFalse(P.event_is_active(event, datetime(2026, 11, 2, 15)))   # 기간 끝
        self.assertEqual(P.event_status(event, datetime(2026, 10, 1)), "예정")
        self.assertEqual(P.event_status({**event, "enabled": False}, WED_15), "꺼짐")

    def test_invalid_events_rejected(self):
        for bad in ({**COFFEE_EVENT, "end": "2026-10-01"}, {**COFFEE_EVENT, "weekdays": "월요일"},
                    {**COFFEE_EVENT, "hours": "17-14"}, {**COFFEE_EVENT, "rate": 0},
                    {**COFFEE_EVENT, "start": "10/20"}, {**COFFEE_EVENT, "name": ""}):
            with self.assertRaises(ValueError):
                P.validate_event(bad)

    def test_upsert_and_remove_event(self):
        policy, first = P.upsert_event(P.load_policy({}), COFFEE_EVENT)
        policy, second = P.upsert_event(policy, {**COFFEE_EVENT, "name": "주말 보너스", "weekdays": "주말"})
        self.assertEqual([first["id"], second["id"]], ["EV001", "EV002"])
        policy, edited = P.upsert_event(policy, {**COFFEE_EVENT, "id": "EV001", "rate": 5})
        self.assertEqual(policy["events"][0]["rate"], 5)
        policy = P.remove_event(policy, "EV001")
        self.assertEqual([e["id"] for e in policy["events"]], ["EV002"])


class PointCalculationTest(unittest.TestCase):
    def setUp(self):
        self.menu = make_menu()
        cart = add_item({}, "M001", 2, None, self.menu)   # 아메리카노 6,000 (커피)
        cart = add_item(cart, "M041", 1, None, self.menu)  # 크루아상 3,500 (디저트)
        self.lines = cart_lines(cart, self.menu)

    def test_default_policy_is_one_percent(self):
        result = P.calculate_points(P.load_policy({}), self.lines, self.menu, 9500, WED_15)
        self.assertEqual(result["earned"], 95)

    def test_category_event_only_boosts_that_category(self):
        policy, _ = P.upsert_event(P.load_policy({}), COFFEE_EVENT)
        result = P.calculate_points(policy, self.lines, self.menu, 9500, WED_15)
        self.assertEqual(result["earned"], 180 + 35)        # 커피 3% + 디저트 1%
        self.assertEqual(result["events"], ["커피 트리플"])
        self.assertEqual(P.calculate_points(policy, self.lines, self.menu, 9500, SAT_10)["earned"], 95)

    def test_discount_is_shared_by_line_ratio(self):
        policy, _ = P.upsert_event(P.load_policy({}), {**COFFEE_EVENT, "rate": 10})
        # 9,500원 중 1,900원 할인 → 실결제 7,600원: 커피 4,800 × 10% + 디저트 2,800 × 1%
        self.assertEqual(P.calculate_points(policy, self.lines, self.menu, 7600, WED_15)["earned"], 480 + 28)

    def test_bonus_points_need_min_order(self):
        policy, _ = P.upsert_event(P.load_policy({}), {
            "name": "만원 이상 보너스", "start": "2026-10-01", "end": "2026-12-31",
            "bonus_points": 300, "min_order": 10000})
        self.assertEqual(P.calculate_points(policy, self.lines, self.menu, 9500, WED_15)["bonus"], 0)
        self.assertEqual(P.calculate_points(policy, self.lines, self.menu, 12000, WED_15)["bonus"], 300)

    def test_policy_validation(self):
        with self.assertRaises(ValueError):
            P.validate_policy({"base_rate": 30})
        with self.assertRaises(ValueError):
            P.validate_policy({"point_unit": 7})
        with self.assertRaises(ValueError):
            P.validate_policy({"point_unit": 100, "min_use": 150})
        self.assertEqual(P.validate_policy({"base_rate": "2.5"})["base_rate"], 2.5)


class PolicyInOrderTest(unittest.TestCase):
    def setUp(self):
        self.vault = MemoryVault()
        run(self.vault)
        self.vault.write("settings", {"next_order_number": 1})

    def set_policy(self, **changes):
        policy = P.validate_policy({**P.load_policy({}), **changes})
        self.vault.write("settings", {"next_order_number": 1, "point_policy": policy})
        return policy

    def test_admin_rate_and_event_apply_to_order_and_history(self):
        policy = self.set_policy(base_rate=2)
        policy, _ = P.upsert_event(policy, COFFEE_EVENT)
        self.vault.write("settings", {"next_order_number": 1, "point_policy": policy})
        order = complete_order(self.vault, {"M001": 2, "M041": 1}, 10000, "C0001", now=WED_15)
        self.assertEqual(order["earned_points"], 180 + 70)  # 커피 3%, 디저트 기본 2%
        self.assertEqual(order["point_events"], ["커피 트리플"])
        history = self.vault.read("customers")["C0001"]["extra"]["point_history"]
        self.assertEqual(history[-1]["delta"], 250)
        self.assertIn("커피 트리플", history[-1]["reason"])

    def test_visit_coupon_rule_is_adjustable(self):
        # C0003은 방문 3회. 기본(5회마다)이면 4번째 방문에 쿠폰이 없지만, 4회마다로 바꾸면 나온다.
        self.set_policy(visit_coupon_every=4, visit_coupon_amount=2000, visit_coupon_days=30)
        order = complete_order(self.vault, {"M001": 1}, 3000, "C0003", now=WED_15)
        self.assertIn("2,000원", order["issued_coupon"])
        coupon = self.vault.read("customers")["C0003"]["extra"]["coupons"][-1]
        self.assertEqual(coupon["amount"], 2000)
        # 0으로 두면 방문 쿠폰을 끈다 (C0002는 5번째 방문이지만 발행되지 않음)
        self.set_policy(visit_coupon_every=0)
        self.assertIsNone(complete_order(self.vault, {"M001": 1}, 3000, "C0002", now=WED_15)["issued_coupon"])

    def test_point_use_rules_follow_policy(self):
        policy = self.set_policy(point_unit=10, min_use=500, max_use_percent=50)
        customer = self.vault.read("customers")["C0001"]
        with self.assertRaisesRegex(ValueError, "최소"):
            apply_benefits(4000, customer, None, 300, policy=policy)
        with self.assertRaisesRegex(ValueError, "50%"):
            apply_benefits(2000, customer, None, 1010, policy=policy)
        self.assertEqual(apply_benefits(4000, customer, None, 1230, policy=policy)["final_total"], 2770)
        self.assertEqual(max_usable_points(4000, 1400, policy), 1400)
        self.assertEqual(max_usable_points(800, 1400, policy), 0)  # 50%=400 < 최소 500


class PointAdjustAndPreferenceTest(unittest.TestCase):
    def setUp(self):
        self.vault = MemoryVault()
        run(self.vault)

    def test_adjust_points_needs_reason_and_keeps_history(self):
        with self.assertRaisesRegex(ValueError, "사유"):
            adjust_points(self.vault, "C0002", 300, "", "admin")
        with self.assertRaisesRegex(ValueError, "0보다"):
            adjust_points(self.vault, "C0002", -5000, "오류", "admin")
        record = adjust_points(self.vault, "C0002", 300, "이벤트 누락 적립", "admin")
        self.assertEqual(record["extra"]["points"], 1200)
        entry = record["extra"]["point_history"][-1]
        self.assertEqual((entry["delta"], entry["by"], entry["balance"]), (300, "admin", 1200))

    def test_preferences_saved_on_member_card(self):
        record = save_preferences(self.vault, "C0001", {"language": "en", "large_mode": True, "evil": 1})
        self.assertEqual(record["extra"]["preferences"], {"language": "en", "large_mode": True})


class I18nTest(unittest.TestCase):
    def test_every_text_has_all_languages(self):
        self.assertEqual(i18n.missing_translations(), [])

    def test_every_menu_has_english_name(self):
        missing = [item["name"] for item in make_menu().values() if item["name"] not in i18n.MENU_NAMES_EN]
        self.assertEqual(missing, [])

    def test_money_and_change_text(self):
        self.assertEqual(i18n.won("en", 12000), "₩12,000")
        self.assertEqual(i18n.change_text("en", {1000: 2, 500: 1}), "2 × ₩1,000 bill · 1 × ₩500 coin")
        self.assertEqual(i18n.change_text("ko", {1000: 2}), "천원권 2장")
        self.assertEqual(i18n.option_text("ja", {"temperature": "ICE", "size": "L", "extras": ["shot"]}),
                         "ICE / L / ショット追加")


if __name__ == "__main__":
    unittest.main()
