/*
  COFFEE & SPOON 키오스크 - RFID 회원 카드 리더 (RC522 + Arduino Uno/Nano)

  카드를 대면 USB 시리얼로 한 줄을 보낸다:   CARD 84E3D237
  - 카드 고유 번호(UID)를 16진수 대문자로 보낸다 (4바이트 카드 = 8글자, 7바이트 카드 = 14글자).
  - 같은 카드를 계속 대고 있어도 2초에 한 번만 보낸다.
  - 켜지면 "READY RC522 v0x92"처럼 칩 버전을, 칩을 못 찾으면 "ERROR RC522 not found"를 보낸다.
  - 카드는 느꼈는데 번호를 못 읽으면 "INFO read failed: (이유)"를 보낸다.

  준비: Arduino IDE → 라이브러리 매니저에서 "MFRC522" (GithubCommunity) 설치 → 보드 Uno/Nano 선택 → 업로드.
  시리얼 속도 9600. 키오스크 쪽은 gui/serial_card.py, 시험은 tools/check_card_reader.py.

  배선 (RC522 → Uno/Nano)  * RC522는 3.3V 전용. 5V에 꽂지 말 것 *
    SDA(SS) → D10    SCK → D13    MOSI → D11    MISO → D12
    RST     → D9     GND → GND    3.3V → 3.3V   IRQ  → 연결 안 함
*/
#include <SPI.h>
#include <MFRC522.h>

// 물류 로봇 보드(Nano, J7 RFID 커넥터)를 그대로 리더로 쓸 때는 아래 줄의 // 를 지운다 (로봇 배선: SS D2 · RST D4)
// #define ROBOT_BOARD
#ifdef ROBOT_BOARD
const byte SS_PIN = 2;
const byte RST_PIN = 4;
#else
const byte SS_PIN = 10;
const byte RST_PIN = 9;
#endif
const unsigned long REPEAT_MS = 2000;     // 같은 카드는 2초에 한 번만
const byte READ_TRIES = 4;                // 호환 칩은 한 번에 못 읽는 일이 잦아 몇 번 다시 시도한다

MFRC522 reader(SS_PIN, RST_PIN);
byte lastUid[10];
byte lastSize = 0;
unsigned long lastSent = 0;

void printHex(const byte *uid, byte size) {
  for (byte i = 0; i < size; i++) {
    if (uid[i] < 0x10) Serial.print('0');
    Serial.print(uid[i], HEX);
  }
}

bool sameAsLast(const byte *uid, byte size) {
  return size == lastSize && memcmp(uid, lastUid, size) == 0;
}

// 카드 번호 읽기(선택). 실패하면 카드를 다시 깨워(WUPA) 몇 번 더 시도한다. 마지막 실패 이유를 돌려준다.
MFRC522::StatusCode readUid() {
  MFRC522::StatusCode status = MFRC522::STATUS_ERROR;
  for (byte attempt = 0; attempt < READ_TRIES; attempt++) {
    if (attempt > 0) {
      byte atqa[2];
      byte atqaSize = sizeof(atqa);
      reader.PICC_HaltA();
      delay(5);
      if (reader.PICC_WakeupA(atqa, &atqaSize) != MFRC522::STATUS_OK) {
        continue;
      }
    }
    status = reader.PICC_Select(&reader.uid, 0);
    if (status == MFRC522::STATUS_OK) {
      return status;
    }
  }
  return status;
}

void setup() {
  Serial.begin(9600);
  SPI.begin();
  reader.PCD_Init();
  delay(50);
  byte version = reader.PCD_ReadRegister(MFRC522::VersionReg);
  if (version == 0x00 || version == 0xFF) {
    Serial.println("ERROR RC522 not found");   // 배선·전원 확인
  } else {
    // 호환 칩(v0x12·0x18 등)은 기본 수신 감도로는 카드를 잘 못 찾는 경우가 있어 최대로 올린다
    reader.PCD_SetAntennaGain(MFRC522::RxGain_max);
    Serial.print("READY RC522 v0x");
    Serial.print(version, HEX);
    Serial.println(" gain max");
  }
}

void loop() {
  if (!reader.PICC_IsNewCardPresent()) {
    return;
  }
  MFRC522::StatusCode status = readUid();
  if (status != MFRC522::STATUS_OK) {
    Serial.print("INFO read failed: ");          // 카드는 느꼈지만 번호를 못 읽음
    Serial.println(MFRC522::GetStatusCodeName(status));
    reader.PICC_HaltA();
    return;
  }
  byte size = reader.uid.size;
  unsigned long now = millis();
  if (!sameAsLast(reader.uid.uidByte, size) || now - lastSent >= REPEAT_MS) {
    Serial.print("CARD ");
    printHex(reader.uid.uidByte, size);
    Serial.println();
    memcpy(lastUid, reader.uid.uidByte, size);
    lastSize = size;
    lastSent = now;
  }
  reader.PICC_HaltA();
  reader.PCD_StopCrypto1();
}
