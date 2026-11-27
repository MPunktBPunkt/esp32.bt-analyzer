/**
 * @file WireGuardTransport.cpp
 * @brief Optional esp_wireguard transport (esp32.wireguard v0.4.9 patterns).
 */

#include "net/WireGuardTransport.h"
#include "core/WgConfigStore.h"

#include <WiFi.h>
#include <string.h>
#include <time.h>

#ifndef BT_ANALYZER_ENABLE_WIREGUARD
#define BT_ANALYZER_ENABLE_WIREGUARD 0
#endif

#if BT_ANALYZER_ENABLE_WIREGUARD
#include <esp_wireguard.h>
#include <lwip/ip4_addr.h>
#include <lwip/netif.h>
#include <lwip/tcpip.h>
#endif

namespace {

#if BT_ANALYZER_ENABLE_WIREGUARD

struct WgParams {
    String privateKey;
    String publicKey;
    String presharedKey;
    String address;
    String allowedIps;
    String endpointHost;
    uint16_t endpointPort = 51820;
    uint16_t keepalive = 25;
};

String trimCopy(String s) {
    s.trim();
    return s;
}

bool parseCidr(const String& cidr, char* ipOut, size_t ipCap, char* maskOut, size_t maskCap) {
    const int slash = cidr.indexOf('/');
    String ip = slash >= 0 ? cidr.substring(0, slash) : cidr;
    ip.trim();
    int prefix = 32;
    if (slash >= 0) {
        prefix = cidr.substring(slash + 1).toInt();
        if (prefix < 0 || prefix > 32) return false;
    }
    if (ip.length() == 0 || ip.length() >= (int)ipCap) return false;
    strncpy(ipOut, ip.c_str(), ipCap - 1);
    ipOut[ipCap - 1] = 0;
    const uint32_t mask = prefix == 0 ? 0u : (0xffffffffu << (32 - prefix));
    snprintf(maskOut, maskCap, "%u.%u.%u.%u", (mask >> 24) & 0xff, (mask >> 16) & 0xff,
             (mask >> 8) & 0xff, mask & 0xff);
    return true;
}

bool parseFirstAllowed(const String& allowedIps, char* ipOut, size_t ipCap, char* maskOut,
                       size_t maskCap) {
    String first = allowedIps;
    const int comma = first.indexOf(',');
    if (comma >= 0) first = first.substring(0, comma);
    first.trim();
    if (!parseCidr(first, ipOut, ipCap, maskOut, maskCap)) return false;
    return strcmp(ipOut, "0.0.0.0") != 0;
}

bool paramsFromConfig(const WgConfigStore& cfg, WgParams& out) {
    out.privateKey = cfg.wgPrivateKey;
    out.publicKey = cfg.wgPublicKey;
    out.presharedKey = cfg.wgPresharedKey;
    out.address = cfg.wgAddress;
    out.allowedIps = cfg.wgAllowedIps;
    out.endpointHost = cfg.wgEndpointHost;
    out.endpointPort = cfg.wgEndpointPort ? cfg.wgEndpointPort : 51820;
    out.keepalive = cfg.wgKeepalive ? cfg.wgKeepalive : 25;
    return out.privateKey.length() > 0 && out.publicKey.length() > 0 && out.address.length() > 0 &&
           out.allowedIps.length() > 0 && out.endpointHost.length() > 0;
}

wireguard_ctx_t gCtx = {};
wireguard_config_t gCfg = ESP_WIREGUARD_CONFIG_DEFAULT();
bool gStackInited = false;
bool gConnected = false;
const char* gErr = "";

char gPrivateKey[64];
char gPublicKey[64];
char gPresharedKey[64];
char gLocalIp[32];
char gLocalMask[32];
char gPeerAllowedIp[32];
char gPeerAllowedMask[32];
char gEndpoint[128];
bool gHasPsk = false;
bool gHasPeerAllowed = false;

esp_err_t gTcpipErr = ESP_FAIL;

/**
 * Run WG/netif work under the lwIP core lock.
 * Arduino-ESP32 2.x (PlatformIO espressif32@6.4) has no tcpip_callback_wait;
 * a naive tcpip_send_msg_wait_sem without a signalling trampoline deadlocks
 * forever (lab brick before HTTP). LOCK_TCPIP_CORE matches the proven
 * esp32.wireguard path once the endpoint is already an IPv4 literal.
 */
bool runOnTcpip(tcpip_callback_fn fn) {
    gTcpipErr = ESP_FAIL;
    LOCK_TCPIP_CORE();
    fn(nullptr);
    UNLOCK_TCPIP_CORE();
    return true;
}

void cbConnect(void* /*arg*/) { gTcpipErr = esp_wireguard_connect(&gCtx); }
void cbDisconnect(void* /*arg*/) { gTcpipErr = esp_wireguard_disconnect(&gCtx); }
void cbPeerUp(void* /*arg*/) { gTcpipErr = esp_wireguardif_peer_is_up(&gCtx); }

void cbInstallRoute(void* /*arg*/) {
    gTcpipErr = ESP_ERR_INVALID_STATE;
    if (!gCtx.netif || !gHasPeerAllowed) {
        gTcpipErr = ESP_OK;
        return;
    }
    ip4_addr_t allowed{};
    ip4_addr_t amask{};
    if (!ip4addr_aton(gPeerAllowedIp, &allowed) || !ip4addr_aton(gPeerAllowedMask, &amask)) {
        gTcpipErr = ESP_ERR_INVALID_ARG;
        return;
    }
    const IPAddress staIp = WiFi.localIP();
    ip4_addr_t sta{};
    IP4_ADDR(&sta, staIp[0], staIp[1], staIp[2], staIp[3]);
    ip4_addr_t route_mask{};
    IP4_ADDR(&route_mask, 255, 255, 255, 0);
    const ip4_addr_t* local = netif_ip4_addr(gCtx.netif);
    if (!ip4_addr_netcmp(local, &allowed, &route_mask)) {
        if (!ip4_addr_netcmp(local, &allowed, &amask)) {
            Serial.printf("[WG] route skip: local %s and allowed %s share no common mask\n",
                          gLocalIp, gPeerAllowedIp);
            gTcpipErr = ESP_ERR_NOT_SUPPORTED;
            return;
        }
        route_mask = amask;
    }
    if (ip4_addr_netcmp(&sta, local, &route_mask)) {
        Serial.printf("[WG] route refuse: STA %s in AllowedIPs net (blackhole risk)\n",
                      staIp.toString().c_str());
        gTcpipErr = ESP_ERR_INVALID_STATE;
        return;
    }
    netif_set_netmask(gCtx.netif, &route_mask);
    Serial.printf("[WG] route installed: wg netmask → %s (STA=%s allowed=%s)\n",
                  ip4addr_ntoa(&route_mask), staIp.toString().c_str(), gPeerAllowedIp);
    gTcpipErr = ESP_OK;
}

bool stackInit(const WgParams& p) {
    gErr = "";
    if (gConnected) {
        runOnTcpip(cbDisconnect);
    }
    gStackInited = false;
    gConnected = false;
    gHasPeerAllowed = false;
    memset(&gCtx, 0, sizeof(gCtx));
    gCfg = ESP_WIREGUARD_CONFIG_DEFAULT();

    if (p.privateKey.length() >= (int)sizeof(gPrivateKey) ||
        p.publicKey.length() >= (int)sizeof(gPublicKey) ||
        p.endpointHost.length() >= (int)sizeof(gEndpoint)) {
        gErr = "key_or_endpoint_too_long";
        return false;
    }
    strncpy(gPrivateKey, p.privateKey.c_str(), sizeof(gPrivateKey) - 1);
    strncpy(gPublicKey, p.publicKey.c_str(), sizeof(gPublicKey) - 1);

    {
        IPAddress resolved;
        if (WiFi.hostByName(p.endpointHost.c_str(), resolved) &&
            resolved != IPAddress((uint32_t)0)) {
            strncpy(gEndpoint, resolved.toString().c_str(), sizeof(gEndpoint) - 1);
        } else {
            strncpy(gEndpoint, p.endpointHost.c_str(), sizeof(gEndpoint) - 1);
        }
        gEndpoint[sizeof(gEndpoint) - 1] = 0;
        Serial.printf("[WG] endpoint resolved → %s:%u\n", gEndpoint, (unsigned)p.endpointPort);
    }

    gHasPsk = false;
    if (p.presharedKey.length()) {
        if (p.presharedKey.length() >= (int)sizeof(gPresharedKey)) {
            gErr = "psk_too_long";
            return false;
        }
        strncpy(gPresharedKey, p.presharedKey.c_str(), sizeof(gPresharedKey) - 1);
        gHasPsk = true;
    }

    String allowed = p.allowedIps;
    allowed.replace(" ", "");
    if (allowed.indexOf("0.0.0.0/0") >= 0) {
        gErr = "full_tunnel_not_allowed";
        return false;
    }

    if (!parseCidr(p.address, gLocalIp, sizeof(gLocalIp), gLocalMask, sizeof(gLocalMask))) {
        gErr = "bad_address_cidr";
        return false;
    }
    if (!parseFirstAllowed(p.allowedIps, gPeerAllowedIp, sizeof(gPeerAllowedIp), gPeerAllowedMask,
                           sizeof(gPeerAllowedMask))) {
        gErr = "bad_or_catchall_allowedips";
        return false;
    }
    gHasPeerAllowed = true;

    gCfg.private_key = gPrivateKey;
    gCfg.public_key = gPublicKey;
    gCfg.preshared_key = gHasPsk ? gPresharedKey : nullptr;
    gCfg.allowed_ip = gLocalIp;
    gCfg.allowed_ip_mask = gLocalMask;
    gCfg.peer_allowed_ip = gPeerAllowedIp;
    gCfg.peer_allowed_mask = gPeerAllowedMask;
    gCfg.endpoint = gEndpoint;
    gCfg.port = p.endpointPort;
    gCfg.persistent_keepalive = p.keepalive;

    const esp_err_t err = esp_wireguard_init(&gCfg, &gCtx);
    if (err != ESP_OK) {
        gErr = "init_fail";
        return false;
    }
    gStackInited = true;
    return true;
}

bool stackConnect() {
    if (!gStackInited) {
        gErr = "not_inited";
        return false;
    }
    Serial.printf("[WG] esp_wireguard_connect (%s)...\n", gEndpoint);
    if (!runOnTcpip(cbConnect)) {
        Serial.printf("[WG] esp_wireguard_connect tcpip_cb fail\n");
        return false;
    }
    const esp_err_t err = gTcpipErr;
    Serial.printf("[WG] esp_wireguard_connect → %s\n", esp_err_to_name(err));
    if (err != ESP_OK) {
        gErr = "connect_fail";
        return false;
    }
    gConnected = true;
    esp_wireguard_reset_traffic();
    if (!runOnTcpip(cbInstallRoute)) {
        gErr = "route_cb_fail";
        return false;
    }
    if (gTcpipErr == ESP_ERR_INVALID_STATE) {
        Serial.printf("[WG] selective route refused (STA in AllowedIPs net)\n");
    } else if (gTcpipErr != ESP_OK && gTcpipErr != ESP_ERR_NOT_SUPPORTED) {
        gErr = "route_fail";
        return false;
    }
    return true;
}

void stackDisconnect() {
    if (gConnected || gStackInited) {
        runOnTcpip(cbDisconnect);
    }
    gConnected = false;
    gStackInited = false;
    gHasPeerAllowed = false;
    memset(&gCtx, 0, sizeof(gCtx));
}

bool stackPeerUp() {
    if (!gConnected) return false;
    if (!runOnTcpip(cbPeerUp)) return false;
    return gTcpipErr == ESP_OK;
}

#endif  // BT_ANALYZER_ENABLE_WIREGUARD

static constexpr unsigned long kPeerPollMs = 5000;
static constexpr time_t kMinEpoch = 1640995200;  // 2022-01-01 — WireGuard needs absolute time

bool timeValid() {
    return time(nullptr) > kMinEpoch;
}

}  // namespace

