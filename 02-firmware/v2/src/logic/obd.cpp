#include "obd.h"

#include <cctype>
#include <cstring>

namespace v2 {
namespace obd {

namespace {

const char* const kSetup[] = {"ATE0", "ATS0", "ATH0", "ATSPA6"};
constexpr int kSetupSteps = (int)(sizeof(kSetup) / sizeof(kSetup[0]));

int hexValue(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  return -1;
}

// Equal, ignoring case and spaces (the echo of a command, "OK", "?").
bool same(const char* a, const char* b) {
  while (true) {
    while (*a == ' ') a++;
    while (*b == ' ') b++;
    if (!*a || !*b) return !*a && !*b;
    if (std::toupper((unsigned char)*a) != std::toupper((unsigned char)*b)) return false;
    a++;
    b++;
  }
}

bool containsNoCase(const char* s, const char* word) {
  const size_t n = std::strlen(word);
  for (; *s; s++) {
    size_t i = 0;
    while (i < n && s[i] && std::toupper((unsigned char)s[i]) == std::toupper((unsigned char)word[i])) i++;
    if (i == n) return true;
  }
  return false;
}

}  // namespace

uint16_t kmhToDmph(uint16_t kmh) { return (uint16_t)(((uint32_t)kmh * 62137u + 5000u) / 10000u); }

bool parseSpeedLine(const char* line, uint8_t& kmh) {
  if (!line) return false;
  char s[12];
  size_t n = 0;
  for (const char* p = line; *p; p++) {
    if (*p == ' ') continue;
    if (hexValue(*p) < 0 || n >= sizeof s) return false;
    s[n++] = (char)std::toupper((unsigned char)*p);
  }
  const char* data;
  if (n == 6) {
    data = s;                                   // 41 0D xx
  } else if (n == 11 && s[3] == '0' && s[4] == '3') {
    data = s + 5;                               // 7E8 03 41 0D xx: 11-bit header, ISO-TP length 3
  } else {
    return false;
  }
  if (std::memcmp(data, "410D", 4) != 0) return false;
  kmh = (uint8_t)(hexValue(data[4]) << 4 | hexValue(data[5]));
  return true;
}

const char* elmStateName(ElmState s) {
  switch (s) {
    case ElmState::Disconnected: return "disconnected";
    case ElmState::Resetting: return "resetting";
    case ElmState::Configuring: return "configuring";
    case ElmState::Polling: return "polling";
  }
  return "?";
}

ElmClient::ElmClient(const ElmConfig& cfg) : cfg_(cfg) {}

void ElmClient::connected(uint32_t, bool up) {
  state_ = up ? ElmState::Resetting : ElmState::Disconnected;
  if (up) noCount_ = false;
  step_ = 0;
  waiting_ = false;
  draining_ = false;
  pollSent_ = false;
  streak_ = 0;
  n_ = 0;
  overflow_ = false;
  fresh_ = false;
}

void ElmClient::feed(uint32_t now, char c) {
  if (state_ == ElmState::Disconnected) return;
  if (c == '\r' || c == '\n') {
    endLine();
  } else if (c == '>') {
    endLine();
    prompt(now);
  } else if (c != '\0') {  // some clones pad with NULs
    if (n_ < kMaxLine) line_[n_++] = c;
    else overflow_ = true;
  }
}

void ElmClient::endLine() {
  const bool ok = n_ > 0 && !overflow_;
  line_[ok ? n_ : 0] = '\0';
  n_ = 0;
  overflow_ = false;
  if (!ok || !waiting_ || same(line_, sent_)) return;  // empty, overlong, unsolicited or the echo
  if (state_ == ElmState::Resetting) {
    // The banner. Clones print all sorts of names ("ELM327 v1.5", "OBDII v1.5", ...): anything but a refusal.
    if (!same(line_, "STOPPED") && !same(line_, "?")) gotId_ = true;
  } else if (state_ == ElmState::Polling) {
    uint8_t v;
    if (parseSpeedLine(line_, v)) {
      gotSpeed_ = true;
      lineKmh_ = v;
    } else if (same(line_, "?")) {
      gotQuestion_ = true;
    } else if (containsNoCase(line_, "SEARCHING")) {
      searching_ = true;   // protocol search under way: give it time (searchTimeoutMs)
    } else if (containsNoCase(line_, "NO DATA")) {
      gotNoData_ = true;
    }
  }
}

void ElmClient::prompt(uint32_t now) {
  if (!waiting_) return;  // a stray prompt (e.g. after a command that already timed out)
  waiting_ = false;
  switch (state_) {
    case ElmState::Resetting:
      if (gotId_) {
        state_ = ElmState::Configuring;
        step_ = 0;
        streak_ = 0;
      } else {
        failed();  // e.g. "STOPPED": the reset was swallowed, send it again
      }
      break;
    case ElmState::Configuring:
      // Best effort: any answer moves on (the parser copes with echo, spaces and headers; ATSPA6 only saves time).
      streak_ = 0;
      if (++step_ >= kSetupSteps) {
        state_ = ElmState::Polling;
        pollSent_ = false;
      }
      break;
    case ElmState::Polling:
      if (gotSpeed_) {
        speedKmh_ = lineKmh_;
        speedMs_ = now;
        fresh_ = true;
        replies_++;
        streak_ = 0;
      } else if (gotQuestion_ && !noCount_) {
        noCount_ = true;  // a clone without the response-count digit: poll with plain "010D"
      } else if (gotNoData_) {
        noData_++;        // the dongle works, the car didn't answer (key in ACC): not a reason to reset it
        streak_ = 0;
      } else {
        failed();         // CAN ERROR, STOPPED, BUFFER FULL, UNABLE TO CONNECT, ...
      }
      break;
    case ElmState::Disconnected:
      break;
  }
}

void ElmClient::failed() {
  failures_++;
  if (state_ != ElmState::Resetting && ++streak_ >= cfg_.maxFailures) {
    state_ = ElmState::Resetting;
    streak_ = 0;
  }
}

const char* ElmClient::poll(uint32_t now) {
  if (state_ == ElmState::Disconnected) return nullptr;
  if (waiting_) {
    const uint32_t limit = state_ == ElmState::Resetting ? cfg_.resetTimeoutMs
                           : searching_                  ? cfg_.searchTimeoutMs
                                                         : cfg_.cmdTimeoutMs;
    if ((uint32_t)(now - sentMs_) < limit) return nullptr;
    waiting_ = false;
    failed();
    draining_ = true;  // a late reply may still be on its way: let it arrive and be ignored
    drainUntil_ = now + cfg_.drainMs;
  }
  if (draining_) {
    if ((int32_t)(now - drainUntil_) < 0) return nullptr;
    draining_ = false;
  }
  const char* cmd = nullptr;
  switch (state_) {
    case ElmState::Resetting:
      cmd = "ATZ";
      resets_++;
      break;
    case ElmState::Configuring:
      cmd = kSetup[step_];
      break;
    case ElmState::Polling:
      if (pollSent_ && (uint32_t)(now - lastPollMs_) < cfg_.pollMs) return nullptr;
      cmd = noCount_ ? "010D" : "010D1";
      pollSent_ = true;
      lastPollMs_ = now;
      break;
    case ElmState::Disconnected:
      return nullptr;
  }
  sent_ = cmd;
  sentMs_ = now;
  waiting_ = true;
  gotId_ = gotSpeed_ = gotQuestion_ = gotNoData_ = searching_ = false;
  n_ = 0;
  overflow_ = false;
  return cmd;
}

bool ElmClient::takeSpeed(uint8_t& kmh, uint32_t& atMs) {
  if (!fresh_) return false;
  fresh_ = false;
  kmh = speedKmh_;
  atMs = speedMs_;
  return true;
}

}  // namespace obd
}  // namespace v2
