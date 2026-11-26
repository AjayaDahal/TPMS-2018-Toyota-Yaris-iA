#pragma once
// ESP32 <-> Raspberry Pi line protocol over UART2 (115200 Bd, 3.3 V, GPIO14/15 on the Pi).
//
// NMEA-style text lines, readable on a serial monitor:  $TYPE,field,...*HH\n
// HH = XOR of every character between '$' and '*', two upper-case hex digits (lower case accepted).
//
// Pi -> ESP32, 10-20 Hz:
//   $BSM,<seq>,<ready 0/1>,<occL 0/1>,<occR 0/1>,<camFaultL 0/1>,<camFaultR 0/1>,<ledLevel 0-255>*HH
// ESP32 -> Pi, 10 Hz and on every turn change:
//   $ESP,<seq>,<turn O/L/R/H>,<speed deci-mph, -1 = unknown>,<ACC mV>,<Pi PGOOD 0/1>,<button presses>,<BSM available 0/1>,
//        <speed source N/G/O = none / GPS / OBD-II>*HH
// ESP32 -> Pi, when a learned tyre sensor is heard:
//   $TPM,<slot 0-3>,<sensor id hex>,<kPa x10>,<temp C>,<RSSI dBm>,<age s>*HH
#include <cstddef>
#include <cstdint>

#include "alerts.h"
#include "blinker.h"

namespace v2 {
namespace link {

constexpr size_t kMaxLine = 96;
constexpr int kMaxFields = 12;

uint8_t checksum(const char* begin, const char* end);

// Assembles lines from the byte stream. A '$' always starts a new line, so garbage before it is dropped.
class LineReader {
 public:
  // Returns true when a complete line (without CR/LF) is ready in line(); read it before the next feed().
  bool feed(char c);
  const char* line() const { return buf_; }
  uint32_t dropped() const { return dropped_; }  // overlong lines discarded

 private:
  char buf_[kMaxLine + 1] = {};
  size_t n_ = 0;
  bool overflow_ = false;
  uint32_t dropped_ = 0;
};

struct Frame {
  int count = 0;                 // fields including the type, e.g. "BSM"
  const char* field[kMaxFields] = {};
  size_t len[kMaxFields] = {};
  bool is(int i, const char* text) const;
};

// Checks the framing and checksum and splits the fields. False on any error.
bool split(const char* line, Frame& out);

bool parseBsm(const char* line, uint32_t& seq, PiStatus& out);

// Both return the line length including the trailing '\n', or 0 if it doesn't fit in cap.
int formatEsp(char* out, size_t cap, uint32_t seq, Turn turn, int speedDmph, uint16_t accMv, bool piPgood,
              uint8_t buttonPresses, bool bsmAvailable, SpeedSource speedSource);
int formatTpm(char* out, size_t cap, uint8_t slot, uint32_t sensorId, uint16_t kpaX10, int tempC, int rssiDbm,
              uint16_t ageS);

}  // namespace link
}  // namespace v2