WireGuardTransport* WireGuardTransport::current_ = nullptr;

WireGuardTransport* WireGuardTransport::current() { return current_; }

void WireGuardTransport::begin(WgConfigStore* cfg) {
    cfg_ = cfg;
    current_ = this;
}

bool WireGuardTransport::enable() {
#if !BT_ANALYZER_ENABLE_WIREGUARD
    return false;
#else
    if (!cfg_ || !cfg_->wgEnable) return false;
    if (active_ || connectRequested_) return true;
    if (WiFi.status() != WL_CONNECTED) {
        gErr = "wifi_down";
        Serial.println("[WG] skip enable: WiFi not connected");
        return false;
    }
    WgParams p;
    if (!paramsFromConfig(*cfg_, p)) {
        gErr = "incomplete_config";
        Serial.println("[WG] skip enable: incomplete config");
        return false;
    }
    connectRequested_ = true;
    gErr = timeValid() ? "" : "waiting_sntp";
    if (!timeValid()) Serial.println("[WG] enable deferred until SNTP");
    return true;
#endif
}

bool WireGuardTransport::tryConnect() {
#if !BT_ANALYZER_ENABLE_WIREGUARD
    return false;
#else
    WgParams p;
    if (!paramsFromConfig(*cfg_, p)) {
        gErr = "incomplete_config";
        return false;
    }
    if (!stackInit(p) || !stackConnect()) {
        Serial.printf("[WG] enable failed: %s\n", gErr ? gErr : "?");
        stackDisconnect();
        active_ = false;
        peerUp_ = false;
        return false;
    }
    active_ = true;
    peerUp_ = stackPeerUp();
    Serial.printf("[WG] enabled peer_up=%d time=%ld\n", peerUp_ ? 1 : 0, (long)time(nullptr));
    return true;
#endif
}

