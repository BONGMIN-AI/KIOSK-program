"""경로 설정. 경로는 여기에서만 정의한다."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
KEYSTORE_PATH = DATA_DIR / "keystore.json"
AUDIT_PATH = DATA_DIR / "audit.log"
MODEL_DIR = ROOT / "models"
FACE_DETECTOR_PATH = MODEL_DIR / "face_detection_yunet_2026may.onnx"
FACE_RECOGNIZER_PATH = MODEL_DIR / "face_recognition_sface_2021dec.onnx"
FACE_DETECTOR_SHA256 = "ebafce4e3c118d6554634be5c27ab333b4c047a9a8c3faf1d7cf93101c22f0f0"
FACE_RECOGNIZER_SHA256 = "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"
