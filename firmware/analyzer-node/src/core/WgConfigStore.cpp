/**
 * @file WgConfigStore.cpp
 * @brief NVS load/save + wg-quick import for optional WireGuard overlay.
 */

#include "WgConfigStore.h"

#include <Preferences.h>

namespace {

Preferences prefs;
constexpr const char* kNs = "bt_wg";

String trimKv(String s) {
    s.trim();
    return s;
}

}  // namespace

bool WgConfigStore::looksConfigured() const {
    return wgPrivateKey.length() > 0 && wgPublicKey.length() > 0 && wgAddress.length() > 0 &&
           wgAllowedIps.length() > 0 && wgEndpointHost.length() > 0;
}

bool WgConfigStore::importWgQuick(const String& text) {
    enum class Sec : uint8_t { None, Interface, Peer };
    Sec sec = Sec::None;
    bool sawInterface = false;
    bool sawPeer = false;

    int start = 0;
    while (start <= (int)text.length()) {
        int end = text.indexOf('\n', start);
        if (end < 0) end = text.length();
        String line = text.substring(start, end);
        if (line.endsWith("\r")) line.remove(line.length() - 1);
        start = end + 1;

        String t = trimKv(line);
        if (t.length() == 0 || t.startsWith("#") || t.startsWith(";")) continue;

        if (t.equalsIgnoreCase("[Interface]")) {
            sec = Sec::Interface;
            sawInterface = true;
            continue;
        }
        if (t.equalsIgnoreCase("[Peer]")) {
            sec = Sec::Peer;
            sawPeer = true;
            continue;
        }
        if (t.startsWith("[")) return false;

        const int eq = t.indexOf('=');
        if (eq <= 0) return false;
        String key = trimKv(t.substring(0, eq));
        String value = trimKv(t.substring(eq + 1));

        if (sec == Sec::Interface) {
            if (key.equalsIgnoreCase("PrivateKey")) wgPrivateKey = value;
            else if (key.equalsIgnoreCase("Address")) wgAddress = value;
        } else if (sec == Sec::Peer) {
            if (key.equalsIgnoreCase("PublicKey")) wgPublicKey = value;
            else if (key.equalsIgnoreCase("PresharedKey")) wgPresharedKey = value;
            else if (key.equalsIgnoreCase("AllowedIPs")) wgAllowedIps = value;
            else if (key.equalsIgnoreCase("Endpoint")) {
                const int colon = value.lastIndexOf(':');
                if (colon > 0) {
                    wgEndpointHost = trimKv(value.substring(0, colon));
                    wgEndpointPort = (uint16_t)trimKv(value.substring(colon + 1)).toInt();
                } else {
                    wgEndpointHost = value;
                }
            } else if (key.equalsIgnoreCase("PersistentKeepalive")) {
                wgKeepalive = (uint16_t)value.toInt();
            }
        }
    }
    if (!sawInterface || !sawPeer) return false;
    String allowed = wgAllowedIps;
    allowed.replace(" ", "");
    if (allowed.indexOf("0.0.0.0/0") >= 0) return false;
    return looksConfigured();
}

void WgConfigStore::load() {
    wgEnable = false;
    wgPrivateKey = "";
    wgPublicKey = "";
    wgPresharedKey = "";
    wgAddress = "";
    wgAllowedIps = "";
    wgEndpointHost = "";
    wgEndpointPort = 51820;
    wgKeepalive = 25;
    if (!prefs.begin(kNs, true)) return;
    wgEnable = prefs.getBool("wg_en", false);
    wgPrivateKey = prefs.getString("wg_priv", "");
    wgPublicKey = prefs.getString("wg_pub", "");
    wgPresharedKey = prefs.getString("wg_psk", "");
    wgAddress = prefs.getString("wg_addr", "");
    wgAllowedIps = prefs.getString("wg_allow", "");
    wgEndpointHost = prefs.getString("wg_ep", "");
    wgEndpointPort = (uint16_t)prefs.getUShort("wg_port", 51820);
    wgKeepalive = (uint16_t)prefs.getUShort("wg_ka", 25);
    prefs.end();
}

bool WgConfigStore::save() {
    if (!prefs.begin(kNs, false)) return false;
    prefs.putBool("wg_en", wgEnable);
    prefs.putString("wg_priv", wgPrivateKey);
    prefs.putString("wg_pub", wgPublicKey);
    prefs.putString("wg_psk", wgPresharedKey);
    prefs.putString("wg_addr", wgAddress);
    prefs.putString("wg_allow", wgAllowedIps);
    prefs.putString("wg_ep", wgEndpointHost);
    prefs.putUShort("wg_port", wgEndpointPort);
    prefs.putUShort("wg_ka", wgKeepalive);
    prefs.end();
    return true;
}
