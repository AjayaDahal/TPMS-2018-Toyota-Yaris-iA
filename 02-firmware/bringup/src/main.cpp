// TPMS panel bring-up and 315 MHz receiver test.
//
// 1. Self-test: CC1101 ID / receive state / noise floor, OLED, LEDs, buzzer, encoder and button.
// 2. Receiver: listens on 315 MHz with the selected profile. GM/Schrader EG53MA4 frames (the sensors in the
//    tyres) are decoded to ID / pressure / temperature and listed on the OLED; any other burst is printed as
//    Manchester / differential Manchester / raw chips for analysis. Turn the knob (or send 'p') to change profile.
#include <Arduino.h>
#include <SPI.h>
#include <U8g2lib.h>

#include <algorithm>

#include "cc1101.h"
#include "driver/gpio.h"
#include "eg53ma4.h"
#include "pins.h"
#include "rf.h"
#include "soc/gpio_reg.h"

namespace {

// Receive profiles (315.000 MHz). See cc1101.h for the register formulas. The FSK profiles use a
// 38.4 kBd filter so chips down to ~50 us (19.2 kchip/s sensors) are resolved.
const RfProfile kProfiles[] = {
    // name               MDMCFG4 MDMCFG3 MDMCFG2 DEVIATN AGCCTRL2/1/0
    {"OOK bw203k 16kBd",   0x89,   0x4B,   0x30,   0x15,   0x03, 0x00, 0x91},  // GM/Schrader EG53MA4 (yours)
    {"FSK d25k bw135k",    0xAA,   0x83,   0x00,   0x40,   0x43, 0x40, 0x91},  // other sensor brands
    {"FSK d38k bw203k",    0x8A,   0x83,   0x00,   0x44,   0x43, 0x40, 0x91},
    {"FSK d48k bw270k",    0x6A,   0x83,   0x00,   0x47,   0x43, 0x40, 0x91},
};
constexpr int kCcModes = sizeof(kProfiles) / sizeof(kProfiles[0]);
constexpr int kModes = kCcModes + 1;   // last mode: optional MX-05V on IO36 (CC1101 idle)

U8G2_SSD1322_NHD_128X64_F_4W_HW_SPI oled(U8G2_R0, PIN_OLED_CS, PIN_OLED_DC, PIN_OLED_RES);
CC1101 cc(SPI, PIN_CC_CS, PIN_SPI_MISO);

bool ccOk = false;
int mode = 0;
bool rawDump = false;
uint32_t nBursts = 0, nFrames = 0;
int peakRssi = -200, liveRssi = -200, lastRssi = 0;
rf::Burst burst;
rf::Frame frame, lastFrame;
uint32_t ledsOffAt = 0, buzzerOffAt = 0;

// EG53MA4 sensors heard so far (the 4 in the tyres plus any from nearby cars)
struct Sensor {
  eg53ma4::Reading r;
  int rssi;
  uint32_t at;
  uint32_t count;
};
constexpr int kMaxSensors = 8;
Sensor sensors[kMaxSensors];
int nSensors = 0;

void remember(const eg53ma4::Reading& r, int rssi) {
  int slot = -1;
  for (int i = 0; i < nSensors; i++) {
    if (sensors[i].r.id == r.id) slot = i;
  }
  if (slot < 0) {
    if (nSensors < kMaxSensors) {
      slot = nSensors++;
    } else {
      slot = 0;   // table full: replace the one heard longest ago
      for (int i = 1; i < kMaxSensors; i++) {
        if (sensors[i].at < sensors[slot].at) slot = i;
      }
    }
    sensors[slot].count = 0;
  }
  sensors[slot].r = r;
  sensors[slot].rssi = rssi;
  sensors[slot].at = millis();
  sensors[slot].count++;
}

// ---- encoder: quadrature state machine on both edges of A and B (EC11: 4 counts per detent)
volatile int32_t encCount = 0;
volatile uint8_t encState = 0;

void IRAM_ATTR onEncoder() {
  static const int8_t kStep[16] = {0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0};
  const uint32_t in = *(volatile uint32_t*)GPIO_IN_REG;
  const uint8_t s = (((in >> PIN_ENC_A) & 1) << 1) | ((in >> PIN_ENC_B) & 1);
  encCount += kStep[(encState << 2) | s];
  encState = s;
}

const char* modeName(int m) { return m < kCcModes ? kProfiles[m].name : "MX-05V on IO36"; }

void setLeds(bool on) {
  for (int p : {PIN_LED_FL, PIN_LED_FR, PIN_LED_RL, PIN_LED_RR}) digitalWrite(p, on ? HIGH : LOW);
}

void beep(uint32_t ms) {
  digitalWrite(PIN_BUZZER, HIGH);   // active buzzer; a passive one needs a tone (ledcWriteTone) instead
  buzzerOffAt = millis() + ms;
}

void ledWalk() {
  for (int p : {PIN_LED_FL, PIN_LED_FR, PIN_LED_RR, PIN_LED_RL}) {
    digitalWrite(p, HIGH);
    delay(120);
    digitalWrite(p, LOW);
  }
}

void setMode(int m) {
  mode = ((m % kModes) + kModes) % kModes;
  bool inRx = false;
  if (mode < kCcModes) {
    if (ccOk) {
      cc.configure(kProfiles[mode]);
      for (int i = 0; i < 20 && !inRx; i++, delay(1)) inRx = cc.marcState() == 0x0D;   // calibration takes ~1 ms
    }
    rf::attach(PIN_CC_GDO0);
  } else {
    if (ccOk) cc.idle();
    rf::attach(PIN_MX05_DATA);
  }
  peakRssi = -200;
  Serial.printf("\nmode %d: %s%s\n", mode, modeName(mode),
                mode < kCcModes && ccOk ? (inRx ? "  (CC1101 in RX)" : "  (CC1101 NOT in RX!)") : "");
}

void printHelp() {
  Serial.println("keys: p = next profile, r = raw pulse dump on/off, t = LED/buzzer test, h = help");
  Serial.println("Profile 0 (OOK) decodes your GM/Schrader EG53MA4 sensors: wake one with the OEC-T5 tool, or drive.");
}

void selfTest() {
  Serial.println("\n=== TPMS panel bring-up ===");
  ccOk = cc.begin();
  Serial.printf("CC1101: PARTNUM 0x%02X VERSION 0x%02X -> %s\n", cc.partnum(), cc.version(),
                ccOk ? (cc.version() == 0x14 || cc.version() == 0x04 ? "TI chip OK" : "clone chip, should work")
                     : "NOT FOUND (0xFF = no answer: check U1 orientation, 3V3, SPI/CS wiring)");
  if (ccOk) {
    cc.configure(kProfiles[0]);
    delay(20);
    int sum = 0;
    for (int i = 0; i < 16; i++) {
      sum += cc.rssiDbm();
      delay(5);
    }
    Serial.printf("CC1101: state 0x%02X (0x0D = RX), noise floor %d dBm at 315 MHz\n", cc.marcState(), sum / 16);
    Serial.println("        (about -100 dBm or lower is good; much higher = interference from the board or nearby)");
  }
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x10_tf);
  oled.drawStr(0, 10, "TPMS panel bring-up");
  oled.drawStr(0, 22, ccOk ? "CC1101 found" : "CC1101 NOT FOUND");
  oled.drawStr(0, 34, "LEDs FL FR RR RL...");
  oled.drawStr(0, 46, "Turn knob = profile");
  oled.drawStr(0, 58, "Press knob = beep");
  oled.sendBuffer();
  Serial.println("OLED: shows a test screen if SPI/DC/RES/CS and the 3V3 rail are OK (if upside down use U8G2_R2)");
  ledWalk();
  beep(80);
  Serial.println("LEDs: walked FL FR RR RL. Buzzer: one beep.");
  Serial.printf("Encoder: A=%d B=%d, button=%s (idle should be A/B either level, button 1)\n",
                digitalRead(PIN_ENC_A), digitalRead(PIN_ENC_B), digitalRead(PIN_ENC_SW) ? "up" : "PRESSED");
}

