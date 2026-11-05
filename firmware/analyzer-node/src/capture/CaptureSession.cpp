#include "capture/CaptureSession.h"

#include <esp_timer.h>
#include <stdio.h>
#include <string.h>

namespace bt_analyzer {

bool CaptureSession::emitMeta(const char *kind, const char *label) {
  if (!cap_ || !kind) {
    return false;
  }
  char buf[192];
  const char *lab = label && label[0] ? label : "";
  // Compact JSON payload for Meta frames (BT_EVENT session_*)
  snprintf(buf, sizeof(buf),
           "{\"k\":\"%s\",\"sid\":%lu,\"cid\":%u,\"marks\":%lu,\"label\":\"%s\"}",
           kind, static_cast<unsigned long>(session_id_),
           static_cast<unsigned>(connection_id_),
           static_cast<unsigned long>(mark_count_), lab);
  const size_t n = strlen(buf);
  return cap_->injectRaw(HciPacketType::Meta, HciDirection::Unknown, 0,
                         reinterpret_cast<const uint8_t *>(buf), n);
}

bool CaptureSession::start(uint16_t conn_handle) {
  if (!cap_ || !ring_) {
    return false;
  }
  if (active_) {
    stop();
  }
  session_id_ = next_id_++;
  if (next_id_ == 0) {
    next_id_ = 1;
  }
  mark_count_ = 0;
  connection_id_ = conn_handle;
  started_us_ = static_cast<uint32_t>(esp_timer_get_time());
  ring_->beginSession();
  active_ = true;
  return emitMeta("START", "");
}

bool CaptureSession::mark(const char *label) {
  if (!active_ || !cap_) {
    return false;
  }
  mark_count_++;
  char safe[48];
  safe[0] = 0;
  if (label) {
    size_t j = 0;
    for (size_t i = 0; label[i] && j + 1 < sizeof(safe); i++) {
      const char c = label[i];
      if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
          (c >= '0' && c <= '9') || c == '_' || c == '-' || c == '/') {
        safe[j++] = c;
      }
    }
    safe[j] = 0;
  }
  return emitMeta("MARK", safe);
}

bool CaptureSession::stop() {
  if (!active_) {
    return false;
  }
  const bool ok = emitMeta("STOP", "");
  active_ = false;
  return ok;
}

void CaptureSession::appendStatusJson(String &json) const {
  json += ",\"captureSession\":{";
  json += "\"active\":";
  json += active_ ? "true" : "false";
  json += ",\"sessionId\":";
  json += String(session_id_);
  json += ",\"connectionId\":";
  json += String(connection_id_);
  json += ",\"markCount\":";
  json += String(mark_count_);
  json += ",\"startedUs\":";
  json += String(started_us_);
  json += ",\"claim\":\"HCI_session_recorder_not_air\"";
  json += "}";
}

}  // namespace bt_analyzer
