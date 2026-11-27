#pragma once

/**
 * @file WgConfigStore.h
 * @brief Optional WireGuard NVS config (bt-analyzer). Never required for BT/capture.
 */

#include <Arduino.h>

/**
 * @brief WireGuard overlay settings in NVS namespace "bt_wg".
 *
 * Mirrors hu-probe wg* fields. Default wgEnable=false. Secrets are not exported
 * as plaintext in status JSON (only *Set flags).
 */
class WgConfigStore {
public:
    bool wgEnable = false;
    String wgPrivateKey;
    String wgPublicKey;
    String wgPresharedKey;
    String wgAddress;
    String wgAllowedIps;
    String wgEndpointHost;
    uint16_t wgEndpointPort = 51820;
    uint16_t wgKeepalive = 25;

    void load();
    bool save();
    bool importWgQuick(const String& text);
    bool looksConfigured() const;
};
