#pragma once
#include <stdint.h>
#include <math.h>

// Fire detection with hysteresis: becomes "hot" at >= 45 °C and stays hot
// until the bowl reads below 40 °C, so the pump does not chatter on and off
// while the reading hovers around one threshold.
class TemperatureState {
 public:
  static constexpr float HOT_ON_C = 45.f, HOT_OFF_C = 40.f;
  void update(float object, float ambient, bool valid, uint32_t now) {
    valid_ = valid && isfinite(object) && isfinite(ambient)
      && object >= -70.01f && object <= 382.2f && ambient >= -40.f && ambient <= 125.f;
    if (!valid_) return;
    object_ = object; ambient_ = ambient; last_ = now;
    if (object_ >= HOT_ON_C) hot_ = true;
    else if (object_ < HOT_OFF_C) hot_ = false;
  }
  bool fresh(uint32_t now) const { return valid_ && uint32_t(now-last_) < 1500; }
  bool hot(uint32_t now) const { return fresh(now) && hot_; }
  float object() const { return object_; }
  float ambient() const { return ambient_; }
 private:
  bool valid_ = false, hot_ = false;
  float object_ = 0, ambient_ = 0;
  uint32_t last_ = 0;
};
