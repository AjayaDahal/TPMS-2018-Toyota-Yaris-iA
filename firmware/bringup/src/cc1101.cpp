#include "cc1101.h"

namespace {
// 4 MHz keeps the bus well inside the CC1101 burst-access limit (6.5 MHz) and the SSD1322 limit (10 MHz).
const SPISettings kSpi(4000000, MSBFIRST, SPI_MODE0);

enum : uint8_t {  // configuration registers 0x00..0x2E
  IOCFG2, IOCFG1, IOCFG0, FIFOTHR, SYNC1, SYNC0, PKTLEN, PKTCTRL1, PKTCTRL0, ADDR, CHANNR,
  FSCTRL1, FSCTRL0, FREQ2, FREQ1, FREQ0, MDMCFG4, MDMCFG3, MDMCFG2, MDMCFG1, MDMCFG0, DEVIATN,
  MCSM2, MCSM1, MCSM0, FOCCFG, BSCFG, AGCCTRL2, AGCCTRL1, AGCCTRL0, WOREVT1, WOREVT0, WORCTRL,
  FREND1, FREND0, FSCAL3, FSCAL2, FSCAL1, FSCAL0, RCCTRL1, RCCTRL0, FSTEST, PTEST, AGCTEST,
  TEST2, TEST1, TEST0
};
enum : uint8_t { SRES = 0x30, SCAL = 0x33, SRX = 0x34, SIDLE = 0x36 };
enum : uint8_t { PARTNUM = 0x30, VERSION = 0x31, RSSI = 0x34, MARCSTATE = 0x35 };
constexpr uint8_t READ = 0x80, BURST = 0x40;
}  // namespace

bool CC1101::select() {
  spi_.beginTransaction(kSpi);
  digitalWrite(cs_, LOW);
  const uint32_t t0 = micros();
  while (digitalRead(miso_)) {           // SO goes low when the crystal is running ("chip ready")
    if (micros() - t0 > 2000) {
      digitalWrite(cs_, HIGH);
      spi_.endTransaction();
      return false;
    }
  }
  return true;
}

void CC1101::deselect() {
  digitalWrite(cs_, HIGH);
  spi_.endTransaction();
}

void CC1101::writeReg(uint8_t addr, uint8_t value) {
  if (!select()) return;
  spi_.transfer(addr);
  spi_.transfer(value);
  deselect();
}

uint8_t CC1101::readReg(uint8_t addr) {
  if (!select()) return 0xFF;
  spi_.transfer(addr | READ);
  const uint8_t v = spi_.transfer(0);
  deselect();
  return v;
}

uint8_t CC1101::readStatus(uint8_t addr) {   // 0x30..0x3D need the burst bit, otherwise they are strobes
  if (!select()) return 0xFF;
  spi_.transfer(addr | READ | BURST);
  const uint8_t v = spi_.transfer(0);
  deselect();
  return v;
}

void CC1101::strobe(uint8_t cmd) {
  if (!select()) return;
  spi_.transfer(cmd);
  deselect();
}

bool CC1101::begin() {
  pinMode(cs_, OUTPUT);
  digitalWrite(cs_, HIGH);
  // Manual power-on reset (CC1101 datasheet 19.1.2): pulse CSn, keep it high >40 us, then SRES.
  digitalWrite(cs_, LOW);
  delayMicroseconds(10);
  digitalWrite(cs_, HIGH);
  delayMicroseconds(45);
  strobe(SRES);
  delay(2);
  partnum_ = readStatus(PARTNUM);
  version_ = readStatus(VERSION);
  // 0x14 / 0x04 = TI CC1101; 0x17 / 0x03 = clone chips that also work (the values RadioLib accepts)
  return partnum_ == 0x00 && (version_ == 0x14 || version_ == 0x04 || version_ == 0x17 || version_ == 0x03);
}

void CC1101::configure(const RfProfile& p) {
  strobe(SIDLE);
  static const uint8_t common[][2] = {
      {IOCFG2, 0x0E},    // GDO2 = carrier sense
      {IOCFG1, 0x2E},    // GDO1/SO high impedance while CSn is high: required for the shared SPI bus
      {IOCFG0, 0x0D},    // GDO0 = asynchronous serial data out (to IO34)
      {FIFOTHR, 0x47},   {PKTLEN, 0xFF},     {PKTCTRL1, 0x00},
      {PKTCTRL0, 0x32},  // asynchronous serial mode, infinite length: the demodulated stream goes to GDO0
      {ADDR, 0x00},      {CHANNR, 0x00},     {FSCTRL1, 0x06},  {FSCTRL0, 0x00},
      {FREQ2, 0x0C},     {FREQ1, 0x1D},      {FREQ0, 0x8A},    // 315.000 MHz with a 26 MHz crystal
      {MDMCFG1, 0x02},   {MDMCFG0, 0xF8},
      {MCSM2, 0x07},     {MCSM1, 0x30},
      {MCSM0, 0x18},     // calibrate on every IDLE -> RX
      {FOCCFG, 0x16},    {BSCFG, 0x6C},      {WORCTRL, 0xFB},
      {FREND1, 0x56},    {FREND0, 0x11},
      {FSCAL3, 0xE9},    {FSCAL2, 0x0A},     {FSCAL1, 0x00},   {FSCAL0, 0x1F},
      {TEST2, 0x81},     {TEST1, 0x35},
      {TEST0, 0x0B},     // VCO selection calibration on: needed below ~323 MHz (0x09 is the 433 MHz value)
  };
  for (const auto& r : common) writeReg(r[0], r[1]);
  writeReg(MDMCFG4, p.mdmcfg4);
  writeReg(MDMCFG3, p.mdmcfg3);
  writeReg(MDMCFG2, p.mdmcfg2);
  writeReg(DEVIATN, p.deviatn);
  writeReg(AGCCTRL2, p.agcctrl2);
  writeReg(AGCCTRL1, p.agcctrl1);
  writeReg(AGCCTRL0, p.agcctrl0);
  strobe(SCAL);
  delay(1);
  rx();
}

void CC1101::rx() { strobe(SRX); }   // the RX FIFO is unused in asynchronous serial mode

void CC1101::idle() { strobe(SIDLE); }

int CC1101::rssiDbm() {
  const int raw = readStatus(RSSI);
  return (raw >= 128 ? raw - 256 : raw) / 2 - 74;   // datasheet 17.3, RSSI offset 74 dB
}

uint8_t CC1101::marcState() { return readStatus(MARCSTATE) & 0x1F; }
