"""회원가입 2단계 흐름(정보 입력 → 얼굴 등록 동의 시 얼굴 화면) 테스트."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from domain import allergens
from domain.customers import validate_password_pair
from face import FakeFace
from tests.test_app_flow import AppFlowBase
from textual.widgets import Input, SelectionList


class AllergenListTest(unittest.TestCase):
    def test_official_list_and_aliases(self):
        self.assertEqual(len(allergens.OFFICIAL), 19)  # 조개류(굴·전복·홍합)를 따로 세면 22종
        self.assertEqual(allergens.normalize("달걀"), "알류(달걀 등)")
        self.assertEqual(allergens.normalize_all(["견과류", "깨", "우유", "우유"]),
                         ["기타 견과류(헤이즐넛·아몬드 등)", "참깨", "우유"])

    def test_search_by_name_and_alias(self):
        self.assertEqual(allergens.search("우유"), ["우유"])
        self.assertIn("알류(달걀 등)", allergens.search("달걀"))
        self.assertIn("조개류(굴·전복·홍합 포함)", allergens.search("굴"))
        self.assertEqual(len(allergens.search("")), len(allergens.ALLERGENS))

    def test_password_pair(self):
        validate_password_pair("abcd", "abcd")
        with self.assertRaisesRegex(ValueError, "다릅니다"):
            validate_password_pair("abcd", "abce")
        with self.assertRaisesRegex(ValueError, "4자"):
            validate_password_pair("ab", "ab")


class SignupFlowTest(AppFlowBase):
    FORM = {"#signup-name": "구름손님", "#signup-login-id": "cloud01", "#signup-password": "1234",
            "#signup-password2": "1234", "#signup-phone": "01055557777"}

    async def fill_and_pick(self, app, pilot, face: bool):
        await self.press(app, pilot, "signup")
        self.assertPage(app, "signup-page")
        app.query_one("#allergy-search", Input).value = "달걀"   # 검색하면 목록이 줄어든다
        await pilot.pause()
        box = app.query_one("#allergy-list", SelectionList)
        self.assertEqual(box.option_count, 1)
        box.select("알류(달걀 등)")
        await pilot.pause()
        app.query_one("#allergy-search", Input).value = ""      # 검색을 지워도 체크는 남는다
        await pilot.pause()
        box.select("우유")
        await pilot.pause()
        self.assertEqual(app.signup_allergies, {"알류(달걀 등)", "우유"})
        self.assertIn("2", str(app.query_one("#allergy-box").title))
        app.query_one("#privacy").value = True
        app.query_one("#face-consent").value = face
        await pilot.pause()

    def test_password_is_masked_with_asterisks_and_must_match(self):
        async def flow(app, pilot):
            await self.press(app, pilot, "signup")
            field = app.query_one("#signup-password")
            field.value = "1234"
            self.assertEqual(str(field._value), "****")
            await self.press(app, pilot, "create-member", **{**self.FORM, "#signup-password2": "9999"})
            self.assertPage(app, "signup-page")
            self.assertIn("다릅니다", self.text(app, "#status"))
        self.run_flow(flow)

    def test_without_face_consent_goes_straight_to_menu(self):
        async def flow(app, pilot):
            await self.fill_and_pick(app, pilot, face=False)
            await self.press(app, pilot, "create-member", **self.FORM)
            self.assertPage(app, "order-page")
            record = next(c for c in app.vault.read("customers").values()
                          if c["extra"]["login_id"] == "cloud01")
            self.assertEqual(record["extra"]["allergies"], ["알류(달걀 등)", "우유"])
            self.assertEqual(record["extra"]["nickname"], "구름손님")
            self.assertEqual(record["phone"], "010-5555-7777")
            self.assertFalse(record["extra"]["face_enrolled"])
        self.run_flow(flow)

    def test_with_face_consent_opens_face_page_then_menu(self):
        async def flow(app, pilot):
            app.face_provider = FakeFace()
            await self.fill_and_pick(app, pilot, face=True)
            await self.press(app, pilot, "create-member", **self.FORM)
            self.assertPage(app, "face-page")
            self.assertIn("구름손님", self.text(app, "#face-target"))
            await self.press(app, pilot, "face-start")
            self.assertPage(app, "order-page")
            record = next(c for c in app.vault.read("customers").values()
                          if c["extra"]["login_id"] == "cloud01")
            self.assertTrue(record["extra"]["face_enrolled"])
        self.run_flow(flow)

    def test_face_page_can_be_skipped(self):
        async def flow(app, pilot):
            await self.fill_and_pick(app, pilot, face=True)
            await self.press(app, pilot, "create-member", **self.FORM)
            self.assertPage(app, "face-page")
            await self.press(app, pilot, "face-skip")
            self.assertPage(app, "order-page")
            self.assertIn("나중에", self.text(app, "#status"))
        self.run_flow(flow)


if __name__ == "__main__":
    unittest.main()
