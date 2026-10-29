"""경로 설정. 경로는 여기에서만 정의한다."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
KEYSTORE_PATH = DATA_DIR / "keystore.json"
AUDIT_PATH = DATA_DIR / "audit.log"
MODEL_DIR = ROOT / "models"
FACE_DETECTOR_PATH = MODEL_DIR / "face_detection_yunet_2026may.onnx"
FACE_ARCFACE_PATH = MODEL_DIR / "face_recognition_arcface_w600k_r50.onnx"
FACE_ANTISPOOF_V2_PATH = MODEL_DIR / "antispoof_minifasnet_v2.onnx"
FACE_ANTISPOOF_V1SE_PATH = MODEL_DIR / "antispoof_minifasnet_v1se.onnx"
FACE_DETECTOR_SHA256 = "ebafce4e3c118d6554634be5c27ab333b4c047a9a8c3faf1d7cf93101c22f0f0"
FACE_ARCFACE_SHA256 = "4c06341c33c2ca1f86781dab0e829f88ad5b64be9fba56e56bc9ebdefc619e43"
FACE_ANTISPOOF_V2_SHA256 = "b32929adc2d9c34b9486f8c4c7bc97c1b69bc0ea9befefc380e4faae4e463907"
FACE_ANTISPOOF_V1SE_SHA256 = "ebab7f90c7833fbccd46d3a555410e78d969db5438e169b6524be444862b3676"
# 실행할 때 지문(SHA-256)을 검사하는 얼굴 모델: (경로, 지문)
FACE_MODELS = (
    (FACE_DETECTOR_PATH, FACE_DETECTOR_SHA256),
    (FACE_ARCFACE_PATH, FACE_ARCFACE_SHA256),
    (FACE_ANTISPOOF_V2_PATH, FACE_ANTISPOOF_V2_SHA256),
    (FACE_ANTISPOOF_V1SE_PATH, FACE_ANTISPOOF_V1SE_SHA256),
)
# 얼굴 확인에 쓸 카메라 번호. USB 카메라는 보통 1 이상이다 (예: set KIOSK_CAMERA=2).
CAMERA_INDEX = int(os.environ.get("KIOSK_CAMERA", "0"))
