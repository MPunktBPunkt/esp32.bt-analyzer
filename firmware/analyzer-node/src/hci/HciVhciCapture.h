#pragma once

#include "capture/CaptureRing.h"
#include "hci/HciTypes.h"

#include <Arduino.h>

namespace bt_analyzer {

/**
 * BT3 (on-chip): raw HCI capture via ESP VHCI.
 * Packet format is H4 (leading type byte 01/02/03/04).
 */
class HciVhciCapture {
public:
  void setRing(CaptureRing *ring) { ring_ = ring; }

  bool begin();
  void onRecv(const uint8_t *data, uint16_t len);

  bool openOk() const { return open_ok_; }
  void setOpenOk(bool v) { open_ok_ = v; }

  uint32_t rxFrames() const { return rx_; }
  uint32_t txFrames() const { return tx_; }
  uint32_t injectFrames() const { return inject_; }
  uint32_t sendFails() const { return send_fails_; }

  bool injectRaw(HciPacketType type, HciDirection dir, uint8_t endpoint,
                 const uint8_t *data, size_t len);

  /** Send H4 packet (type byte included) host→controller; also enqueues. */
  bool writeH4(const uint8_t *data, size_t len);

  /** Convenience: HCI command payload without type (prepends 0x01). */
  bool writeCommand(const uint8_t *cmd, size_t len);

  void appendStatusJson(String &json) const;
  String drainJsonl(size_t max_frames);

private:
  CaptureRing *ring_ = nullptr;
  bool open_ok_ = false;
  uint32_t rx_ = 0;
  uint32_t tx_ = 0;
  uint32_t inject_ = 0;
  uint32_t send_fails_ = 0;

  void enqueue(HciPacketType type, HciDirection dir, uint8_t endpoint,
               const uint8_t *data, size_t len);
  static HciPacketType typeFromH4(uint8_t t);
};

}  // namespace bt_analyzer
