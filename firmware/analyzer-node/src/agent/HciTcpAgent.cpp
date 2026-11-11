#include "agent/HciTcpAgent.h"

#include "core/DiagLog.h"

#include <esp_bt.h>
#include <esp_mac.h>
#include <esp_wifi.h>
#include <lwip/sockets.h>
#include <nvs_flash.h>
#include <stdio.h>
#include <string.h>

#if CONFIG_IDF_TARGET_ESP32
#include <esp32-hal-bt.h>
#endif

#if defined(CONFIG_BT_BLUEDROID_ENABLED) && CONFIG_BT_BLUEDROID_ENABLED
#include <esp_bt_main.h>
#endif

namespace bt_analyzer {
namespace {

HciTcpAgent *g_agent = nullptr;

constexpr size_t kMaxPacketsPerPump = 16;
constexpr size_t kMaxItemsPerPump = 32;

void flushRing(RingbufHandle_t rb) {
  size_t n = 0;
  void *item = nullptr;
  while ((item = xRingbufferReceive(rb, &n, 0)) != nullptr) {
    vRingbufferReturnItem(rb, item);
  }
}

void enableKeepalive(int fd) {
  if (fd < 0) {
    return;
  }
  int on = 1;
  int idle_s = 5;
  int intvl_s = 2;
  int cnt = 3;
  setsockopt(fd, SOL_SOCKET, SO_KEEPALIVE, &on, sizeof(on));
#ifdef TCP_KEEPIDLE
  setsockopt(fd, IPPROTO_TCP, TCP_KEEPIDLE, &idle_s, sizeof(idle_s));
  setsockopt(fd, IPPROTO_TCP, TCP_KEEPINTVL, &intvl_s, sizeof(intvl_s));
  setsockopt(fd, IPPROTO_TCP, TCP_KEEPCNT, &cnt, sizeof(cnt));
#else
  (void)idle_s;
  (void)intvl_s;
  (void)cnt;
#endif
}

void enlargeTcpBuffers(int fd, int bytes) {
  if (fd < 0) {
    return;
  }
  setsockopt(fd, SOL_SOCKET, SO_RCVBUF, &bytes, sizeof(bytes));
  setsockopt(fd, SOL_SOCKET, SO_SNDBUF, &bytes, sizeof(bytes));
}

}  // namespace

void HciTcpAgent::begin() {
  g_agent = this;
  if (!startController()) {
    DiagLog::printf("[hci_agent] controller failed: %s\n", last_err_);
    return;
  }
  // After the controller: ESP32 BTDM bring-up needs the internal DRAM first.
  to_host_ = xRingbufferCreate(kToHostRingBytes, RINGBUF_TYPE_NOSPLIT);
  if (!to_host_) {
    snprintf(last_err_, sizeof(last_err_), "ring_alloc");
    DiagLog::printf("[hci_agent] ring alloc failed heap=%u\n",
                    static_cast<unsigned>(ESP.getFreeHeap()));
    return;
  }
  static const esp_vhci_host_callback_t cb = {
      .notify_host_send_available = HciTcpAgent::onSendAvailable,
      .notify_host_recv = HciTcpAgent::onControllerPacket,
  };
  const esp_err_t err = esp_vhci_host_register_callback(&cb);
  if (err != ESP_OK) {
    snprintf(last_err_, sizeof(last_err_), "vhci:%s", esp_err_to_name(err));
    DiagLog::printf("[hci_agent] %s\n", last_err_);
    return;
  }
  ready_ = true;
  setWifiPs("min");
  xTaskCreatePinnedToCore(&HciTcpAgent::taskEntry, "hci_agent", 4096, this, 3,
                          nullptr, 1);
  DiagLog::printf("[hci_agent] ready port=%u heap=%u wifi_ps=%s\n",
                  static_cast<unsigned>(HCI_AGENT_PORT),
                  static_cast<unsigned>(ESP.getFreeHeap()), wifi_ps_name_);
}

bool HciTcpAgent::setWifiPs(const char *mode) {
  wifi_ps_type_t ps = WIFI_PS_MIN_MODEM;
  const char *name = "min";
  if (mode && strcasecmp(mode, "none") == 0) {
    ps = WIFI_PS_NONE;
    name = "none";
  } else if (mode && strcasecmp(mode, "max") == 0) {
    ps = WIFI_PS_MAX_MODEM;
    name = "max";
  } else if (mode && strcasecmp(mode, "min") == 0) {
    ps = WIFI_PS_MIN_MODEM;
    name = "min";
  } else if (mode && mode[0]) {
    return false;
  }
  const esp_err_t err = esp_wifi_set_ps(ps);
  if (err != ESP_OK) {
    return false;
  }
  WiFi.setSleep(ps != WIFI_PS_NONE);
  wifi_ps_name_ = name;
  DiagLog::printf("[hci_agent] wifi_ps=%s\n", wifi_ps_name_);
  return true;
}

void HciTcpAgent::registerRoutes(WebServer &server) {
  WebServer *srv = &server;
  server.on("/api/hci/wifi_ps", HTTP_GET, [this, srv]() {
    String j = "{\"wifi_ps\":\"";
    j += wifi_ps_name_;
    j += "\",\"modes\":[\"none\",\"min\",\"max\"]}";
    srv->send(200, "application/json", j);
  });
  server.on("/api/hci/wifi_ps", HTTP_POST, [this, srv]() {
    String mode = srv->hasArg("mode") ? srv->arg("mode") : "";
    if (mode.isEmpty() && srv->hasArg("plain")) {
      mode = srv->arg("plain");
      mode.trim();
    }
    if (!setWifiPs(mode.c_str())) {
      srv->send(400, "application/json",
                "{\"ok\":false,\"error\":\"bad_mode\",\"hint\":\"none|min|max\"}");
      return;
    }
    String j = "{\"ok\":true,\"wifi_ps\":\"";
    j += wifi_ps_name_;
    j += "\"}";
    srv->send(200, "application/json", j);
  });
}

bool HciTcpAgent::startController() {
  esp_err_t err = nvs_flash_init();
  if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
    nvs_flash_erase();
    nvs_flash_init();
  }
#if CONFIG_IDF_TARGET_ESP32
  if (esp_bt_controller_get_status() != ESP_BT_CONTROLLER_STATUS_ENABLED &&
      !btStartMode(BT_MODE_BTDM)) {
    snprintf(last_err_, sizeof(last_err_), "btStart_BTDM heap=%u",
             static_cast<unsigned>(ESP.getFreeHeap()));
    return false;
  }
#else
  // Agent targets Classic proxy endpoints (D1 Mini / ESP32) only.
  snprintf(last_err_, sizeof(last_err_), "needs_esp32_classic");
  return false;
#endif
#if defined(CONFIG_BT_BLUEDROID_ENABLED) && CONFIG_BT_BLUEDROID_ENABLED
  if (esp_bluedroid_get_status() == ESP_BLUEDROID_STATUS_ENABLED) {
    esp_bluedroid_disable();
  }
  if (esp_bluedroid_get_status() == ESP_BLUEDROID_STATUS_INITIALIZED) {
    esp_bluedroid_deinit();
  }
#endif
  return true;
}

