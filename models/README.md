# OpenCV 얼굴 모델

이 폴더의 ONNX 파일은 OpenCV 공식 `opencv_zoo`에서 2026-10-19에 내려받았다.

| 파일 | 용도 | SHA-256 |
|---|---|---|
| `face_detection_yunet_2026may.onnx` | YuNet 얼굴·랜드마크 감지 | `ebafce4e3c118d6554634be5c27ab333b4c047a9a8c3faf1d7cf93101c22f0f0` |
| `face_recognition_sface_2021dec.onnx` | SFace 128차원 얼굴 특징 생성 | `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79` |

- YuNet: <https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet>
- SFace: <https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface>
- OpenCV Zoo 라이선스: <https://github.com/opencv/opencv_zoo/blob/main/LICENSE>

프로그램은 실행할 때 두 파일의 SHA-256을 검사한다. 파일이 없거나 바뀌면 얼굴 기능만
중단하고 비밀번호 로그인 안내를 표시한다.
