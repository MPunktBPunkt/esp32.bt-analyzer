/**
 * @file Recovery.cpp
 * @brief RTC recovery history and restart orchestration.
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include "Recovery.h"
#include "DiagLog.h"
#include "PanicTail.h"

#include <esp_attr.h>
#include <cstring>

namespace {

constexpr uint32_t kMagic = 0x45524356;  // ERCV
constexpr uint8_t kHistCap = 6;

struct Event {
    uint8_t reason;
    uint8_t level;
    uint16_t reserved;
    uint32_t bootGen;
    uint32_t uptimeMs;
};

struct Store {
    uint32_t magic;
    uint8_t next;
    uint8_t count;
    uint8_t hardCount;
    uint8_t reserved;
    Event events[kHistCap];
};

RTC_NOINIT_ATTR Store retained;
bool begun = false;

bool storeValid() {
    return retained.magic == kMagic && retained.count <= kHistCap && retained.next < kHistCap;
}

void ensureStore() {
    if (storeValid()) return;
    memset(&retained, 0, sizeof(retained));
    retained.magic = kMagic;
}

PanicTail::RestartCause toPanicCause(Recovery::Reason reason) {
    switch (reason) {
        case Recovery::WifiPortalTimeout: return PanicTail::RestartWifiPortalTimeout;
        case Recovery::HubOta: return PanicTail::RestartHubOta;
        case Recovery::WebOta: return PanicTail::RestartWebOta;
        case Recovery::LegacyWatchdog: return PanicTail::RestartWatchdog;
        case Recovery::WifiReset: return PanicTail::RestartWifiReset;
        default: return PanicTail::RestartNone;
    }
}

void pushEvent(Recovery::Reason reason, Recovery::Level level) {
    ensureStore();
    Event& e = retained.events[retained.next];
    e.reason = static_cast<uint8_t>(reason);
    e.level = static_cast<uint8_t>(level);
    e.bootGen = PanicTail::bootGeneration();
    e.uptimeMs = millis();
    retained.next = (uint8_t)((retained.next + 1) % kHistCap);
    if (retained.count < kHistCap) retained.count++;
    if (level == Recovery::Hard && retained.hardCount < 0xFF) retained.hardCount++;
}

void appendHistoryJson(String& j) {
    j += "[";
    if (!storeValid() || retained.count == 0) {
        j += "]";
        return;
    }
    const uint8_t first = (uint8_t)((retained.next + kHistCap - retained.count) % kHistCap);
    for (uint8_t i = 0; i < retained.count; i++) {
        if (i) j += ",";
        const Event& e = retained.events[(first + i) % kHistCap];
        j += "{\"reason\":\"";
        j += Recovery::reasonName(static_cast<Recovery::Reason>(e.reason));
        j += "\",\"level\":\"";
        j += Recovery::levelName(static_cast<Recovery::Level>(e.level));
        j += "\",\"bootGen\":";
        j += String(e.bootGen);
        j += ",\"uptimeMs\":";
        j += String(e.uptimeMs);
        j += "}";
    }
    j += "]";
}

}  // namespace

const char* Recovery::reasonName(Reason reason) {
    switch (reason) {
        case WifiPortalTimeout: return "wifi_portal_timeout";
        case HubOta: return "hub_ota";
        case WebOta: return "web_ota";
        case LegacyWatchdog: return "legacy_watchdog";
        case WifiReset: return "wifi_reset";
        default: return "none";
    }
}

Recovery::Level Recovery::levelFor(Reason reason) {
    switch (reason) {
        case HubOta:
        case WebOta:
        case WifiReset:
            return Soft;
        case WifiPortalTimeout:
            return Degraded;
        case LegacyWatchdog:
            return Hard;
        default:
            return Soft;
    }
}

const char* Recovery::levelName(Level level) {
    switch (level) {
        case Soft: return "soft";
        case Degraded: return "degraded";
        case Hard: return "hard";
        default: return "soft";
    }
}

void Recovery::begin() {
    ensureStore();
    begun = true;

    const char* prev = PanicTail::restartCause();
    DiagLog::printf("[RECOVERY] begin prev_cause=%s hard_count=%u hist=%u\n",
                    prev, (unsigned)retained.hardCount, (unsigned)retained.count);
    if (retained.hardCount >= 3) {
        DiagLog::printf("[RECOVERY] escalation: hard_count=%u (repeated hard recoveries)\n",
                        (unsigned)retained.hardCount);
    }
}

void Recovery::requestRestart(Reason reason, const char* detail) {
    const Level level = levelFor(reason);
    if (!begun) ensureStore();

    pushEvent(reason, level);
    DiagLog::printf("[RECOVERY] restart reason=%s level=%s hard_count=%u%s%s\n",
                    reasonName(reason), levelName(level), (unsigned)retained.hardCount,
                    detail ? " detail=" : "", detail ? detail : "");
    DiagLog::persist("recovery", true);

    PanicTail::requestRestart(toPanicCause(reason));
}

uint8_t Recovery::hardCount() {
    return storeValid() ? retained.hardCount : 0;
}

uint8_t Recovery::historyCount() {
    return storeValid() ? retained.count : 0;
}

void Recovery::appendStatusFields(String& json) {
    json += ",\"recoveryHard\":";
    json += String(hardCount());
    json += ",\"recoveryHist\":";
    json += String(historyCount());
    if (storeValid() && retained.count > 0) {
        const uint8_t lastIdx = (uint8_t)((retained.next + kHistCap - 1) % kHistCap);
        const Event& e = retained.events[lastIdx];
        json += ",\"recoveryLast\":\"";
        json += reasonName(static_cast<Reason>(e.reason));
        json += "\"";
    } else {
        json += ",\"recoveryLast\":null";
    }
}

void Recovery::appendDiagFields(String& json) {
    json += ",\"recovery\":";
    json += buildDiagJson();
}

String Recovery::buildDiagJson() {
    String j = "{";
    j += "\"hardCount\":";
    j += String(hardCount());
    j += ",\"historyCount\":";
    j += String(historyCount());
    j += ",\"prevCause\":\"";
    j += PanicTail::restartCause();
    j += "\",\"history\":";
    appendHistoryJson(j);
    j += "}";
    return j;
}
