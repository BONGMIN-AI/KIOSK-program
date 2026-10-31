"""RC522 + 아두이노 카드 리더를 키오스크 없이 점검한다. 카드를 대면 키오스크가 받을 번호를 보여 준다.

사용: python tools/check_card_reader.py            (아두이노 포트를 스스로 찾음)
      python tools/check_card_reader.py COM5       (포트를 직접)
끄기: Ctrl+C. 카드 번호는 화면에만 보여 주고 저장하지 않는다.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gui.serial_card import BAUD, find_port, parse_line


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
    print(f"\n{name} 를 엽니다 (속도 {BAUD}). 아두이노가 다시 켜지느라 2초쯤 걸립니다. 카드를 대 보세요. 끄기: Ctrl+C\n")
    seen = {}
    link = None
    while link is None:                       # 시리얼 모니터 같은 다른 프로그램이 잡고 있으면 풀릴 때까지 기다린다
        try:
            link = serial.Serial(name, BAUD, timeout=0.5)
        except serial.SerialException:
            print(f"{name} 를 다른 프로그램이 쓰고 있어요 (Arduino IDE 시리얼 모니터를 닫아 주세요). 3초 뒤 다시…", flush=True)
            time.sleep(3)
    print(f"{name} 연결됨. 카드를 대 보세요.", flush=True)
    with link:
        try:
            while True:
                line = link.readline().decode("ascii", errors="ignore").strip()
                if not line:
                    continue
                number = parse_line(line)
                if number:
                    seen[number] = seen.get(number, 0) + 1
                    print(f"카드 번호 {number}  (이 카드 {seen[number]}번째) → 키오스크가 받는 번호", flush=True)
                elif line.startswith("ERROR"):
                    print(f"[리더 오류] {line} → RC522 배선(3.3V·GND·SDA→D10·RST→D9)을 확인하세요")
                else:
                    print(f"[리더] {line}", flush=True)
        except KeyboardInterrupt:
            print(f"\n끝. 읽은 카드 {len(seen)}장.")


if __name__ == "__main__":
    main()
