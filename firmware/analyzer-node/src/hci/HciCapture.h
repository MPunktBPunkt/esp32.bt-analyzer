#pragma once

#include "capture/CaptureRing.h"
#include "hci/HciTypes.h"

#include <Arduino.h>
#include <EspUsbHost.h>

namespace bt_analyzer {

/**
 * BT3: raw HCI capture from USB-HCI bulk IN (ACL / controller→host).
 *
 * HCI Events on interrupt IN are not yet driven by EspUsbHost vendor API —
 * status reports eventCapture="pending_interrupt_in".
 *
 * Observe mode: ESP is USB Host; we capture what the controller sends on bulk IN
 * and optional host→controller writes we ourselves submit.
 */
class HciCapture {
public:
  void setUsb(EspUsbHost *usb) { usb_ = usb; }
  void setRing(CaptureRing *ring) { ring_ = ring; }

  bool begin();
  void loop();

  void onHciAttached(uint8_t address, const HciUsbDiscovery &hci);
  void onHciDetached();

  bool openOk() const { return open_ok_; }
  bool captureArmed() const { return armed_; }
  uint32_t aclInFrames() const { return acl_in_; }
  uint32_t cmdOutFrames() const { return cmd_out_; }
  uint32_t injectFrames() const { return inject_; }
  uint32_t openFails() const { return open_fails_; }

  /** Lab: enqueue synthetic frame (no USB). */
  bool injectRaw(HciPacketType type, HciDirection dir, uint8_t endpoint,
                 const uint8_t *data, size_t len);

  /** Lab: HCI Command (or ACL) bulk OUT via vendorWrite. */
  bool writeHost(const uint8_t *data, size_t len);

  void appendStatusJson(String &json) const;

  /** Build JSONL of up to max recent dequeued frames (drains ring). */
  String drainJsonl(size_t max_frames);

private:
  EspUsbHost *usb_ = nullptr;
  CaptureRing *ring_ = nullptr;

  bool callbacks_set_ = false;
  bool armed_ = false;
  bool open_ok_ = false;
  bool pending_open_ = false;
  uint8_t pending_addr_ = 0;
  uint8_t pending_iface_ = 0xff;
  uint8_t bulk_in_ep_ = 0;
  uint8_t bulk_out_ep_ = 0;

  uint32_t acl_in_ = 0;
  uint32_t cmd_out_ = 0;
  uint32_t inject_ = 0;
  uint32_t open_fails_ = 0;

  void tryOpen();
  void enqueueFromUsb(HciPacketType type, HciDirection dir, uint8_t endpoint,
                      const uint8_t *data, size_t len);
};

}  // namespace bt_analyzer
