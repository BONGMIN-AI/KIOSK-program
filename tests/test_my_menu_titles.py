"""3일차 새 기능: 이벤트 테마, 잔돈 포인트, 칭호, My Menu."""
import unittest
from datetime import date, datetime

from core import schema
from core.storage import MemoryVault
from domain import seed
from domain.my_menu import (caffeine_of, caffeine_report, likes_of, recent_order,
                            toggle_like, usual_order)
from domain.orders import complete_order
from domain.policy import banner_message, display_event, load_policy, validate_event
from domain.titles import count_stats, progress

ICE_AMERICANO = {"M001|ICE|M": {"menu_id": "M001", "options": {"temperature": "ICE", "size": "M", "extras": []},
                                "quantity": 1}}


def make_vault():
    vault = MemoryVault()
    vault.write("settings", dict(schema.DEFAULT_SETTINGS))
    seed.run(vault)
    return vault


class EventThemeTest(unittest.TestCase):
    def test_theme_default_and_check(self):
        base = {"name": "테스트", "start": "2026-10-01", "end": "2026-10-31", "rate": 2}
        self.assertEqual(validate_event(base)["theme"], "basic")
        self.assertEqual(validate_event({**base, "theme": "festival"})["theme"], "festival")
        with self.assertRaises(ValueError):
            validate_event({**base, "theme": "rainbow"})

    def test_banner_message_auto(self):
        event = validate_event({"name": "커피 이벤트", "start": "2026-10-01", "end": "2026-10-31",
                                "categories": ["커피"], "rate": 3, "bonus_points": 200, "min_order": 10000})
        self.assertEqual(banner_message(event), "회원은 커피 3% 적립 + 1만원 이상 200P · 10/31까지")

    def test_display_event_from_demo_policy(self):
        vault = make_vault()
        seed.add_demo_events(vault)
        policy = load_policy(vault.read("settings"))
        shown = display_event(policy, datetime(2026, 10, 23, 12))
        self.assertEqual(shown["name"], "가을 더블 포인트")
        self.assertEqual(shown["theme"], "season")
        self.assertIsNone(display_event(policy, datetime(2026, 12, 1, 12)))


class ChangeToPointsTest(unittest.TestCase):
    def test_member_change_becomes_points(self):
        vault = make_vault()
        before = vault.read("customers")["C0002"]["extra"]["points"]
        order = complete_order(vault, {"M001": 1}, 5000, "C0002", change_to_points=True)
        self.assertEqual(order["change"], 0)
        self.assertEqual(order["change_points"], 2000)
        after = vault.read("customers")["C0002"]["extra"]
        self.assertEqual(after["points"], before + order["earned_points"] + 2000)
        self.assertIn("잔돈 적립", after["point_history"][-1]["reason"])

    def test_guest_cannot_and_default_is_cash(self):
        vault = make_vault()
        with self.assertRaises(ValueError):
            complete_order(vault, {"M001": 1}, 5000, None, change_to_points=True)
        order = complete_order(vault, {"M001": 1}, 5000, "C0002")
        self.assertEqual((order["change"], order["change_points"]), (2000, 0))


class TitleTest(unittest.TestCase):
    def test_first_order_and_ice_americano(self):
        vault = make_vault()
        first = complete_order(vault, ICE_AMERICANO, 3000, "C0003")
        self.assertEqual(first["new_titles"], ["새내기"])
        self.assertEqual(first["customer"]["title"], "새내기")
        nine = {"M001|ICE|M": {**ICE_AMERICANO["M001|ICE|M"], "quantity": 9}}
        tenth = complete_order(vault, nine, 27000, "C0003")
        self.assertIn("아아수호자", tenth["new_titles"])
        record = vault.read("customers")["C0003"]["extra"]
        self.assertEqual(record["titles"][:2], ["새내기", "아아수호자"])
        again = complete_order(vault, ICE_AMERICANO, 3000, "C0003")
        self.assertEqual(again["new_titles"], [])          # 같은 칭호를 두 번 주지 않는다

    def test_progress_counts(self):
        menu = seed.make_menu()
        stats = count_stats([[{"menu_id": "M051", "name": "디카페인 아메리카노", "quantity": 2,
                               "options": {}}]], menu)
        decaf = next(p for p in progress(stats) if p["title"] == "디카페인 지킴이")
        self.assertEqual((decaf["count"], decaf["goal"], decaf["done"]), (2, 5, False))


class MyMenuTest(unittest.TestCase):
    def test_usual_order_is_most_frequent(self):
        vault = make_vault()
        self.assertIsNone(usual_order({}, "C0001", vault.read("menu")))
        complete_order(vault, {"M002": 1}, 4000, "C0004")
        complete_order(vault, ICE_AMERICANO, 3000, "C0004")
        complete_order(vault, ICE_AMERICANO, 3000, "C0004")
        usual = usual_order(vault.read("orders"), "C0004", vault.read("menu"))
        self.assertEqual((usual["name"], usual["options"]["temperature"], usual["times"]), ("아메리카노", "ICE", 2))

    def test_toggle_like(self):
        vault = make_vault()
        self.assertTrue(toggle_like(vault, "C0001", "M003"))
        self.assertEqual(likes_of(vault.read("customers")["C0001"]), ["M003"])
        self.assertFalse(toggle_like(vault, "C0001", "M003"))
        self.assertEqual(likes_of(vault.read("customers")["C0001"]), [])

    def test_caffeine_rules(self):
        menu = seed.make_menu()
        americano, decaf = menu["M001"], menu["M051"]
        self.assertEqual(caffeine_of(americano, {"size": "M", "extras": []}), 150)
        self.assertEqual(caffeine_of(americano, {"size": "L", "extras": ["shot"]}), 270)   # 150×1.3 + 75
        self.assertEqual(caffeine_of(americano, None, 2), 300)
        self.assertEqual(caffeine_of(decaf, {"size": "L", "extras": ["shot"]}), 0)

    def test_weekly_report(self):
        vault = make_vault()
        for day, quantity in ((date(2026, 10, 13), 1), (date(2026, 10, 19), 1), (date(2026, 10, 20), 1)):
            when = datetime(day.year, day.month, day.day, 10)
            complete_order(vault, {"M001": quantity}, 3000, "C0001", now=when)
        report = caffeine_report(vault.read("orders"), "C0001", vault.read("menu"), date(2026, 10, 20))
        self.assertEqual(report["this_week"][:2], [150, 150])   # 10/19(월)·10/20(화)
        self.assertEqual(report["total"], 300)
        self.assertEqual(report["last_week_total"], 150)
        self.assertEqual(report["change_percent"], 100)
        self.assertEqual(report["message"], "이번 주는 매일 카페인을 드셨네요")
        self.assertTrue(report["suggest_decaf"])


if __name__ == "__main__":
    unittest.main()
