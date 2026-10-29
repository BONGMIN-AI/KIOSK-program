# GUI 2일차 기록 — 비회원 주문 흐름 (2026-10-23, Claude)

## seed 점검·수정
- 메뉴 60개(6분류 × 10), ID M001~M060, 가격 100원 단위, 재고 20 — 테스트 `tests/test_seed.py`로 고정.
- 알레르기 보완: 복숭아 아이스티 → 복숭아, 크루아상 → 알류 추가. 모든 알레르기 이름이 표준 목록과 일치.
- 메뉴별 온도·사이즈 예외: 콜드브루·디카페인 콜드브루·복숭아 아이스티는 ICE만, 에스프레소 2종은 HOT·M만
  (`seed.TEMPERATURE_ONLY`, `SIZE_ONLY` → `options.available_options`가 읽음).
- 가게 이름 기본값 `COFFEE & SPOON` (`core/schema.py`).

## 화면
| 파일 | 내용 |
|---|---|
| gui/order.py | 손님 한 명의 주문 상태(장바구니·넣은 현금). 계산은 domain 함수 |
| gui/screens/unlock.py | 키오스크를 켤 때 운영자가 금고를 여는 화면 (`--demo`면 건너뜀) |
| gui/screens/menu.py | 03: 왼쪽 카테고리 줄 · 메뉴 카드(컵 그림+기어 라떼 아트) · 이벤트 배너 · 오른쪽 장바구니 |
| gui/screens/option.py | 04: 온도·사이즈·추가·수량, 알레르기 성분 표시, 재고 부족 안내 |
| gui/screens/checkout.py | 05 장바구니 확인(± · 삭제) · 07 현금(시연 버튼, 부족·거스름돈 단위·반환) · 08 완료(대기 번호·영수증) |

실행: `python -m gui.main` (금고 열기) / `python -m gui.main --demo` (메모리 샘플, 저장 안 됨).
테스트 102개 통과. (화면 캡처는 이후 `docs/gui_screens/`로 통합)

## 다음(3일차)
domain 새 기능: My Menu·칭호·잔돈 포인트·이벤트 theme. 회원 알레르기 경고 팝업(04-A)은 4일차 회원 흐름에서.