void drawScreen() {
  char line[32];
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x10_tf);
  if (nSensors > 0) {   // sensor table: ID, pressure, temperature, seconds since last heard
    oled.drawStr(0, 9, "ID      psi   F  age");
    for (int i = 0; i < nSensors && i < 4; i++) {
      const Sensor& s = sensors[i];
      const unsigned long age = std::min<unsigned long>((millis() - s.at) / 1000, 999);
      snprintf(line, sizeof line, "%06lX %4.1f %3d %3lus", (unsigned long)s.r.id, eg53ma4::psi(s.r), s.r.tempF, age);
      oled.drawStr(0, 20 + i * 11, line);
    }
    snprintf(line, sizeof line, "%s %4ddBm %lu", mode < kCcModes ? "315" : "MX05", liveRssi, (unsigned long)nFrames);
    oled.drawStr(0, 63, line);
    oled.sendBuffer();
    return;
  }
  if (mode < kCcModes) {
    snprintf(line, sizeof line, ccOk ? "CC1101 v%02X %4ddBm" : "CC1101 missing", cc.version(), liveRssi);
  } else {
    snprintf(line, sizeof line, "MX-05V input");
  }
  oled.drawStr(0, 9, line);
  oled.drawStr(0, 19, modeName(mode));
  snprintf(line, sizeof line, "bursts %lu frames %lu", (unsigned long)nBursts, (unsigned long)nFrames);
  oled.drawStr(0, 29, line);
  if (lastFrame.nbits) {
    snprintf(line, sizeof line, "%uus %ub %ddBm", lastFrame.chipUs, lastFrame.nbits, lastRssi);
    oled.drawStr(0, 39, line);
    char hex[21];
    for (int row = 0; row < 2; row++) {
      int k = 0;
      for (int i = row * 10; i < row * 10 + 10 && i * 8 < lastFrame.nbits; i++) {
        k += snprintf(hex + k, sizeof hex - k, "%02X", lastFrame.man[i]);
      }
      hex[k] = 0;
      oled.drawStr(0, 50 + row * 10, hex);
    }
  } else {
    snprintf(line, sizeof line, "knob %ld  btn %s", (long)(encCount / 4), digitalRead(PIN_ENC_SW) ? "up" : "DN");
    oled.drawStr(0, 39, line);
    oled.drawStr(0, 50, "waiting for sensors");
    oled.drawStr(0, 60, "(drive or use LF tool)");
  }
  oled.sendBuffer();
}

