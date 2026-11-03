#pragma once

#include "hci/HciTypes.h"

#include <stddef.h>
#include <stdint.h>

namespace bt_analyzer {

/** Max HCI payload stored per frame (USB FS bulk/interrupt typical ≤1024). */
static constexpr size_t kCaptureMaxPayload = 1024;

struct CaptureFrame {
  uint32_t seq = 0;
  uint64_t ts_us = 0;
  HciDirection dir = HciDirection::Unknown;
  HciPacketType type = HciPacketType::Unknown;
  uint8_t usb_endpoint = 0;
  uint16_t length = 0;
  uint8_t payload[kCaptureMaxPayload]{};
};

}  // namespace bt_analyzer