void HciTcpAgent::noteRingEnqueue(size_t n) {
  const uint32_t used = ring_used_ + static_cast<uint32_t>(n);
  ring_used_ = used;
  if (used > ring_peak_) {
    ring_peak_ = used;
  }
}

void HciTcpAgent::noteRingDequeue(size_t n) {
  const uint32_t cur = ring_used_;
  ring_used_ = (n >= cur) ? 0 : (cur - static_cast<uint32_t>(n));
}

void HciTcpAgent::noteHostCommand(const uint8_t *pkt, size_t n) {
  // H4 Command: type | opcode_lo | opcode_hi | plen | ...
  if (!pkt || n < 3 || pkt[0] != kH4Command || rtt_pending_) {
    return;
  }
  rtt_opcode_ = static_cast<uint16_t>(pkt[1] | (pkt[2] << 8));
  rtt_start_us_ = micros();
  rtt_pending_ = true;
}

void HciTcpAgent::noteControllerEvent(const uint8_t *pkt, size_t n) {
  // H4 Event: type | event | plen | params...
  if (!rtt_pending_ || !pkt || n < 3 || pkt[0] != kH4Event) {
    return;
  }
  uint16_t op = 0;
  if (pkt[1] == 0x0e && n >= 6) {
    // Command Complete: Num_HCI_Command_Packets, Opcode
    op = static_cast<uint16_t>(pkt[4] | (pkt[5] << 8));
  } else if (pkt[1] == 0x0f && n >= 7) {
    // Command Status: Status, Num_HCI_Command_Packets, Opcode
    op = static_cast<uint16_t>(pkt[5] | (pkt[6] << 8));
  } else {
    return;
  }
  if (op != rtt_opcode_) {
    return;
  }
  const uint32_t dt = micros() - rtt_start_us_;
  rtt_last_us_ = dt;
  if (dt > rtt_max_us_) {
    rtt_max_us_ = dt;
  }
  rtt_samples_++;
  rtt_pending_ = false;
}