void printHex(const char* label, const uint8_t* bytes, int nbits) {
  Serial.printf("    %-6s(%3d bits) ", label, nbits);
  for (int i = 0; i * 8 < nbits; i++) Serial.printf("%02X", bytes[i]);
  Serial.println();
}

void handleBurst() {
  nBursts++;
  const int rssi = peakRssi;
  peakRssi = -200;
  if (rawDump) {
    Serial.printf("raw %u pulses (first level %u):", burst.n, burst.firstLevel);
    for (int i = 0; i < burst.n; i++) Serial.printf(i % 16 ? " %u" : "\n  %u", burst.us[i]);
    Serial.println();
  }
  eg53ma4::Reading readings[4];
  const int nr = eg53ma4::decode(burst, readings, 4);
  for (int i = 0; i < nr; i++) {
    const eg53ma4::Reading& r = readings[i];
    nFrames++;
    remember(r, rssi);
    Serial.printf("%9.3f s  EG53MA4 id %06lX  %5.1f kPa = %4.1f psi  %3d F (%3.0f C)  flags %08lX  rssi %4d dBm\n",
                  millis() / 1000.0, (unsigned long)r.id, r.kPa10 / 10.0, eg53ma4::psi(r), r.tempF,
                  eg53ma4::tempC(r), (unsigned long)r.flags, rssi);
  }
  if (nr == 0) {   // not one of ours: show the bits for analysis
    if (!rf::decode(burst, frame)) return;
    nFrames++;
    lastFrame = frame;
    lastRssi = rssi;
    Serial.printf("%9.3f s  %-17s pulses=%-4u chip=%-4uus rssi=%4d dBm\n", millis() / 1000.0, modeName(mode),
                  burst.n, frame.chipUs, rssi);
    printHex("MAN", frame.man, frame.nbits);
    printHex("DMAN", frame.dman, frame.ndman);
    printHex("chips", frame.chips, frame.nchips);
  }
  setLeds(true);
  ledsOffAt = millis() + 40;
}

}  // namespace

