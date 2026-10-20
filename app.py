"""BONGMIN CAFE Textual TUI 실행점.

처음 한 번: python tools/reset_data.py --yes
실행:       python app.py

화면 순서는 docs/FLOWCHART_AND_WIREFRAME.md 와 Figma 와이어프레임 01~09 를 따른다.
화면 맨 위의 `언어 · 고대비 · 큰 글자` 바는 와이어프레임에 자리가 정해지면 그 위치로 옮긴다.
"""
from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from rich.text import Text
from textual.widgets import (
    Button, Checkbox, Collapsible, DataTable, Footer, Header, Input, Label, Select,
    SelectionList, Static, Tab, Tabs,
)
from textual.widgets.selection_list import Selection

import config
from core import audit, auth
from core import schema
from core.validators import mask_phone
from domain import cart as cart_logic
from domain import policy as policy_logic
from domain.benefits import apply_benefits, coupons_of, max_usable_points
from domain import allergens as allergen_list
from domain.customers import (
    adjust_points, allergy_warnings, login_with_face, login_with_password, register_customer,
    save_preferences, set_face_enrolled, validate_password_pair,
)
from domain.options import SIZE_PRICES, available_options, normalize_options, option_price
from domain.orders import complete_order
from domain.payment import insert_cash, payment_status
from face import FaceError, create_face_provider
from ui.i18n import (
    LANGUAGES, allergen_name, category_name, change_text, menu_name, option_text, t, won,
)

CATEGORY_TABS = {
    "cat-coffee": "커피", "cat-noncoffee": "논커피", "cat-tea": "차",
    "cat-ade": "에이드", "cat-dessert": "디저트",
}
CATEGORY_ICONS = {"커피": "☕", "논커피": "🥛", "차": "🍵", "에이드": "🍹", "디저트": "🥐"}
DEMO_MEMBER_IDS = {"bomin", "member1", "member2", "member3"}

# 손님 화면 위젯과 번역 키. 언어를 바꾸면 이 목록을 따라 문구를 다시 쓴다.
I18N_WIDGETS = [
    ("#lbl-lang", "label", "lang"), ("#pref-contrast", "checkbox", "high_contrast"),
    ("#pref-large", "checkbox", "large_mode"),
    ("#home-title", "label", "home_title"), ("#home-desc", "static", "home_desc"),
    ("#member-order", "button", "member_order"), ("#guest-order", "button", "guest_order"),
    ("#signup", "button", "signup"), ("#admin", "button", "operator"),
    ("#member-login-title", "label", "member_login"), ("#member-login-hint", "static", "demo_hint"),
    ("#member-login-id", "placeholder", "ph_member_id"), ("#member-login-password", "placeholder", "ph_member_pw"),
    ("#member-face-login", "button", "face_login"), ("#member-password-login", "button", "pw_login"),
    ("#member-face-enroll", "button", "face_enroll"), ("#member-as-guest", "button", "as_guest"),
    ("#member-login-cancel", "button", "to_home"),
    ("#signup-title", "label", "signup_title"), ("#signup-hint", "static", "signup_hint"),
    ("#lbl-signup-name", "label", "lbl_name"), ("#signup-name", "placeholder", "ph_name"),
    ("#lbl-signup-login-id", "label", "lbl_login_id"), ("#signup-login-id", "placeholder", "ph_login_id"),
    ("#lbl-signup-password", "label", "lbl_password"), ("#signup-password", "placeholder", "ph_password"),
    ("#lbl-signup-password2", "label", "lbl_password2"), ("#signup-password2", "placeholder", "ph_password2"),
    ("#lbl-signup-phone", "label", "lbl_phone"), ("#signup-phone", "placeholder", "ph_phone"),
    ("#lbl-signup-allergy", "label", "lbl_allergy"), ("#allergy-search", "placeholder", "ph_allergy_search"),
    ("#lbl-signup-consent", "label", "lbl_consent"),
    ("#privacy", "checkbox", "privacy"), ("#marketing", "checkbox", "marketing"),
    ("#lbl-signup-face", "label", "lbl_face"), ("#face-consent", "checkbox", "face_consent"),
    ("#face-consent-help", "static", "face_consent_help"),
    ("#create-member", "button", "signup_next"), ("#cancel-signup", "button", "to_home"),
    ("#face-title", "label", "face_title"), ("#face-guide", "static", "face_guide"),
    ("#face-start", "button", "face_start"), ("#face-skip", "button", "face_skip"),
    ("#order-title", "label", "menu_title"), ("#cart-delete", "button", "cart_delete"),
    ("#clear-cart", "button", "cart_clear"), ("#go-checkout", "button", "checkout"), ("#home", "button", "to_home"),
    ("#opt-shot", "checkbox", "shot"), ("#opt-syrup", "checkbox", "syrup"),
    ("#opt-quantity", "placeholder", "ph_qty"), ("#option-cancel", "button", "cancel"),
    ("#benefit-title", "label", "benefit_title"), ("#benefit-apply", "button", "benefit_apply"),
    ("#benefit-max", "button", "benefit_max"), ("#benefit-pay", "button", "benefit_pay"),
    ("#benefit-skip", "button", "benefit_skip"), ("#benefit-back", "button", "back_to_cart"),
    ("#payment-title", "label", "payment_title"), ("#cash", "placeholder", "ph_cash"),
    ("#insert-cash", "button", "insert_cash"), ("#pay", "button", "pay"),
    ("#cash-refund", "button", "refund"), ("#back-from-payment", "button", "back"),
    ("#receipt-title", "label", "receipt_title"), ("#next-customer", "button", "next_customer"),
]
ADMIN_VIEWS = {
    "menu": "운영자 · 메뉴 관리", "customers": "운영자 · 회원 조회 · 포인트 조정",
    "orders": "운영자 · 주문 조회", "policy": "운영자 · 포인트·이벤트·화면 설정",
    "audit": "운영자 · 감사 로그",
}


class PasswordInput(Input):
    """비밀번호를 * 로 가려 보여 준다 (Textual 기본 표시는 •)."""

    @property
    def _value(self) -> Text:
        if self.password:
            return Text("*" * len(self.value), no_wrap=True, overflow="ignore", end="")
        return super()._value


def is_blank(value) -> bool:
    """Select에서 아무것도 고르지 않은 상태인지. Textual 버전마다 표시값이 달라 둘 다 확인한다."""
    return value is Select.NULL or value is Select.BLANK or value is None


