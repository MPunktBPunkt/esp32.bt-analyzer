#pragma once

#include "capture/CaptureFrame.h"

#include <Arduino.h>

namespace bt_analyzer {

/**
 * SPSC-ish capture ring. Enqueue from USB callback (copy payload immediately).
 * Drain from AppCore loop / HTTP handlers.
 *
 * Backing store prefers PSRAM when available; falls back to internal heap.
 */
class CaptureRing {
public:
  bool begin(size_t capacity = 512);
  void clear();

  /** Copy frame into ring. Returns false on overflow (drop counted). */
  bool enqueue(const CaptureFrame &frame);

  bool dequeue(CaptureFrame &out);
  size_t size() const;
  size_t capacity() const { return capacity_; }
  bool inPsram() const { return in_psram_; }

  uint32_t captured() const { return captured_; }
  uint32_t dropped() const { return dropped_; }
  uint32_t dequeued() const { return dequeued_; }
  uint32_t highWater() const { return high_water_; }
  uint32_t nextSeq() { return ++seq_; }

  void appendStatusJson(String &json) const;

private:
  CaptureFrame *slots_ = nullptr;
  size_t capacity_ = 0;
  volatile size_t head_ = 0;  // write
  volatile size_t tail_ = 0;  // read
  bool in_psram_ = false;
  uint32_t seq_ = 0;
  uint32_t captured_ = 0;
  uint32_t dropped_ = 0;
  uint32_t dequeued_ = 0;
  uint32_t high_water_ = 0;
};

}  // namespace bt_analyzer
