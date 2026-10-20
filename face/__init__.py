"""얼굴 인증 공급자.

실제 앱은 :func:`create_face_provider`를 사용한다. ``FakeFace``는 카메라가 없는
자동 테스트에서만 사용한다.
"""


class FaceError(ValueError):
    """카메라·생체 확인·얼굴 비교 과정의 사용자 표시용 오류."""


class FakeFace:
    """자동 테스트용 대역. 실제 앱에서 사용하지 않는다."""

    def verify_face(self, on_status=print) -> bool:
        on_status("[TEST] 가짜 얼굴 인증 통과")
        return True

    def enroll_face(self, customer_id, on_status=print) -> bool:
        on_status(f"[TEST] {customer_id} 가짜 얼굴 등록")
        return True

    def identify_face(self, claimed_customer_id, on_status=print):
        on_status("[TEST] 가짜 얼굴 식별 통과")
        return claimed_customer_id


def create_face_provider(vault, camera_index: int = 0):
    """실제 OpenCV 공급자를 만든다. 의존성 오류는 실행 시 명확히 알린다."""
    try:
        from .opencv_face import OpenCVFace
    except ImportError as exc:
        raise FaceError(
            "카메라 모듈을 불러오지 못했습니다. requirements.txt를 다시 설치한 뒤 "
            "비밀번호 로그인을 사용하세요"
        ) from exc
    return OpenCVFace(vault, camera_index=camera_index)
