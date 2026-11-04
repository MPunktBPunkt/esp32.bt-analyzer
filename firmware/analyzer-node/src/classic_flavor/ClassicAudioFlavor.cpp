#include "classic_flavor/ClassicAudioFlavor.h"

namespace classic_flavor {

void ClassicAudioFlavor::begin() {
  state_ = State::Scaffold;
  stimulus_tx_ = 0;
}

void ClassicAudioFlavor::poll() {}

bool ClassicAudioFlavor::startPhoneFirst(const char * /*name*/) {
  // Scaffold: refuse runtime start until Bluedroid stack is wired (BT17).
  state_ = State::Scaffold;
  return false;
}

void ClassicAudioFlavor::stop() {
  state_ = State::Idle;
}

void ClassicAudioFlavor::appendStatusJson(String &json) const {
  json += ",\"classicAudio\":{";
  json += "\"id\":\"classic_audio\"";
  json += ",\"state\":\"scaffold\"";
  json += ",\"claim\":\"STIMULUS_scaffold_no_A2DP_yet\"";
  json += ",\"board\":\".87_only\"";
  json += ",\"stimulusTx\":";
  json += String(stimulus_tx_);
  json += "}";
}

}  // namespace classic_flavor
