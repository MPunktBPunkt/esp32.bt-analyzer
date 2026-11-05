#pragma once

#include <stddef.h>
#include <stdint.h>

namespace bt_analyzer {

/**
 * Static GATT attribute table for the lab peer (.89).
 * Keeps BT16 thr handles 0x0003/0x0004; adds HID (0x1812) + FTMS (0x1826).
 */
struct PeerAttr {
  uint16_t handle;
  uint16_t uuid16;
  uint8_t kind;  // 0=svc, 1=char_decl, 2=value, 3=cccd, 4=report_ref
  uint16_t svc_end;   // for primary service
  uint8_t props;      // for char decl
  uint16_t value_h;   // for char decl
};

bool gattPeerHandleRequest(uint8_t conn_role, const char *adv_name,
                           bool (*write_att)(void *, const uint8_t *, uint16_t),
                           void *ctx, const uint8_t *att, uint16_t att_len,
                           bool *hid_cccd_on, bool *ftms_cccd_on,
                           bool *ftms_cp_cccd_on = nullptr,
                           uint8_t *pending_ind = nullptr,
                           uint16_t *pending_ind_len = nullptr);

/** Minimal Report Map / HID Info / FTMS feature blobs. */
const uint8_t *gattPeerReportMap(size_t *len);
const uint8_t *gattPeerHidInfo(size_t *len);
const uint8_t *gattPeerFtmsFeature(size_t *len);

}  // namespace bt_analyzer
