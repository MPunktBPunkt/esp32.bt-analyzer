#pragma once

#include "core/BaseModule.h"
#include "usb/UsbHostEnum.h"

namespace bt_analyzer {

/** App module: USB enum status in /api/status + Hub ios via main updateIoValues. */
class BtAnalyzerModule : public BaseModule {
public:
  explicit BtAnalyzerModule(UsbHostEnum *host) : host_(host) {}

  const char *name() const override { return "bt"; }

  void begin() override {
    if (host_) {
      host_->begin();
    }
  }

  void loop() override {
    if (host_) {
      host_->loop();
    }
  }

  void appendStatusJson(String &json) override {
    if (host_) {
      host_->appendStatusJson(json);
    }
  }

  void registerRoutes(WebServer &server) override;

private:
  UsbHostEnum *host_;
};

}  // namespace bt_analyzer
