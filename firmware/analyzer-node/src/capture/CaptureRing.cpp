#include "capture/CaptureRing.h"

#include <esp_heap_caps.h>
#include <string.h>

namespace bt_analyzer {

bool CaptureRing::begin(size_t capacity) {
  if (slots_) {
    return true;
  }
  if (capacity < 8) {
    capacity = 8;
  }
  capacity_ = capacity;
  const size_t bytes = capacity_ * sizeof(CaptureFrame);
  slots_ = static_cast<CaptureFrame *>(
      heap_caps_malloc(bytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  if (slots_) {
    in_psram_ = true;
  } else {
    slots_ = static_cast<CaptureFrame *>(
        heap_caps_malloc(bytes, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT));
    in_psram_ = false;
  }
  if (!slots_) {
    capacity_ = 0;
    Serial.println("[capture] ring alloc FAILED");
    return false;
  }
  memset(slots_, 0, bytes);
  head_ = tail_ = 0;
  Serial.printf("[capture] ring capacity=%u frame=%uB total=%uB psram=%d\n",
                static_cast<unsigned>(capacity_),
                static_cast<unsigned>(sizeof(CaptureFrame)),
                static_cast<unsigned>(bytes), in_psram_ ? 1 : 0);
  return true;
}

void CaptureRing::clear() {
  head_ = tail_ = 0;
  high_water_ = 0;
}

bool CaptureRing::enqueue(const CaptureFrame &frame) {
  if (!slots_ || capacity_ == 0) {
    dropped_++;
    return false;
  }
  const size_t next = (head_ + 1) % capacity_;
  if (next == tail_) {
    dropped_++;
    return false;
  }
  slots_[head_] = frame;
  head_ = next;
  captured_++;
  const size_t fill = size();
  if (fill > high_water_) {
    high_water_ = static_cast<uint32_t>(fill);
  }
  return true;
}

bool CaptureRing::dequeue(CaptureFrame &out) {
  if (!slots_ || head_ == tail_) {
    return false;
  }
  out = slots_[tail_];
  tail_ = (tail_ + 1) % capacity_;
  dequeued_++;
  return true;
}

size_t CaptureRing::size() const {
  if (!capacity_) {
    return 0;
  }
  if (head_ >= tail_) {
    return head_ - tail_;
  }
  return capacity_ - tail_ + head_;
}

void CaptureRing::appendStatusJson(String &json) const {
  json += ",\"capture\":{";
  json += "\"capacity\":";
  json += String(static_cast<unsigned>(capacity_));
  json += ",\"fill\":";
  json += String(static_cast<unsigned>(size()));
  json += ",\"highWater\":";
  json += String(high_water_);
  json += ",\"captured\":";
  json += String(captured_);
  json += ",\"dequeued\":";
  json += String(dequeued_);
  json += ",\"dropped\":";
  json += String(dropped_);
  json += ",\"psram\":";
  json += in_psram_ ? "true" : "false";
  json += ",\"fillPct\":";
  json += String(capacity_ ? static_cast<unsigned>((100u * size()) / capacity_) : 0u);
  json += ",\"frameBytes\":";
  json += String(static_cast<unsigned>(sizeof(CaptureFrame)));
  json += ",\"nextSeq\":";
  json += String(seq_);
  json += "}";
}

}  // namespace bt_analyzer
