/**
 * @file OtaService.cpp
 * @brief OTA lifecycle implementation for Hub URL and web upload.
 *
 * Base repository (keep when forking/copying):
 * https://github.com/MPunktBPunkt/ESP32.esp-hub
 */

#include "OtaService.h"
#include "DiagLog.h"
#include "PanicTail.h"
#include "ProgressWatch.h"
#include "Recovery.h"

#include <HTTPClient.h>
#include <Update.h>
#include <WiFi.h>
#include <cstring>

const char* OtaService::stateName(State state) {
    switch (state) {
        case Idle: return "idle";
        case Scheduled: return "scheduled";
        case Fetching: return "fetching";
        case Writing: return "writing";
        case Success: return "success";
        case Failed: return "failed";
        default: return "unknown";
    }
}

void OtaService::setState(State s) {
    state_ = s;
    DiagLog::printf("[OTA] state=%s progress=%d%%\n", stateName(s), progressPct_);
}

void OtaService::setError(const char* err) {
    strncpy(lastError_, err ? err : "error", sizeof(lastError_) - 1);
    lastError_[sizeof(lastError_) - 1] = 0;
    setState(Failed);
}

bool OtaService::active() const {
    return state_ == Scheduled || state_ == Fetching || state_ == Writing;
}

void OtaService::scheduleUrl(const String& url) {
    pendingUrl_ = url;
    progressPct_ = 0;
    bytesDone_ = 0;
    bytesTotal_ = 0;
    lastError_[0] = 0;
    setState(Scheduled);
}

bool OtaService::poll() {
    if (state_ != Scheduled || pendingUrl_.isEmpty()) return false;
    const String url = pendingUrl_;
    pendingUrl_ = "";
    performFromUrl(url);
    return true;
}

void OtaService::performFromUrl(const String& url) {
    PanicTail::breadcrumb(PanicTail::OtaStart);
    ProgressWatch::note(ProgressWatch::Ota);
    DiagLog::printf("[OTA] fetch %s\n", url.c_str());
    setState(Fetching);

    HTTPClient http;
    http.begin(url);
    http.setTimeout(30000);
    const int code = http.GET();
    if (code != 200) {
        http.end();
        setError("http_error");
        DiagLog::printf("[OTA] HTTP %d\n", code);
        return;
    }

    const int len = http.getSize();
    bytesTotal_ = len > 0 ? (uint32_t)len : 0;
    if (!Update.begin(len > 0 ? len : UPDATE_SIZE_UNKNOWN)) {
        http.end();
        setError("update_begin");
        Update.printError(Serial);
        return;
    }

    setState(Writing);
    WiFiClient* stream = http.getStreamPtr();
    uint8_t buf[512];
    size_t written = 0;
    lastYieldMs_ = millis();

    while (http.connected() && (len <= 0 || written < (size_t)len)) {
        ProgressWatch::note(ProgressWatch::Ota);
        if (yieldFn_ && (millis() - lastYieldMs_ >= 400UL)) {
            yieldFn_();
            lastYieldMs_ = millis();
        }
        size_t avail = stream->available();
        if (!avail) {
            delay(1);
            continue;
        }
        size_t rd = stream->readBytes(buf, min(avail, sizeof(buf)));
        if (!rd) break;
        if (Update.write(buf, rd) != rd) {
            http.end();
            setError("update_write");
            Update.printError(Serial);
            return;
        }
        written += rd;
        bytesDone_ = (uint32_t)written;
        if (bytesTotal_ > 0) {
            progressPct_ = (int)((written * 100UL) / bytesTotal_);
            if (progressPct_ > 100) progressPct_ = 100;
        }
        if (len > 0) Serial.printf("[OTA] %d/%d\r", (int)written, len);
    }
    Serial.println();

    if (Update.end(true)) {
        progressPct_ = 100;
        setState(Success);
        http.end();
        ProgressWatch::note(ProgressWatch::Ota);
        Recovery::requestRestart(Recovery::HubOta, "hub_url_ok");
    } else {
        http.end();
        setError("update_end");
        Update.printError(Serial);
    }
}

void OtaService::webBegin(const char* filename) {
    progressPct_ = 0;
    bytesDone_ = 0;
    bytesTotal_ = 0;
    lastError_[0] = 0;
    PanicTail::breadcrumb(PanicTail::OtaStart);
    ProgressWatch::note(ProgressWatch::Ota);
    DiagLog::printf("[OTA] web begin %s\n", filename ? filename : "?");
    setState(Writing);
    if (!Update.begin(UPDATE_SIZE_UNKNOWN)) {
        setError("update_begin");
        Update.printError(Serial);
    }
}

void OtaService::webWrite(uint8_t* data, size_t len) {
    if (state_ == Failed) return;
    ProgressWatch::note(ProgressWatch::Ota);
    if (Update.write(data, len) != len) {
        setError("update_write");
        Update.printError(Serial);
        return;
    }
    bytesDone_ += (uint32_t)len;
    // Unknown total for multipart — show growing KB as soft progress 0..95.
    progressPct_ = (int)min(95UL, bytesDone_ / 10240UL);
}

void OtaService::webFinish(bool ok) {
    if (!ok || Update.hasError()) {
        setError("web_upload");
        return;
    }
    if (!Update.end(true)) {
        setError("update_end");
        Update.printError(Serial);
        return;
    }
    progressPct_ = 100;
    setState(Success);
    ProgressWatch::note(ProgressWatch::Ota);
}

void OtaService::appendStatusFields(String& json) const {
    json += ",\"otaState\":\"";
    json += stateName(state_);
    json += "\",\"otaProgress\":";
    json += String(progressPct_);
    json += ",\"otaBytes\":";
    json += String(bytesDone_);
    json += ",\"otaTotal\":";
    json += String(bytesTotal_);
    json += ",\"otaActive\":";
    json += active() ? "true" : "false";
    if (lastError_[0]) {
        json += ",\"otaError\":\"";
        json += lastError_;
        json += "\"";
    } else {
        json += ",\"otaError\":null";
    }
}
