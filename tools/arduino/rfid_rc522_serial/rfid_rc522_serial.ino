/*
  COFFEE & SPOON 키오스크 - RFID 회원 카드 리더 (RC522 + Arduino Uno/Nano)

  카드를 대면 USB 시리얼로 한 줄을 보낸다:   CARD 84E3D237
  - 카드 고유 번호(UID)를 16진수 대문자로 보낸다 (4바이트 카드 = 8글자, 7바이트 카드 = 14글자).
  - 11/04: 카드를 댈 때 한 번만 보낸다. 대고 있는 동안은 다시 보내지 않고, 떼면 "REMOVED"를 보낸다.
    키오스크는 REMOVED를 받으면 같은 카드라도 다음에 대면 바로 받는다 (떼었다 다시 대기).
  - 11/04: 칩 버전이 이상하거나 카드 없이 20초가 지나면 칩을 다시 초기화한다.
    (못 읽을 때마다 다시 켜던 것은 뺐다: 카드를 대는 동안 계속 꺼졌다 켜져서 더 못 읽었다)
  - 11/04: 카드는 느끼는데 번호 대답이 없으면(Timeout) 수신 세기를 48 → 43 → 38 → 33dB로 바꿔 가며 읽는다.
    카드가 아주 가까우면 최대 세기에서 오히려 못 읽는 일이 있다. 한 번 읽힌 세기를 기억해 다음에 먼저 쓴다.
  - 11/04: 칩 상태 검사는 2초에 한 번, 3번 이어서 이상할 때만 다시 켠다 (너무 자주 켜서 카드를 못 읽었음).
  - 시험 도구(tools/check_card_reader.py)가 'D'를 보내면 자세히 보기: 시도마다 결과 · 카드 종류(SAK)를 보낸다.
    키오스크는 아무것도 보내지 않으니 평소에는 꺼져 있다. 'N'을 보내면 끈다.
  - 5초마다 "ALIVE"를 보낸다. 키오스크는 이게 오래 안 오면 포트를 다시 열어 보드를 리셋한다.
  - 켜지면 "READY RC522 v0x92 tap"처럼 칩 버전을, 칩을 못 찾으면 "ERROR RC522 not found"를 보낸다.
  - 카드는 느꼈는데 번호를 못 읽으면 카드를 댈 때마다 한 번 "INFO read failed: (이유)"를 보낸다.

  준비: Arduino IDE → 라이브러리 매니저에서 "MFRC522" (GithubCommunity) 설치 → 보드 Uno/Nano 선택 → 업로드.
  시리얼 속도 9600. 키오스크 쪽은 gui/serial_card.py, 시험은 tools/check_card_reader.py.

  배선 (RC522 → Uno/Nano)  * RC522는 3.3V 전용. 5V에 꽂지 말 것 *
    SDA(SS) → D10    SCK → D13    MOSI → D11    MISO → D12
    RST     → D9     GND → GND    3.3V → 3.3V   IRQ  → 연결 안 함
*/
#include <SPI.h>
#include <MFRC522.h>

// 11/04: 키오스크 리더는 RC카(물류 로봇) 보드 Nano + J7 RFID 커넥터를 그대로 쓴다 (로봇 배선: SS D2 · RST D4).
// (우노 + 따로 꽂은 RC522는 카드는 느끼지만 번호를 못 읽었다.) 우노 배선(SS D10 · RST D9)으로 쓸 때만 아래 줄을 // 로 막는다.
#define ROBOT_BOARD
#ifdef ROBOT_BOARD
const byte SS_PIN = 2;
const byte RST_PIN = 4;
#else
const byte SS_PIN = 10;
const byte RST_PIN = 9;
#endif
// 수신 세기 차례 (48 · 43 · 38 · 33dB). 시도마다 하나씩 바꾼다.
const byte GAINS[] = {MFRC522::RxGain_48dB, MFRC522::RxGain_43dB, MFRC522::RxGain_38dB, MFRC522::RxGain_33dB};
const byte GAIN_DB[] = {48, 43, 38, 33};
const byte READ_TRIES = sizeof(GAINS);
const unsigned long DEBUG_GAP_MS = 1000;     // 자세히 보기에서 못 읽음 줄은 1초에 한 번만
const unsigned long GONE_MS = 1000;          // 이만큼 카드가 안 보이면 뗀 것으로 본다
const unsigned long IDLE_RESET_MS = 20000;   // 카드 없이 이만큼 지나면 칩을 한 번 다시 켠다 (멈춤 예방)
const unsigned long ALIVE_MS = 5000;
const unsigned long HEALTH_MS = 2000;        // 칩 상태 검사 간격
const byte HEALTH_BAD_LIMIT = 3;             // 이만큼 이어서 이상하면 다시 켠다

