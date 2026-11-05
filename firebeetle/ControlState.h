#pragma once
#include <stdint.h>

// Campfire Aftercare control rules (see report §5.2):
//  - Two LEDs mirror the readings: green person in view, red fire.
//  - Tank low is spoken ("I need some more water", every 5 s while someone is in view);
//    a held heart is answered by "I love you too" and, if the bowl is hot, by water.
//  - Water flows only (a) while a heart is held and the bowl is hot, or
//    (b) automatically when nobody is in view, after 20 s grace + 3 alarm bursts.
//  - Never spray near a person who is not holding a heart.
//  - Coming back during the grace period: nothing happens.
//    Coming back during the alarm / auto spray: alarm stops, fire prompt plays once.
//  - Low water blocks every spray but never silences the station.
class ControlState {
 public:
  enum class Mode { Monitor, Grace, Alarm, AutoSpray };
  enum class Voice { None, Water, Fire, Love, Spray };
  struct Input {
    bool link = false, person = false, heart = false;
    bool temperatureKnown = false, hot = false;
    bool waterKnown = false, lowWater = false;
  };
  struct Output {
    bool green = false, red = false;
    bool pump = false, alarm = false;
    Voice voice = Voice::None;
    Mode mode = Mode::Monitor;
  };
  static constexpr uint32_t GRACE_MS = 20000, BURST_MS = 5000, WATER_VOICE_MS = 5000;

  void reset() {
    mode_ = Mode::Monitor;
    previousHeart_ = false;
    waterVoiceSent_ = sprayAnnounced_ = false;
  }

  Output tick(uint32_t now, const Input &in) {
    Output out;
    const bool person = in.link && in.person;
    const bool heart = in.link && in.heart;
    const bool hot = in.link && in.temperatureKnown && in.hot;
    const bool waterOK = in.waterKnown && !in.lowWater;
    out.green = person;
    out.red = in.temperatureKnown && in.hot;
    const bool tankLow = in.waterKnown && in.lowWater;

    // "I love you too" once per heart gesture, fire or no fire.
    if (heart && !previousHeart_) out.voice = Voice::Love;
    previousHeart_ = heart;

    if (!hot) {
      mode_ = Mode::Monitor;                       // no fire: no sound, no pump
    } else if (person) {
      // Called back by the alarm or an automatic spray: prompt once.
      if ((mode_ == Mode::Alarm || mode_ == Mode::AutoSpray) && out.voice == Voice::None)
        out.voice = Voice::Fire;
      mode_ = Mode::Monitor;                       // fire + people = normal use
    } else {
      if (mode_ == Mode::Monitor) {                // fire + nobody (incl. never seen)
        mode_ = Mode::Grace;
        phaseStarted_ = now;
      }
      if (mode_ == Mode::Grace && uint32_t(now - phaseStarted_) >= GRACE_MS) {
        mode_ = Mode::Alarm;
        phaseStarted_ += GRACE_MS;
      }
      if (mode_ == Mode::Alarm) {
        // Bursts at 0-5, 10-15, 20-25 s; automatic spray after the third pause (30 s).
        const uint32_t elapsed = now - phaseStarted_;
        if (elapsed >= 6 * BURST_MS) {
          mode_ = Mode::AutoSpray;
          phaseStarted_ = now;
          sprayAnnounced_ = false;
        } else {
          out.alarm = (elapsed / BURST_MS) % 2 == 0;
        }
      }
      if (mode_ == Mode::AutoSpray) {
        if (waterOK) {
          if (!sprayAnnounced_ && out.voice == Voice::None) {
            out.voice = Voice::Spray;              // "Putting the fire out."
            sprayAnnounced_ = true;
          }
        } else {
          // Cannot spray: keep calling people back instead of going silent.
          out.alarm = (uint32_t(now - phaseStarted_) / BURST_MS) % 2 == 0;
        }
      }
    }

    const bool heartSpray = heart && hot;                          // only while held
    const bool autoSpray = mode_ == Mode::AutoSpray && !person && hot;
    out.pump = (heartSpray || autoSpray) && waterOK;

    // Water request has priority over other speech while someone is in view.
    if (tankLow && person) {
      if (!waterVoiceSent_ || uint32_t(now - waterVoiceAt_) >= WATER_VOICE_MS) {
        out.voice = Voice::Water;
        waterVoiceAt_ = now;
        waterVoiceSent_ = true;
      }
    } else {
      waterVoiceSent_ = false;
    }
    out.mode = mode_;
    return out;
  }

 private:
  Mode mode_ = Mode::Monitor;
  uint32_t phaseStarted_ = 0, waterVoiceAt_ = 0;
  bool previousHeart_ = false, waterVoiceSent_ = false, sprayAnnounced_ = false;
};
