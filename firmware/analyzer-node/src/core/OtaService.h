#pragma once

/**
 * @file OtaService.h
 * @brief OTA operation with explicit lifecycle state and progress (D-015).
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include <Arduino.h>

/**
 * @brief Hub-URL and web-upload OTA with observable states.
 *
 * Hub download remains sequential (HTTP stream) but reports state/progress and
 * feeds ProgressWatch. Legacy WDT must not fire while active() is true.
 */
class OtaService {
public:
    enum State : uint8_t {
        Idle = 0,
        Scheduled = 1,
        Fetching = 2,
        Writing = 3,
        Success = 4,
        Failed = 5,
    };

    /** @brief Optional yield callback (e.g. webServer.handleClient) during download. */
    using YieldFn = void (*)();

    void setYield(YieldFn fn) { yieldFn_ = fn; }

    /**
     * @brief Queue a Hub firmware URL for the next poll()/perform cycle.
     * @param url  HTTP URL of the .bin.
     */
    void scheduleUrl(const String& url);

    /**
     * @brief Run a scheduled Hub OTA if pending (blocking stream with progress).
     * @return true if an OTA attempt was executed.
     */
    bool poll();

    /** @brief True while an OTA operation is in progress (skip legacy WDT). */
    bool active() const;

    State state() const { return state_; }
    int progressPercent() const { return progressPct_; }
    uint32_t bytesDone() const { return bytesDone_; }
    uint32_t bytesTotal() const { return bytesTotal_; }
    const char* lastError() const { return lastError_; }
    static const char* stateName(State state);

    /** @brief Web-upload lifecycle hooks. */
    void webBegin(const char* filename);
    void webWrite(uint8_t* data, size_t len);
    void webFinish(bool ok);

    /** @brief Additive status: otaState, otaProgress, otaError. */
    void appendStatusFields(String& json) const;

private:
    void setState(State s);
    void setError(const char* err);
    void performFromUrl(const String& url);

    State state_ = Idle;
    String pendingUrl_;
    int progressPct_ = 0;
    uint32_t bytesDone_ = 0;
    uint32_t bytesTotal_ = 0;
    char lastError_[48] = {0};
    YieldFn yieldFn_ = nullptr;
    unsigned long lastYieldMs_ = 0;
};
