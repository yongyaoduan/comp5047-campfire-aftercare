#pragma once
#include <stdint.h>

class WaterLevelState {
 public:
  void update(const uint8_t *data, bool valid, uint32_t now) {
    if (!valid) { dryCount_ = wetCount_ = 0; return; }
    lastValid_ = now;
    valid_ = true;
    wetSections_ = levelSections_ = 0;
    bool contiguous = true;
    for (unsigned i = 0; i < 20; ++i) {
      const bool wet = data[i] > 100; // Seeed reference threshold
      if (wet) ++wetSections_;
      if (contiguous && wet) ++levelSections_;
      else contiguous = false;
    }
    // Isolated upper droplets do not establish a water level.
    if (levelSections_ == 0) {
      wetCount_ = 0;
      if (dryCount_ < 2) ++dryCount_;
      if (dryCount_ >= 2) { dry_ = true; settled_ = true; }
    } else {
      dryCount_ = 0;
      if (wetCount_ < 2) ++wetCount_;
      if (wetCount_ >= 2) { dry_ = false; settled_ = true; }
    }
  }
  bool settled() const { return settled_; }
  bool fresh(uint32_t now) const { return valid_ && uint32_t(now-lastValid_) < 1000; }
  bool dry(uint32_t now) const { return fresh(now) && settled_ && dry_; }
  unsigned levelMM() const { return levelSections_ * 5; }
  unsigned wetSections() const { return wetSections_; }
 private:
  uint32_t lastValid_ = 0;
  unsigned wetSections_ = 0, levelSections_ = 0;
  uint8_t dryCount_ = 0, wetCount_ = 0;
  bool valid_ = false, settled_ = false, dry_ = false;
};