void WireGuardTransport::disable() {
#if BT_ANALYZER_ENABLE_WIREGUARD
    stackDisconnect();
    gErr = "";
#endif
    connectRequested_ = false;
    active_ = false;
    peerUp_ = false;
}

void WireGuardTransport::loop() {
#if BT_ANALYZER_ENABLE_WIREGUARD
    if (connectRequested_ && !active_) {
        if (WiFi.status() != WL_CONNECTED) return;
        if (!timeValid()) {
            const unsigned long now = millis();
            if (now - lastSntpLogMs_ > 10000) {
                lastSntpLogMs_ = now;
                Serial.printf("[WG] waiting SNTP (epoch=%ld)\n", (long)time(nullptr));
            }
            return;
        }
        connectRequested_ = false;
        tryConnect();
    }
    if (!active_) return;
    const unsigned long now = millis();
    if (now - lastPeerPollMs_ < kPeerPollMs) return;
    lastPeerPollMs_ = now;
    const bool was = peerUp_;
    peerUp_ = stackPeerUp();
    if (peerUp_ != was) {
        Serial.printf("[WG] peer_up=%d\n", peerUp_ ? 1 : 0);
    }
#endif
}

bool WireGuardTransport::active() const { return active_; }

bool WireGuardTransport::peerUp() const { return peerUp_; }

const char* WireGuardTransport::lastError() const {
#if BT_ANALYZER_ENABLE_WIREGUARD
    return gErr ? gErr : "";
#else
    return "";
#endif
}