/**
 * @file DiagLog.cpp
 * @brief RAM/RTC rings and NVS snapshot slots for DiagLog.
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include "DiagLog.h"
#include "EspHubConfig.h"
#include "PanicTail.h"
#include "Checkpoint.h"

#include <Preferences.h>
#include <esp_attr.h>
#include <cstdarg>
#include <cstdio>
#include <cstring>

namespace {

constexpr uint32_t kRtcMagic = 0x45484C47;  // EHLG
constexpr size_t kRtcBytes = 1024;
constexpr size_t kRamBytes = 4096;
constexpr size_t kLineMax = 160;
constexpr uint8_t kSlots = 2;
constexpr size_t kSnapMax = 1500;
constexpr unsigned long kPersistMinMs = 10000;
constexpr const char* kNvsNs = "ehlog";

struct RtcRing {
    uint32_t magic;
    uint16_t head;
    uint16_t len;
    char data[kRtcBytes];
};

RTC_NOINIT_ATTR RtcRing rtc;

char prevTail[kRtcBytes + 1] = {0};
char* ram = nullptr;
size_t ramHead = 0;
size_t ramLen = 0;
unsigned long lastPersistMs = 0;

void rtcPut(const char* s, size_t n) {
    for (size_t i = 0; i < n; i++) {
        rtc.data[rtc.head] = s[i];
        rtc.head = (uint16_t)((rtc.head + 1) % kRtcBytes);
        if (rtc.len < kRtcBytes) rtc.len++;
    }
}

void ramPut(const char* s, size_t n) {
    if (!ram) return;
    for (size_t i = 0; i < n; i++) {
        ram[ramHead] = s[i];
        ramHead = (ramHead + 1) % kRamBytes;
        if (ramLen < kRamBytes) ramLen++;
    }
}

void rescuePrevTail() {
    prevTail[0] = 0;
    if (rtc.magic != kRtcMagic || rtc.len == 0 || rtc.len > kRtcBytes) return;
    const uint16_t start = (uint16_t)((rtc.head + kRtcBytes - rtc.len) % kRtcBytes);
    for (uint16_t i = 0; i < rtc.len; i++) {
        prevTail[i] = rtc.data[(start + i) % kRtcBytes];
    }
    prevTail[rtc.len] = 0;
    // Prefer starting at a line boundary when the ring wrapped.
    if (rtc.len == kRtcBytes) {
        char* nl = strchr(prevTail, '\n');
        if (nl && nl[1]) {
            memmove(prevTail, nl + 1, strlen(nl + 1) + 1);
        }
    }
}

String escapeJson(const char* s) {
    String out;
    if (!s) return out;
    out.reserve(strlen(s) + 8);
    for (const char* p = s; *p; ++p) {
        if (*p == '\\' || *p == '"') {
            out += '\\';
            out += *p;
        } else if (*p == '\n') {
            out += "\\n";
        } else if (*p == '\r') {
            out += "\\r";
        } else if ((uint8_t)*p < 0x20) {
            out += ' ';
        } else {
            out += *p;
        }
    }
    return out;
}

String copyRamText(size_t maxBytes) {
    if (!ram || ramLen == 0) return String();
    size_t n = ramLen;
    size_t off = 0;
    if (n > maxBytes) {
        off = n - maxBytes;
        n = maxBytes;
    }
    String out;
    out.reserve(n);
    char buf[256];
    while (n) {
        size_t chunk = n < sizeof(buf) ? n : sizeof(buf);
        size_t got = DiagLog::copyRam(off, buf, chunk);
        if (!got) break;
        out.concat(buf, got);
        off += got;
        n -= got;
    }
    return out;
}

}  // namespace

void DiagLog::begin() {
    rescuePrevTail();
    memset(&rtc, 0, sizeof(rtc));
    rtc.magic = kRtcMagic;

#if defined(BOARD_HAS_PSRAM)
    ram = static_cast<char*>(ps_malloc(kRamBytes));
#endif
    if (!ram) ram = static_cast<char*>(malloc(kRamBytes));
    ramHead = 0;
    ramLen = 0;
    if (ram) {
        memset(ram, 0, kRamBytes);
        printf("[DIAG] ram_ring=%u prev_tail=%u\n", (unsigned)kRamBytes,
               (unsigned)strlen(prevTail));
    } else {
        // Still log to Serial + RTC without RAM ring.
        Serial.println("[DIAG] ram_ring=0 (alloc fail)");
    }
}

void DiagLog::printf(const char* fmt, ...) {
    char line[kLineMax];
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(line, sizeof(line), fmt, ap);
    va_end(ap);
    if (n < 0) return;
    if ((size_t)n >= sizeof(line)) n = (int)sizeof(line) - 1;
    line[n] = 0;

    Serial.print(line);
    if (n == 0 || line[n - 1] != '\n') Serial.println();

    char stamped[kLineMax + 24];
    int m = snprintf(stamped, sizeof(stamped), "%lu %s", (unsigned long)millis(), line);
    if (m < 0) return;
    if ((size_t)m >= sizeof(stamped)) m = (int)sizeof(stamped) - 1;
    if (m > 0 && stamped[m - 1] != '\n') {
        if ((size_t)m + 1 < sizeof(stamped)) {
            stamped[m++] = '\n';
            stamped[m] = 0;
        }
    }
    rtcPut(stamped, (size_t)m);
    ramPut(stamped, (size_t)m);
}

const char* DiagLog::previousTail() { return prevTail; }

size_t DiagLog::ramSize() { return ramLen; }

size_t DiagLog::copyRam(size_t offset, char* dst, size_t n) {
    if (!ram || !dst || n == 0 || offset >= ramLen) return 0;
    size_t avail = ramLen - offset;
    if (n > avail) n = avail;
    const size_t start = (ramHead + kRamBytes - ramLen + offset) % kRamBytes;
    for (size_t i = 0; i < n; i++) {
        dst[i] = ram[(start + i) % kRamBytes];
    }
    return n;
}

bool DiagLog::persist(const char* reason, bool force) {
    const unsigned long now = millis();
    if (!force && lastPersistMs != 0 && (now - lastPersistMs) < kPersistMinMs) {
        return false;
    }

    String body;
    body.reserve(kSnapMax);
    body += "# diag ";
    body += reason ? reason : "?";
    body += " fw=";
    body += FW_VERSION;
    body += " reset=";
    body += PanicTail::resetReason();
    body += " cause=";
    body += PanicTail::restartCause();
    body += " gen=";
    body += String(PanicTail::bootGeneration());
    body += "\n";
    if (Checkpoint::hasLastCrash()) {
        body += "# ckpt_last=";
        body += Checkpoint::name(Checkpoint::lastCrashPhase());
        body += " arg=";
        body += String(Checkpoint::lastCrashArg());
        body += "\n";
    }
    if (prevTail[0]) {
        body += "# prev_tail\n";
        body += prevTail;
        if (body[body.length() - 1] != '\n') body += '\n';
    }
    body += "# ram_tail\n";
    body += copyRamText(512);
    if (body.length() > kSnapMax) body = body.substring(0, kSnapMax);

    Preferences prefs;
    if (!prefs.begin(kNvsNs, false)) return false;
    const uint8_t idx = prefs.getUChar("idx", 0) % kSlots;
    char key[8];
    snprintf(key, sizeof(key), "s%u", (unsigned)idx);
    prefs.putString(key, body);
    prefs.putUChar("idx", (uint8_t)((idx + 1) % kSlots));
    uint8_t count = prefs.getUChar("count", 0);
    if (count < kSlots) count++;
    prefs.putUChar("count", count);
    prefs.end();

    lastPersistMs = now;
    printf("[DIAG] persist reason=%s bytes=%u slot=%u\n", reason ? reason : "?",
           (unsigned)body.length(), (unsigned)idx);
    return true;
}

uint8_t DiagLog::snapshotCount() {
    Preferences prefs;
    if (!prefs.begin(kNvsNs, true)) return 0;
    const uint8_t c = prefs.getUChar("count", 0);
    prefs.end();
    return c > kSlots ? kSlots : c;
}

String DiagLog::loadSnapshot(uint8_t newestIndex) {
    Preferences prefs;
    if (!prefs.begin(kNvsNs, true)) return String();
    const uint8_t count = prefs.getUChar("count", 0);
    if (newestIndex >= count || newestIndex >= kSlots) {
        prefs.end();
        return String();
    }
    // idx points to next write slot; newest is (idx-1-newestIndex) mod kSlots
    const uint8_t next = prefs.getUChar("idx", 0) % kSlots;
    const uint8_t slot = (uint8_t)((next + kSlots - 1 - newestIndex) % kSlots);
    char key[8];
    snprintf(key, sizeof(key), "s%u", (unsigned)slot);
    String body = prefs.getString(key, "");
    prefs.end();
    return body;
}

String DiagLog::buildLogJson() {
    String ramText = copyRamText(1024);
    String j = "{";
    j += "\"ramBytes\":";
    j += String((uint32_t)ramLen);
    j += ",\"prevTailBytes\":";
    j += String((uint32_t)strlen(prevTail));
    j += ",\"snapshots\":";
    j += String(snapshotCount());
    j += ",\"prevTail\":\"";
    j += escapeJson(prevTail);
    j += "\",\"ram\":\"";
    j += escapeJson(ramText.c_str());
    j += "\",\"newestSnap\":\"";
    j += escapeJson(loadSnapshot(0).c_str());
    j += "\"}";
    return j;
}

void DiagLog::appendStatusFields(String& json) {
    json += ",\"diagRam\":";
    json += String((uint32_t)ramLen);
    json += ",\"diagPrev\":";
    json += String((uint32_t)strlen(prevTail));
    json += ",\"diagSnaps\":";
    json += String(snapshotCount());
}
