#pragma once
// BT17 Classic Audio Flavor — scaffold only (not linked into thin VHCI core).
// Build env: analyzer-esp32-classic-audio  · board: .87 only
// See docs/BT17_CLASSIC_AUDIO.md

#include <Arduino.h>

namespace classic_flavor {

enum class State : uint8_t {
  Idle = 0,
  Scaffold,
  Error,
};

// Placeholder API surface — no Bluedroid A2DP/HFP yet.
class ClassicAudioFlavor {
 public:
  void begin();
  void poll();
  bool startPhoneFirst(const char *name);
  void stop();
  State state() const { return state_; }
  void appendStatusJson(String &json) const;

 private:
  State state_ = State::Scaffold;
  uint32_t stimulus_tx_ = 0;
};

}  // namespace classic_flavor
