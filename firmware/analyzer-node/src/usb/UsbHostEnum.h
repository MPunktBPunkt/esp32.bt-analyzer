#pragma once

#include <Arduino.h>

#include "hci/HciTypes.h"

namespace bt_analyzer {

/**
 * BT1: USB Host enumeration (VID/PID/if/ep).
 * BT2: USB-HCI role map from descriptors (no packet capture).
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

  /** Append otg/usbHost/dut/hci/lastUsbEvent fields (leading commas). */
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
  bool dut_wireless_ctrl_ = false;  // class 0xE0 subclass 0x01 (Bluetooth)
  String dut_mfr_;
  String dut_product_;
  String dut_serial_;
  String dut_speed_;
  String dut_ifaces_json_;  // cached array fragment
  String dut_eps_json_;     // cached array fragment
  HciUsbDiscovery hci_{};

  void clearDut();
  void cacheDescriptors(uint8_t address);
  void printNoDeviceHints() const;
};

}  // namespace bt_analyzer
