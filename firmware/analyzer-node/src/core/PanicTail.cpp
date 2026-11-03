/**
 * @file PanicTail.cpp
 * @brief RTC PanicTail storage and JSON/diag export.
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include "PanicTail.h"
#include "Checkpoint.h"
#include "DiagLog.h"
#include "Recovery.h"

#include <esp_attr.h>
#include <esp_system.h>
#include <cstdio>
#include <cstring>

namespace {

constexpr uint32_t kMagic = 0x48424553;  // 'HBES' layout v1
constexpr uint8_t kCapacity = 16;

struct Breadcrumb {
    uint32_t ms;
    uint32_t arg;
    uint8_t code;
    uint8_t reserved;
    uint16_t repeat;
};

struct Tail {
    uint32_t magic;
    uint32_t generation;
    uint8_t next;
    uint8_t count;
    uint8_t restartCause;
    uint8_t reserved;
    Breadcrumb crumbs[kCapacity];
};

RTC_NOINIT_ATTR Tail retained;
Tail previous;
bool gPreviousValid = false;
esp_reset_reason_t bootResetReason = ESP_RST_UNKNOWN;

const char* reasonName(esp_reset_reason_t reason) {
    switch (reason) {
        case ESP_RST_POWERON: return "power_on";
        case ESP_RST_EXT: return "external";
        case ESP_RST_SW: return "software";
        case ESP_RST_PANIC: return "panic";
        case ESP_RST_INT_WDT: return "interrupt_watchdog";
        case ESP_RST_TASK_WDT: return "task_watchdog";
        case ESP_RST_WDT: return "watchdog";
        case ESP_RST_DEEPSLEEP: return "deep_sleep";
        case ESP_RST_BROWNOUT: return "brownout";
        case ESP_RST_SDIO: return "sdio";
        default: return "unknown";
    }
}

const char* causeName(uint8_t cause) {
    switch (cause) {
        case PanicTail::RestartWifiPortalTimeout: return "wifi_portal_timeout";
        case PanicTail::RestartHubOta: return "hub_ota";
        case PanicTail::RestartWebOta: return "web_ota";
        case PanicTail::RestartWatchdog: return "watchdog";
        case PanicTail::RestartWifiReset: return "wifi_reset";
        default: return "none";
    }
}

const char* crumbName(uint8_t code) {
    switch (code) {
        case PanicTail::Boot: return "boot";
        case PanicTail::WifiUp: return "wifi_up";
        case PanicTail::HubOk: return "hub_ok";
        case PanicTail::WebUp: return "web_up";
        case PanicTail::OtaStart: return "ota_start";
        case PanicTail::WifiLost: return "wifi_lost";
        case PanicTail::WdtFire: return "wdt_fire";
        case PanicTail::RestartRequested: return "restart";
        case PanicTail::ResetButton: return "reset_button";
        default: return "other";
    }
}

void appendCrumbsJson(String& out, const Tail& tail) {
    out += "[";
    const uint8_t first = (tail.next + kCapacity - tail.count) % kCapacity;
    for (uint8_t i = 0; i < tail.count; ++i) {
        if (i) out += ",";
        const Breadcrumb& c = tail.crumbs[(first + i) % kCapacity];
        out += "{\"code\":";
        out += String(c.code);
        out += ",\"name\":\"";
        out += crumbName(c.code);
        out += "\",\"t_ms\":";
        out += String(c.ms);
        out += ",\"arg\":";
        out += String(c.arg);
        if (c.repeat) {
            out += ",\"repeat\":";
            out += String(c.repeat);
        }
        out += "}";
    }
    out += "]";
}

}  // namespace

void PanicTail::begin() {
    bootResetReason = esp_reset_reason();
    gPreviousValid = retained.magic == kMagic && retained.count <= kCapacity;
    if (gPreviousValid) {
        memcpy(&previous, &retained, sizeof(previous));
    }

    memset(&retained, 0, sizeof(retained));
    retained.magic = kMagic;
    retained.generation = gPreviousValid ? previous.generation + 1 : 1;
    breadcrumb(Boot, static_cast<uint32_t>(bootResetReason));
}

void PanicTail::breadcrumb(Code code, uint32_t arg) {
    if (retained.count > 0) {
        Breadcrumb& last = retained.crumbs[(retained.next + kCapacity - 1) % kCapacity];
        if (last.code == code && last.arg == arg) {
            if (last.repeat < 0xFFFF) last.repeat++;
            last.ms = millis();
            return;
        }
    }
    const uint8_t slot = retained.next % kCapacity;
    Breadcrumb& crumb = retained.crumbs[slot];
    crumb.ms = millis();
    crumb.arg = arg;
    crumb.code = static_cast<uint8_t>(code);
    crumb.repeat = 0;
    retained.next = (slot + 1) % kCapacity;
    if (retained.count < kCapacity) retained.count++;
    // Mirror new crumbs into DiagLog (folded repeats stay quiet).
    DiagLog::printf("[BC] %s arg=%lu\n", crumbName(code), (unsigned long)arg);
}

void PanicTail::noteRestart(RestartCause cause) {
    retained.restartCause = static_cast<uint8_t>(cause);
    breadcrumb(RestartRequested, cause);
    // Planned restart must not look like a hung open checkpoint.
    Checkpoint::clearOpenForPlannedRestart();
    DiagLog::persist("restart", true);
}

void PanicTail::requestRestart(RestartCause cause) {
    noteRestart(cause);
    delay(200);
    ESP.restart();
}

const char* PanicTail::resetReason() { return reasonName(bootResetReason); }

const char* PanicTail::restartCause() {
    return gPreviousValid ? causeName(previous.restartCause) : "none";
}

uint32_t PanicTail::bootGeneration() { return retained.generation; }

bool PanicTail::previousValid() { return gPreviousValid; }

void PanicTail::logToSerial() {
    Serial.printf("[BOOT] reason=%s gen=%u prev_cause=%s\n",
                  resetReason(), (unsigned)bootGeneration(), restartCause());
    if (!gPreviousValid || previous.count == 0) {
        Serial.println("[BOOT] panic_tail=(none)");
        return;
    }
    Serial.printf("[BOOT] panic_tail gen=%u crumbs=%u:\n",
                  (unsigned)previous.generation, (unsigned)previous.count);
    const uint8_t first = (previous.next + kCapacity - previous.count) % kCapacity;
    for (uint8_t i = 0; i < previous.count; ++i) {
        const Breadcrumb& c = previous.crumbs[(first + i) % kCapacity];
        if (c.repeat) {
            Serial.printf("  %lu %s arg=%lu x%u\n",
                          (unsigned long)c.ms, crumbName(c.code),
                          (unsigned long)c.arg, (unsigned)c.repeat);
        } else {
            Serial.printf("  %lu %s arg=%lu\n",
                          (unsigned long)c.ms, crumbName(c.code),
                          (unsigned long)c.arg);
        }
    }
}

void PanicTail::appendStatusFields(String& json) {
    json += ",\"resetReason\":\"";
    json += resetReason();
    json += "\",\"restartCause\":\"";
    json += restartCause();
    json += "\",\"bootGen\":";
    json += String(bootGeneration());
}

String PanicTail::buildDiagJson() {
    String j = "{";
    j += "\"resetReason\":\"";
    j += resetReason();
    j += "\",\"restartCause\":\"";
    j += restartCause();
    j += "\",\"bootGen\":";
    j += String(bootGeneration());
    j += ",\"uptimeMs\":";
    j += String((uint32_t)millis());
    j += ",\"panicNow\":{\"generation\":";
    j += String(retained.generation);
    j += ",\"count\":";
    j += String(retained.count);
    j += ",\"breadcrumbs\":";
    appendCrumbsJson(j, retained);
    j += "}";
    if (gPreviousValid) {
        j += ",\"panicTail\":{\"generation\":";
        j += String(previous.generation);
        j += ",\"count\":";
        j += String(previous.count);
        j += ",\"restartCause\":\"";
        j += causeName(previous.restartCause);
        j += "\",\"breadcrumbs\":";
        appendCrumbsJson(j, previous);
        j += "}";
    } else {
        j += ",\"panicTail\":null";
    }
    Checkpoint::appendDiagFields(j);
    Recovery::appendDiagFields(j);
    j += "}";
    return j;
}
