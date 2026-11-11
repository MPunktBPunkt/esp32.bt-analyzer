#include "agent/HciTcpAgent.h"

#include "core/DiagLog.h"

#include <esp_bt.h>
#include <esp_mac.h>
#include <lwip/sockets.h>
#include <nvs_flash.h>
#include <stdio.h>

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
  xTaskCreatePinnedToCore(&HciTcpAgent::taskEntry, "hci_agent", 4096, this, 3,
                          nullptr, 1);
  DiagLog::printf("[hci_agent] ready port=%u heap=%u\n",
                  static_cast<unsigned>(HCI_AGENT_PORT),
                  static_cast<unsigned>(ESP.getFreeHeap()));
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

int HciTcpAgent::onControllerPacket(uint8_t *data, uint16_t len) {
  HciTcpAgent *self = g_agent;
  if (!self || !self->client_active_ || !data || len == 0) {
    return 0;
  }
  if (xRingbufferSend(self->to_host_, data, len, 0) != pdTRUE) {
    self->drops_++;
    self->overflow_ = true;
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
    if (overflow_) {
      dropClient("to_host_overflow");
      continue;
    }
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
  framer_.reset();
  pending_ = false;
  in_len_ = in_pos_ = 0;
  overflow_ = false;
  flushRing(to_host_);
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
  for (size_t i = 0; i < kMaxItemsPerPump; i++) {
    size_t n = 0;
    auto *item = static_cast<uint8_t *>(
        xRingbufferReceive(to_host_, &n, i == 0 ? wait : 0));
    if (!item) {
      break;
    }
    const size_t w = client_.write(item, n);
    vRingbufferReturnItem(to_host_, item);
    if (w != n) {
      dropClient("write_fail");
      return moved;
    }
    to_host_pkts_++;
    to_host_bytes_ += n;
    moved = true;
  }
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
  json += "}";
}

}  // namespace bt_analyzer
