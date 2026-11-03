/**
 * esp32.bt-analyzer — analyzer-node
 *
 * Phase BT0: esp-hub-base AppCore (WiFi / Hub / Web UI / OTA / PSRAM).
 * Phase BT1: USB Host enumeration (VID/PID/interfaces/endpoints).
 * Phase BT2: USB-HCI interface/endpoint role detection (no capture yet).
 *
 * Base: ESP32.esp-hub esp-hub-base v1.10.5 (vendored under src/core/).
 */

#include "ProjectConfig.h"
#include "core/IoTypes.h"
#include "core/AppCore.h"
#include "app/BtAnalyzerModule.h"
#include "usb/UsbHostEnum.h"

static bt_analyzer::UsbHostEnum g_usb_host;
static bt_analyzer::BtAnalyzerModule g_bt(&g_usb_host);
static AppCore app;

IoValue ioTable[] = {
    {"usb_devs", "number", 0.0f, ""},
    {"usb_att", "number", 0.0f, ""},
    {"usb_vid", "number", 0.0f, ""},
    {"usb_pid", "number", 0.0f, ""},
    {"hci_det", "number", 0.0f, ""},
};

const int IO_COUNT = sizeof(ioTable) / sizeof(ioTable[0]);

void updateIoValues() {
  const size_t n = g_usb_host.deviceCount();
  ioTable[0].value = static_cast<float>(n);
  ioTable[1].value = n > 0 ? 1.0f : 0.0f;
  ioTable[2].value = static_cast<float>(g_usb_host.dutVid());
  ioTable[3].value = static_cast<float>(g_usb_host.dutPid());
  ioTable[4].value = g_usb_host.hciDetected() ? 1.0f : 0.0f;
}

void setup() {
  app.modules().add(&g_bt);
  app.begin();
}

void loop() {
  app.loop();
}