int HciTcpAgent::onControllerPacket(uint8_t *data, uint16_t len) {
  HciTcpAgent *self = g_agent;
  if (!self || !self->client_active_ || !data || len == 0) {
    return 0;
  }
  self->noteControllerEvent(data, len);
  if (xRingbufferSend(self->to_host_, data, len, 0) != pdTRUE) {
    self->drops_++;
    self->overflow_ = true;
  } else {
    self->noteRingEnqueue(len);
  }
  return 0;
}

void HciTcpAgent::taskEntry(void *self) {
  static_cast<HciTcpAgent *>(self)->run();
}

void HciTcpAgent::run() {
  for (;;) {
    if (WiFi.status() != WL_CONNECTED) {
      if (client_active_) {
        dropClient("wifi_down");
      }
      vTaskDelay(pdMS_TO_TICKS(200));
      continue;
    }
    if (!listening_) {
      server_.begin();
      server_.setNoDelay(true);
      listening_ = true;
      DiagLog::printf("[hci_agent] listen :%u\n",
                      static_cast<unsigned>(HCI_AGENT_PORT));
    }
    WiFiClient fresh = server_.accept();
    if (fresh) {
      adoptClient(fresh);
    }
    if (!client_active_) {
      vTaskDelay(pdMS_TO_TICKS(20));
      continue;
    }
    // Ring overflow only counts drops — killing the TCP session forced a full
    // HCI reset and was worse for A2DP than a short ACL gap.
    overflow_ = false;
    if (!client_.connected()) {
      dropClient("peer_closed");
      continue;
    }
    const bool moved = pumpToController();
    if (client_active_) {
      pumpToHost(moved ? 0 : pdMS_TO_TICKS(2));
    }
  }
}

void HciTcpAgent::adoptClient(WiFiClient &fresh) {
  if (client_active_) {
    dropClient("replaced");
  }
  client_ = fresh;
  client_.setNoDelay(true);
  enableKeepalive(client_.fd());
  enlargeTcpBuffers(client_.fd(), kSockBufBytes);
  framer_.reset();
  pending_ = false;
  in_len_ = in_pos_ = 0;
  overflow_ = false;
  flushRing(to_host_);
  ring_used_ = 0;
  ring_peak_ = 0;
  rtt_pending_ = false;
  rtt_last_us_ = 0;
  rtt_max_us_ = 0;
  rtt_samples_ = 0;
  client_ip_ = static_cast<uint32_t>(client_.remoteIP());
  sessions_++;
  client_active_ = true;
  DiagLog::printf("[hci_agent] client %s session=%u\n",
                  client_.remoteIP().toString().c_str(),
                  static_cast<unsigned>(sessions_));
}

void HciTcpAgent::dropClient(const char *why) {
  client_active_ = false;
  client_.stop();
  framer_.reset();
  pending_ = false;
  in_len_ = in_pos_ = 0;
  overflow_ = false;
  // Without a host the controller must not keep phone/HU links alive.
  sendControllerReset();
  vTaskDelay(pdMS_TO_TICKS(50));
  flushRing(to_host_);
  DiagLog::printf("[hci_agent] client dropped: %s\n", why);
}

void HciTcpAgent::sendControllerReset() {
  static uint8_t reset_cmd[] = {kH4Command, 0x03, 0x0c, 0x00};
  for (int i = 0; i < 50 && !esp_vhci_host_check_send_available(); i++) {
    vTaskDelay(pdMS_TO_TICKS(1));
  }
  if (esp_vhci_host_check_send_available()) {
    esp_vhci_host_send_packet(reset_cmd, sizeof(reset_cmd));
  }
}

