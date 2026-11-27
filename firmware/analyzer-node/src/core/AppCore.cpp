/**
 * @file AppCore.cpp
 * @brief AppCore lifecycle implementation wiring core services.
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include "AppCore.h"
#include "BootContext.h"
#include "Checkpoint.h"
#include "CpuLoad.h"
#include "DiagLog.h"
#include "DiagSaved.h"
#include "PanicTail.h"
#include "ProgressWatch.h"
#include "Recovery.h"

#include <ESPmDNS.h>
#include <WiFi.h>

void AppCore::begin() {
    Serial.begin(115200);
    delay(500);
    Serial.println("\n=== ESP-Hub v" FW_VERSION " ===");

    BootContext::begin();
    ProgressWatch::begin();
    CpuLoad::begin();

    hw_.probe();
    hw_.logToSerial();
    DiagSaved::persistBootSnapshot(&hw_);
    DiagLog::persist("hw", false);
    hub_.setHardware(&hw_);
    web_.setHardware(&hw_);
    web_.setOta(&ota_);
    web_.setModules(&modules_);

    net_.checkResetButton();

    // On-chip BT (esp. ESP32 BTDM) needs internal DRAM before WiFi buffers land.
    // Module HTTP routes still register later in web_.begin().
    modules_.beginAll();

    Checkpoint::enter(Checkpoint::Wifi);
    net_.begin(deviceName_, hubHost_, hubPort_);
    Checkpoint::leave(Checkpoint::Wifi);
    PanicTail::breadcrumb(PanicTail::WifiUp);
    ProgressWatch::note(ProgressWatch::Idle);

    hub_.configure(deviceName_, hubHost_, hubPort_);

    String mdns = "esphub-" + WiFi.macAddress();
    mdns.replace(":", "");
    mdns.toUpperCase();
    mdns = "esphub-" + mdns.substring(6);
    if (MDNS.begin(mdns.c_str())) Serial.println("[mDNS] " + mdns + ".local");

    Checkpoint::enter(Checkpoint::Web);
    web_.begin(deviceName_, hubHost_, hubPort_, heartbeatIntervalMs_);
    Checkpoint::leave(Checkpoint::Web);
    PanicTail::breadcrumb(PanicTail::WebUp);

    // Pump web clients during Hub OTA download so SSE/status stay observable.
    ota_.setYield(+[]() {
        // No capture — WebUi exposes a static pump from the live instance.
        WebUi::pumpActiveClient();
    });

    // Optional WireGuard after HTTP is up — connect failure must not brick control plane.
    wgCfg_.load();
    web_.setWg(&wgCfg_, &wireGuard_);
    wireGuard_.begin(&wgCfg_);
    if (wgCfg_.wgEnable) {
        configTime(0, 0, "192.168.178.1", "pool.ntp.org", "time.nist.gov");
    }
    if (WiFi.status() == WL_CONNECTED && wgCfg_.wgEnable && wgCfg_.looksConfigured()) {
        if (!wireGuard_.enable()) {
            DiagLog::printf("[WG] optional transport failed: %s (BT continues)\n",
                            wireGuard_.lastError());
        }
    }
    lastWifiUp_ = (WiFi.status() == WL_CONNECTED);

    lastSuccess_ = millis();
    Checkpoint::enter(Checkpoint::Hub);
    bool nameChanged = false;
    if (hub_.sendHeartbeat(deviceName_, lastSuccess_, heartbeatIntervalMs_, otaPending_, otaUrl_,
                           &nameChanged)) {
        Checkpoint::leave(Checkpoint::Hub);
        PanicTail::breadcrumb(PanicTail::HubOk);
        ProgressWatch::note(ProgressWatch::Heartbeat);
    } else {
        Checkpoint::leave(Checkpoint::Hub);
    }
    ProgressWatch::note(ProgressWatch::Idle);
    web_.updateConfig(deviceName_, hubHost_, hubPort_, heartbeatIntervalMs_);
    lastHeartbeat_ = millis();
}

void AppCore::loop() {
    // USB-serial lab: LAB WG ON|OFF|STATUS ; LAB WIFI ssid|pass
    while (Serial.available()) {
        static String labLine;
        const char c = (char)Serial.read();
        if (c == '\r') continue;
        if (c != '\n') {
            if (labLine.length() < 192) labLine += c;
            continue;
        }
        labLine.trim();
        if (labLine.startsWith("LAB WIFI ")) {
            String rest = labLine.substring(9);
            const int bar = rest.indexOf('|');
            if (bar > 0) {
                String ssid = rest.substring(0, bar);
                String pass = rest.substring(bar + 1);
                ssid.trim();
                pass.trim();
                Serial.printf("[LAB] WIFI join ssid=%s (persistent=false)\n", ssid.c_str());
                WiFi.persistent(false);
                WiFi.disconnect(false, false);
                delay(50);
                WiFi.begin(ssid.c_str(), pass.c_str());
                const unsigned long t0 = millis();
                while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000UL) delay(200);
                if (WiFi.status() == WL_CONNECTED) {
                    Serial.printf("[LAB] WIFI ok ip=%s ssid=%s\n",
                                  WiFi.localIP().toString().c_str(), WiFi.SSID().c_str());
                    wireGuard_.disable();
                    if (wgCfg_.wgEnable) wireGuard_.enable();
                } else {
                    Serial.println("[LAB] WIFI FAIL timeout");
                }
            }
        } else if (labLine == "LAB WG OFF") {
            wgCfg_.wgEnable = false;
            wgCfg_.save();
            wireGuard_.disable();
            Serial.println("[LAB] WG disabled (runtime + NVS)");
        } else if (labLine == "LAB WG ON") {
            wgCfg_.wgEnable = true;
            wgCfg_.save();
            configTime(0, 0, "192.168.178.1", "pool.ntp.org", "time.nist.gov");
            wireGuard_.enable();
            Serial.println("[LAB] WG enable requested");
        } else if (labLine == "LAB WG STATUS") {
            Serial.printf("[LAB] WG enable=%d active=%d peer_up=%d err=%s ip=%s ssid=%s\n",
                          wgCfg_.wgEnable ? 1 : 0, wireGuard_.active() ? 1 : 0,
                          wireGuard_.peerUp() ? 1 : 0, wireGuard_.lastError(),
                          WiFi.localIP().toString().c_str(), WiFi.SSID().c_str());
        }
        labLine = "";
    }

    wireGuard_.loop();
    web_.handleClient();
    modules_.loopAll();
    unsigned long now = millis();
    ProgressWatch::note(ProgressWatch::Idle);
    web_.pushSseIfDue(now);

    if (now - lastHeartbeat_ >= heartbeatIntervalMs_) {
        lastHeartbeat_ = now;
        Checkpoint::enter(Checkpoint::Hub);
        bool nameChanged = false;
        if (hub_.sendHeartbeat(deviceName_, lastSuccess_, heartbeatIntervalMs_, otaPending_, otaUrl_,
                               &nameChanged)) {
            Checkpoint::leave(Checkpoint::Hub);
            PanicTail::breadcrumb(PanicTail::HubOk);
            ProgressWatch::note(ProgressWatch::Heartbeat);
        } else {
            Checkpoint::leave(Checkpoint::Hub);
        }
        web_.updateConfig(deviceName_, hubHost_, hubPort_, heartbeatIntervalMs_);
    }

    if (otaPending_) {
        otaPending_ = false;
        Checkpoint::enter(Checkpoint::Ota);
        ota_.scheduleUrl(otaUrl_);
        otaUrl_ = "";
        ota_.poll();  // blocking; success restarts via Recovery
        Checkpoint::leave(Checkpoint::Ota);
    }

    // Re-sample millis after heartbeat/OTA: lastSuccess_/ProgressWatch notes use
    // live millis(); comparing against a stale loop-start `now` underflows and
    // falsely trips WDT (~30s after boot, right after the first periodic HB).
    now = millis();
    ProgressWatch::evaluate(now);

#if WATCHDOG_TIMEOUT_S > 0
    // D-010 / M11: legacy WDT retained until ProgressWatch is field-proven.
    // While OTA is active, do not trip — download can exceed the heartbeat window.
    if (!ota_.active() &&
        now - lastSuccess_ > (unsigned long)WATCHDOG_TIMEOUT_S * 1000UL) {
        Serial.println("[WDT] Neustart");
        DiagLog::printf("[WDT] legacy fire age_s=%lu prog_hb_stalled=%d\n",
                        (unsigned long)((now - lastSuccess_) / 1000UL),
                        ProgressWatch::stalled(ProgressWatch::Heartbeat, now) ? 1 : 0);
        PanicTail::breadcrumb(PanicTail::WdtFire);
        Recovery::requestRestart(Recovery::LegacyWatchdog, "heartbeat_timeout");
    }
#endif

    net_.maintain();
    {
        const bool up = (WiFi.status() == WL_CONNECTED);
        if (up && !lastWifiUp_ && wgCfg_.wgEnable && wgCfg_.looksConfigured()) {
            wireGuard_.disable();
            wireGuard_.enable();
        }
        lastWifiUp_ = up;
    }
    CpuLoad::poll();
    delay(10);
}
