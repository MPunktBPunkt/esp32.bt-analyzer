/**
 * esp32.bt-analyzer — analyzer-node
 *
 * Phase BT0: esp-hub-base AppCore only (WiFi / Hub / Web UI / OTA / PSRAM).
 * No Bluetooth, no USB Host yet.
 *
 * Base: ESP32.esp-hub esp-hub-base v1.10.5 (vendored under src/core/).
 */

#include "ProjectConfig.h"
#include "core/IoTypes.h"
#include "core/AppCore.h"

IoValue ioTable[] = {
    // BT1+: USB / HCI / capture counters as Hub ios
};

const int IO_COUNT = sizeof(ioTable) / sizeof(ioTable[0]);

void updateIoValues() {
    // BT1+: refresh USB/HCI/capture metrics for Hub heartbeat.
}

static AppCore app;

void setup() {
    app.begin();
}

void loop() {
    app.loop();
}