MFRC522 reader(SS_PIN, RST_PIN);
byte lastUid[10];
byte lastSize = 0;
bool holding = false;          // 카드를 대고 있는 중 (CARD를 이미 보냄)
bool failedShown = false;      // 이번에 댄 카드의 '못 읽음'을 이미 보냄
byte bestGain = 0;             // 마지막으로 읽힌 세기 (GAINS 차례 번호)
byte atqa[2];                  // 카드가 처음 대답한 종류 값 (자세히 보기용)
unsigned long lastDebug = 0;
unsigned long lastSeen = 0;    // 카드를 마지막으로 느낀 때
unsigned long lastReset = 0;
unsigned long lastAlive = 0;
unsigned long lastHealth = 0;
byte healthBad = 0;
bool debug = false;            // 시험 도구가 켠 자세히 보기

void printHex(const byte *uid, byte size) {
  for (byte i = 0; i < size; i++) {
    if (uid[i] < 0x10) Serial.print('0');
    Serial.print(uid[i], HEX);
  }
}

bool sameAsLast(const byte *uid, byte size) {
  return size == lastSize && memcmp(uid, lastUid, size) == 0;
}

// 칩 켜기 (처음 · 멈춘 것 같을 때). 칩 버전을 돌려준다 (0x00·0xFF = 못 찾음).
byte startReader() {
  reader.PCD_Init();
  delay(50);
  byte version = reader.PCD_ReadRegister(MFRC522::VersionReg);
  if (version != 0x00 && version != 0xFF) {
    // 호환 칩(v0x12·0x18 등)은 기본 수신 감도로는 카드를 잘 못 찾는 경우가 있어 높여 둔다
    reader.PCD_SetAntennaGain(GAINS[bestGain]);
    reader.PCD_AntennaOn();
  }
  lastReset = millis();
  return version;
}

void restartReader(const char *why) {
  byte version = startReader();
  Serial.print("STATUS reader restarted (");
  Serial.print(why);
  Serial.print(") v0x");
  Serial.println(version, HEX);
}

// 칩이 멀쩡한지: 버전이 읽히는지 (안테나 레지스터는 호환 칩에서 자주 다르게 읽혀 보지 않는다)
bool readerHealthy() {
  byte version = reader.PCD_ReadRegister(MFRC522::VersionReg);
  return version != 0x00 && version != 0xFF;
}

// 카드 번호 읽기(선택). 실패하면 수신 세기를 바꾸고 카드를 다시 깨워(WUPA) 또 시도한다.
// 자세히 보기면 "DEBUG atqa 0400 | 48:3 43:0" (세기:결과 번호) 처럼 한 줄로 보낸다.
MFRC522::StatusCode readUid(bool report) {
  MFRC522::StatusCode status = MFRC522::STATUS_ERROR;
  if (report) {
    Serial.print("DEBUG atqa ");
    printHex(atqa, 2);
    Serial.print(" |");
  }
  for (byte attempt = 0; attempt < READ_TRIES; attempt++) {
    byte g = (bestGain + attempt) % READ_TRIES;
    if (attempt > 0) {
      reader.PCD_SetAntennaGain(GAINS[g]);
      byte size = sizeof(atqa);
      reader.PICC_HaltA();
      delay(5);
      if (reader.PICC_WakeupA(atqa, &size) != MFRC522::STATUS_OK) {
        if (report) { Serial.print(" "); Serial.print(GAIN_DB[g]); Serial.print(":gone"); }
        continue;
      }
    }
    status = reader.PICC_Select(&reader.uid, 0);
    if (report) {
      Serial.print(" ");
      Serial.print(GAIN_DB[g]);
      Serial.print(":");
      Serial.print((int)status);                 // 0 성공 · 2 충돌 · 3 대답 없음 · 7 CRC (시험 도구가 글로 바꿈)
    }
    if (status == MFRC522::STATUS_OK) {
      bestGain = g;
      break;
    }
  }
  if (report) Serial.println();
  reader.PCD_SetAntennaGain(GAINS[bestGain]);
  return status;
}

