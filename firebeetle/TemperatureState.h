#pragma once
#include <stdint.h>
#include <math.h>

class TemperatureState {
 public:
  void update(float object, float ambient, bool valid, uint32_t now) {
    valid_ = valid && isfinite(object) && isfinite(ambient)
      && object >= -70.01f && object <= 382.2f && ambient >= -40.f && ambient <= 125.f;
    if (!valid_) return;
    object_ = object; ambient_ = ambient; last_ = now;
  }
  bool fresh(uint32_t now) const { return valid_ && uint32_t(now-last_) < 1500; }
  bool hot(uint32_t now) const { return fresh(now) && object_ >= 45.f; }
  float object() const { return object_; }
  float ambient() const { return ambient_; }
 private:
  bool valid_ = false;
  float object_ = 0, ambient_ = 0;
  uint32_t last_ = 0;
};
