#pragma once

#include <stdint.h>

/**
 * Capture / node roles for esp32.bt-analyzer.
 *
 * V1: single OBSERVE node (USB Host + HCI capture).
 * Later: STIMULUS = second ESP as USB Device / HCI replay (not MITM).
 */

namespace bt_analyzer {

enum class Role : uint8_t {
  Observe = 0,   // ESP #1 — USB Host → HCI capture → TCP
  Stimulus = 1,  // ESP #2 — USB Device HCI stimulus/replay (BT11+)
};

inline const char* roleName(Role r) {
  switch (r) {
    case Role::Observe:  return "observe";
    case Role::Stimulus: return "stimulus";
    default:             return "unknown";
  }
}

}  // namespace bt_analyzer
