#pragma once

#include "hci/HciVhciCapture.h"

#include <Arduino.h>
#include <stdint.h>

namespace bt_analyzer {

/**
 * Recorder session control (0.3.9) — START/STOP/MARK into the HCI ring as Meta frames.
 * Capture continues whether or not a BTAC TCP client is connected.
 */
class CaptureSession {
public:
  void bind(HciVhciCapture *cap, CaptureRing *ring) {
    cap_ = cap;
    ring_ = ring;
  }

  bool start(uint16_t conn_handle = 0);
  bool mark(const char *label);
  bool stop();

  bool active() const { return active_; }
  uint32_t sessionId() const { return session_id_; }
  uint32_t markCount() const { return mark_count_; }
  uint16_t connectionId() const { return connection_id_; }
  uint32_t startedUs() const { return started_us_; }

  void setConnectionId(uint16_t h) { connection_id_ = h; }
  void appendStatusJson(String &json) const;

private:
  HciVhciCapture *cap_ = nullptr;
  CaptureRing *ring_ = nullptr;
  bool active_ = false;
  uint32_t session_id_ = 0;
  uint32_t next_id_ = 1;
  uint32_t mark_count_ = 0;
  uint16_t connection_id_ = 0;
  uint32_t started_us_ = 0;

  bool emitMeta(const char *kind, const char *label);
};

}  // namespace bt_analyzer
