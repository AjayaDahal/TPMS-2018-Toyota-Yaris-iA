#pragma once
// ELM327 (Bluetooth OBD-II dongle) client: the car's own speed, PID 0x0D, for the speed gate. Optional.
//
// Why only the speed: standard OBD-II (SAE J1979) has no turn-signal data, so the blinker stays on the
// opto-isolated lamp taps (see "OBD-II dongle" in 00-project-management/PREMORTEM_v2.md). The speed is a good use:
// it comes from the wheel sensors, is exact at walking pace, needs no sky and is there a second after the dongle
// connects. If the dongle stops answering, AlertArbiter falls back to the GPS, so a bad dongle can only make the
// buzzer quieter, never louder.
//
// Pure logic with no hardware access, unit-tested on a PC (test/host/test_logic.cpp). The application moves bytes
// between this class and the Bluetooth link (BluetoothSerial on the ESP32):
//   connected(now, up)   when the link comes up or drops
//   feed(now, c)         for every received byte
//   poll(now)            every loop: returns a command to send followed by '\r', or nullptr
//   takeSpeed(kmh, at)   true once per new speed reply
//
// Sequence (ELM327 datasheet, Elm Electronics): ATZ (reset; ~0.8 s to its "ELM327 v..." line), ATE0 (echo off),
// ATS0 (spaces off), ATH0 (headers off), ATSP6 (ISO 15765-4 CAN, 11 bit, 500 kbit/s: no "SEARCHING..." on every
// start), then "010D1" every pollMs. The trailing "1" makes the ELM327 return after the first reply instead of
// waiting out its 200 ms timer; a clone that answers "?" to it is polled with plain "010D". The setup commands are
// best effort: the reply parser copes with echo, spaces and headers. The speed is only ever requested, never
// monitored: in monitor mode (AT MA) the ELM327's 512-byte buffer overflows on a busy bus ("BUFFER FULL").
#include <cstddef>
#include <cstdint>

namespace v2 {
namespace obd {

// km/h -> tenths of a mph, rounded (the unit of the speed gate).
uint16_t kmhToDmph(uint16_t kmh);

// One reply line to "010D", with or without spaces and 11-bit headers: "410D3C", "41 0D 3C", "7E803410D3C",
// "7E8 03 41 0D 3C". True, and kmh set, only for a well-formed reply.
bool parseSpeedLine(const char* line, uint8_t& kmh);

enum class ElmState : uint8_t { Disconnected, Resetting, Configuring, Polling };
const char* elmStateName(ElmState s);

struct ElmConfig {
  uint32_t resetTimeoutMs = 3000;  // no prompt after ATZ within this: send it again
  uint32_t cmdTimeoutMs = 1000;    // no prompt after any other command within this: it failed
  uint32_t pollMs = 200;           // speed request period (5 Hz)
  uint8_t maxFailures = 3;         // consecutive failed commands before a full reset (ATZ)
};

class ElmClient {
 public:
  static constexpr size_t kMaxLine = 48;

  explicit ElmClient(const ElmConfig& cfg = ElmConfig());

  void connected(uint32_t nowMs, bool up);
  void feed(uint32_t nowMs, char c);
  const char* poll(uint32_t nowMs);
  bool takeSpeed(uint8_t& kmh, uint32_t& atMs);

  ElmState state() const { return state_; }
  uint32_t replies() const { return replies_; }    // valid speed replies
  uint32_t failures() const { return failures_; }  // failed or timed-out commands
  uint32_t resets() const { return resets_; }      // ATZ sent

 private:
  void endLine();
  void prompt(uint32_t now);
  void failed();

  ElmConfig cfg_;
  ElmState state_ = ElmState::Disconnected;
  int step_ = 0;
  bool waiting_ = false;
  const char* sent_ = "";
  uint32_t sentMs_ = 0;
  bool pollSent_ = false;
  uint32_t lastPollMs_ = 0;
  bool noCount_ = false;   // the dongle rejects the response-count digit
  uint8_t streak_ = 0;     // consecutive failures
  bool gotId_ = false, gotSpeed_ = false, gotQuestion_ = false;
  uint8_t lineKmh_ = 0;
  char line_[kMaxLine + 1] = {};
  size_t n_ = 0;
  bool overflow_ = false;
  bool fresh_ = false;
  uint8_t speedKmh_ = 0;
  uint32_t speedMs_ = 0;
  uint32_t replies_ = 0, failures_ = 0, resets_ = 0;
};

}  // namespace obd
}  // namespace v2
