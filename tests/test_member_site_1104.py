"""11/04 회의: QR 회원 페이지 — 휴대폰으로 가입 · 로그인 · 내 정보 고치기 · 비밀번호 바꾸기. 주문은 없다."""
import http.cookiejar
import urllib.parse
import urllib.request

import pytest

from domain.customers import login_with_password


@pytest.fixture
def site():
    pytest.importorskip("PySide6")
    from gui.main import demo_vault
    from gui.member_site import MemberSite
    vault = demo_vault()
    server = MemberSite(lambda: vault, port=0)
    server.start()
    yield server, vault, f"http://127.0.0.1:{server.port}"
    server.stop()


def browser():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def post(opener, url, data):
    body = urllib.parse.urlencode(data, doseq=True).encode()
    with opener.open(url, body) as response:
        return response.geturl(), response.read().decode("utf-8")


def test_signup_then_kiosk_login_and_edit(site):
    server, vault, base = site
    phone = browser()
    url, text = post(phone, base + "/signup", {
        "name": "조민기", "login_id": "minki", "password": "abcd", "confirm": "abcd", "phone": "01055556666",
        "allergies": ["우유"], "privacy": "1"})
    assert url.endswith("/me?new=1") and "가입했어요" in text and "조민기 님" in text
    customer = login_with_password(vault, "minki", "abcd")            # 키오스크에서 바로 로그인 가능
    assert customer["extra"]["allergies"] == ["우유"]
    url, text = post(phone, base + "/me", {"nickname": "민기", "phone": "010-5555-7777", "birthday": "2001-02-03",
                                            "allergies": ["땅콩"], "marketing": "1"})
    assert "저장했어요" in text
    record = vault.read("customers")[customer["id"]]
    assert record["phone"] == "010-5555-7777" and record["extra"]["allergies"] == ["땅콩"]
    _, text = post(phone, base + "/password", {"current": "abcd", "password": "wxyz", "confirm": "wxyz"})
    assert "바꿨어요" in text
    assert login_with_password(vault, "minki", "wxyz")
    assert "주문" not in text or "주문 기능" not in text


def test_signup_needs_privacy_and_me_needs_login(site):
    server, vault, base = site
    _, text = post(browser(), base + "/signup", {"name": "a", "login_id": "aa11", "password": "abcd",
                                                  "confirm": "abcd", "phone": "01011112222"})
    assert "필수 개인정보" in text
    with browser().open(base + "/me") as response:
        assert response.geturl().endswith("/login")
