/**
 * @file Checkpoint.cpp
 * @brief RTC and NVS checkpoint gate implementation.
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include "Checkpoint.h"

#include <Preferences.h>
#include <esp_attr.h>
#include <esp_system.h>
#include <cstddef>
#include <cstdio>
#include <cstring>

namespace {

constexpr uint32_t kMagic = 0x434B5054;  // CKPT
constexpr uint8_t kStackCap = 4;
constexpr const char* kNvsNs = "ehckpt";

struct Frame {
    uint8_t phase;
    uint8_t reserved;
    uint16_t reserved2;
    uint32_t arg;
    uint32_t ms;
};

struct Gate {
    uint32_t magic;
    uint32_t generation;
    uint8_t depth;
    uint8_t reserved[3];
    Frame stack[kStackCap];
    uint8_t crashPhase;
    uint8_t crashDepth;
    uint16_t reserved3;
    uint32_t crashArg;
    uint32_t crashMs;
    uint8_t lastLeavePhase;
    uint8_t lastFailPhase;
    uint16_t reserved4;
    uint32_t lastLeaveMs;
    uint32_t lastLeaveArg;
    uint32_t lastFailMs;
    uint32_t lastFailArg;
    uint32_t crc;
};

RTC_NOINIT_ATTR Gate retained;

Gate previousCrash;
bool previousCrashValid = false;

uint32_t crc32Bytes(const uint8_t* data, size_t n) {
    uint32_t c = 0xFFFFFFFFUL;
    for (size_t i = 0; i < n; i++) {
        c ^= data[i];
        for (int b = 0; b < 8; b++) {
            c = (c & 1) ? (0xEDB88320UL ^ (c >> 1)) : (c >> 1);
        }
    }
    return ~c;
}

uint32_t gateCrc(const Gate& g) {
    return crc32Bytes(reinterpret_cast<const uint8_t*>(&g), offsetof(Gate, crc));
}

bool rtcValid() {
    return retained.magic == kMagic && retained.depth <= kStackCap &&
           retained.crc == gateCrc(retained);
}

void rtcCommit() {
    retained.magic = kMagic;
    retained.crc = gateCrc(retained);
}

bool isPowerLikeReset() {
    const esp_reset_reason_t r = esp_reset_reason();
    return r == ESP_RST_POWERON || r == ESP_RST_BROWNOUT || r == ESP_RST_EXT;
}

bool nvsWriteOpen() {
    Preferences prefs;
    if (!prefs.begin(kNvsNs, false)) return false;
    if (retained.depth == 0) {
        prefs.putUChar("valid", 0);
        prefs.putUChar("sticky", 0);
    } else {
        const Frame& top = retained.stack[retained.depth - 1];
        prefs.putUChar("valid", 1);
        prefs.putUChar("phase", top.phase);
        prefs.putUInt("arg", top.arg);
        prefs.putUInt("ms", top.ms);
        prefs.putUChar("depth", retained.depth);
        prefs.putUChar("sticky", 1);
        prefs.putUChar("s_phase", top.phase);
        prefs.putUInt("s_arg", top.arg);
        prefs.putUInt("s_ms", top.ms);
        prefs.putUChar("s_depth", retained.depth);
    }
    prefs.end();
    return true;
}

void nvsClearOpen() {
    Preferences prefs;
    if (!prefs.begin(kNvsNs, false)) return;
    prefs.putUChar("valid", 0);
    prefs.putUChar("sticky", 0);
    prefs.end();
}

bool nvsLoadCrash(uint8_t* phase, uint32_t* arg, uint32_t* ms, uint8_t* depth,
                  const char** via) {
    Preferences prefs;
    if (!prefs.begin(kNvsNs, true)) return false;
    bool ok = prefs.getUChar("valid", 0) == 1;
    if (ok) {
        *phase = prefs.getUChar("phase", 0);
        *arg = prefs.getUInt("arg", 0);
        *ms = prefs.getUInt("ms", 0);
        *depth = prefs.getUChar("depth", 1);
        *via = "nvs";
    } else if (prefs.getUChar("sticky", 0) == 1) {
        *phase = prefs.getUChar("s_phase", 0);
        *arg = prefs.getUInt("s_arg", 0);
        *ms = prefs.getUInt("s_ms", 0);
        *depth = prefs.getUChar("s_depth", 1);
        ok = (*phase != 0);
        *via = "nvs_sticky";
    }
    prefs.end();
    return ok && *phase != 0;
}

void latchCrash(uint8_t phase, uint32_t arg, uint32_t ms, uint8_t depth, const char* source) {
    retained.crashPhase = phase;
    retained.crashArg = arg;
    retained.crashMs = ms;
    retained.crashDepth = depth;
    previousCrash = retained;
    previousCrashValid = true;
    Serial.printf("[CKPT] last_open=%s arg=%u depth=%u t_ms=%u via=%s\n",
                  Checkpoint::name(static_cast<Checkpoint::Phase>(phase)),
                  (unsigned)arg, (unsigned)depth, (unsigned)ms,
                  source ? source : "?");
    nvsClearOpen();
}

void ensureRtc() {
    if (!rtcValid()) {
        memset(&retained, 0, sizeof(retained));
        retained.magic = kMagic;
        retained.generation = 1;
        rtcCommit();
    }
}

}  // namespace

const char* Checkpoint::name(Phase phase) {
    switch (phase) {
        case Wifi: return "wifi";
        case Web: return "web";
        case Hub: return "hub";
        case Ota: return "ota";
        case None:
        default: return "none";
    }
}

void Checkpoint::begin() {
    previousCrashValid = false;
    memset(&previousCrash, 0, sizeof(previousCrash));

    const bool powerLike = isPowerLikeReset();
    const bool rtcOk = rtcValid();
    const char* nvsVia = nullptr;
    uint8_t nvsPh = 0, nvsDepth = 0;
    uint32_t nvsArg = 0, nvsMs = 0;
    const bool nvsOk = nvsLoadCrash(&nvsPh, &nvsArg, &nvsMs, &nvsDepth, &nvsVia);

    if (powerLike && nvsOk) {
        latchCrash(nvsPh, nvsArg, nvsMs, nvsDepth, nvsVia);
    } else if (!powerLike && rtcOk && retained.depth > 0) {
        const Frame& top = retained.stack[retained.depth - 1];
        latchCrash(top.phase, top.arg, top.ms, retained.depth, "rtc");
    } else if (nvsOk) {
        latchCrash(nvsPh, nvsArg, nvsMs, nvsDepth, nvsVia ? nvsVia : "nvs");
    } else if (!rtcOk) {
        memset(&retained, 0, sizeof(retained));
    }

    retained.generation = rtcOk ? retained.generation + 1 : 1;
    retained.depth = 0;
    memset(retained.stack, 0, sizeof(retained.stack));
    if (!previousCrashValid) {
        retained.crashPhase = None;
        retained.crashDepth = 0;
        retained.crashArg = 0;
        retained.crashMs = 0;
    }
    retained.lastLeavePhase = None;
    retained.lastFailPhase = None;
    retained.lastLeaveArg = 0;
    retained.lastLeaveMs = 0;
    retained.lastFailArg = 0;
    retained.lastFailMs = 0;
    rtcCommit();

    Serial.printf("[CKPT] begin crash=%s gen=%u\n",
                  previousCrashValid
                      ? name(static_cast<Phase>(previousCrash.crashPhase))
                      : "none",
                  (unsigned)retained.generation);
}

void Checkpoint::enter(Phase phase, uint32_t arg) {
    if (phase == None) return;
    ensureRtc();
    if (retained.depth >= kStackCap) {
        memmove(&retained.stack[0], &retained.stack[1], sizeof(Frame) * (kStackCap - 1));
        retained.depth = kStackCap - 1;
    }
    Frame& f = retained.stack[retained.depth++];
    f.phase = static_cast<uint8_t>(phase);
    f.arg = arg;
    f.ms = millis();
    rtcCommit();
    nvsWriteOpen();
    Serial.printf("[CKPT] ENTER %s arg=%u depth=%u\n", name(phase), (unsigned)arg,
                  (unsigned)retained.depth);
}

void Checkpoint::leave(Phase phase) {
    if (phase == None || !rtcValid() || retained.depth == 0) return;
    Frame& top = retained.stack[retained.depth - 1];
    if (top.phase != static_cast<uint8_t>(phase)) {
        Serial.printf("[CKPT] LEAVE mismatch want=%s top=%s\n", name(phase),
                      name(static_cast<Phase>(top.phase)));
        return;
    }
    retained.lastLeavePhase = top.phase;
    retained.lastLeaveArg = top.arg;
    retained.lastLeaveMs = millis();
    retained.depth--;
    rtcCommit();
    nvsWriteOpen();
    Serial.printf("[CKPT] LEAVE %s arg=%u depth=%u\n", name(phase), (unsigned)top.arg,
                  (unsigned)retained.depth);
}

void Checkpoint::fail(Phase phase, uint32_t arg) {
    if (phase == None) return;
    ensureRtc();
    uint32_t ms = millis();
    uint8_t depth = retained.depth;
    if (retained.depth > 0 &&
        retained.stack[retained.depth - 1].phase == static_cast<uint8_t>(phase)) {
        arg = retained.stack[retained.depth - 1].arg;
        ms = retained.stack[retained.depth - 1].ms;
        retained.depth--;
    }
    retained.lastFailPhase = static_cast<uint8_t>(phase);
    retained.lastFailArg = arg;
    retained.lastFailMs = millis();
    latchCrash(static_cast<uint8_t>(phase), arg, ms, depth ? depth : 1, "fail");
    rtcCommit();
    Serial.printf("[CKPT] FAIL %s arg=%u\n", name(phase), (unsigned)arg);
}

void Checkpoint::clearOpenForPlannedRestart() {
    if (!rtcValid()) {
        nvsClearOpen();
        return;
    }
    retained.depth = 0;
    memset(retained.stack, 0, sizeof(retained.stack));
    rtcCommit();
    nvsClearOpen();
}

Checkpoint::Phase Checkpoint::lastCrashPhase() {
    if (previousCrashValid) return static_cast<Phase>(previousCrash.crashPhase);
    if (rtcValid() && retained.crashPhase != None)
        return static_cast<Phase>(retained.crashPhase);
    return None;
}

uint32_t Checkpoint::lastCrashArg() {
    if (previousCrashValid) return previousCrash.crashArg;
    if (rtcValid()) return retained.crashArg;
    return 0;
}

bool Checkpoint::hasLastCrash() { return lastCrashPhase() != None; }

void Checkpoint::logToSerial() {
    if (!hasLastCrash()) {
        Serial.println("[CKPT] last_open=(none)");
        return;
    }
    Serial.printf("[CKPT] last_open=%s arg=%u\n", name(lastCrashPhase()),
                  (unsigned)lastCrashArg());
}

void Checkpoint::appendStatusFields(String& json) {
    json += ",\"ckptOpen\":";
    if (rtcValid() && retained.depth > 0) {
        const Frame& top = retained.stack[retained.depth - 1];
        json += "{\"phase\":\"";
        json += name(static_cast<Phase>(top.phase));
        json += "\",\"arg\":";
        json += String(top.arg);
        json += "}";
    } else {
        json += "null";
    }
    json += ",\"ckptLastOpen\":";
    if (hasLastCrash()) {
        json += "{\"phase\":\"";
        json += name(lastCrashPhase());
        json += "\",\"arg\":";
        json += String(lastCrashArg());
        json += "}";
    } else {
        json += "null";
    }
}

void Checkpoint::appendDiagFields(String& json) {
    json += ",\"checkpoint\":{";
    json += "\"generation\":";
    json += String(rtcValid() ? retained.generation : 0);
    json += ",\"open\":[";
    if (rtcValid()) {
        for (uint8_t i = 0; i < retained.depth && i < kStackCap; i++) {
            if (i) json += ",";
            json += "{\"phase\":\"";
            json += name(static_cast<Phase>(retained.stack[i].phase));
            json += "\",\"arg\":";
            json += String(retained.stack[i].arg);
            json += ",\"t_ms\":";
            json += String(retained.stack[i].ms);
            json += "}";
        }
    }
    json += "],\"lastOpen\":";
    if (hasLastCrash()) {
        json += "{\"phase\":\"";
        json += name(lastCrashPhase());
        json += "\",\"arg\":";
        json += String(lastCrashArg());
        if (previousCrashValid) {
            json += ",\"t_ms\":";
            json += String(previousCrash.crashMs);
            json += ",\"depth\":";
            json += String(previousCrash.crashDepth);
        }
        json += "}";
    } else {
        json += "null";
    }
    if (rtcValid() && retained.lastLeavePhase != None) {
        json += ",\"lastLeave\":{\"phase\":\"";
        json += name(static_cast<Phase>(retained.lastLeavePhase));
        json += "\",\"arg\":";
        json += String(retained.lastLeaveArg);
        json += ",\"t_ms\":";
        json += String(retained.lastLeaveMs);
        json += "}";
    }
    if (rtcValid() && retained.lastFailPhase != None) {
        json += ",\"lastFail\":{\"phase\":\"";
        json += name(static_cast<Phase>(retained.lastFailPhase));
        json += "\",\"arg\":";
        json += String(retained.lastFailArg);
        json += ",\"t_ms\":";
        json += String(retained.lastFailMs);
        json += "}";
    }
    json += "}";
}
