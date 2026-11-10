"""운영자 광고 추가가 PNG/JPG 파일을 안전하게 복사하고 등록하는지 확인한다."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from face import FakeFace
from gui import theme
from gui.main import KioskWindow, demo_vault
from gui.screens import admin as admin_module
from domain.kiosk_settings import login_promos, shown_slides


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    result = KioskWindow(vault=demo_vault(), face_factory=lambda vault: FakeFace())
    result.show()
    result.router.admin_id = "admin"
    result.router.show_screen("admin", tab="banners")
    app.processEvents()
    yield result
    result.close()
    result.deleteLater()
    app.processEvents()


@pytest.mark.parametrize("suffix", ["png", "jpg"])
def test_add_banner_from_file_picker(window, tmp_path, monkeypatch, suffix):
    source = tmp_path / f"chosen.{suffix}"
    image = QImage(80, 60, QImage.Format.Format_RGB32)
    image.fill(0xC48252)
    assert image.save(str(source))
    assets = tmp_path / "assets"
    assets.mkdir()
    monkeypatch.setattr(theme, "ASSETS", assets)
    def choose_image(_parent, _title, initial_dir, _filter):
        assert initial_dir == str(assets)
        return str(source), "이미지 파일"

    monkeypatch.setattr(admin_module.QFileDialog, "getOpenFileName", choose_image)
    admin = window.router.screens["admin"]
    admin.show_tab("banners")
    old_count = len(admin.banners())
    admin.banner_caption.setText("가을 한정 음료")
    admin.add_banner()
    slides = admin.banners()
    assert len(slides) == old_count + 1
    assert slides[-1]["file"].startswith("promo_upload_")
    assert slides[-1]["file"].endswith(f".{suffix}")
    assert (assets / slides[-1]["file"]).read_bytes() == source.read_bytes()
    assert slides[-1]["caption"] == "가을 한정 음료"
    assert slides[-1]["on"] is True


def test_invalid_image_is_not_added(window, tmp_path, monkeypatch):
    source = tmp_path / "broken.png"
    source.write_text("not an image")
    assets = tmp_path / "assets"
    assets.mkdir()
    monkeypatch.setattr(theme, "ASSETS", assets)
    monkeypatch.setattr(admin_module.QFileDialog, "getOpenFileName",
                        lambda *_args: (str(source), "이미지 파일"))
    admin = window.router.screens["admin"]
    old_count = len(admin.banners())
    admin.add_banner()
    assert len(admin.banners()) == old_count
    assert not list(assets.glob("promo_upload_*"))


def test_existing_banner_caption_is_editable_and_shown(window):
    admin = window.router.screens["admin"]
    admin.show_tab("banners")
    admin.banner_table.selectRow(0)
    admin.banner_edit_caption.setText("오늘의 추천 음료")
    admin.save_banner_caption()
    assert admin.banners()[0]["caption"] == "오늘의 추천 음료"
    assert shown_slides(window.router.session.vault.read("settings"))[0][1] == "오늘의 추천 음료"
    assert admin.banner_preview.source[0][1] == "오늘의 추천 음료"


def test_login_ad_can_change_one_slot(window, tmp_path, monkeypatch):
    source = tmp_path / "login.jpg"
    image = QImage(80, 60, QImage.Format.Format_RGB32)
    image.fill(0xA14221)
    assert image.save(str(source))
    assets = tmp_path / "assets"
    assets.mkdir()
    monkeypatch.setattr(theme, "ASSETS", assets)
    def choose_image(_parent, _title, initial_dir, _filter):
        assert initial_dir == str(assets)
        return str(source), "이미지 파일"

    monkeypatch.setattr(admin_module.QFileDialog, "getOpenFileName", choose_image)
    admin = window.router.screens["admin"]
    admin.show_tab("login_ads")
    admin.change_login_ad(1)
    files = login_promos(window.router.session.vault.read("settings"))
    assert files[0] == "promo_photo.webp"
    assert files[1].startswith("promo_upload_") and (assets / files[1]).exists()
    login = window.router.screens["login"]
    login.on_show()
    from gui.widgets import PromoBanner
    assert not login.promo.findChildren(PromoBanner)[1].picture.isNull()
