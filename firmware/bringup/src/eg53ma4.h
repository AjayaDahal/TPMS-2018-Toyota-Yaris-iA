#pragma once
#include <cstdint>

#include "rf.h"

// GM / Schrader EG53MA4 TPMS sensor: 315 MHz OOK, Manchester, 123 us half-bit. The frame format is the one
// rtl_433 decodes as "Schrader-EG53MA4" (src/devices/schraeder.c): a 120-bit message whose last 80 bits are
//   flags (32) | ID (24) | pressure (8, x 25 mbar) | temperature (8, deg F) | checksum (8, sum of the 9 bytes)
namespace eg53ma4 {

struct Reading {
  uint32_t id;      // 24-bit sensor ID (6 hex digits; often printed on the sensor)
  uint32_t flags;   // status bits (not documented)
  uint16_t kPa10;   // pressure in 0.1 kPa
  int16_t tempF;    // temperature in deg F
};

// Slices a burst the way rtl_433's OOK_PULSE_MANCHESTER_ZEROBIT does (a message ends at any gap longer than
// 300 us) and returns how many valid readings were written to out. One burst can hold several repeats.
int decode(const rf::Burst& b, Reading* out, int maxOut);

inline float psi(const Reading& r) { return r.kPa10 * 0.0145038f; }
inline float tempC(const Reading& r) { return (r.tempF - 32) * 5.0f / 9.0f; }

}  // namespace eg53ma4
