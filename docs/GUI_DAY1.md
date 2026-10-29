# GUI 1일차 기록 — 2026-10-23

## 범위와 실행

00 대기, 01 시작, 준비 중 화면만 구현했다. GUI는 core/domain/face/app을
import하지 않으며 저장소·카메라·관리자 인증을 열지 않는다.
기존 파일 중 requirements.txt에만 PySide6 한 줄을 추가했다.
FLOWCHART_AND_WIREFRAME.md의 기존 작업자 수정은 보존했다.

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m gui.main
.venv\Scripts\python.exe -m gui.main --fullscreen
# 개발 중 종료: Ctrl+Shift+Q
.venv\Scripts\python.exe -m pytest
```

pytest가 없는 새 환경에서는 별도로 `python -m pip install pytest`가 필요하다.
실제 data 폴더 생성·삭제와 reset_data 실행, git push는 하지 않았다.

## 파일 안내

| 파일 | 역할 |
|---|---|
| gui/__init__.py, gui/screens/__init__.py | 패키지 선언 |
| gui/main.py | 1200×800 창, 아이콘, 전체 화면 옵션, 종료 단축키 |
| gui/theme.py | 색·이벤트 테마·글꼴·크기·모서리 상수와 예시 이벤트 |
| gui/widgets.py | 버튼·언어 칩·그림자 카드·이벤트 띠 |
| gui/router.py | 이름별 화면 전환, 입력 감지, 60초 복귀 |
| gui/screens/idle.py | 가운데 cover 배경, 언어 선택, 이벤트 띠 |
| gui/screens/home.py | 주문 방식 카드, 가입·운영자·하단 버튼 |
| gui/screens/placeholder.py | 준비 중 안내와 처음으로 버튼 |
| gui/assets/idle_bg.webp | 지정한 대기 그림 원본 복사 |
| gui/assets/logo_main.png | 지정한 메인 로고 원본 복사 |
| gui/assets/logo_sub.png | 지정한 서브 로고 원본 복사 |
| gui/assets/fonts/README.md | 선택 글꼴 배치 안내 |
| tests/test_gui_smoke.py | PySide6 미설치 시 skip하는 offscreen 테스트 |
| docs/gui_day1/idle.png, home.png | Qt Windows 렌더링으로 생성한 화면 캡처 |

## 검증

- PySide6 6.12.0 설치 완료, pytest는 검증 환경에 별도 설치.
- 전체 테스트 86개 통과(기존 78개 + GUI 8개).
- 샌드박스 실행은 기존 테스트의 임시파일 생성에서 지연되어 중지했다.
  일반 권한 환경에서 동일한 전체 pytest 명령은 37.72초에 통과했다.
- GUI 테스트: 초기 화면·크기·아이콘, idle→home→idle,
  색 표, None 이벤트 숨김, 언어 칩 선택, 회원/비회원 준비 중 연결,
  입력 시 타이머 재시작 및 무입력 복귀를 확인했다.
- 일반 Windows 환경에서 `python -m gui.main` 창 제목과 유효한 창 핸들을 확인하고 닫았다.
- offscreen에서는 시스템 글꼴이 네모로 나오는 환경 제약이 있어 캡처는
  Windows Qt 렌더링으로 만들었다. 데스크톱 화면 조작은 사용하지 않았다.
- 60초 테스트는 설정값을 확인한 뒤 짧은 타이머로 동작을 검증했다.
  실제 터치 장치와 접근 감지는 검증하거나 연결하지 않았다.

## 기준과 차이

- 00은 첨부 S-00 도식 대신 지시서에 지정된 사진형 WebP를 그대로 쓴다.
  그림에 포함된 접근 감지 안내는 이미지 일부이며 실제 기능은 없다.
- 글꼴 파일이 없어 Malgun Gothic을 사용한다. 폰트 폴더에 Noto 파일을 넣으면
  다음 실행에 등록한다.
- 축제 테마는 이미지의 분홍 바탕 대신 문서 표의 #FFF0B3 / #B4236B를 따른다.
- 언어 칩은 시안보다 높게 56px로 만들어 최소 터치 높이 기준을 따른다.
  대기 화면 언어는 선택 표시만 바뀐다.
- 01의 언어·고대비·큰 글자는 오늘 범위를 제한하기 위해 준비 중 화면으로 연결한다.
- 로고 파일은 원본 그대로 복사하고 표시할 때만 투명 여백을 제외한다.

## 2일차 연결 지점

1. Router.open_action의 guest 분기를 03 메뉴로 연결한다. 현재는
   pending_action에 member/guest/signup/admin 등을 기록하고 준비 중 화면을 연다.
2. 새 화면은 Router.add_screen으로 등록한다. 04 옵션·05 장바구니·07 현금·08 완료도
   이 경로를 사용하고, 화면 내부가 아닌 별도 주문 상태/서비스 계층에서 domain을 호출한다.
3. 처음으로 또는 시간 초과로 idle에 가면 pending_action은 지워진다.
   주문 상태가 생기면 같은 지점에서 비회원 주문 상태 초기화를 연결해야 한다.
4. 현금 투입 중에는 자동 복귀 전에 반환 처리가 필요하다. 2일차에는 타이머 복귀와
   결제 취소를 서비스 계층에 연결한 뒤 현금 흐름을 활성화해야 한다.
5. EventBanner.set_event(None/이벤트)로 띠를 교체할 수 있다.
   실제 이벤트 조회는 이후 서비스에서 처리하고 theme의 예시는 교체한다.

미구현: 03 이후 화면, 실제 언어 전환·접근성 설정, 데이터 저장, 현금 처리, 회원 인증.

## 1일차 보완 (Claude, 10/23)

- 글꼴: Noto Sans KR·Noto Serif KR 가변 글꼴(OFL)을 `gui/assets/fonts/`에 넣었다. 세리프 제목이 적용된다.
- 버튼 키보드 포커스 끔(`widgets.button`) → 01 첫 화면의 주황 테두리 제거.
- 대기 화면: `tools/make_idle_background.py`로 원본 그림에서 로고·안내 글자를 지운 `idle_bg_clean.png`를 만들고,
  `idle.py`가 그 위에 로고(1.1배, 12px 아래)와 시작 안내(언어별, 칸에 맞게 글자 크기 자동 축소)를 그린다.
  접근 안내 문구는 `show_approach_hint`(기본 False, D10 연결 때 True)일 때만 그린다. 이벤트 띠 높이 64 → 56.
- 테스트 89개 통과(GUI 11개). 캡처 `docs/gui_day1/idle.png`, `home.png`.
- 접근 안내 배치 **B안 확정(10/23)**: 그림 위가 아니라 아래 이벤트 띠에서 이벤트 문구와 5초마다 번갈아 보여 준다
  (글자만 0.4초 흐려졌다 나타남, 접근 안내 차례에는 기본 테마 색). `IdleScreen.set_approach_hint(True)`로 켠다 — D10 연결 때.
  이벤트가 없으면 접근 안내만, 둘 다 없으면 띠를 숨긴다. 테스트 91개 통과. 캡처 `idle_band_event.png`, `idle_band_hint.png`.
