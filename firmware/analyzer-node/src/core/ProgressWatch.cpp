/**
 * @file ProgressWatch.cpp
 * @brief ProgressWatch channel timestamps and parallel stall logging.
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include "ProgressWatch.h"
#include "DiagLog.h"

namespace {

unsigned long lastMs[ProgressWatch::ChannelCount] = {0, 0, 0};
bool reportedStall[ProgressWatch::ChannelCount] = {false, false, false};
bool otaArmed = false;
bool begun = false;

unsigned long timeoutMs() {
#if PROGRESS_TIMEOUT_S > 0
    return (unsigned long)PROGRESS_TIMEOUT_S * 1000UL;
#else
    return 0;
#endif
}

}  // namespace

const char* ProgressWatch::name(Channel channel) {
    switch (channel) {
        case Idle: return "idle";
        case Heartbeat: return "heartbeat";
        case Ota: return "ota";
        default: return "other";
    }
}

void ProgressWatch::begin() {
    const unsigned long now = millis();
    for (uint8_t i = 0; i < ChannelCount; i++) {
        lastMs[i] = now;
        reportedStall[i] = false;
    }
    otaArmed = false;
    begun = true;
    DiagLog::printf("[PROG] begin timeout_s=%d (parallel to legacy WDT)\n",
                    (int)PROGRESS_TIMEOUT_S);
}

void ProgressWatch::note(Channel channel) {
    if (!begun || channel >= ChannelCount) return;
    lastMs[channel] = millis();
    if (channel == Ota) otaArmed = true;
    if (reportedStall[channel]) {
        DiagLog::printf("[PROG] resume %s\n", name(channel));
        reportedStall[channel] = false;
    }
}

bool ProgressWatch::stalled(Channel channel, unsigned long nowMs) {
    const unsigned long lim = timeoutMs();
    if (!begun || lim == 0 || channel >= ChannelCount) return false;
    if (channel == Ota && !otaArmed) return false;
    return (nowMs - lastMs[channel]) > lim;
}

void ProgressWatch::evaluate(unsigned long nowMs) {
    const unsigned long lim = timeoutMs();
    if (!begun || lim == 0) return;

    for (uint8_t i = 0; i < ChannelCount; i++) {
        const Channel ch = static_cast<Channel>(i);
        if (ch == Ota && !otaArmed) continue;
        const bool isStalled = (nowMs - lastMs[i]) > lim;
        if (isStalled && !reportedStall[i]) {
            reportedStall[i] = true;
            DiagLog::printf("[PROG] STALL %s age_s=%lu (legacy WDT still armed)\n",
                            name(ch), (unsigned long)((nowMs - lastMs[i]) / 1000UL));
        }
    }
}

void ProgressWatch::appendStatusFields(String& json) {
    const unsigned long now = millis();
    json += ",\"progIdleAge\":";
    json += String((now - lastMs[Idle]) / 1000UL);
    json += ",\"progHbAge\":";
    json += String((now - lastMs[Heartbeat]) / 1000UL);
    json += ",\"progOtaAge\":";
    json += otaArmed ? String((now - lastMs[Ota]) / 1000UL) : String("null");
    json += ",\"progStalled\":{";
    json += "\"idle\":";
    json += stalled(Idle, now) ? "true" : "false";
    json += ",\"heartbeat\":";
    json += stalled(Heartbeat, now) ? "true" : "false";
    json += ",\"ota\":";
    json += stalled(Ota, now) ? "true" : "false";
    json += "}";
}
