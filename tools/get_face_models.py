"""얼굴 인증 모델을 내려받아 models/ 에 넣는다. 사용: python tools/get_face_models.py

ArcFace(약 170MB)는 GitHub 100MB 제한 때문에 저장소에 올리지 않으므로, 새 PC에서는 이 파일로 받는다.
받은 뒤 SHA-256 지문이 config.py와 같은지 확인하고, 다르면 지운다.
"""
import hashlib
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

BUFFALO_L = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"
ANTISPOOF = "https://github.com/yakhyo/face-anti-spoofing/releases/download/weights/{}.onnx"


def fingerprint(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save(path: Path, data: bytes, expected: str) -> None:
    if fingerprint(data) != expected:
        raise SystemExit(f"지문이 달라 저장하지 않았습니다: {path.name}")
    path.write_bytes(data)
    print(f"저장: {path.name} ({len(data) / 1e6:.1f}MB)")


def download(url: str) -> bytes:
    print(f"내려받는 중: {url}")
    with urllib.request.urlopen(url) as response:
        return response.read()


def main():
    config.MODEL_DIR.mkdir(exist_ok=True)
    if not config.FACE_ARCFACE_PATH.exists():
        with zipfile.ZipFile(io.BytesIO(download(BUFFALO_L))) as pack:
            save(config.FACE_ARCFACE_PATH, pack.read("w600k_r50.onnx"), config.FACE_ARCFACE_SHA256)
    for path, expected, name in ((config.FACE_ANTISPOOF_V2_PATH, config.FACE_ANTISPOOF_V2_SHA256, "MiniFASNetV2"),
                                 (config.FACE_ANTISPOOF_V1SE_PATH, config.FACE_ANTISPOOF_V1SE_SHA256, "MiniFASNetV1SE")):
        if not path.exists():
            save(path, download(ANTISPOOF.format(name)), expected)
    for path, expected in config.FACE_MODELS:
        state = "OK" if path.exists() and fingerprint(path.read_bytes()) == expected else "없음/다름"
        print(f"{state:6} {path.name}")


if __name__ == "__main__":
    main()
