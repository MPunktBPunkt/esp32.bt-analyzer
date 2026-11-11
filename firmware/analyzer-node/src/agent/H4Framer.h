#pragma once

/**
 * H4 (UART HCI) packet framing — header-only, no Arduino, host-testable.
 * Packet = [type][header][payload]; lengths per Bluetooth Core Vol 4 Part A.
 */

#include <stddef.h>
#include <stdint.h>

namespace bt_analyzer {

enum : uint8_t {
  kH4Command = 0x01,
  kH4Acl = 0x02,
  kH4Sco = 0x03,
  kH4Event = 0x04,
  kH4Iso = 0x05,
};

/** Header length after the type byte; 0 = unknown type. */
inline size_t h4HeaderLen(uint8_t type) {
  switch (type) {
  case kH4Command: return 3;
  case kH4Acl: return 4;
  case kH4Sco: return 3;
  case kH4Event: return 2;
  case kH4Iso: return 4;
  default: return 0;
  }
}

/** Payload length from a complete header (hdr points after the type byte). */
inline size_t h4PayloadLen(uint8_t type, const uint8_t *hdr) {
  switch (type) {
  case kH4Command: return hdr[2];
  case kH4Acl: return static_cast<size_t>(hdr[2] | (hdr[3] << 8));
  case kH4Sco: return hdr[2];
  case kH4Event: return hdr[1];
  case kH4Iso: return static_cast<size_t>((hdr[2] | (hdr[3] << 8)) & 0x3fff);
  default: return 0;
  }
}

/** Byte-wise H4 reassembler with a fixed buffer of N bytes. */
template <size_t N>
class H4Framer {
public:
  enum class Result { NeedMore, Packet, Error };

  void reset() {
    len_ = 0;
    need_ = 1;
  }

  /** After Packet: data()/size() hold the full H4 packet until reset(). */
  Result push(uint8_t b) {
    if (len_ >= N) {
      return Result::Error;
    }
    buf_[len_++] = b;
    if (len_ < need_) {
      return Result::NeedMore;
    }
    if (len_ == 1) {
      const size_t h = h4HeaderLen(buf_[0]);
      if (h == 0) {
        return Result::Error;
      }
      need_ = 1 + h;
      return Result::NeedMore;
    }
    const size_t hdr_end = 1 + h4HeaderLen(buf_[0]);
    if (len_ == hdr_end) {
      need_ = hdr_end + h4PayloadLen(buf_[0], buf_ + 1);
      if (need_ > N) {
        return Result::Error;
      }
      if (len_ < need_) {
        return Result::NeedMore;
      }
    }
    return Result::Packet;
  }

  const uint8_t *data() const { return buf_; }
  size_t size() const { return len_; }

private:
  uint8_t buf_[N]{};
  size_t len_ = 0;
  size_t need_ = 1;
};

}  // namespace bt_analyzer
