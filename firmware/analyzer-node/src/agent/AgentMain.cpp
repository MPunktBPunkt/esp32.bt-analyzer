/**
 * esp32.bt-analyzer — hci-agent (D1 Mini / ESP32)
 *
 * On-chip BR/EDR+LE controller as raw H4 over TCP for a Linux BlueZ host.
 * Built only by env hci-agent-esp32; replaces the thin-host analyzer image.
 */

#include "ProjectConfig.h"
#include "agent/HciTcpAgent.h"
#include "core/AppCore.h"
#include "core/IoTypes.h"

static bt_analyzer::HciTcpAgent g_agent;
static AppCore app;

IoValue ioTable[] = {
    {"hci_ready", "number", 0.0f, ""},
    {"hci_client", "number", 0.0f, ""},
};

const int IO_COUNT = sizeof(ioTable) / sizeof(ioTable[0]);

void updateIoValues() {
  ioTable[0].value = g_agent.controllerReady() ? 1.0f : 0.0f;
  ioTable[1].value = g_agent.clientConnected() ? 1.0f : 0.0f;
}

void setup() {
  app.modules().add(&g_agent);
  app.begin();
}

void loop() {
  app.loop();
}
