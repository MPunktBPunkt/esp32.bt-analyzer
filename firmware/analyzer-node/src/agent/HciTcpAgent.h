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
  // Larger ring absorbs WiFi coexistence stalls without killing the TCP session.
  static constexpr size_t kToHostRingBytes = 24 * 1024;
  // Batch controller→host H4 into ~one TCP segment (BT+WiFi coex hates tiny writes).
  static constexpr size_t kToHostBatchBytes = 1200;
  static constexpr int kSockBufBytes = 32 * 1024;

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
  // Self-tracked ring occupancy (NOSPLIT free-size is contiguous-only).
  volatile uint32_t ring_used_ = 0;
  volatile uint32_t ring_peak_ = 0;
  // HCI Command → Command Complete/Status RTT (controller path only).
  volatile bool rtt_pending_ = false;
  volatile uint16_t rtt_opcode_ = 0;
  volatile uint32_t rtt_start_us_ = 0;
  volatile uint32_t rtt_last_us_ = 0;
  volatile uint32_t rtt_max_us_ = 0;
  volatile uint32_t rtt_samples_ = 0;

  bool startController();
  void adoptClient(WiFiClient &fresh);
  void dropClient(const char *why);
  bool pumpToController();
  bool pumpToHost(TickType_t wait);
  void sendControllerReset();
  bool setWifiPs(const char *mode);  // "none"|"min"|"max"
  const char *wifiPsName() const { return wifi_ps_name_; }
  bool setCoex(const char *mode);  // "default"|"a2dp"|"prefer_bt"
  void noteRingEnqueue(size_t n);
  void noteRingDequeue(size_t n);
  void noteHostCommand(const uint8_t *pkt, size_t n);
  void noteControllerEvent(const uint8_t *pkt, size_t n);
  void run();
  void registerRoutes(WebServer &server) override;

  static int onControllerPacket(uint8_t *data, uint16_t len);
  static void onSendAvailable() {}
  static void taskEntry(void *self);

  // Default matches pre-0.3.16-opt behavior (modem sleep). "none" helps TCP
  // RTT but can break Classic page/ACL under BT/WiFi coex — toggle via API.
  const char *wifi_ps_name_ = "min";
  // BlueZ runs A2DP on Linux, so the coex scheduler never sees the
  // A2DP-streaming status Bluedroid would set — "a2dp" sets it by hand.
  const char *coex_name_ = "default";
  char coex_err_[24] = "";
};

}  // namespace bt_analyzer