// 새 카드(IDLE)뿐 아니라 앞에서 읽고 잠든(HALT) 카드도 깨워서 찾는다. 대답(ATQA)은 atqa에 남긴다.
bool cardPresent() {
  byte size = sizeof(atqa);
  reader.PCD_WriteRegister(MFRC522::TxModeReg, 0x00);      // PICC_IsNewCardPresent와 같은 준비
  reader.PCD_WriteRegister(MFRC522::RxModeReg, 0x00);
  reader.PCD_WriteRegister(MFRC522::ModWidthReg, 0x26);
  MFRC522::StatusCode status = reader.PICC_RequestA(atqa, &size);
  if (status == MFRC522::STATUS_OK || status == MFRC522::STATUS_COLLISION) {
    return true;
  }
  size = sizeof(atqa);
  return reader.PICC_WakeupA(atqa, &size) == MFRC522::STATUS_OK;
}

void setup() {
  Serial.begin(9600);
  SPI.begin();
  byte version = startReader();
  if (version == 0x00 || version == 0xFF) {
    Serial.println("ERROR RC522 not found");   // 배선·전원 확인
  } else {
    Serial.print("READY RC522 v0x");
    Serial.print(version, HEX);
    Serial.println(" gain auto tap");             // tap = 댈 때 한 번 + REMOVED 를 보내는 판
  }
}

void loop() {
  unsigned long now = millis();
  while (Serial.available()) {                       // 시험 도구가 보내는 글자
    char c = Serial.read();
    if (c == 'D') { debug = true; Serial.println("DEBUG on"); }
    if (c == 'N') { debug = false; Serial.println("DEBUG off"); }
  }
  if (now - lastAlive >= ALIVE_MS) {
    Serial.println("ALIVE");
    lastAlive = now;
  }

  if (!cardPresent()) {
    if ((holding || failedShown) && now - lastSeen >= GONE_MS) {
      if (holding) Serial.println("REMOVED");
      holding = false;
      failedShown = false;
    }
    if (!holding && now - lastSeen >= IDLE_RESET_MS && now - lastReset >= IDLE_RESET_MS) {
      startReader();                               // 조용히 다시 켠다 (카드 없을 때만)
    } else if (now - lastHealth >= HEALTH_MS) {
      lastHealth = now;
      healthBad = readerHealthy() ? 0 : healthBad + 1;
      if (healthBad >= HEALTH_BAD_LIMIT) {
        healthBad = 0;
        restartReader("health");
      }
    }
    delay(50);
    return;
  }
  lastSeen = now;
  bool report = debug && !holding && now - lastDebug >= DEBUG_GAP_MS;
  if (report) lastDebug = now;

  MFRC522::StatusCode status = readUid(report);
  if (status != MFRC522::STATUS_OK) {
    if (!holding && !failedShown) {                // 댈 때마다 한 번만 알린다
      Serial.print("INFO read failed: ");
      Serial.println(MFRC522::GetStatusCodeName(status));
      failedShown = true;
    }
    reader.PICC_HaltA();
    return;
  }

  byte size = reader.uid.size;
  if (!holding || !sameAsLast(reader.uid.uidByte, size)) {
    Serial.print("CARD ");
    printHex(reader.uid.uidByte, size);
    Serial.println();
    if (debug) {
      Serial.print("DEBUG gain ");
      Serial.print(GAIN_DB[bestGain]);
      Serial.print(" sak 0x");
      Serial.print(reader.uid.sak, HEX);
      Serial.print(" ");
      Serial.println(MFRC522::PICC_GetTypeName(MFRC522::PICC_GetType(reader.uid.sak)));
    }
    memcpy(lastUid, reader.uid.uidByte, size);
    lastSize = size;
    holding = true;
    failedShown = false;
  }
  reader.PICC_HaltA();
  reader.PCD_StopCrypto1();
}