void setup() {
  Serial.begin(115200);
  for (int p : {PIN_LED_FL, PIN_LED_FR, PIN_LED_RL, PIN_LED_RR, PIN_BUZZER}) {
    pinMode(p, OUTPUT);
    digitalWrite(p, LOW);
  }
  pinMode(PIN_ENC_A, INPUT);    // the board has the pull-ups and RC filters
  pinMode(PIN_ENC_B, INPUT);
  pinMode(PIN_ENC_SW, INPUT);
  pinMode(PIN_CC_GDO2, INPUT);
  pinMode(PIN_CC_CS, OUTPUT);   // both chip selects idle high before the shared bus starts
  digitalWrite(PIN_CC_CS, HIGH);
  pinMode(PIN_OLED_CS, OUTPUT);
  digitalWrite(PIN_OLED_CS, HIGH);

  SPI.begin(PIN_SPI_SCK, PIN_SPI_MISO, PIN_SPI_MOSI);
  // SCK/MOSI run ~100-130 mm to two loads: weaker drive = slower edges = no ringing / double clocking
  gpio_set_drive_capability((gpio_num_t)PIN_SPI_SCK, GPIO_DRIVE_CAP_1);
  gpio_set_drive_capability((gpio_num_t)PIN_SPI_MOSI, GPIO_DRIVE_CAP_1);
  oled.setBusClock(4000000);
  oled.begin();

  selfTest();
  encState = (digitalRead(PIN_ENC_A) << 1) | digitalRead(PIN_ENC_B);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_A), onEncoder, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_B), onEncoder, CHANGE);
  setMode(0);
  printHelp();
}

void loop() {
  const uint32_t now = millis();

  static int32_t lastDetent = 0;
  const int32_t detent = encCount / 4;
  if (detent != lastDetent) {
    setMode(mode + (detent - lastDetent));
    lastDetent = detent;
  }

  static uint32_t pressedAt = 0;
  static bool wasDown = false;
  const bool down = digitalRead(PIN_ENC_SW) == LOW;
  if (down && !wasDown && now - pressedAt > 50) {
    pressedAt = now;
    beep(40);
    Serial.println("button pressed");
  }
  wasDown = down;

  while (Serial.available()) {
    switch (Serial.read()) {
      case 'p': setMode(mode + 1); break;
      case 'r': rawDump = !rawDump; Serial.printf("raw dump %s\n", rawDump ? "on" : "off"); break;
      case 't': ledWalk(); beep(80); break;
      case 'h': printHelp(); break;
      default: break;
    }
  }

  static uint32_t lastRssiAt = 0;
  if (ccOk && mode < kCcModes && now - lastRssiAt >= 2) {   // track the peak RSSI while a burst arrives
    lastRssiAt = now;
    liveRssi = cc.rssiDbm();
    peakRssi = max(peakRssi, liveRssi);
  }

  while (rf::nextBurst(burst)) handleBurst();

  if (ledsOffAt && now >= ledsOffAt) {
    setLeds(false);
    ledsOffAt = 0;
  }
  if (buzzerOffAt && now >= buzzerOffAt) {
    digitalWrite(PIN_BUZZER, LOW);
    buzzerOffAt = 0;
  }

  static uint32_t lastDraw = 0, lastStats = 0;
  if (now - lastDraw >= 250) {
    lastDraw = now;
    drawScreen();
  }
  if (now - lastStats >= 10000) {
    lastStats = now;
    Serial.printf("[%lu s] bursts %lu frames %lu, edges %lu (noise), dropped %lu, RSSI now %d dBm\n",
                  (unsigned long)(now / 1000), (unsigned long)nBursts, (unsigned long)nFrames,
                  (unsigned long)rf::edges(), (unsigned long)rf::dropped(), liveRssi);
  }
}
