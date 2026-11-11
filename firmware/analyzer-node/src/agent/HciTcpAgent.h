#pragma once

#include "agent/H4Framer.h"
#include "core/BaseModule.h"

#include <Arduino.h>
#include <WiFi.h>
#include <freertos/FreeRTOS.h>
#include <freertos/ringbuf.h>

#ifndef HCI_AGENT_PORT
#define HCI_AGENT_PORT 9754
#endif

namespace bt_analyzer {

/**
 * On-chip controller exposed as raw H4 over one TCP client (no thin host).
 * The Linux side (tools/hci_tcp_bridge.py) turns the stream into a BlueZ hciN.
 * Newest TCP client wins; client loss resets the controller so links drop.
 */
class HciTcpAgent : public BaseModule {
public:
  const char *name() const override { return "hci_agent"; }
  void begin() override;
  void appendStatusJson(String &json) override;

  bool controllerReady() const { return ready_; }
  bool clientConnected() const { return client_active_; }

private:
  // ESP32 BR/EDR ACL buffer is 1021 B; headroom for the H4 header.
  static constexpr size_t kMaxPacket = 1100;
  static constexpr size_t kToHostRingBytes = 16 * 1024;

  RingbufHandle_t to_host_ = nullptr;
  WiFiServer server_{HCI_AGENT_PORT};
  WiFiClient client_;
  bool listening_ = false;
  bool ready_ = false;
  char last_err_[32] = "";

  H4Framer<kMaxPacket> framer_;
  bool pending_ = false;
  uint8_t in_[512]{};
  size_t in_len_ = 0;
  size_t in_pos_ = 0;

  volatile bool client_active_ = false;
  volatile bool overflow_ = false;
  volatile uint32_t client_ip_ = 0;
  volatile uint32_t sessions_ = 0;
  volatile uint32_t to_ctrl_pkts_ = 0;
  volatile uint32_t to_ctrl_bytes_ = 0;
  volatile uint32_t to_host_pkts_ = 0;
  volatile uint32_t to_host_bytes_ = 0;
  volatile uint32_t drops_ = 0;
  volatile uint32_t framing_errors_ = 0;

  bool startController();
  void adoptClient(WiFiClient &fresh);
  void dropClient(const char *why);
  bool pumpToController();
  bool pumpToHost(TickType_t wait);
  void sendControllerReset();
  void run();

  static int onControllerPacket(uint8_t *data, uint16_t len);
  static void onSendAvailable() {}
  static void taskEntry(void *self);
};

}  // namespace bt_analyzer
