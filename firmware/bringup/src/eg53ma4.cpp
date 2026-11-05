// GM / Schrader EG53MA4 decoder (no ESP32 dependencies, unit-tested on a PC). The slicing follows the
// behaviour of rtl_433's OOK_PULSE_MANCHESTER_ZEROBIT slicer with short width 123 us and reset limit
// 300 us, and the frame checks follow rtl_433's schrader_EG53MA4 decoder.
#include "eg53ma4.h"

namespace eg53ma4 {
namespace {

constexpr int kShortUs = 123;    // Manchester half-bit
constexpr int kResetUs = 300;    // a longer gap ends a message
constexpr int kFrameBits = 120;  // 40 sync/preamble bits + 80 payload bits

struct Row {
  uint8_t bits[kFrameBits];
  int n = 0;
};

void addBit(Row& r, int bit) {
  if (r.n < kFrameBits) r.bits[r.n] = (uint8_t)bit;
  r.n++;                           // keep counting so an over-long message is rejected
}

bool parse(const Row& r, Reading& out) {
  if (r.n != kFrameBits) return false;
  uint8_t b[10] = {};
  for (int i = 0; i < 80; i++) {
    if (r.bits[40 + i]) b[i / 8] |= 0x80 >> (i % 8);
  }
  if (!b[1] && !b[2] && !b[4] && !b[5] && !b[7] && !b[8]) return false;   // all-zero payload
  unsigned sum = 0;
  for (int i = 0; i < 9; i++) sum += b[i];
  if ((sum & 0xFF) != b[9]) return false;
  out.flags = (uint32_t)b[0] << 24 | (uint32_t)b[1] << 16 | (uint32_t)b[2] << 8 | b[3];
  out.id = (uint32_t)b[4] << 16 | (uint32_t)b[5] << 8 | b[6];
  out.kPa10 = (uint16_t)(b[7] * 25);   // 25 mbar = 2.5 kPa per step
  out.tempF = b[8];
  return true;
}

}  // namespace

int decode(const rf::Burst& b, Reading* out, int maxOut) {
  int found = 0;
  Row row;
  addBit(row, 0);                  // the first rising edge always counts as a 0
  int since = 0;                   // time since the last data edge
  auto endMessage = [&]() {
    if (found < maxOut && parse(row, out[found])) found++;
    row.n = 0;
    addBit(row, 0);
    since = 0;
  };
  // carrier-on pulses alternate with gaps; skip a leading gap if the burst starts low
  for (int i = b.firstLevel ? 0 : 1; i < b.n; i += 2) {
    const int pulse = b.us[i];
    const bool lastPulse = i + 1 >= b.n;
    const int gap = lastPulse ? 0 : b.us[i + 1];
    if (2 * (pulse + since) > 3 * kShortUs) {   // falling edge more than 1.5 half-bits after the last data edge
      addBit(row, 1);
      since = 0;
    } else {
      since += pulse;
    }
    if (lastPulse || gap > kResetUs) {
      endMessage();
    } else if (2 * (gap + since) > 3 * kShortUs) {   // rising data edge
      addBit(row, 0);
      since = 0;
    } else {
      since += gap;
    }
  }
  if (row.n > 1) endMessage();     // burst ended on a short gap
  return found;
}

}  // namespace eg53ma4
