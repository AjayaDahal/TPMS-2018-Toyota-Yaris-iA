#pragma once
#include <Arduino.h>
#include <SPI.h>

// Modem settings that differ between receive profiles. Everything else (315.000 MHz, asynchronous
// serial output on GDO0, carrier sense on GDO2, 315 MHz VCO calibration) is common.
//   MDMCFG4 = CHANBW_E << 6 | CHANBW_M << 4 | DRATE_E,  MDMCFG3 = DRATE_M
//   RX bandwidth = 26 MHz / (8 * (4 + CHANBW_M) * 2^CHANBW_E)
//   data rate    = (256 + DRATE_M) * 2^DRATE_E * 26 MHz / 2^28
//   deviation    = 26 MHz / 2^17 * (8 + DEVIATION_M) * 2^DEVIATION_E   (DEVIATN = E << 4 | M)
// In asynchronous mode the data rate only sets the demodulator filtering; about 2x the chip rate works.
struct RfProfile {
  const char* name;
  uint8_t mdmcfg4, mdmcfg3, mdmcfg2, deviatn, agcctrl2, agcctrl1, agcctrl0;
};

class CC1101 {
 public:
  CC1101(SPIClass& spi, int cs, int miso) : spi_(spi), cs_(cs), miso_(miso) {}

  bool begin();                         // reset + identify; true if a known CC1101 answers
  void configure(const RfProfile& p);   // 315 MHz receive, asynchronous serial data on GDO0
  void rx();
  void idle();
  int rssiDbm();
  uint8_t marcState();                  // 0x0D = RX
  uint8_t partnum() const { return partnum_; }
  uint8_t version() const { return version_; }

  void writeReg(uint8_t addr, uint8_t value);
  uint8_t readReg(uint8_t addr);
  uint8_t readStatus(uint8_t addr);
  void strobe(uint8_t cmd);

 private:
  bool select();
  void deselect();

  SPIClass& spi_;
  int cs_, miso_;
  uint8_t partnum_ = 0xFF, version_ = 0xFF;
};
