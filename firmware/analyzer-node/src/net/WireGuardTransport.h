#pragma once

/**
 * @file WireGuardTransport.h
 * @brief Optional WireGuard overlay (compile-time gated). MSC/capture never depend on this.
 */

#include <Arduino.h>

class WgConfigStore;

/**
 * @brief Thin adapter around vendored esp_wireguard (only when BT_ANALYZER_ENABLE_WIREGUARD=1).
 *
 * enable() is best-effort and may defer until SNTP is valid; failures are logged only.
 * loop() completes a deferred connect and polls peer state periodically.
 */
class WireGuardTransport {
public:
    void begin(WgConfigStore* cfg);
    /** @brief Request init+connect from WgConfigStore (no-op when disabled or unconfigured). */
    bool enable();
    void disable();
    void loop();
    bool active() const;
    bool peerUp() const;
    const char* lastError() const;

    /** @brief Most recently begun instance (for /api/status); may be null. */
    static WireGuardTransport* current();

private:
    bool tryConnect();

    WgConfigStore* cfg_ = nullptr;
    bool connectRequested_ = false;
    bool active_ = false;
    bool peerUp_ = false;
    unsigned long lastPeerPollMs_ = 0;
    unsigned long lastSntpLogMs_ = 0;

    static WireGuardTransport* current_;
};