class KioskApp(App):
    TITLE = "BONGMIN CAFE KIOSK"
    SUB_TITLE = "현금 결제 · 회원 데이터 카드"
    # 손님이 Ctrl+Q로 KIOSK를 끄지 못하게 막는다. 종료는 운영자 화면에서만 한다.
    BINDINGS = [Binding("ctrl+q", "guarded_quit", "종료", show=False, priority=True)]
    CSS = """
    Screen { background: $surface; }
    #shell { width: 100%; max-width: 120; height: auto; margin: 1 2; }
    #access-bar { height: auto; margin-bottom: 1; }
    #access-bar Label { padding: 1 1 0 0; }
    #pref-language { width: 22; margin: 0 1 0 0; }
    #access-bar Checkbox { margin-right: 1; }
    .page { display: none; padding: 1 2; border: round $primary; height: auto; }
    .page.active { display: block; }
    .actions { height: auto; margin-top: 1; }
    .actions Button { margin-right: 1; }
    #cart-table { height: 10; margin: 1 0; }
    #category-tabs { margin: 1 0; }
    #menu-grid { grid-size: 3; grid-gutter: 1; height: auto; min-height: 12; }
    #menu-grid Button { width: 100%; height: 4; }
    #member-card, #event-banner { height: auto; color: $accent; }
    #status { height: auto; min-height: 3; margin-top: 1; color: $text-muted; }
    #receipt { height: auto; min-height: 12; }
    #admin-data { height: 14; margin-top: 1; }
    .admin-form { height: auto; display: none; }
    .admin-form.shown { display: block; }
    .row { height: auto; }
    .row Input, .row Select { width: 1fr; margin-right: 1; }
    .title { text-style: bold; margin-bottom: 1; }
    .subtitle { text-style: bold; margin-top: 1; }
    .caption { color: $text-muted; height: auto; }
    .field-label { text-style: bold; margin-top: 1; }
    #allergy-list { height: 12; }
    #face-guide { height: auto; margin: 1 0; }
    .warning { color: $error; text-style: bold; }
    .summary { border: round $secondary; padding: 0 1; margin-bottom: 1; height: auto; }
    Input, Select { margin-bottom: 1; }

    /* 고대비: 검정 바탕 · 흰/노랑 글자 · 굵은 테두리 */
    Screen.high-contrast { background: black; color: white; }
    Screen.high-contrast .page { border: heavy yellow; background: black; }
    Screen.high-contrast Label, Screen.high-contrast Static { color: white; }
    Screen.high-contrast .title, Screen.high-contrast .warning { color: yellow; }
    Screen.high-contrast #member-card, Screen.high-contrast #event-banner { color: yellow; }
    Screen.high-contrast Button { background: black; color: yellow; border: tall white; text-style: bold; }
    Screen.high-contrast Button:focus, Screen.high-contrast Button:hover { background: yellow; color: black; }
    Screen.high-contrast Input, Screen.high-contrast Select { border: tall white; }
    Screen.high-contrast #status { color: white; text-style: bold; }

    /* 큰 글자: 터미널 글자 크기는 앱이 바꿀 수 없어서 버튼·칸을 키우고 굵게 표시한다 */
    Screen.large Button { height: 5; min-width: 20; text-style: bold; }
    Screen.large #menu-grid { grid-size: 2; }
    Screen.large #menu-grid Button { height: 6; }
    Screen.large Label, Screen.large Static, Screen.large Checkbox { text-style: bold; }
    Screen.large .page { padding: 2 3; }
    Screen.large #cart-table { height: 14; }
    """

    def __init__(self):
        super().__init__()
        self.vault = None
        self.menu = {}
        self.face_provider = None
        self.admin_id = None          # 운영자 화면에 들어간 관리자 ID (로그아웃 시 None)
        self.admin_view = "menu"
        self.pending_delete = None
        self.lang = "ko"
        self.high_contrast = False
        self.large_mode = False
        self._applying_prefs = False
        self.signup_allergies = set()
        self.face_target = None       # 얼굴 등록 화면에서 등록할 회원 카드
        self.reset_session()

    # ------------------------------------------------------------------ 화면 구성
    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="shell"):
            # 언어 · 고대비 · 큰 글자 (와이어프레임 확정 후 위치 이동 예정)
            with Horizontal(id="access-bar"):
                yield Label("언어", id="lbl-lang")
                yield Select([(name, code) for code, name in LANGUAGES.items()], value="ko",
                             allow_blank=False, id="pref-language")
                yield Checkbox("고대비", id="pref-contrast")
                yield Checkbox("큰 글자", id="pref-large")

            with Vertical(id="login-page", classes="page active"):
                yield Label("시연 준비 · 장치 금고 열기", classes="title")
                yield Static("여기는 회원 로그인이 아닙니다. 관리자 ID admin과 초기화할 때 정한 비밀번호로 금고를 먼저 엽니다. 실제 키오스크에서는 최초 장치 등록 뒤 고객 화면이 자동 실행됩니다.")
                yield Input(placeholder="관리자 ID (admin)", id="admin-id")
                yield PasswordInput(placeholder="비밀번호", password=True, id="admin-password")
                yield Button("KIOSK 열기", id="unlock", variant="primary")

            # 01 주문 시작
            with Vertical(id="home-page", classes="page"):
                yield Label("", id="home-title", classes="title")
                yield Static("", id="home-desc")
                with Horizontal(classes="actions"):
                    yield Button("", id="member-order", variant="primary")
                    yield Button("", id="guest-order")
                    yield Button("", id="signup")
                    yield Button("", id="admin")

            # 02 회원 ID·얼굴 인증 / 02-B 비밀번호 대체 로그인
            with Vertical(id="member-login-page", classes="page"):
                yield Label("", id="member-login-title", classes="title")
                yield Static("", id="member-login-hint")
                yield Input(id="member-login-id")
                yield PasswordInput(password=True, id="member-login-password")
                with Horizontal(classes="actions"):
                    yield Button("", id="member-face-login", variant="primary")
                    yield Button("", id="member-password-login")
                    yield Button("", id="member-face-enroll")
                    yield Button("", id="member-as-guest")
                    yield Button("", id="member-login-cancel")

            # 10 회원가입 — 한 줄에 한 항목씩 세로로 배치
            with Vertical(id="signup-page", classes="page"):
                yield Label("", id="signup-title", classes="title")
                yield Static("", id="signup-hint", classes="caption")
                yield Label("", id="lbl-signup-name", classes="field-label")
                yield Input(id="signup-name")
                yield Label("", id="lbl-signup-login-id", classes="field-label")
                yield Input(id="signup-login-id")
                yield Label("", id="lbl-signup-password", classes="field-label")
                yield PasswordInput(password=True, id="signup-password")
                yield Label("", id="lbl-signup-password2", classes="field-label")
                yield PasswordInput(password=True, id="signup-password2")
                yield Label("", id="lbl-signup-phone", classes="field-label")
                yield Input(id="signup-phone")
                yield Label("", id="lbl-signup-allergy", classes="field-label")
                with Collapsible(title="", id="allergy-box", collapsed=True):
                    yield Input(id="allergy-search")
                    yield SelectionList(id="allergy-list")
                yield Static("", id="allergy-selected", classes="caption")
                yield Label("", id="lbl-signup-consent", classes="field-label")
                yield Checkbox("", id="privacy")
                yield Checkbox("", id="marketing")
                yield Label("", id="lbl-signup-face", classes="field-label")
                yield Checkbox("", id="face-consent")
                yield Static("", id="face-consent-help", classes="caption")
                with Horizontal(classes="actions"):
                    yield Button("", id="create-member", variant="primary")
                    yield Button("", id="cancel-signup")

            # 10-B 얼굴 등록 — 동의한 사람만 이 화면으로 온다. 카메라는 큰 별도 창으로 열린다.
            with Vertical(id="face-page", classes="page"):
                yield Label("", id="face-title", classes="title")
                yield Static("", id="face-target", classes="summary")
                yield Static("", id="face-guide")
                with Horizontal(classes="actions"):
                    yield Button("", id="face-start", variant="primary")
                    yield Button("", id="face-skip")

            # 03 메뉴 선택 + 05 장바구니 확인
            with Vertical(id="order-page", classes="page"):
                yield Label("", id="order-title", classes="title")
                yield Static("", id="member-card")
                yield Static("", id="event-banner")
                yield Tabs(*(Tab(f"{CATEGORY_ICONS[name]} {name}", id=tab_id)
                             for tab_id, name in CATEGORY_TABS.items()), id="category-tabs")
                with Grid(id="menu-grid"):
                    pass
                yield DataTable(id="cart-table", cursor_type="row", zebra_stripes=True)
                with Horizontal(classes="actions"):
                    yield Button("＋1", id="cart-plus")
                    yield Button("－1", id="cart-minus")
                    yield Button("", id="cart-delete")
                    yield Button("", id="clear-cart")
                with Horizontal(classes="actions"):
                    yield Button("", id="go-checkout", variant="primary")
                    yield Button("", id="home")

            # 04 옵션 선택
            with Vertical(id="option-page", classes="page"):
                yield Label("", id="option-title", classes="title")
                yield Static("", id="option-info")
                yield Static("", id="option-warning", classes="warning")
                yield Select([("HOT", "HOT"), ("ICE", "ICE")], id="opt-temperature", allow_blank=False)
                yield Select([(size, size) for size in SIZE_PRICES], id="opt-size", allow_blank=False)
                yield Checkbox("", id="opt-shot")
                yield Checkbox("", id="opt-syrup")
                yield Input(value="1", type="integer", id="opt-quantity")
                yield Static("", id="option-price")
                with Horizontal(classes="actions"):
                    yield Button("", id="option-add", variant="primary")
                    yield Button("", id="option-cancel")

            # 06 쿠폰·포인트 사용 (회원만)
            with Vertical(id="benefit-page", classes="page"):
                yield Label("", id="benefit-title", classes="title")
                yield Static("", id="benefit-summary", classes="summary")
                yield Select([], id="benefit-coupon")
                yield Input(type="integer", id="benefit-points")
                with Horizontal(classes="actions"):
                    yield Button("", id="benefit-apply")
                    yield Button("", id="benefit-max")
                with Horizontal(classes="actions"):
                    yield Button("", id="benefit-pay", variant="primary")
                    yield Button("", id="benefit-skip")
                    yield Button("", id="benefit-back")

            # 07 현금 결제
            with Vertical(id="payment-page", classes="page"):
                yield Label("", id="payment-title", classes="title")
                yield Static("", id="payment-total", classes="summary")
                yield Input(type="integer", id="cash")
                with Horizontal(classes="actions"):
                    yield Button("", id="insert-cash", variant="primary")
                    yield Button("+1,000", id="cash-1000")
                    yield Button("+5,000", id="cash-5000")
                    yield Button("+10,000", id="cash-10000")
                    yield Button("+50,000", id="cash-50000")
                with Horizontal(classes="actions"):
                    yield Button("", id="pay", variant="success")
                    yield Button("", id="cash-refund")
                    yield Button("", id="back-from-payment")

            # 08 주문 완료
            with Vertical(id="receipt-page", classes="page"):
                yield Label("", id="receipt-title", classes="title")
                yield Static("", id="receipt")
                yield Button("", id="next-customer", variant="primary")

            # 09-A 운영자 로그인 (운영자 화면은 한국어로만 표시)
            with Vertical(id="admin-login-page", classes="page"):
                yield Label("운영자 로그인", classes="title")
                yield Static("운영자 전용 영역: 메뉴·품절 관리, 회원·주문 조회, 포인트 조정, 포인트·이벤트·화면 설정, KIOSK 종료")
                yield Input(placeholder="운영자 ID", id="op-id")
                yield PasswordInput(placeholder="비밀번호", password=True, id="op-password")
                with Horizontal(classes="actions"):
                    yield Button("비밀번호 로그인", id="op-password-login", variant="primary")
                    yield Button("ID + 얼굴 로그인", id="op-face-login")
                    yield Button("처음으로", id="op-cancel")

            # 09-B/C 운영자 화면 + 포인트·이벤트 설정
            with Vertical(id="admin-page", classes="page"):
                yield Label("운영자 · 메뉴 관리", id="admin-title", classes="title")
                with Horizontal(classes="actions"):
                    yield Button("메뉴 관리", id="view-menu", variant="primary")
                    yield Button("회원·포인트", id="view-customers")
                    yield Button("주문 조회", id="view-orders")
                    yield Button("포인트·이벤트 설정", id="view-policy")
                    yield Button("감사 로그", id="view-audit")
                yield Input(placeholder="검색 (메뉴명·닉네임·주문번호)", id="admin-search")

                with Vertical(id="form-menu", classes="admin-form shown"):
                    yield Select([], prompt="수정할 메뉴 선택 (새 메뉴는 선택 안 함)", id="admin-menu-id")
                    with Horizontal(classes="row"):
                        yield Input(placeholder="메뉴 이름", id="admin-menu-name")
                        yield Input(placeholder="카테고리 (커피·논커피·차·에이드·디저트)", id="admin-category")
                    with Horizontal(classes="row"):
                        yield Input(placeholder="가격", type="integer", id="admin-price")
                        yield Input(placeholder="재고", type="integer", id="admin-stock")
                    with Horizontal(classes="actions"):
                        yield Button("추가/수정 저장", id="save-menu", variant="primary")
                        yield Button("판매중 ↔ 품절", id="toggle-sold-out")
                        yield Button("선택 메뉴 삭제", id="delete-menu", variant="error")

                with Vertical(id="form-customers", classes="admin-form"):
                    yield Select([], prompt="포인트를 조정할 회원 선택", id="admin-customer-id")
                    with Horizontal(classes="row"):
                        yield Input(placeholder="조정 포인트 (+500 / -300)", id="adjust-delta")
                        yield Input(placeholder="사유 (예: 결제 오류 보상, 이벤트 누락 적립)", id="adjust-reason")
                    with Horizontal(classes="actions"):
                        yield Button("포인트 조정 저장", id="adjust-points", variant="primary")
                        yield Button("선택 회원 포인트 내역", id="view-point-history")

                with Vertical(id="form-policy", classes="admin-form"):
                    yield Label("기본 적립 · 사용 · 방문 쿠폰", classes="subtitle")
                    yield Static("기본 적립률(%) │ 포인트 사용 단위(P) │ 최소 사용(P) │ 결제액 중 최대 사용(%)", classes="caption")
                    with Horizontal(classes="row"):
                        yield Input(placeholder="기본 적립률 %", id="pol-base-rate")
                        yield Input(placeholder="사용 단위 P", type="integer", id="pol-unit")
                        yield Input(placeholder="최소 사용 P", type="integer", id="pol-min-use")
                        yield Input(placeholder="최대 사용 %", type="integer", id="pol-max-pct")
                    yield Static("방문 쿠폰: N번째 방문마다(0=끔) │ 쿠폰 금액(원) │ 유효 일수(0=그해 12/31까지)", classes="caption")
                    with Horizontal(classes="row"):
                        yield Input(placeholder="방문 쿠폰: N회마다 (0=끔)", type="integer", id="pol-coupon-every")
                        yield Input(placeholder="쿠폰 금액 원", type="integer", id="pol-coupon-amount")
                        yield Input(placeholder="유효 일수 (0=연말)", type="integer", id="pol-coupon-days")
                    yield Button("적립·사용 정책 저장", id="save-policy", variant="primary")

                    yield Label("기간 이벤트", classes="subtitle")
                    yield Select([], prompt="수정할 이벤트 선택 (새 이벤트는 선택 안 함)", id="ev-id")
                    yield Static("이벤트 이름 │ 시작일 │ 종료일 (YYYY-MM-DD, 종료일 포함)", classes="caption")
                    with Horizontal(classes="row"):
                        yield Input(placeholder="이벤트 이름", id="ev-name")
                        yield Input(placeholder="시작일 2026-10-20", id="ev-start")
                        yield Input(placeholder="종료일 2026-10-31", id="ev-end")
                    yield Static("요일(월,수,금 / 평일 / 주말 / 비우면 매일) │ 시간대(14-17 = 14시~17시 전) │ 대상 카테고리(비우면 전체)", classes="caption")
                    with Horizontal(classes="row"):
                        yield Input(placeholder="요일 (월,수,금 / 평일 / 주말 / 비우면 매일)", id="ev-weekdays")
                        yield Input(placeholder="시간대 14-17 (비우면 종일)", id="ev-hours")
                        yield Input(placeholder="카테고리 (커피,디저트 / 비우면 전체)", id="ev-categories")
                    yield Static("이벤트 적립률(%, 기본보다 높을 때 적용) │ 보너스 포인트(주문당) │ 보너스 받을 최소 결제액(원) │ 사용 여부", classes="caption")
                    with Horizontal(classes="row"):
                        yield Input(placeholder="이벤트 적립률 %", id="ev-rate")
                        yield Input(placeholder="보너스 포인트", type="integer", id="ev-bonus")
                        yield Input(placeholder="보너스 최소 결제액", type="integer", id="ev-min-order")
                        yield Checkbox("사용", value=True, id="ev-enabled")
                    with Horizontal(classes="actions"):
                        yield Button("이벤트 추가/수정", id="save-event", variant="primary")
                        yield Button("새 이벤트 입력", id="new-event")
                        yield Button("선택 이벤트 삭제", id="delete-event", variant="error")

                    yield Label("손님 화면 기본값 (다음 손님부터 적용)", classes="subtitle")
                    with Horizontal(classes="row"):
                        yield Select([(name, code) for code, name in LANGUAGES.items()], value="ko",
                                     allow_blank=False, id="def-language")
                        yield Checkbox("고대비 기본", id="def-contrast")
                        yield Checkbox("큰 글자 기본", id="def-large")
                    yield Button("화면 기본값 저장", id="save-display")

                yield DataTable(id="admin-data", zebra_stripes=True)
                with Horizontal(classes="actions"):
                    yield Button("관리자 얼굴 등록", id="op-face-enroll")
                    yield Button("로그아웃", id="admin-logout")
                    yield Button("KIOSK 종료", id="quit", variant="error")

            yield Static("준비됨", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.apply_language()

    # ------------------------------------------------------------------ 공통 도우미
    def reset_session(self) -> None:
        """한 손님의 주문 상태를 모두 비운다."""
        self.cart = {}
        self.customer = None
        self.option_menu_id = None
        self.benefit_choice = {"coupon_id": None, "use_points": 0}
        self.inserted_cash = 0

    def tr(self, key: str, **values) -> str:
        return t(self.lang, key, **values)

    def money(self, amount: int) -> str:
        return won(self.lang, amount)

    def show_page(self, page_id: str) -> None:
        for page in self.query(".page"):
            page.remove_class("active")
        self.query_one(f"#{page_id}").add_class("active")
        # 운영자 화면에서는 손님용 언어·접근성 바를 숨긴다
        self.query_one("#access-bar").display = page_id not in {"admin-page", "admin-login-page", "login-page"}

    def set_status(self, message: str, error: bool = False) -> None:
        self.query_one("#status", Static).update(("[bold red]" if error else "[dim]") + message)

    def get_face_provider(self):
        if self.face_provider is None:
            self.face_provider = create_face_provider(self.vault)
        return self.face_provider

    def settings(self) -> dict:
        return self.vault.read("settings", default=dict(schema.DEFAULT_SETTINGS))

    def policy(self) -> dict:
        return policy_logic.load_policy(self.settings())

    def audit(self, action: str, target: str = "") -> None:
        """운영자 행동을 해시 체인 감사 로그에 남긴다. 개인정보 대신 ID만 기록한다."""
        audit.AuditLog(Path(config.DATA_DIR) / "audit.log").append(self.admin_id or "system", action, target)

    def go_home(self, message: str = "") -> None:
        refund = self.inserted_cash
        self.reset_session()
        self.apply_display_defaults()
        self.show_page("home-page")
        if refund:
            message = self.tr("returned_on_home", n=self.money(refund)) + message
        self.set_status(message or self.tr("home_status"))

    def action_guarded_quit(self) -> None:
        if self.admin_id:
            self.exit()
        else:
            self.set_status("KIOSK 종료는 운영자 메뉴에서만 할 수 있습니다.", True)

    def value_of(self, selector: str) -> str:
        return self.query_one(selector, Input).value.strip()

    def int_of(self, selector: str, default: int = 0) -> int:
        raw = self.value_of(selector).replace(",", "")
        try:
            return int(raw) if raw else default
        except ValueError as exc:
            raise ValueError("숫자를 입력해 주세요") from exc

    def float_of(self, selector: str, default: float = 0.0) -> float:
        raw = self.value_of(selector)
        try:
            return float(raw) if raw else default
        except ValueError as exc:
            raise ValueError("숫자를 입력해 주세요") from exc

    # ------------------------------------------------------------------ 언어 · 접근성
    def apply_language(self) -> None:
        for selector, kind, key in I18N_WIDGETS:
            widget = self.query_one(selector)
            text = self.tr(key)
            if kind in ("label", "static"):
                widget.update(text)
            elif kind in ("button", "checkbox"):
                widget.label = text
            elif kind == "placeholder":
                widget.placeholder = text
        for tab_id, category in CATEGORY_TABS.items():
            self.query_one(f"#{tab_id}", Tab).label = f"{CATEGORY_ICONS[category]} {category_name(self.lang, category)}"
        self.query_one("#opt-size", Select).set_options(
            [(self.tr("size_option", size=size, price=f"{price:,}"), size) for size, price in SIZE_PRICES.items()])
        self.query_one("#benefit-coupon", Select).prompt = self.tr("coupon_none")
        table = self.query_one("#cart-table", DataTable)
        table.clear(columns=True)
        table.add_columns(*(self.tr(k) for k in ("col_menu", "col_option", "col_qty", "col_unit", "col_amount")))
        if self.vault:
            self.call_later(self.refresh_customer_views)

    async def refresh_customer_views(self) -> None:
        """언어를 바꾼 직후 지금 보이는 손님 화면의 동적 문구를 다시 그린다."""
        active = self.query_one("#category-tabs", Tabs).active
        await self.render_menu_tiles(CATEGORY_TABS.get(active, "커피"))
        self.query_one("#member-card", Static).update(self.member_card_text())
        self.update_event_banner()
        self.refresh_cart(quiet=True)
        if self.option_menu_id:
            self.refresh_option_texts()
        if self.query_one("#benefit-page").has_class("active"):
            self.update_benefit_summary(self.benefit_choice)
        if self.query_one("#payment-page").has_class("active"):
            self.update_payment_summary()
        self.query_one("#benefit-points", Input).placeholder = self.tr(
            "ph_points", unit=self.policy()["point_unit"])

    def apply_display(self, lang: str, high_contrast: bool, large_mode: bool) -> None:
        """언어·고대비·큰 글자를 화면에 적용하고 위쪽 바의 값도 맞춘다."""
        self._applying_prefs = True
        try:
            self.query_one("#pref-language", Select).value = lang
            self.query_one("#pref-contrast", Checkbox).value = high_contrast
            self.query_one("#pref-large", Checkbox).value = large_mode
        finally:
            self.call_later(self._end_applying)
        changed_lang = lang != self.lang
        self.lang, self.high_contrast, self.large_mode = lang, high_contrast, large_mode
        self.screen.set_class(high_contrast, "high-contrast")
        self.screen.set_class(large_mode, "large")
        if changed_lang:
            self.apply_language()

    def _end_applying(self) -> None:
        self._applying_prefs = False

    def apply_display_defaults(self) -> None:
        if not self.vault:
            return
        s = self.settings()
        self.apply_display(s.get("language", "ko"), bool(s.get("high_contrast")), bool(s.get("large_mode")))

    def on_display_pref_changed(self) -> None:
        lang = self.query_one("#pref-language", Select).value
        wanted = (lang if not is_blank(lang) else "ko",
                  self.query_one("#pref-contrast", Checkbox).value,
                  self.query_one("#pref-large", Checkbox).value)
        # 프로그램이 값을 맞추면서 생긴 변경 알림은 지금 상태와 같으므로 무시한다
        if self._applying_prefs or wanted == (self.lang, self.high_contrast, self.large_mode):
            return
        self.apply_display(*wanted)
        if self.customer and self.vault:
            self.customer = save_preferences(self.vault, self.customer["id"], {
                "language": self.lang, "high_contrast": self.high_contrast, "large_mode": self.large_mode})
            self.set_status(self.tr("prefs_saved"))

    # ------------------------------------------------------------------ 10 회원가입 · 10-B 얼굴 등록
    def open_signup(self) -> None:
        self.clear_signup_form()
        self.show_page("signup-page")
        self.query_one("#signup-name", Input).focus()

    def clear_signup_form(self) -> None:
        for field in ("name", "login-id", "password", "password2", "phone"):
            self.query_one(f"#signup-{field}", Input).value = ""
        self.query_one("#allergy-search", Input).value = ""
        for box in ("#privacy", "#marketing", "#face-consent"):
            self.query_one(box, Checkbox).value = False
        self.query_one("#allergy-box", Collapsible).collapsed = True
        self.signup_allergies = set()
        self.render_allergy_options()

    def render_allergy_options(self) -> None:
        """검색어에 맞는 알레르기 항목만 체크 목록으로 다시 그린다. 이미 고른 항목은 체크를 유지한다."""
        keyword = self.value_of("#allergy-search")
        names = allergen_list.search(keyword)
        if keyword:  # 번역된 이름으로도 찾을 수 있게 한다
            names += [n for n in allergen_list.ALLERGENS
                      if n not in names and keyword.lower() in allergen_name(self.lang, n).lower()]
        box = self.query_one("#allergy-list", SelectionList)
        box.clear_options()
        box.add_options([Selection(allergen_name(self.lang, n), n, n in self.signup_allergies) for n in names])
        self.update_allergy_summary()

    def update_allergy_summary(self) -> None:
        chosen = sorted(self.signup_allergies, key=allergen_list.ALLERGENS.index)
        self.query_one("#allergy-box", Collapsible).title = self.tr("allergy_box", count=len(chosen))
        self.query_one("#allergy-selected", Static).update(
            self.tr("allergy_chosen", items=", ".join(allergen_name(self.lang, n) for n in chosen))
            if chosen else self.tr("allergy_none"))

    def on_selection_list_selected_changed(self, event: SelectionList.SelectedChanged) -> None:
        if event.selection_list.id != "allergy-list":
            return
        box = event.selection_list
        visible = {box.get_option_at_index(i).value for i in range(box.option_count)}
        self.signup_allergies = (self.signup_allergies - visible) | set(box.selected)
        self.update_allergy_summary()

    def open_face_page(self, customer: dict) -> None:
        self.face_target = customer
        self.query_one("#face-target", Static).update(
            self.tr("face_target", nick=customer["extra"]["nickname"],
                    login_id=customer["extra"].get("login_id", "")))
        self.show_page("face-page")
        self.query_one("#face-start", Button).focus()

    # ------------------------------------------------------------------ 메뉴·장바구니
    async def load_menu_controls(self) -> None:
        self.menu = self.vault.read("menu", default={})
        admin_select = self.query_one("#admin-menu-id", Select)
        admin_select.set_options([(f"{menu_id} · {item['name']}", menu_id) for menu_id, item in self.menu.items()])
        active = self.query_one("#category-tabs", Tabs).active
        await self.render_menu_tiles(CATEGORY_TABS.get(active, "커피"))

    async def render_menu_tiles(self, category: str) -> None:
        grid = self.query_one("#menu-grid", Grid)
        await grid.remove_children()
        for menu_id, item in self.menu.items():
            if item["category"] == category:
                sold = f"\n[{self.tr('sold_out')}]" if item["sold_out"] else ""
                await grid.mount(Button(
                    f"{CATEGORY_ICONS.get(category, '●')} {menu_name(self.lang, item)}\n{self.money(item['price'])}{sold}",
                    id=f"menu-{menu_id}", classes="menu-tile",
                    disabled=item["sold_out"],
                ))

    def member_card_text(self) -> str:
        if not self.customer:
            return self.tr("card_guest")
        extra = self.customer["extra"]
        return self.tr("card_member", nick=extra["nickname"], points=f"{extra['points']:,}",
                       coupons=len(coupons_of(self.customer)), visits=extra["visits"],
                       allergies=", ".join(extra.get("allergies", [])) or self.tr("none"))

    def update_event_banner(self) -> None:
        banner = self.query_one("#event-banner", Static)
        if not self.vault:
            return
        events = policy_logic.active_events(self.policy(), datetime.now())
        banner.update(self.tr("event_banner", names=" · ".join(e["name"] for e in events)) if events else "")

    def open_order(self, customer=None) -> None:
        self.reset_session()
        self.customer = customer
        prefs = (customer or {}).get("extra", {}).get("preferences")
        if prefs:
            self.apply_display(prefs.get("language", self.lang), bool(prefs.get("high_contrast")),
                               bool(prefs.get("large_mode")))
        self.query_one("#member-card", Static).update(self.member_card_text())
        self.update_event_banner()
        self.show_page("order-page")
        self.refresh_cart()
        if prefs:
            self.set_status(self.tr("prefs_applied"))

    def refresh_cart(self, quiet: bool = False) -> None:
        table = self.query_one("#cart-table", DataTable)
        table.clear()
        try:
            lines = cart_logic.cart_lines(self.cart, self.menu)
        except ValueError as exc:
            self.set_status(str(exc), True)
            return
        for line in lines:
            table.add_row(menu_name(self.lang, self.menu[line["menu_id"]]), option_text(self.lang, line["options"]),
                          str(line["quantity"]), f"{line['unit_price']:,}", f"{line['subtotal']:,}", key=line["key"])
        if not quiet:
            total = sum(line["subtotal"] for line in lines)
            count = sum(line["quantity"] for line in lines)
            self.set_status(self.tr("cart_status", count=count, total=self.money(total)))

    def selected_cart_key(self) -> str:
        table = self.query_one("#cart-table", DataTable)
        if not self.cart or table.row_count == 0:
            raise ValueError(self.tr("pick_cart_row"))
        row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
        return row_key.value

    def cart_total(self) -> int:
        return cart_logic.total_price(self.cart, self.menu)

    # ------------------------------------------------------------------ 04 옵션 화면
    def open_options(self, menu_id: str) -> None:
        item = self.menu[menu_id]
        rules = available_options(item)
        self.option_menu_id = menu_id
        temperature = self.query_one("#opt-temperature", Select)
        has_options = bool(rules["temperatures"])
        temperature.display = has_options
        self.query_one("#opt-size", Select).display = has_options
        if has_options:
            temperature.set_options([(x, x) for x in rules["temperatures"]])
            temperature.value = rules["temperatures"][-1]
            self.query_one("#opt-size", Select).value = "M"
        for extra in ("shot", "syrup"):
            box = self.query_one(f"#opt-{extra}", Checkbox)
            box.value = False
            box.display = extra in rules["extras"]
        self.query_one("#opt-quantity", Input).value = "1"
        self.refresh_option_texts()
        self.show_page("option-page")
        self.update_option_price()

    def refresh_option_texts(self) -> None:
        item = self.menu[self.option_menu_id]
        self.query_one("#option-title", Label).update(self.tr("option_title", name=menu_name(self.lang, item)))
        self.query_one("#option-info", Static).update(self.tr(
            "option_info", price=self.money(item["price"]), stock=item["stock"],
            allergens=", ".join(item.get("allergens", [])) or self.tr("none")))
        warnings = allergy_warnings(self.customer, [{"menu_id": self.option_menu_id, "name": item["name"]}], self.menu)
        warning = self.query_one("#option-warning", Static)
        add_button = self.query_one("#option-add", Button)
        if warnings:
            warning.update(self.tr("allergy_warning", items=" / ".join(warnings)))
            add_button.label = self.tr("add_anyway")
        else:
            warning.update("")
            add_button.label = self.tr("add_to_cart")
        self.update_option_price()

    def selected_options(self) -> dict:
        item = self.menu[self.option_menu_id]
        if not available_options(item)["temperatures"]:
            return {}
        extras = [extra for extra in ("shot", "syrup")
                  if self.query_one(f"#opt-{extra}", Checkbox).display
                  and self.query_one(f"#opt-{extra}", Checkbox).value]
        return normalize_options(item, {
            "temperature": self.query_one("#opt-temperature", Select).value,
            "size": self.query_one("#opt-size", Select).value,
            "extras": extras,
        })

    def update_option_price(self) -> None:
        if not self.option_menu_id:
            return
        try:
            quantity = self.int_of("#opt-quantity", 1)
            unit = self.menu[self.option_menu_id]["price"] + option_price(self.selected_options())
            self.query_one("#option-price", Static).update("[bold]" + self.tr(
                "option_price", unit=self.money(unit), qty=quantity, total=self.money(unit * quantity)) + "[/bold]")
        except (ValueError, KeyError):
            pass

    def on_select_changed(self, event: Select.Changed) -> None:
        select_id = event.select.id
        if select_id == "pref-language":
            self.on_display_pref_changed()
        elif select_id == "admin-menu-id" and not is_blank(event.value):
            item = self.menu[str(event.value)]
            self.query_one("#admin-menu-name", Input).value = item["name"]
            self.query_one("#admin-category", Input).value = item["category"]
            self.query_one("#admin-price", Input).value = str(item["price"])
            self.query_one("#admin-stock", Input).value = str(item["stock"])
            self.pending_delete = None
        elif select_id == "ev-id" and not is_blank(event.value):
            self.fill_event_form(str(event.value))
        elif select_id in {"opt-temperature", "opt-size"}:
            self.update_option_price()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id in {"pref-contrast", "pref-large"}:
            self.on_display_pref_changed()
        elif event.checkbox.id in {"opt-shot", "opt-syrup"}:
            self.update_option_price()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "opt-quantity":
            self.update_option_price()
        elif event.input.id == "allergy-search":
            self.render_allergy_options()
        elif event.input.id == "admin-search" and self.admin_id:
            self.show_admin_view()

    async def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        if self.vault and event.tab.id in CATEGORY_TABS:
            await self.render_menu_tiles(CATEGORY_TABS[event.tab.id])

    # ------------------------------------------------------------------ 06 혜택 · 07 결제
    def open_checkout(self) -> None:
        if self.cart_total() == 0:
            raise ValueError(self.tr("empty_cart"))
        if self.customer:
            self.open_benefits()
        else:
            self.benefit_choice = {"coupon_id": None, "use_points": 0}
            self.open_payment()

    def open_benefits(self) -> None:
        coupons = coupons_of(self.customer)
        select = self.query_one("#benefit-coupon", Select)
        select.set_options([
            (f"{c['name']} (-{c['amount']:,}"
             + (f", ≥{c['min_order']:,}" if c.get("min_order") else "")
             + (f", ~{c['expires']}" if c.get("expires") else "") + ")", c["id"])
            for c in coupons
        ])
        if self.benefit_choice["coupon_id"]:
            select.value = self.benefit_choice["coupon_id"]
        points = self.benefit_choice["use_points"]
        points_input = self.query_one("#benefit-points", Input)
        points_input.value = str(points) if points else ""
        points_input.placeholder = self.tr("ph_points", unit=self.policy()["point_unit"])
        self.show_page("benefit-page")
        self.update_benefit_summary(self.benefit_choice)

    def read_benefit_inputs(self) -> dict:
        value = self.query_one("#benefit-coupon", Select).value
        coupon_id = None if is_blank(value) else str(value)
        return {"coupon_id": coupon_id, "use_points": self.int_of("#benefit-points")}

    def update_benefit_summary(self, choice: dict) -> dict:
        total = self.cart_total()
        policy = self.policy()
        result = apply_benefits(total, self.customer, choice["coupon_id"], choice["use_points"], policy=policy)
        self.query_one("#benefit-summary", Static).update(self.tr(
            "benefit_summary", balance=f"{self.customer['extra']['points']:,}",
            coupons=len(coupons_of(self.customer)), total=self.money(total),
            coupon=self.money(result["coupon_discount"]), points=self.money(result["points_used"]),
            final=self.money(result["final_total"]), unit=policy["point_unit"],
            min_use=f"{policy['min_use']:,}", max_pct=policy["max_use_percent"]))
        return result

    def payable_total(self) -> int:
        choice = self.benefit_choice
        return apply_benefits(self.cart_total(), self.customer, choice["coupon_id"],
                              choice["use_points"], policy=self.policy())["final_total"]

    def open_payment(self) -> None:
        self.query_one("#cash", Input).value = ""
        self.show_page("payment-page")
        self.update_payment_summary()
        self.query_one("#cash", Input).focus()

    def update_payment_summary(self) -> None:
        total = self.payable_total()
        status = payment_status(total, self.inserted_cash)
        if status["paid"]:
            state = ("[bold green]" + self.tr("pay_enough", change=self.money(status["change"])) + "[/bold green]\n"
                     + self.tr("pay_return", detail=change_text(self.lang, status["breakdown"])))
        else:
            state = "[bold red]" + self.tr("pay_short", n=self.money(status["shortage"])) + "[/bold red]"
        self.query_one("#payment-total", Static).update(
            self.tr("pay_summary", total=self.money(total), cash=self.money(self.inserted_cash)) + "\n" + state)

    def add_cash(self, amount: int) -> None:
        self.inserted_cash = insert_cash(self.inserted_cash, amount)
        self.query_one("#cash", Input).value = ""
        self.update_payment_summary()
        self.set_status(self.tr("cash_inserted", n=self.money(amount), total=self.money(self.inserted_cash)))

    def finish_payment(self) -> None:
        customer_id = self.customer["id"] if self.customer else None
        order = complete_order(self.vault, self.cart, self.inserted_cash, customer_id,
                               self.benefit_choice["coupon_id"], self.benefit_choice["use_points"])
        lines = "\n".join(
            f"- {menu_name(self.lang, self.menu.get(x['menu_id'], {'name': x['name']}))}"
            + (f" ({option_text(self.lang, x['options'])})" if x["options"] else "")
            + f" × {x['quantity']} = {self.money(x['subtotal'])}" for x in order["lines"])
        discount = ""
        if order["coupon_discount"] or order["points_used"]:
            discount = "\n" + self.tr("receipt_discount", coupon=self.money(order["coupon_discount"]),
                                      points=self.money(order["points_used"]), final=self.money(order["final_total"]))
        if order["customer"]:
            snap = order["customer"]
            who = snap["nickname"]
            member_line = self.tr("receipt_member", earned=f"{order['earned_points']:,}", points=f"{snap['points']:,}",
                                  visits=snap["visits"], coupons=snap["coupon_count"])
            if order["point_events"]:
                member_line += "\n" + self.tr("receipt_event", names=", ".join(order["point_events"]))
            if order["issued_coupon"]:
                member_line += "\n" + self.tr("receipt_coupon", name=order["issued_coupon"])
        else:
            who = self.tr("guest")
            member_line = self.tr("receipt_guest")
        self.query_one("#receipt", Static).update(
            self.tr("receipt_head", id=order["id"], who=who) + f"\n\n{lines}\n\n"
            + self.tr("receipt_total", total=self.money(order["total"])) + discount + "\n"
            + self.tr("receipt_cash", cash=self.money(order["cash"]), change=self.money(order["change"]),
                      detail=change_text(self.lang, order["change_breakdown"]))
            + f"\n\n{member_line}")
        self.menu = self.vault.read("menu", default={})
        self.inserted_cash = 0
        self.show_page("receipt-page")
        self.set_status(self.tr("paid_done"))

    # ------------------------------------------------------------------ 09 운영자
    def require_admin(self) -> None:
        if not self.admin_id:
            raise ValueError("운영자 로그인이 필요합니다")

    async def enter_admin(self, admin_id: str, how: str) -> None:
        self.admin_id = admin_id
        self.query_one("#op-password", Input).value = ""
        await self.load_menu_controls()
        self.audit("admin_login", how)
        self.set_admin_view("menu")
        self.show_page("admin-page")
        self.set_status(f"운영자 {admin_id} 로그인 ({how}). 끝나면 로그아웃을 눌러 주세요.")

    def set_admin_view(self, view: str) -> None:
        self.admin_view = view
        for name in ADMIN_VIEWS:
            self.query_one(f"#view-{name}", Button).variant = "primary" if name == view else "default"
        form_of = {"menu": "form-menu", "customers": "form-customers", "policy": "form-policy"}
        for form_id in ("form-menu", "form-customers", "form-policy"):
            self.query_one(f"#{form_id}").set_class(form_of.get(view) == form_id, "shown")
        if view == "customers":
            customers = self.vault.read("customers", default={})
            self.query_one("#admin-customer-id", Select).set_options(
                [(f"{cid} · {c['extra']['nickname']} ({c['extra']['points']:,}P)", cid) for cid, c in customers.items()])
        elif view == "policy":
            self.fill_policy_form()
        self.show_admin_view()

    def show_admin_view(self, history_of: str | None = None) -> None:
        table = self.query_one("#admin-data", DataTable)
        keyword = self.value_of("#admin-search").lower()
        self.query_one("#admin-title", Label).update(ADMIN_VIEWS[self.admin_view])
        table.clear(columns=True)
        if history_of:
            customer = self.vault.read("customers", default={})[history_of]
            table.add_columns("시각", "변동", "잔액", "사유", "처리자")
            for row in reversed(customer["extra"].get("point_history", [])):
                table.add_row(row["at"].replace("T", " ")[5:16], f"{row['delta']:+,}P", f"{row['balance']:,}P",
                              row["reason"], row["by"])
            return
        if self.admin_view == "menu":
            table.add_columns("ID", "메뉴명", "분류", "가격", "재고", "판매 수", "상태")
            for menu_id, item in self.menu.items():
                if keyword and keyword not in item["name"].lower() and keyword not in menu_id.lower():
                    continue
                table.add_row(menu_id, item["name"], item["category"], f"{item['price']:,}원",
                              str(item["stock"]), str(item.get("sold_count", 0)),
                              "품절" if item["sold_out"] else "판매 중")
        elif self.admin_view == "customers":
            table.add_columns("ID", "닉네임", "전화번호", "포인트", "쿠폰", "방문", "얼굴", "언어")
            for customer_id, customer in self.vault.read("customers", default={}).items():
                extra = customer["extra"]
                if keyword and keyword not in extra["nickname"].lower() and keyword not in customer_id.lower():
                    continue
                lang = extra.get("preferences", {}).get("language", "-")
                table.add_row(customer_id, extra["nickname"], mask_phone(customer["phone"]),
                              f"{extra['points']:,}P", f"{len(coupons_of(customer))}장",
                              f"{extra['visits']}회", "등록" if extra.get("face_enrolled") else "-", lang)
        elif self.admin_view == "orders":
            table.add_columns("주문번호", "대기자", "품목", "결제액", "적립", "받은 돈", "거스름돈", "시각")
            for order_id, order in sorted(self.vault.read("orders", default={}).items(), reverse=True):
                who = order["customer"]["nickname"] if order.get("customer") else "비회원"
                if keyword and keyword not in order_id.lower() and keyword not in who.lower():
                    continue
                items = ", ".join(f"{x['name']}×{x['quantity']}" for x in order["lines"])
                table.add_row(order_id, who, items, f"{order.get('final_total', order['total']):,}원",
                              f"{order.get('earned_points', 0):,}P", f"{order['cash']:,}원",
                              f"{order['change']:,}원", order["created_at"].replace("T", " ")[5:16])
        elif self.admin_view == "policy":
            table.add_columns("ID", "이벤트", "상태", "조건·혜택")
            now = datetime.now()
            for event in self.policy()["events"]:
                if keyword and keyword not in event["name"].lower():
                    continue
                table.add_row(event["id"], event["name"], policy_logic.event_status(event, now),
                              policy_logic.describe_event(event))
        else:
            log = audit.AuditLog(Path(config.DATA_DIR) / "audit.log")
            ok, broken = log.verify()
            table.add_columns("번호", "시각", "처리자", "행동", "대상")
            for entry in reversed(log._entries()[-100:]):
                table.add_row(str(entry["seq"]), datetime.fromtimestamp(entry["ts"]).strftime("%m-%d %H:%M"),
                              entry["actor"], entry["action"], entry["target"])
            self.set_status("감사 로그 무결성: 정상 (해시 체인 일치)" if ok
                            else f"감사 로그 변조 의심: {broken}번째 줄부터 해시가 맞지 않습니다", not ok)

    def selected_admin_menu(self) -> str:
        selected = self.query_one("#admin-menu-id", Select).value
        if is_blank(selected):
            raise ValueError("먼저 위에서 메뉴를 선택하세요")
        return str(selected)

    def fill_policy_form(self) -> None:
        policy = self.policy()
        values = {
            "#pol-base-rate": f"{policy['base_rate']:g}", "#pol-unit": policy["point_unit"],
            "#pol-min-use": policy["min_use"], "#pol-max-pct": policy["max_use_percent"],
            "#pol-coupon-every": policy["visit_coupon_every"], "#pol-coupon-amount": policy["visit_coupon_amount"],
            "#pol-coupon-days": policy["visit_coupon_days"],
        }
        for selector, value in values.items():
            self.query_one(selector, Input).value = str(value)
        self.query_one("#ev-id", Select).set_options([(f"{e['id']} · {e['name']}", e["id"]) for e in policy["events"]])
        settings = self.settings()
        self.query_one("#def-language", Select).value = settings.get("language", "ko")
        self.query_one("#def-contrast", Checkbox).value = bool(settings.get("high_contrast"))
        self.query_one("#def-large", Checkbox).value = bool(settings.get("large_mode"))

    def fill_event_form(self, event_id: str) -> None:
        event = next(e for e in self.policy()["events"] if e["id"] == event_id)
        days = ",".join(policy_logic.WEEKDAY_NAMES[d] for d in event["weekdays"])
        hours = f"{event['hours'][0]}-{event['hours'][1]}" if event.get("hours") else ""
        for selector, value in {
            "#ev-name": event["name"], "#ev-start": event["start"], "#ev-end": event["end"],
            "#ev-weekdays": days, "#ev-hours": hours, "#ev-categories": ",".join(event["categories"]),
            "#ev-rate": f"{event['rate']:g}" if event["rate"] else "", "#ev-bonus": str(event["bonus_points"] or ""),
            "#ev-min-order": str(event["min_order"] or ""),
        }.items():
            self.query_one(selector, Input).value = value
        self.query_one("#ev-enabled", Checkbox).value = event["enabled"]
        self.pending_delete = None

    def clear_event_form(self) -> None:
        self.query_one("#ev-id", Select).clear()
        for selector in ("#ev-name", "#ev-start", "#ev-end", "#ev-weekdays", "#ev-hours", "#ev-categories",
                         "#ev-rate", "#ev-bonus", "#ev-min-order"):
            self.query_one(selector, Input).value = ""
        self.query_one("#ev-enabled", Checkbox).value = True

    def save_settings(self, **changes) -> None:
        settings = self.settings()
        settings.update(changes)
        self.vault.write("settings", settings)

    # ------------------------------------------------------------------ 버튼 처리
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        try:
            await self.handle_button(button_id)
        except (ValueError, auth.AuthError) as exc:
            self.set_status(str(exc), True)

    async def handle_button(self, button_id: str) -> None:
        # 장치 금고 열기 -----------------------------------------------------
        if button_id == "unlock":
            if not Path(config.KEYSTORE_PATH).exists():
                raise ValueError("먼저 터미널에서 python tools/reset_data.py --yes 를 실행하세요")
            entered_admin_id = self.value_of("#admin-id").lower()
            if entered_admin_id in DEMO_MEMBER_IDS:
                raise ValueError("지금은 관리자 준비 화면입니다. 관리자 ID admin을 입력하세요")
            self.vault = auth.unlock(config.KEYSTORE_PATH, config.DATA_DIR, entered_admin_id,
                                     self.query_one("#admin-password", Input).value)
            self.query_one("#admin-password", Input).value = ""
            await self.load_menu_controls()
            self.face_provider = None
            self.apply_display_defaults()
            self.show_page("home-page")
            self.set_status("시연 준비가 끝났습니다. 여기부터가 고객용 KIOSK 흐름입니다.")

        # 01 주문 시작 · 02 회원 인증 ----------------------------------------
        elif button_id == "member-order":
            self.show_page("member-login-page")
            self.query_one("#member-login-id", Input).focus()
        elif button_id in {"guest-order", "member-as-guest"}:
            self.open_order()
        elif button_id in {"member-login-cancel", "cancel-signup", "home", "op-cancel"}:
            self.go_home()
        elif button_id == "member-face-login":
            customer = login_with_face(self.vault, self.value_of("#member-login-id"),
                                       self.get_face_provider(), lambda m: self.set_status(m))
            self.open_order(customer)
            self.set_status(self.tr("login_face_ok"))
        elif button_id == "member-password-login":
            customer = login_with_password(self.vault, self.value_of("#member-login-id"),
                                           self.query_one("#member-login-password", Input).value)
            self.query_one("#member-login-password", Input).value = ""
            self.open_order(customer)
            if not customer["extra"].get("preferences"):
                self.set_status(self.tr("login_pw_ok"))
        elif button_id == "member-face-enroll":
            customer = login_with_password(self.vault, self.value_of("#member-login-id"),
                                           self.query_one("#member-login-password", Input).value)
            self.query_one("#member-login-password", Input).value = ""
            self.open_face_page(customer)
        elif button_id == "face-start":
            target = self.face_target
            if not target:
                raise ValueError("등록할 회원 정보가 없습니다. 처음부터 다시 시도하세요")
            try:
                self.get_face_provider().enroll_face(target["id"], lambda m: self.set_status(m))
            except ValueError as exc:
                raise ValueError(self.tr("face_failed", reason=str(exc))) from exc
            record = set_face_enrolled(self.vault, target["id"], True)
            self.face_target = None
            self.open_order(record)
            self.set_status(self.tr("face_done"))
        elif button_id == "face-skip":
            record, self.face_target = self.face_target, None
            self.open_order(record)
            self.set_status(self.tr("face_later"))

        # 회원 가입 ---------------------------------------------------------
        elif button_id == "signup":
            self.open_signup()
        elif button_id == "create-member":
            password = self.query_one("#signup-password", Input).value
            validate_password_pair(password, self.query_one("#signup-password2", Input).value)
            record = register_customer(
                self.vault, self.value_of("#signup-name"), "",
                self.value_of("#signup-phone"), self.value_of("#signup-login-id"),
                password, "", sorted(self.signup_allergies, key=allergen_list.ALLERGENS.index),
                self.query_one("#privacy", Checkbox).value,
                self.query_one("#marketing", Checkbox).value, False,
            )
            # 가입할 때 고른 언어·접근성 설정을 회원 카드에 같이 저장한다
            record = save_preferences(self.vault, record["id"], {
                "language": self.lang, "high_contrast": self.high_contrast, "large_mode": self.large_mode})
            face_requested = self.query_one("#face-consent", Checkbox).value
            self.clear_signup_form()
            if face_requested:
                self.open_face_page(record)   # 동의한 사람만 얼굴 등록 화면으로
            else:
                self.open_order(record)       # 동의하지 않으면 바로 이용 화면으로
                self.set_status(self.tr("signup_done", nick=record["extra"]["nickname"],
                                        phone=mask_phone(record["phone"])))

        # 03 메뉴 · 04 옵션 · 05 장바구니 -----------------------------------
        elif button_id.startswith("menu-"):
            self.open_options(button_id.removeprefix("menu-"))
        elif button_id == "option-add":
            quantity = self.int_of("#opt-quantity", 1)
            updated = cart_logic.add_item(self.cart, self.option_menu_id, quantity,
                                          self.selected_options(), self.menu)
            cart_logic.cart_lines(updated, self.menu)  # 재고가 모자라면 여기서 막고 장바구니는 그대로
            self.cart = updated
            item = self.menu[self.option_menu_id]
            self.option_menu_id = None
            self.show_page("order-page")
            self.refresh_cart(quiet=True)
            self.set_status(self.tr("added", name=menu_name(self.lang, item), qty=quantity,
                                    total=self.money(self.cart_total())))
        elif button_id == "option-cancel":
            self.option_menu_id = None
            self.show_page("order-page")
            self.refresh_cart()
        elif button_id in {"cart-plus", "cart-minus", "cart-delete"}:
            key = self.selected_cart_key()
            current = cart_logic.cart_lines({key: self.cart[key]}, self.menu)[0]["quantity"]
            new_quantity = {"cart-plus": current + 1, "cart-minus": current - 1, "cart-delete": 0}[button_id]
            updated = cart_logic.change_quantity(self.cart, key, new_quantity)
            cart_logic.cart_lines(updated, self.menu)  # 재고 초과면 바꾸지 않는다
            self.cart = updated
            self.refresh_cart()
        elif button_id == "clear-cart":
            self.cart = {}
            self.refresh_cart()
        elif button_id == "go-checkout":
            self.open_checkout()

        # 06 혜택 ----------------------------------------------------------
        elif button_id == "benefit-apply":
            choice = self.read_benefit_inputs()
            self.update_benefit_summary(choice)
            self.benefit_choice = choice
            self.set_status(self.tr("benefit_applied"))
        elif button_id == "benefit-max":
            choice = self.read_benefit_inputs()
            policy = self.policy()
            after_coupon = apply_benefits(self.cart_total(), self.customer, choice["coupon_id"],
                                          policy=policy)["final_total"]
            choice["use_points"] = max_usable_points(after_coupon, self.customer["extra"]["points"], policy)
            self.query_one("#benefit-points", Input).value = str(choice["use_points"])
            self.update_benefit_summary(choice)
            self.benefit_choice = choice
        elif button_id == "benefit-pay":
            choice = self.read_benefit_inputs()
            self.update_benefit_summary(choice)
            self.benefit_choice = choice
            self.open_payment()
        elif button_id == "benefit-skip":
            self.benefit_choice = {"coupon_id": None, "use_points": 0}
            self.open_payment()
        elif button_id == "benefit-back":
            self.show_page("order-page")
            self.refresh_cart()

        # 07 현금 결제 -----------------------------------------------------
        elif button_id == "insert-cash":
            self.add_cash(self.int_of("#cash"))
        elif button_id.startswith("cash-") and button_id[5:].isdigit():
            self.add_cash(int(button_id[5:]))
        elif button_id == "pay":
            if self.value_of("#cash"):
                self.add_cash(self.int_of("#cash"))
            total = self.payable_total()
            if self.inserted_cash < total:
                raise ValueError(self.tr("pay_short_error", n=self.money(total - self.inserted_cash)))
            self.finish_payment()
        elif button_id == "cash-refund":
            refund, self.inserted_cash = self.inserted_cash, 0
            self.update_payment_summary()
            self.set_status(self.tr("cash_returned", n=self.money(refund)) if refund else self.tr("no_cash"))
        elif button_id == "back-from-payment":
            if self.inserted_cash:
                raise ValueError(self.tr("refund_first"))
            if self.customer:
                self.open_benefits()
            else:
                self.show_page("order-page")
                self.refresh_cart()

        # 08 완료 ----------------------------------------------------------
        elif button_id == "next-customer":
            self.go_home(self.tr("next_waiting"))

        # 09 운영자 --------------------------------------------------------
        elif button_id == "admin":
            self.reset_session()
            self.show_page("admin-login-page")
            self.query_one("#op-id", Input).focus()
        elif button_id == "op-password-login":
            admin_id = self.value_of("#op-id").lower()
            auth.unlock(config.KEYSTORE_PATH, config.DATA_DIR, admin_id,
                        self.query_one("#op-password", Input).value)
            await self.enter_admin(admin_id, "비밀번호")
        elif button_id == "op-face-login":
            admin_id = self.value_of("#op-id").lower()
            if not admin_id or not auth.admin_exists(config.KEYSTORE_PATH, admin_id):
                raise ValueError("운영자 ID를 확인해 주세요")
            key = auth.admin_face_key(admin_id)
            try:
                matched = self.get_face_provider().identify_face(key, lambda m: self.set_status(m))
            except FaceError as exc:
                raise ValueError(f"{exc} · 비밀번호 로그인을 사용하세요") from exc
            if matched != key:
                raise ValueError("얼굴이 일치하지 않습니다. 비밀번호 로그인을 사용하세요")
            await self.enter_admin(admin_id, "얼굴")
        elif button_id in {"view-menu", "view-customers", "view-orders", "view-policy", "view-audit"}:
            self.require_admin()
            self.pending_delete = None
            self.set_admin_view(button_id.removeprefix("view-"))

        # 메뉴 관리
        elif button_id == "save-menu":
            self.require_admin()
            name = self.value_of("#admin-menu-name")
            category = self.value_of("#admin-category")
            price = self.int_of("#admin-price")
            stock = self.int_of("#admin-stock")
            if not name or not category or price <= 0 or stock < 0:
                raise ValueError("이름·분류·가격(1원 이상)·재고(0개 이상)를 확인하세요")
            if category not in CATEGORY_ICONS:
                raise ValueError("카테고리는 커피·논커피·차·에이드·디저트 중 하나로 입력하세요")
            selected = self.query_one("#admin-menu-id", Select).value
            menu_id = schema.next_id("M", self.menu, width=3) if is_blank(selected) else str(selected)
            old = self.menu.get(menu_id, {})
            self.menu[menu_id] = {
                **old, "id": menu_id, "name": name, "category": category, "price": price,
                "stock": stock, "sold_count": old.get("sold_count", 0),
                "sold_out": stock == 0, "allergens": old.get("allergens", []),
            }
            self.vault.write("menu", self.menu)
            self.audit("menu_save", menu_id)
            await self.load_menu_controls()
            self.set_admin_view("menu")
            self.set_status(f"{menu_id} 메뉴를 저장했습니다")
        elif button_id == "toggle-sold-out":
            self.require_admin()
            menu_id = self.selected_admin_menu()
            item = self.menu[menu_id]
            if item["sold_out"] and item["stock"] == 0:
                raise ValueError("재고가 0개입니다. 재고를 먼저 채우고 저장하세요")
            item["sold_out"] = not item["sold_out"]
            self.vault.write("menu", self.menu)
            self.audit("menu_sold_out" if item["sold_out"] else "menu_on_sale", menu_id)
            await self.load_menu_controls()
            self.set_admin_view("menu")
            self.set_status(f"{item['name']} → {'품절' if item['sold_out'] else '판매 중'}")
        elif button_id == "delete-menu":
            self.require_admin()
            menu_id = self.selected_admin_menu()
            if self.pending_delete != menu_id:
                self.pending_delete = menu_id
                raise ValueError(f"'{self.menu[menu_id]['name']}' 메뉴를 삭제할까요? 한 번 더 누르면 삭제합니다")
            self.pending_delete = None
            removed = self.menu.pop(menu_id)
            self.vault.write("menu", self.menu)
            self.audit("menu_delete", menu_id)
            await self.load_menu_controls()
            self.show_admin_view()
            self.set_status(f"{removed['name']} 메뉴를 삭제했습니다")

        # 회원 포인트 조정
        elif button_id == "adjust-points":
            self.require_admin()
            selected = self.query_one("#admin-customer-id", Select).value
            if is_blank(selected):
                raise ValueError("포인트를 조정할 회원을 먼저 선택하세요")
            raw = self.value_of("#adjust-delta").replace(",", "").replace("+", "")
            try:
                delta = int(raw)
            except ValueError as exc:
                raise ValueError("조정 포인트는 +500 / -300 처럼 숫자로 입력하세요") from exc
            record = adjust_points(self.vault, str(selected), delta, self.value_of("#adjust-reason"), self.admin_id)
            self.audit("points_adjust", f"{selected} {delta:+d}")
            self.query_one("#adjust-delta", Input).value = ""
            self.query_one("#adjust-reason", Input).value = ""
            self.set_admin_view("customers")
            self.query_one("#admin-customer-id", Select).value = str(selected)
            self.show_admin_view(history_of=str(selected))
            self.set_status(f"{record['extra']['nickname']} 포인트 {delta:+,}P 조정 → 잔액 {record['extra']['points']:,}P")
        elif button_id == "view-point-history":
            self.require_admin()
            selected = self.query_one("#admin-customer-id", Select).value
            if is_blank(selected):
                raise ValueError("내역을 볼 회원을 먼저 선택하세요")
            self.show_admin_view(history_of=str(selected))

        # 포인트 정책 · 이벤트 · 화면 기본값
        elif button_id == "save-policy":
            self.require_admin()
            current = self.policy()
            policy = policy_logic.validate_policy({
                **current,
                "base_rate": self.float_of("#pol-base-rate", current["base_rate"]),
                "point_unit": self.int_of("#pol-unit", current["point_unit"]),
                "min_use": self.int_of("#pol-min-use", current["min_use"]),
                "max_use_percent": self.int_of("#pol-max-pct", current["max_use_percent"]),
                "visit_coupon_every": self.int_of("#pol-coupon-every", current["visit_coupon_every"]),
                "visit_coupon_amount": self.int_of("#pol-coupon-amount", current["visit_coupon_amount"]),
                "visit_coupon_days": self.int_of("#pol-coupon-days", current["visit_coupon_days"]),
            })
            self.save_settings(point_policy=policy)
            self.audit("policy_save", f"rate={policy['base_rate']:g}% unit={policy['point_unit']}")
            self.set_admin_view("policy")
            self.set_status(f"적립·사용 정책 저장: 기본 {policy['base_rate']:g}% · {policy['point_unit']}P 단위 · "
                            f"최소 {policy['min_use']}P · 최대 {policy['max_use_percent']}% · "
                            + (f"{policy['visit_coupon_every']}회마다 {policy['visit_coupon_amount']:,}원 쿠폰"
                               if policy["visit_coupon_every"] else "방문 쿠폰 끔"))
        elif button_id == "save-event":
            self.require_admin()
            selected = self.query_one("#ev-id", Select).value
            policy, event = policy_logic.upsert_event(self.policy(), {
                "id": "" if is_blank(selected) else str(selected),
                "name": self.value_of("#ev-name"), "start": self.value_of("#ev-start"),
                "end": self.value_of("#ev-end"), "weekdays": self.value_of("#ev-weekdays"),
                "hours": self.value_of("#ev-hours"), "categories": self.value_of("#ev-categories"),
                "rate": self.float_of("#ev-rate"), "bonus_points": self.int_of("#ev-bonus"),
                "min_order": self.int_of("#ev-min-order"),
                "enabled": self.query_one("#ev-enabled", Checkbox).value,
            })
            self.save_settings(point_policy=policy)
            self.audit("event_save", event["id"])
            self.set_admin_view("policy")
            self.query_one("#ev-id", Select).value = event["id"]
            self.set_status(f"{event['id']} '{event['name']}' 저장 · {policy_logic.event_status(event)} · "
                            f"{policy_logic.describe_event(event)}")
        elif button_id == "new-event":
            self.require_admin()
            self.clear_event_form()
            self.set_status("새 이벤트 정보를 입력한 뒤 '이벤트 추가/수정'을 누르세요")
        elif button_id == "delete-event":
            self.require_admin()
            selected = self.query_one("#ev-id", Select).value
            if is_blank(selected):
                raise ValueError("삭제할 이벤트를 먼저 선택하세요")
            if self.pending_delete != f"event:{selected}":
                self.pending_delete = f"event:{selected}"
                raise ValueError(f"{selected} 이벤트를 삭제할까요? 한 번 더 누르면 삭제합니다")
            self.pending_delete = None
            self.save_settings(point_policy=policy_logic.remove_event(self.policy(), str(selected)))
            self.audit("event_delete", str(selected))
            self.clear_event_form()
            self.set_admin_view("policy")
            self.set_status(f"{selected} 이벤트를 삭제했습니다")
        elif button_id == "save-display":
            self.require_admin()
            lang = self.query_one("#def-language", Select).value
            self.save_settings(language="ko" if is_blank(lang) else str(lang),
                               high_contrast=self.query_one("#def-contrast", Checkbox).value,
                               large_mode=self.query_one("#def-large", Checkbox).value)
            self.audit("display_defaults", str(lang))
            self.set_status("손님 화면 기본값을 저장했습니다. 다음 손님부터 적용됩니다.")

        # 계정 · 종료
        elif button_id == "op-face-enroll":
            self.require_admin()
            self.get_face_provider().enroll_face(auth.admin_face_key(self.admin_id), lambda m: self.set_status(m))
            self.audit("admin_face_enroll", self.admin_id)
            self.set_status("관리자 얼굴 등록 완료 · 다음부터 운영자 ID + 얼굴로 로그인할 수 있습니다.")
        elif button_id == "admin-logout":
            self.audit("admin_logout")
            self.admin_id = None
            self.pending_delete = None
            self.query_one("#admin-search", Input).value = ""
            self.go_home("운영자 로그아웃 완료.")
        elif button_id == "quit":
            self.require_admin()
            self.audit("kiosk_shutdown")
            self.exit()


if __name__ == "__main__":
    KioskApp().run()
