#pragma once

#include "bt/OnchipBt.h"
#include "capture/BtacStream.h"
#include "capture/CaptureSession.h"
#include "core/BaseModule.h"
#include "usb/UsbHostEnum.h"

namespace bt_analyzer {

/** App module: on-chip VHCI primary; USB Host optional (legacy). */
class BtAnalyzerModule : public BaseModule {
public:
  BtAnalyzerModule(OnchipBt *onchip, UsbHostEnum *usb = nullptr)
      : onchip_(onchip), usb_(usb) {}

  const char *name() const override { return "bt"; }

  void begin() override {
    if (onchip_) {
      onchip_->begin();
      btac_.setRing(&onchip_->ring());
      btac_.begin();
      session_.bind(&onchip_->capture(), &onchip_->ring());
    }
#if BT_ANALYZER_ENABLE_USB_HOST
    if (usb_) {
      usb_->begin();
    }
#endif
  }

  void loop() override {
    if (onchip_) {
      onchip_->loop();
    }
    btac_.loop();
#if BT_ANALYZER_ENABLE_USB_HOST
    if (usb_) {
      usb_->loop();
    }
#endif
  }

  void appendStatusJson(String &json) override {
    if (onchip_) {
      onchip_->appendStatusJson(json);
    }
    session_.appendStatusJson(json);
    btac_.appendStatusJson(json);
#if BT_ANALYZER_ENABLE_USB_HOST
    if (usb_) {
      usb_->appendStatusJson(json);
    }
#else
    json += ",\"usbHost\":{\"enabled\":false,\"beginOk\":false,\"state\":\"disabled\"}";
    json += ",\"otg\":{\"mode\":\"none\",\"state\":\"disabled\",\"connected\":false,\"devices\":0}";
    json += ",\"dut\":{\"present\":false,\"note\":\"onchip_primary_no_dongle\"}";
#endif
  }

  void registerRoutes(WebServer &server) override;

  OnchipBt *onchip() { return onchip_; }
  BtacStream &btac() { return btac_; }
  CaptureSession &session() { return session_; }

private:
  OnchipBt *onchip_;
  UsbHostEnum *usb_;
  BtacStream btac_{};
  CaptureSession session_{};
};

}  // namespace bt_analyzer

