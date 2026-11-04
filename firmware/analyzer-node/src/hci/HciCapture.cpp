#if BT_ANALYZER_ENABLE_USB_HOST
#include "hci/HciCapture.h"

#include <esp_timer.h>
#include <string.h>

namespace bt_analyzer {

bool HciCapture::begin() {
  if (!usb_ || !ring_) {
    Serial.println("[hci-cap] missing usb/ring");
    return false;
  }
  if (!ring_->begin(256)) {
    return false;
  }
  if (!callbacks_set_) {
    usb_->onVendorData([this](const EspUsbHostVendorData &vd) {
      if (!vd.data || vd.length == 0) {
        return;
      }
      // Continuous bulk IN on HCI iface → ACL (controller → host).
      const uint8_t ep = vd.endpoint ? vd.endpoint
                                    : (bulk_in_ep_ ? bulk_in_ep_ : 0x80);
      enqueueFromUsb(HciPacketType::Acl, HciDirection::ControllerToHost, ep,
                     vd.data, vd.length);
      acl_in_++;
    });
    callbacks_set_ = true;
  }
  Serial.println("[hci-cap] ready (bulk IN ACL; event interrupt pending)");
  return true;
}

void HciCapture::onHciAttached(uint8_t address, const HciUsbDiscovery &hci) {
  if (!hci.wirelessControllerIface) {
    armed_ = false;
    pending_open_ = false;
    return;
  }
  pending_addr_ = address;
  pending_iface_ = hci.hciInterfaceNumber;
  bulk_in_ep_ = 0;
  bulk_out_ep_ = 0;
  for (uint8_t i = 0; i < hci.endpointCount; i++) {
    if (hci.endpoints[i].role &&
        strcmp(hci.endpoints[i].role, "hci_acl_in") == 0) {
      bulk_in_ep_ = hci.endpoints[i].address;
    }
    if (hci.endpoints[i].role &&
        strcmp(hci.endpoints[i].role, "hci_command_acl_out") == 0) {
      bulk_out_ep_ = hci.endpoints[i].address;
    }
  }
  pending_open_ = true;
  armed_ = true;
  open_ok_ = false;
  Serial.printf("[hci-cap] attach addr=%u iface=%u in=0x%02x out=0x%02x\n",
                address, pending_iface_, bulk_in_ep_, bulk_out_ep_);
}

void HciCapture::onHciDetached() {
  pending_open_ = false;
  open_ok_ = false;
  armed_ = false;
  Serial.println("[hci-cap] detached");
}

void HciCapture::tryOpen() {
  if (!pending_open_ || !usb_ || !armed_) {
    return;
  }
  pending_open_ = false;
  // Explicit iface claims Wireless Controller regardless of class 0xE0.
  const bool ok = usb_->vendorOpen(pending_addr_, pending_iface_,
                                   ESP_USB_HOST_VENDOR_READ_CONTINUOUS, 0);
  open_ok_ = ok;
  if (ok) {
    if (usb_->vendorInEndpoint(pending_addr_)) {
      bulk_in_ep_ = usb_->vendorInEndpoint(pending_addr_);
    }
    if (usb_->vendorOutEndpoint(pending_addr_)) {
      bulk_out_ep_ = usb_->vendorOutEndpoint(pending_addr_);
    }
    Serial.printf("[hci-cap] vendorOpen OK in=0x%02x out=0x%02x\n", bulk_in_ep_,
                  bulk_out_ep_);
  } else {
    open_fails_++;
    Serial.printf("[hci-cap] vendorOpen FAILED: %s\n", usb_->lastErrorName());
  }
}

void HciCapture::loop() {
  tryOpen();
}

void HciCapture::enqueueFromUsb(HciPacketType type, HciDirection dir,
                                uint8_t endpoint, const uint8_t *data,
                                size_t len) {
  if (!ring_ || !data || len == 0) {
    return;
  }
  CaptureFrame f;
  f.seq = ring_->nextSeq();
  f.ts_us = static_cast<uint64_t>(esp_timer_get_time());
  f.dir = dir;
  f.type = type;
  f.usb_endpoint = endpoint;
  f.length = static_cast<uint16_t>(len > kCaptureMaxPayload ? kCaptureMaxPayload
                                                            : len);
  memcpy(f.payload, data, f.length);
  ring_->enqueue(f);
}

bool HciCapture::injectRaw(HciPacketType type, HciDirection dir,
                           uint8_t endpoint, const uint8_t *data, size_t len) {
  if (!data && len) {
    return false;
  }
  enqueueFromUsb(type, dir, endpoint, data, len);
  inject_++;
  return true;
}

bool HciCapture::writeHost(const uint8_t *data, size_t len) {
  if (!usb_ || !open_ok_ || !data || len == 0) {
    return false;
  }
  if (!usb_->vendorWrite(data, len, pending_addr_)) {
    return false;
  }
  enqueueFromUsb(HciPacketType::Command, HciDirection::HostToController,
                 bulk_out_ep_, data, len);
  cmd_out_++;
  return true;
}

void HciCapture::appendStatusJson(String &json) const {
  json += ",\"hciCapture\":{";
  json += "\"armed\":";
  json += armed_ ? "true" : "false";
  json += ",\"openOk\":";
  json += open_ok_ ? "true" : "false";
  json += ",\"eventCapture\":\"pending_interrupt_in\"";
  json += ",\"aclIn\":";
  json += String(acl_in_);
  json += ",\"cmdOut\":";
  json += String(cmd_out_);
  json += ",\"inject\":";
  json += String(inject_);
  json += ",\"openFails\":";
  json += String(open_fails_);
  json += ",\"bulkInEp\":";
  json += String(bulk_in_ep_);
  json += ",\"bulkOutEp\":";
  json += String(bulk_out_ep_);
  json += "}";
}

String HciCapture::drainJsonl(size_t max_frames) {
  String out;
  if (!ring_) {
    return out;
  }
  CaptureFrame f;
  size_t n = 0;
  while (n < max_frames && ring_->dequeue(f)) {
    out += "{\"seq\":";
    out += String(f.seq);
    out += ",\"ts_us\":";
    // uint64 as string to avoid JSON number precision loss in JS
    char ts[32];
    snprintf(ts, sizeof(ts), "%llu", static_cast<unsigned long long>(f.ts_us));
    out += ts;
    out += ",\"dir\":\"";
    out += hciDirectionName(f.dir);
    out += "\",\"transport\":\"usb_hci\",\"type\":\"";
    out += hciPacketTypeName(f.type);
    out += "\",\"endpoint\":";
    out += String(f.usb_endpoint);
    out += ",\"length\":";
    out += String(f.length);
    out += ",\"payload_hex\":\"";
    for (uint16_t i = 0; i < f.length; i++) {
      char hx[3];
      snprintf(hx, sizeof(hx), "%02x", f.payload[i]);
      out += hx;
    }
    out += "\"}\n";
    n++;
  }
  return out;
}

}  // namespace bt_analyzer
#endif
