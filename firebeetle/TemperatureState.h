#pragma once
#include <stdint.h>
#include <math.h>

// Fire detection relative to the room.
//  - Calibration: the mean object reading over the first 10 s after power-up (no fire in
//    view) is taken as room temperature. If the readings in the window spread by more than
//    2 °C (something warm moved past), the window restarts.
//  - Fire: object >= room + 10 °C for 4 consecutive samples (about 1 s at 4 Hz).
//    Cleared once object < room + 7 °C for 4 consecutive samples. The two thresholds stop the
//    pump chattering; the sample counts reject single spikes (a lighter flash, a hand).
// Measured on 6 Nov with a tealight in front of the IR window (room 22.7 °C):
// 50 cm about 27 °C, 30 cm about 31 °C, 20 cm or closer 52-61 °C; the reading falls back to
// room level within about 1 s of the flame moving away.
class TemperatureState {
 public:
  static constexpr float FIRE_RISE_C = 10.f, CLEAR_RISE_C = 7.f, CAL_SPREAD_C = 2.f;
  static constexpr uint32_t CAL_MS = 10000;
  static constexpr uint8_t CONFIRM_SAMPLES = 4, MIN_CAL_SAMPLES = 10;

  void update(float object, float ambient, bool valid, uint32_t now) {
    valid_ = valid && isfinite(object) && isfinite(ambient)
      && object >= -70.01f && object <= 382.2f && ambient >= -40.f && ambient <= 125.f;
    if (!valid_) return;
    object_ = object; ambient_ = ambient; last_ = now;
    if (!calibrated_) { calibrate(now); return; }
    if (object_ >= room_ + FIRE_RISE_C) {
      below_ = 0;
      if (above_ < CONFIRM_SAMPLES) ++above_;
      if (above_ >= CONFIRM_SAMPLES) hot_ = true;
    } else if (object_ < room_ + CLEAR_RISE_C) {
      above_ = 0;
      if (below_ < CONFIRM_SAMPLES) ++below_;
      if (below_ >= CONFIRM_SAMPLES) hot_ = false;
    } else {
      above_ = below_ = 0;                       // in between: keep the current state
    }
  }
  bool fresh(uint32_t now) const { return valid_ && uint32_t(now-last_) < 1500; }
  bool calibrated() const { return calibrated_; }
  bool hot(uint32_t now) const { return calibrated_ && fresh(now) && hot_; }
  float object() const { return object_; }
  float ambient() const { return ambient_; }
  float room() const { return room_; }
  unsigned calibrationRestarts() const { return restarts_; }

 private:
  void calibrate(uint32_t now) {
    if (calCount_ == 0 || fmaxf(calMax_, object_) - fminf(calMin_, object_) > CAL_SPREAD_C) {
      if (calCount_ > 0) ++restarts_;
      calStart_ = now; calSum_ = 0; calCount_ = 0; calMin_ = calMax_ = object_;
    }
    calSum_ += object_; ++calCount_;
    calMin_ = fminf(calMin_, object_); calMax_ = fmaxf(calMax_, object_);
    if (uint32_t(now - calStart_) >= CAL_MS && calCount_ >= MIN_CAL_SAMPLES) {
      room_ = calSum_ / calCount_;
      calibrated_ = true;
    }
  }
  bool valid_ = false, hot_ = false, calibrated_ = false;
  float object_ = 0, ambient_ = 0, room_ = 0;
  float calSum_ = 0, calMin_ = 0, calMax_ = 0;
  uint32_t last_ = 0, calStart_ = 0;
  unsigned calCount_ = 0, restarts_ = 0;
  uint8_t above_ = 0, below_ = 0;
};
