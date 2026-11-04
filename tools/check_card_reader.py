"""RC522 + 아두이노 카드 리더를 키오스크 없이 점검한다 (11/04: 못 읽는 이유까지 한국어로 보여 준다).

사용: 4_카드리더_시험.bat 더블클릭, 또는 python tools/check_card_reader.py [COM6]
키오스크가 켜져 있으면 포트를 같이 쓸 수 없으니 키오스크를 먼저 끈다. 끄기: Ctrl+C 또는 창 닫기.
리더에 'D'를 보내 자세히 보기를 켠다: 시도마다 결과, 읽으면 카드 종류(SAK)까지 온다.
카드 번호는 화면에만 보여 주고 저장하지 않는다.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gui.serial_card import BAUD, find_port, parse_line

# 라이브러리가 보내는 실패 이유 → 무슨 뜻인지 · 어떻게 해 볼지
REASONS = {
    "Timeout in communication.": "카드 대답이 없음 → 카드를 리더기 가운데에 평평하게, 1~2cm 안으로 대고 2초 기다려 보세요",
    "A collision was detected.": "카드가 여러 장 → 지갑 · 폰 케이스 속 다른 카드를 빼고 한 장만 대 보세요",
    "A CRC_A does not match.": "신호가 흐트러짐 → 조금 더 가까이, 움직이지 말고 대 보세요",
    "Error in communication.": "통신 오류 → 배선(특히 3.3V · GND)이 헐겁지 않은지 보세요",
    "Invalid argument.": "프로그램 오류 (거의 없음)",
    "Internal error in the code. Should not happen.": "카드 종류가 맞지 않을 수 있음 → 다른 카드로 비교해 보세요",
}
# 카드가 처음 대답한 값 (ATQA, 리더가 보내는 순서 그대로)
ATQA = {"0400": "MIFARE Classic 1K", "0200": "MIFARE Classic 4K", "4400": "Ultralight / NTAG",
        "4403": "DESFire", "0800": "보안 카드(교통카드 등)"}
# 시도 결과 번호 (MFRC522 StatusCode)
SHORT = {"0": "✅성공", "1": "통신 오류", "2": "카드 여러 장", "3": "대답 없음", "5": "내부 오류",
         "7": "신호 흐트러짐", "gone": "카드가 사라짐"}
# 읽었을 때 카드 종류 (SAK). 0x20 = 교통카드 · 신용카드 · 폰처럼 보안 카드
KINDS = {
    "0x8": "MIFARE Classic 1K (일반 회원카드 · 흰 카드) → 키오스크용으로 딱 맞아요",
    "0x18": "MIFARE Classic 4K → 써도 돼요",
    "0x0": "MIFARE Ultralight / NTAG (스티커 · 열쇠고리) → 써도 돼요",
    "0x20": "보안 카드 (교통카드 · 신용카드 · 휴대폰) → 번호가 바뀔 수 있어 회원카드로는 안 맞아요",
    "0x28": "보안 카드 (교통카드 등) → 회원카드로는 안 맞아요",
}


def explain(line, seen, counts):
    """리더 한 줄 → 한국어 한 줄 (보여 줄 게 없으면 None)."""
    number = parse_line(line)
    if number:
        seen[number] = seen.get(number, 0) + 1
        counts["ok"] += 1
        return f"✅ 읽음! 카드 번호 {number} (이 카드 {seen[number]}번째) → 키오스크가 받는 번호"
    if line.startswith("INFO read failed:"):
        counts["fail"] += 1
        reason = line.split(":", 1)[1].strip()
        return f"❌ 카드는 느꼈는데 번호를 못 읽음: {REASONS.get(reason, reason)}"
    if line.startswith("DEBUG atqa"):
        counts["seen"] += 1
        head, _, tries = line[len("DEBUG atqa "):].partition("|")
        code = head.strip()
        steps = []
        for part in tries.split():
            db, _, reason = part.partition(":")
            steps.append(f"{db}dB {SHORT.get(reason, reason)}")
        kind = ATQA.get(code, "모르는 종류")
        return f"   … 카드 느낌 (대답 {code} = {kind}) → " + " · ".join(steps)
    if line.startswith("DEBUG gain"):
        parts = line.split(" ", 5)                        # DEBUG gain 43 sak 0x8 이름
        kind = KINDS.get(parts[4].lower(), parts[5] if len(parts) > 5 else parts[4])
        return f"   카드 종류: {kind} (읽힌 세기 {parts[2]}dB)"
    if line.startswith("REMOVED"):
        return "   (카드를 뗌)"
    if line.startswith("STATUS reader restarted"):
        counts["restart"] += 1
        return "⚠ 리더 칩이 대답을 안 해서 다시 켰음 — 자주 나오면 배선(3.3V · GND) · 전원 문제"
    if line.startswith("READY"):
        tail = "" if "tap" in line else "  ※ 옛 스케치예요. 새 스케치를 올려야 자세히 보기가 돼요"
        return f"리더 준비됨: {line}{tail}"
    if line.startswith("ERROR"):
        return f"[리더 오류] {line} → RC522 배선(3.3V · GND · SDA→D10 · RST→D9)을 확인하세요"
    if line.startswith(("ALIVE", "DEBUG on", "DEBUG off")):
        return None
    return f"[리더] {line}"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")   # 안내 문구(SystemExit)도 한글이 깨지지 않게
    try:
        import serial
        from serial.tools import list_ports
    except ImportError:
        raise SystemExit("pyserial이 없습니다. 1_처음설치.bat 를 다시 실행하세요.")
    ports = list_ports.comports()
    print("이 PC의 COM 포트:")
    for port in ports:
        vid = f"{port.vid:04X}" if port.vid is not None else "----"
        print(f"  {port.device:8} VID {vid}  {port.description}")
    if not ports:
        print("  (없음) USB 케이블·드라이버(CH340)를 확인하세요.")
    name = sys.argv[1] if len(sys.argv) > 1 else find_port(ports)
    if not name:
        raise SystemExit("아두이노로 보이는 포트를 못 찾았습니다. 포트를 직접 적어 주세요: check_card_reader.py COM5")
    link = None
    while link is None:                       # 키오스크 · 시리얼 모니터가 잡고 있으면 풀릴 때까지 기다린다
        try:
            link = serial.Serial(name, BAUD, timeout=0.5)
        except serial.SerialException:
            print(f"{name} 를 다른 프로그램이 쓰고 있어요 (키오스크 · Arduino IDE 시리얼 모니터를 꺼 주세요). 3초 뒤 다시…",
                  flush=True)
            time.sleep(3)
    print(f"\n{name} 연결됨. 아두이노가 다시 켜지느라 2초쯤 걸려요.")
    print("카드를 한 장씩 대 보세요. 대고 2초 기다렸다가 떼고, 다시 대 보세요. 끄기: Ctrl+C 또는 창 닫기\n", flush=True)
    seen, counts = {}, {"ok": 0, "fail": 0, "seen": 0, "restart": 0}
    asked = False
    buffer = ""
    with link:
        try:
            while True:
                buffer += link.readline().decode("ascii", errors="ignore")
                if not buffer.endswith("\n"):               # 0.5초 안에 다 안 온 줄은 이어 받는다
                    continue
                line, buffer = buffer.strip(), ""
                if not line:
                    continue
                if line.startswith("READY") and not asked:
                    link.write(b"D")                 # 자세히 보기 켜기
                    asked = True
                text = explain(line, seen, counts)
                if text:
                    print(f"{time.strftime('%H:%M:%S')}  {text}", flush=True)
        except KeyboardInterrupt:
            pass
    print(f"\n끝. 읽음 {counts['ok']}번 · 못 읽음 {counts['fail']}번 · 칩 다시 켬 {counts['restart']}번 · 카드 {len(seen)}장")


if __name__ == "__main__":
    main()
