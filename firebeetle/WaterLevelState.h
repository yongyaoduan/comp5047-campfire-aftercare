#pragma once
#include <stdint.h>

class WaterLevelState {
 public:
  static constexpr unsigned LOW_SECTIONS = 2;   // fewer than 2 wet sections (10 mm) = tank low
  static constexpr unsigned FULL_SECTIONS = 15;
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
    // Isolated upper droplets do not establish a water level; below 2 sections the
    // pump intake is close to air, so treat it as low.
    // Full: 15 of 20 sections (75 mm) wet twice in a row, leaving headroom below the
    // top of the sensor; cleared once the level drops below 13 sections (65 mm).
    if (levelSections_ >= FULL_SECTIONS) { if (fullCount_ < 2) ++fullCount_; if (fullCount_ >= 2) full_ = true; }
    else { fullCount_ = 0; if (levelSections_ < FULL_SECTIONS - 2) full_ = false; }
    // The Grove sensor calibrates itself at power-up; powered up in water it then
    // reports every pad as 0 although I2C works (found on 5 Nov; also reported on
    // Seeed's forum). Real water cannot fall from 15 mm or more to nothing in one
    // reading (the pump drains about 1.5 mm/s), so a sudden all-dry reading marks
    // the sensor as faulty: no water request and no spray until real readings return.
    // An all-zero reading at start-up cannot be told apart from an empty tank, so the
    // station must be powered with the sensor dry (user manual).
    if (levelSections_ > 0) { lastLevel_ = levelSections_; suspect_ = false; }
    else if (lastLevel_ >= 3) suspect_ = true;
    if (suspect_) { dryCount_ = 0; return; }
    if (levelSections_ < LOW_SECTIONS) {
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
  bool full(uint32_t now) const { return fresh(now) && full_; }
  bool suspect() const { return suspect_; }
  unsigned levelMM() const { return levelSections_ * 5; }
  unsigned wetSections() const { return wetSections_; }
 private:
  uint32_t lastValid_ = 0;
  unsigned lastLevel_ = 0;
  bool suspect_ = false;
  unsigned wetSections_ = 0, levelSections_ = 0;
  uint8_t dryCount_ = 0, wetCount_ = 0, fullCount_ = 0;
  bool valid_ = false, settled_ = false, dry_ = false, full_ = false;
};
