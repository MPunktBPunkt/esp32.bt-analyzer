/**
 * esp32.bt-analyzer — analyzer-node
 *
 * Primary: on-chip Bluetooth controller via VHCI (no USB dongle).
 * Optional: USB Host HCI path when BT_ANALYZER_ENABLE_USB_HOST=1.
 *
 * Base: ESP32.esp-hub esp-hub-base v1.10.5 (vendored under src/core/).
 */

#include "ProjectConfig.h"
#include "core/IoTypes.h"
#include "core/AppCore.h"
#include "app/BtAnalyzerModule.h"
#include "bt/OnchipBt.h"
#include "usb/UsbHostEnum.h"

static bt_analyzer::OnchipBt g_onchip;
#if BT_ANALYZER_ENABLE_USB_HOST
static bt_analyzer::UsbHostEnum g_usb_host;
static bt_analyzer::BtAnalyzerModule g_bt(&g_onchip, &g_usb_host);
#else
static bt_analyzer::BtAnalyzerModule g_bt(&g_onchip, nullptr);
#endif
static AppCore app;

IoValue ioTable[] = {
    {"bt_ready", "number", 0.0f, ""},
    {"bt_devs", "number", 0.0f, ""},
    {"bt_scan", "number", 0.0f, ""},
    {"bt_ble", "number", 0.0f, ""},
    {"bt_classic", "number", 0.0f, ""},
};

const int IO_COUNT = sizeof(ioTable) / sizeof(ioTable[0]);

void updateIoValues() {
  ioTable[0].value = g_onchip.ready() ? 1.0f : 0.0f;
  ioTable[1].value = static_cast<float>(g_onchip.deviceCount());
  ioTable[2].value = g_onchip.scanning() ? 1.0f : 0.0f;
  ioTable[3].value = g_onchip.bleCapable() ? 1.0f : 0.0f;
  ioTable[4].value = g_onchip.classicCapable() ? 1.0f : 0.0f;
}

void setup() {
  app.modules().add(&g_bt);
  app.begin();
}

void loop() {
  app.loop();
}
