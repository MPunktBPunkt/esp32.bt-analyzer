#pragma once

#include <Arduino.h>

#include "capture/CaptureRing.h"
#include "hci/HciTypes.h"

#if BT_ANALYZER_ENABLE_USB_HOST
#include "hci/HciCapture.h"
#endif

namespace bt_analyzer {

/**
 * Legacy USB Host enumeration / USB-HCI path.
 * Compiled fully only when BT_ANALYZER_ENABLE_USB_HOST=1.
 */
class UsbHostEnum {
public:
  bool begin();
  void loop();

  bool beginOk() const { return begin_ok_; }
  size_t deviceCount() const;
  const char *otgState() const;
  String lastEventJson() const { return last_event_json_; }
  uint16_t dutVid() const { return dut_present_ ? dut_vid_ : 0; }
  uint16_t dutPid() const { return dut_present_ ? dut_pid_ : 0; }
  bool hciDetected() const { return hci_.wirelessControllerIface; }
  const HciUsbDiscovery &hciDiscovery() const { return hci_; }

#if BT_ANALYZER_ENABLE_USB_HOST
  CaptureRing &ring() { return ring_; }
  HciCapture &hciCapture() { return hci_cap_; }
#endif

  void appendStatusJson(String &json) const;

private:
  bool ready_ = false;
  bool begin_ok_ = false;
  bool hint_printed_ = false;
  uint32_t started_ms_ = 0;
  uint32_t last_report_ms_ = 0;
  String last_event_json_;

  bool dut_present_ = false;
  uint16_t dut_vid_ = 0;
  uint16_t dut_pid_ = 0;
  uint8_t dut_address_ = 0;
  uint8_t dut_cfg_ = 0;
  uint8_t dut_iface_count_ = 0;
  uint8_t dut_ep_count_ = 0;
  bool dut_wireless_ctrl_ = false;
  String dut_mfr_;
  String dut_product_;
  String dut_serial_;
  String dut_speed_;
  String dut_ifaces_json_;
  String dut_eps_json_;
  HciUsbDiscovery hci_{};

#if BT_ANALYZER_ENABLE_USB_HOST
  CaptureRing ring_;
  HciCapture hci_cap_;
#endif

  void clearDut();
  void cacheDescriptors(uint8_t address);
  void printNoDeviceHints() const;
};

}  // namespace bt_analyzer
