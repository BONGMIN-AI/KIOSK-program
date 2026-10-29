# 3일차 기록 — 새 기능 4개 (domain, 2026-10-23, Claude)

| 기능 | 파일 | 내용 |
|---|---|---|
| 이벤트 테마 | domain/policy.py | 이벤트에 `theme`(basic·season·festival)·`message`(배너 문구, 60자) 추가. `display_event()`가 진행 중 이벤트 하나를 손님 화면용으로 돌려줌, 문구가 없으면 `banner_message()`가 혜택으로 만듦 |
| 시연 이벤트 | domain/seed.py | `add_demo_events()`: 가을 더블 포인트(10/20~11/11, 커피 3%+1만원 이상 200P, 시즌), 할로윈 축제(10/31, 전 메뉴 +300P, 축제). `reset_data.py`와 `--demo`가 넣음 |
| 잔돈 포인트 (C1) | domain/orders.py | `complete_order(..., change_to_points=True)` — 회원만, 거스름돈 전액 → 포인트, 내역 "잔돈 적립". 주문에 `change_points` |
| 칭호 (A1) | domain/titles.py | 새내기·아아수호자(ICE 아메리카노 10잔)·라떼 장인·디카페인 지킴이·딸기 완주자·신메뉴 헌터·단골손님. 주문 완료 때 검사 → `extra["titles"]`, 대표 칭호 `extra["title"]`, 주문에 `new_titles` |
| My Menu (핵심) | domain/my_menu.py | `usual_order()` 가장 자주 시킨 메뉴+옵션, `toggle_like()` 좋아요, `caffeine_report()` 이번 주 요일별 mg·지난주 대비 %·문구·디카페인 추천 (L ×1.3, 샷 +75mg, 디카페인 0) |

GUI 연결: 대기 화면 띠·메뉴 배너가 운영자 정책의 진행 중 이벤트를 테마 색으로 보여 준다(없으면 숨김).
테스트 116개 통과 (`tests/test_my_menu_titles.py` 11개 추가).
