#pragma once
#include <stdint.h>

class ControlState {
 public:
  enum class Mode { Monitor, Attended, Grace, Alarm, ManualSpray, AutoSpray };
  enum class Voice { None, Water, Fire, Love };
  struct Input {
    bool link = false, person = false, heart = false;
    bool temperatureKnown = false, hot = false;
    bool waterKnown = false, lowWater = false;
  };
  struct Output {
    bool green = false, yellow = false, red = false, blue = false;
    bool pump = false, alarm = false;
    Voice voice = Voice::None;
    Mode mode = Mode::Monitor;
  };
  static constexpr uint32_t GRACE_MS = 20000, BURST_MS = 5000;
  void reset() {
    mode_ = Mode::Monitor;
    previousHeart_ = previousPerson_ = false;
    waterVoiceSent_ = false;
  }
  Output tick(uint32_t now, const Input &in) {
    Output out;
    out.green = in.link && in.person;
    out.yellow = in.waterKnown && in.lowWater;
    out.red = in.temperatureKnown && in.hot;
    out.blue = in.link && in.heart;
    bool risingHeart = in.link && in.heart && !previousHeart_;
    bool arriving = in.link && in.person && !previousPerson_;
    previousHeart_ = in.link && in.heart;
    previousPerson_ = in.link && in.person;
    if (risingHeart) out.voice = Voice::Love;

    if (!in.link || !in.temperatureKnown || !in.hot) {
      mode_ = Mode::Monitor;
    } else if (in.person) {
      if (mode_ != Mode::ManualSpray) {
        const bool entering = mode_ != Mode::Attended || arriving;
        mode_ = Mode::Attended;
        if (entering && out.voice == Voice::None) out.voice = Voice::Fire;
      }
      // A recognised heart authorises spraying until cool, while still attended.
      if (risingHeart) mode_ = Mode::ManualSpray;
    } else {
      if (mode_ == Mode::Monitor || mode_ == Mode::Attended || mode_ == Mode::ManualSpray) {
        mode_ = Mode::Grace;
        phaseStarted_ = now;
      }
      if (mode_ == Mode::Grace && uint32_t(now - phaseStarted_) >= GRACE_MS) {
        phaseStarted_ += GRACE_MS;
        mode_ = Mode::Alarm;
      }
      if (mode_ == Mode::Alarm) {
        // Bursts at 0-5, 10-15, 20-25 s; spray after the third pause at 30 s.
        const uint32_t elapsed = now - phaseStarted_;
        if (elapsed >= 6 * BURST_MS) mode_ = Mode::AutoSpray;
        else out.alarm = (elapsed / BURST_MS) % 2 == 0;
      }
    }
    const bool sprayMode = mode_ == Mode::ManualSpray || mode_ == Mode::AutoSpray;
    out.pump = sprayMode && in.link && in.temperatureKnown && in.hot &&
               in.waterKnown && !in.lowWater;
    // Water warning has priority over spoken fire/heart prompts.
    if (out.yellow && out.green) {
      if (!waterVoiceSent_ || uint32_t(now - waterVoiceAt_) >= 5000) {
        out.voice = Voice::Water;
        waterVoiceAt_ = now;
        waterVoiceSent_ = true;
      }
    } else waterVoiceSent_ = false;
    out.mode = mode_;
    return out;
  }
 private:
  Mode mode_ = Mode::Monitor;
  uint32_t phaseStarted_ = 0, waterVoiceAt_ = 0;
  bool previousHeart_ = false, previousPerson_ = false, waterVoiceSent_ = false;
};