bool HciTcpAgent::pumpToController() {
  bool moved = false;
  for (size_t sent = 0; sent < kMaxPacketsPerPump;) {
    if (pending_) {
      if (!esp_vhci_host_check_send_available()) {
        return moved;  // leave bytes in the socket: TCP back-pressure
      }
      noteHostCommand(framer_.data(), framer_.size());
      esp_vhci_host_send_packet(const_cast<uint8_t *>(framer_.data()),
                                static_cast<uint16_t>(framer_.size()));
      to_ctrl_pkts_++;
      to_ctrl_bytes_ += framer_.size();
      framer_.reset();
      pending_ = false;
      moved = true;
      sent++;
      continue;
    }
    if (in_pos_ >= in_len_) {
      const int avail = client_.available();
      if (avail <= 0) {
        return moved;
      }
      const int n = client_.read(in_, min(avail, static_cast<int>(sizeof(in_))));
      if (n <= 0) {
        return moved;
      }
      in_len_ = static_cast<size_t>(n);
      in_pos_ = 0;
    }
    while (in_pos_ < in_len_ && !pending_) {
      switch (framer_.push(in_[in_pos_++])) {
      case H4Framer<kMaxPacket>::Result::Packet:
        pending_ = true;
        break;
      case H4Framer<kMaxPacket>::Result::Error:
        framing_errors_++;
        dropClient("framing");
        return moved;
      case H4Framer<kMaxPacket>::Result::NeedMore:
        break;
      }
    }
  }
  return moved;
}

bool HciTcpAgent::pumpToHost(TickType_t wait) {
  bool moved = false;
  uint8_t batch[kToHostBatchBytes];
  size_t batch_len = 0;
  auto flush_batch = [&]() -> bool {
    if (batch_len == 0) {
      return true;
    }
    const size_t w = client_.write(batch, batch_len);
    if (w != batch_len) {
      dropClient("write_fail");
      return false;
    }
    to_host_bytes_ += batch_len;
    batch_len = 0;
    moved = true;
    return true;
  };
  for (size_t i = 0; i < kMaxItemsPerPump; i++) {
    size_t n = 0;
    auto *item = static_cast<uint8_t *>(
        xRingbufferReceive(to_host_, &n, i == 0 ? wait : 0));
    if (!item) {
      break;
    }
    if (n > sizeof(batch)) {
      // Oversized (should not happen with kMaxPacket): flush then raw write.
      if (!flush_batch()) {
        vRingbufferReturnItem(to_host_, item);
        return moved;
      }
      const size_t w = client_.write(item, n);
      vRingbufferReturnItem(to_host_, item);
      noteRingDequeue(n);
      if (w != n) {
        dropClient("write_fail");
        return moved;
      }
      to_host_pkts_++;
      to_host_bytes_ += n;
      moved = true;
      continue;
    }
    if (batch_len + n > sizeof(batch) && !flush_batch()) {
      vRingbufferReturnItem(to_host_, item);
      return moved;
    }
    memcpy(batch + batch_len, item, n);
    batch_len += n;
    vRingbufferReturnItem(to_host_, item);
    noteRingDequeue(n);
    to_host_pkts_++;
  }
  flush_batch();
  return moved;
}

void HciTcpAgent::appendStatusJson(String &json) {
  uint8_t mac[6]{};
  esp_read_mac(mac, ESP_MAC_BT);
  char bd[18];
  snprintf(bd, sizeof(bd), "%02x:%02x:%02x:%02x:%02x:%02x", mac[0], mac[1],
           mac[2], mac[3], mac[4], mac[5]);
  json += ",\"hciAgent\":{\"port\":";
  json += String(HCI_AGENT_PORT);
  json += ",\"ready\":";
  json += ready_ ? "true" : "false";
  json += ",\"error\":\"";
  json += last_err_;
  json += "\",\"bdAddr\":\"";
  json += bd;
  json += "\",\"client\":";
  if (client_active_) {
    json += "\"" + IPAddress(client_ip_).toString() + "\"";
  } else {
    json += "null";
  }
  json += ",\"sessions\":" + String(sessions_);
  json += ",\"toCtrlPkts\":" + String(to_ctrl_pkts_);
  json += ",\"toCtrlBytes\":" + String(to_ctrl_bytes_);
  json += ",\"toHostPkts\":" + String(to_host_pkts_);
  json += ",\"toHostBytes\":" + String(to_host_bytes_);
  json += ",\"drops\":" + String(drops_);
  json += ",\"framingErrors\":" + String(framing_errors_);
  json += ",\"ringBytes\":" + String(static_cast<unsigned>(kToHostRingBytes));
  json += ",\"ringUsed\":" + String(ring_used_);
  json += ",\"ringPeak\":" + String(ring_peak_);
  json += ",\"rttLastUs\":" + String(rtt_last_us_);
  json += ",\"rttMaxUs\":" + String(rtt_max_us_);
  json += ",\"rttSamples\":" + String(rtt_samples_);
  json += ",\"wifiPs\":\"";
  json += wifi_ps_name_;
  json += "\"}";
}

}  // namespace bt_analyzer
