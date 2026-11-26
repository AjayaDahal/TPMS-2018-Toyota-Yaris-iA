#include "link.h"

#include <cstdio>
#include <cstring>

namespace v2 {
namespace link {

namespace {

int hexValue(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  return -1;
}

bool parseUint(const char* s, size_t n, uint32_t maxValue, uint32_t& out) {
  if (n == 0 || n > 10) return false;
  uint64_t v = 0;
  for (size_t i = 0; i < n; i++) {
    if (s[i] < '0' || s[i] > '9') return false;
    v = v * 10 + (uint32_t)(s[i] - '0');
    if (v > maxValue) return false;
  }
  out = (uint32_t)v;
  return true;
}

bool parseFlag(const Frame& f, int i, bool& out) {
  uint32_t v;
  if (!parseUint(f.field[i], f.len[i], 1, v)) return false;
  out = v != 0;
  return true;
}

// Appends "*HH\n" for the body that starts at out[1] (after '$').
int finish(char* out, size_t cap, int bodyLen) {
  if (bodyLen <= 0 || (size_t)bodyLen + 5 > cap) return 0;
  const uint8_t cs = checksum(out + 1, out + bodyLen);
  const int n = std::snprintf(out + bodyLen, cap - (size_t)bodyLen, "*%02X\n", cs);
  return n == 4 ? bodyLen + 4 : 0;
}

}  // namespace

uint8_t checksum(const char* begin, const char* end) {
  uint8_t cs = 0;
  for (const char* p = begin; p < end; p++) cs ^= (uint8_t)*p;
  return cs;
}

bool LineReader::feed(char c) {
  if (c == '\r') return false;
  if (c == '\n') {
    const bool ok = !overflow_ && n_ > 0;
    if (overflow_) dropped_++;
    buf_[ok ? n_ : 0] = '\0';
    n_ = 0;
    overflow_ = false;
    return ok;
  }
  if (c == '$') {
    if (overflow_) dropped_++;  // an overlong line cut short by the next one
    n_ = 0;
    overflow_ = false;
  }
  if (n_ >= kMaxLine) {
    overflow_ = true;
    return false;
  }
  buf_[n_++] = c;
  return false;
}

bool Frame::is(int i, const char* text) const {
  return i < count && len[i] == std::strlen(text) && std::memcmp(field[i], text, len[i]) == 0;
}

bool split(const char* line, Frame& out) {
  out = Frame();
  if (!line || line[0] != '$') return false;
  const char* star = std::strchr(line, '*');
  if (!star || std::strlen(star) != 3) return false;
  const int hi = hexValue(star[1]), lo = hexValue(star[2]);
  if (hi < 0 || lo < 0 || checksum(line + 1, star) != (uint8_t)(hi << 4 | lo)) return false;
  const char* p = line + 1;
  while (true) {
    if (out.count >= kMaxFields) return false;
    const char* comma = (const char*)std::memchr(p, ',', (size_t)(star - p));
    const char* end = comma ? comma : star;
    out.field[out.count] = p;
    out.len[out.count] = (size_t)(end - p);
    out.count++;
    if (!comma) break;
    p = comma + 1;
  }
  return true;
}

bool parseBsm(const char* line, uint32_t& seq, PiStatus& status) {
  Frame f;
  if (!split(line, f) || f.count != 8 || !f.is(0, "BSM")) return false;
  PiStatus s;
  uint32_t level;
  if (!parseUint(f.field[1], f.len[1], 0xFFFFFFFFu, seq)) return false;
  if (!parseFlag(f, 2, s.ready) || !parseFlag(f, 3, s.occLeft) || !parseFlag(f, 4, s.occRight) ||
      !parseFlag(f, 5, s.camFaultLeft) || !parseFlag(f, 6, s.camFaultRight)) {
    return false;
  }
  if (!parseUint(f.field[7], f.len[7], 255, level)) return false;
  s.ledLevel = (uint8_t)level;
  status = s;
  return true;
}

int formatEsp(char* out, size_t cap, uint32_t seq, Turn turn, int speedDmph, uint16_t accMv, bool piPgood,
              uint8_t buttonPresses, bool bsmAvailable, SpeedSource speedSource) {
  static const char kTurn[] = {'O', 'L', 'R', 'H'};
  static const char kSource[] = {'N', 'G', 'O'};
  const int n = std::snprintf(out, cap, "$ESP,%lu,%c,%d,%u,%d,%u,%d,%c", (unsigned long)seq, kTurn[(int)turn & 3],
                              speedDmph < 0 ? -1 : speedDmph, (unsigned)accMv, piPgood ? 1 : 0,
                              (unsigned)buttonPresses, bsmAvailable ? 1 : 0,
                              (unsigned)speedSource < 3 ? kSource[(int)speedSource] : 'N');
  return finish(out, cap, n);
}

int formatTpm(char* out, size_t cap, uint8_t slot, uint32_t sensorId, uint16_t kpaX10, int tempC, int rssiDbm,
              uint16_t ageS) {
  const int n = std::snprintf(out, cap, "$TPM,%u,%lX,%u,%d,%d,%u", (unsigned)slot, (unsigned long)sensorId,
                              (unsigned)kpaX10, tempC, rssiDbm, (unsigned)ageS);
  return finish(out, cap, n);
}

}  // namespace link
}  // namespace v2
