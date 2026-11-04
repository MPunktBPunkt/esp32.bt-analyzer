#pragma once

#include "bt/GattClientFlavor.h"

#include <Arduino.h>

namespace bt_analyzer {

/** HOGP Host Flavor (BT18b) — binds to discovered HID service. */
class HogpFlavor {
public:
  void bind(GattClientFlavor *gc) { gc_ = gc; }
  void reset();
  bool startAfterDiscover();  // read map + subscribe
  void onAttPdu(const uint8_t *att, uint16_t len);
  void poll();

  const char *stateName() const;
  uint16_t reportHandle() const { return report_h_; }
  uint16_t cccdHandle() const { return cccd_h_; }
  uint16_t reportMapLen() const { return map_len_; }
  uint32_t reports() const { return reports_; }
  uint8_t lastKey() const { return last_key_; }
  uint8_t lastMod() const { return last_mod_; }
  bool ok() const { return state_ == 3; }

  void appendStatusJson(String &json) const;

private:
  GattClientFlavor *gc_ = nullptr;
  uint8_t state_ = 0;  // 0 idle 1 read_map 2 sub 3 ready 4 error
  uint16_t report_h_ = 0;
  uint16_t cccd_h_ = 0;
  uint16_t map_h_ = 0;
  uint16_t map_len_ = 0;
  uint32_t reports_ = 0;
  uint8_t last_key_ = 0;
  uint8_t last_mod_ = 0;
  uint32_t t0_ = 0;
};

/** FTMS Client Flavor (BT18c) — Indoor Bike Data + Feature read. */
class FtmsFlavor {
public:
  void bind(GattClientFlavor *gc) { gc_ = gc; }
  void reset();
  bool startAfterDiscover();
  void onAttPdu(const uint8_t *att, uint16_t len);
  void poll();

  const char *stateName() const;
  uint16_t ibdHandle() const { return ibd_h_; }
  uint16_t cccdHandle() const { return cccd_h_; }
  uint32_t notifies() const { return notifies_; }
  uint16_t lastPower() const { return last_power_; }
  uint16_t lastCadence() const { return last_cadence_; }
  uint32_t featureLo() const { return feature_lo_; }
  bool ok() const { return state_ == 3; }

  void appendStatusJson(String &json) const;

private:
  GattClientFlavor *gc_ = nullptr;
  uint8_t state_ = 0;
  uint16_t feat_h_ = 0;
  uint16_t ibd_h_ = 0;
  uint16_t cccd_h_ = 0;
  uint32_t feature_lo_ = 0;
  uint32_t notifies_ = 0;
  uint16_t last_power_ = 0;
  uint16_t last_cadence_ = 0;
  uint32_t t0_ = 0;
};

}  // namespace bt_analyzer
