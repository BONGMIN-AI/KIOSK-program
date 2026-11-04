"""11/02 C묶음: 대기 화면 접근 감지(1m) · 주문 중 자리 비움 → '로그아웃할까요? (10) · 아니요'."""
import os
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest

from face.presence import FakePresence, face_distance


def test_face_width_distance():
    assert face_distance(66) == pytest.approx(1.0)
    assert face_distance(120) < 0.6


@pytest.fixture
def kiosk():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from face import FakeFace
    from gui.main import KioskWindow, demo_vault
    app = QApplication.instance() or QApplication([])
    sensor = FakePresence()
    window = KioskWindow(vault=demo_vault(), face_factory=lambda vault: FakeFace(), presence=sensor)
    window.show()
    window.router.presence_timer.stop()      # 시험에서는 check_presence를 직접 부른다
    app.processEvents()
    yield window, sensor
    window.close()
    window.deleteLater()
    app.processEvents()


def test_approach_starts_from_idle(kiosk):
    window, sensor = kiosk
    router = window.router
    router.check_presence()
    assert router.screens["idle"].show_approach_hint
    sensor.distance = 2.0                       # 멀리 지나가는 사람은 무시
    for _ in range(4):
        router.check_presence()
    assert router.current_name == "idle"
    sensor.distance = 0.8
    router.check_presence()
    assert router.current_name == "idle"        # 1초(2번)는 머물러야
    router.check_presence()
    assert router.current_name == "idle" and router.choosing_dine()   # 다가오면 대기 화면 위에 매장 / 포장


def test_away_asks_then_leaves_and_refunds(kiosk):
    window, sensor = kiosk
    router = window.router
    router.show_screen("menu")
    router.session.insert(1000)
    sensor.distance = None
    router.last_seen = time.monotonic() - router.away_seconds - 1
    router.check_presence()
    box = router.away_box
    assert box.isVisible() and box.yes_button.text() == "처음 화면으로 (10)"
    assert "1,000원" in box.text.text()
    box.count_down()
    assert box.yes_button.text() == "처음 화면으로 (9)"
    box.left = 1
    box.count_down()                            # 0초 → 처음 화면, 현금 반환
    assert router.current_name == "idle" and router.session.inserted == 0 and not box.isVisible()


def test_away_no_and_return_close_box(kiosk):
    window, sensor = kiosk
    router = window.router
    router.show_screen("menu")
    router.last_seen = time.monotonic() - 100
    router.check_presence()
    assert router.away_box.isVisible()
    router.away_box.no_button.click()           # '아니요'
    assert not router.away_box.isVisible() and router.current_name == "menu"
    router.last_seen = time.monotonic() - 100
    router.check_presence()
    sensor.distance = 0.7                       # 11/03: 돌아와도 닫히지 않는다 (다음 사람이 로그아웃을 누를 수 있게)
    router.check_presence()
    assert router.away_box.isVisible() and router.current_name == "menu"


def test_presence_off_in_settings_and_camera_handover(kiosk):
    window, sensor = kiosk
    router = window.router
    settings = router.session.vault.read("settings")
    settings["presence"] = False
    router.session.vault.write("settings", settings)
    router.check_presence()
    assert not router.screens["idle"].show_approach_hint
    router.show_screen("menu")
    router.last_seen = time.monotonic() - 100
    router.check_presence()
    assert not router.away_box.isVisible()      # 꺼 두면 묻지 않는다
    seen = []
    router.run_face(lambda face: seen.append(sensor.paused))
    assert seen == [True] and not sensor.paused  # 얼굴 인증 동안 카메라를 놓고, 끝나면 다시


def test_sitting_close_does_not_restart_until_stepping_back(kiosk):
    """11/03: 이미 앞에 앉아 있으면 대기 화면으로 돌아와도 바로 시작하지 않는다 → 1m 밖으로 한 번 물러났다가 다가오면 시작."""
    window, sensor = kiosk
    router = window.router
    window.camera_status.show()
    sensor.distance = 0.4
    for _ in range(4):
        router.check_presence()
    assert router.current_name == "idle" and "물러났다가" in window.camera_status.text()
    assert "0.40m" in window.camera_status.text()
    sensor.distance = 1.6
    router.check_presence()
    assert "다가오면 시작" in window.camera_status.text()
    sensor.distance = 0.5
    router.check_presence()
    router.check_presence()
    assert router.choosing_dine()
