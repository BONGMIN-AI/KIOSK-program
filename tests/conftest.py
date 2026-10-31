"""테스트 중에는 꽂혀 있는 아두이노 카드 리더(시리얼)를 열지 않는다."""
import os

os.environ.setdefault("KIOSK_CARD_PORT", "off")
