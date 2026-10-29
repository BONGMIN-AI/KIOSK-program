# 얼굴 모델

프로그램은 실행할 때 아래 파일의 SHA-256을 검사한다(`config.FACE_MODELS`). 파일이 없거나 바뀌면
얼굴 기능만 멈추고 비밀번호 로그인 안내를 표시한다. 없는 파일은 `python tools/get_face_models.py`로 받는다.

| 파일 | 용도 | 출처 · 라이선스 | SHA-256 |
|---|---|---|---|
| `face_detection_yunet_2026may.onnx` | YuNet 얼굴·5점 찾기 | OpenCV Zoo (Apache-2.0), 10/19 | `ebafce4e3c118d6554634be5c27ab333b4c047a9a8c3faf1d7cf93101c22f0f0` |
| `face_recognition_arcface_w600k_r50.onnx` | ArcFace 512차원 얼굴 특징 (10/29~) | InsightFace `buffalo_l` v0.7 — 코드 MIT, **모델은 비상업 연구용** (수업 과제 사용). 약 170MB라 git에 올리지 않음 | `4c06341c33c2ca1f86781dab0e829f88ad5b64be9fba56e56bc9ebdefc619e43` |
| `antispoof_minifasnet_v2.onnx` | 사진·화면 판정 (얼굴 2.7배 영역) | minivision Silent-Face-Anti-Spoofing (Apache-2.0), ONNX: yakhyo/face-anti-spoofing | `b32929adc2d9c34b9486f8c4c7bc97c1b69bc0ea9befefc380e4faae4e463907` |
| `antispoof_minifasnet_v1se.onnx` | 사진·화면 판정 (얼굴 4배 영역) | 위와 같음 | `ebab7f90c7833fbccd46d3a555410e78d969db5438e169b6524be444862b3676` |
| `face_recognition_sface_2021dec.onnx` | (10/28까지 쓰던 SFace, 지금은 안 씀) | OpenCV Zoo | `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79` |

- YuNet: <https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet>
- InsightFace: <https://github.com/deepinsight/insightface> (buffalo_l 모델 팩)
- Silent-Face-Anti-Spoofing: <https://github.com/minivision-ai/Silent-Face-Anti-Spoofing>
- ONNX 변환본: <https://github.com/yakhyo/face-anti-spoofing>
