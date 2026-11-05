"""사람 감지와 얼굴 인증 사이에 카메라 연결을 유지한다."""

import sys
import time
from types import SimpleNamespace

import pytest

from face.presence import CameraPresence


def wait_for(check, seconds=2):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if check():
            return True
        time.sleep(0.01)
    return check()


@pytest.mark.parametrize("use_depth", [False, True])
def test_camera_connection_survives_handoff(monkeypatch, use_depth):
    opened = []

    class Camera:
        closed = False
        def isOpened(self):
            return True
        def read(self):
            return True, object()
        def release(self):
            self.closed = True

    def open_camera(*args):
        camera = Camera()
        opened.append(camera)
        return camera

    class DepthCamera(Camera):
        def __enter__(self):
            opened.append(self)
            return self
        def read(self):
            return object(), object()
        def __exit__(self, *args):
            self.closed = True

    if use_depth:
        import face.depth_check as depth_check
        monkeypatch.setattr(depth_check, "RealSenseCamera", DepthCamera)

    cv2 = SimpleNamespace(CAP_DSHOW=700, VideoCapture=open_camera,
                          FaceDetectorYN=SimpleNamespace(create=lambda *args: object()))
    monkeypatch.setitem(sys.modules, "cv2", cv2)
    monkeypatch.setattr(CameraPresence, "_measure", staticmethod(lambda *args: 0.7))
    presence = CameraPresence(use_depth=use_depth)
    try:
        assert wait_for(lambda: opened and presence.latest() == 0.7)
        camera, depth = presence.pause(handoff=True)
        assert camera is opened[0] and depth is use_depth
        assert not camera.closed
        assert camera.read()[0]  # 얼굴 인증에서 같은 연결을 읽을 수 있다
        presence.resume()
        assert wait_for(lambda: presence.latest() == 0.7)
        assert len(opened) == 1  # 닫고 다시 열지 않았다
        assert not camera.closed
    finally:
        presence.stop()
    assert camera.closed


def test_router_passes_borrowed_camera_to_face_provider(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from gui.main import KioskWindow, demo_vault

    camera = object()

    class Presence:
        resumed = False
        def pause(self, handoff=False):
            assert handoff
            return camera, False
        def resume(self):
            self.resumed = True
        def stop(self):
            pass

    class Provider:
        shared_camera = None
        use_depth = None

    app = QApplication.instance() or QApplication([])
    presence = Presence()
    window = KioskWindow(vault=demo_vault(), face_factory=lambda vault: Provider(), presence=presence)
    try:
        assert window.router.run_face(lambda provider: provider.shared_camera) == (camera, False)
        assert presence.resumed
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()
