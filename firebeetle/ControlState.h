#pragma once
#include <stdint.h>

// Campfire Aftercare control rules (see report §5.2):
//  - Two LEDs mirror the readings: green person in view, red fire.
//  - Tank low (fewer than 5 of 20 sensor sections wet) is spoken ("I need some water",
//    every 5 s while someone is in view); it does not block the pump.
//    a held heart is answered by "I love you too" and, if the bowl is hot, by water.
//  - Water flows only (a) while a heart is held and the bowl is hot, or
//    (b) automatically when nobody is in view, after 5 s grace + 3 alarm bursts (1 s on, 1 s off).
//  - At most 10 alarm bursts per unattended episode (including the 3 before the spray).
//  - Never spray near a person who is not holding a heart.
//  - Coming back during the grace period: nothing happens.
//    Coming back during the alarm / auto spray: alarm stops, fire prompt plays once.
//  - An empty tank (no section wet) blocks every spray; the alarm keeps calling people
//    back until the 10-burst cap is reached.
//  - Tank full (15 of 20 sensor sections wet): "Enough water, thank you" once.
class ControlState {
 public:
  enum class Mode { Monitor, Grace, Alarm, AutoSpray };
  enum class Voice { None, Water, Fire, Love, Spray, Full };
  struct Input {
    bool link = false, person = false, heart = false;
    bool temperatureKnown = false, hot = false;
    bool waterKnown = false, lowWater = false, emptyWater = false, fullWater = false;
  };
  struct Output {
    bool green = false, red = false;
    bool pump = false, alarm = false;
    Voice voice = Voice::None;
    Mode mode = Mode::Monitor;
  };
  static constexpr uint32_t GRACE_MS = 5000, BURST_MS = 1000, WATER_VOICE_MS = 5000;
  static constexpr unsigned PRE_SPRAY_BURSTS = 3, MAX_BURSTS = 10;

  void reset() {
    mode_ = Mode::Monitor;
    previousHeart_ = false;
    waterVoiceSent_ = sprayAnnounced_ = fullAnnounced_ = false;
  }

  Output tick(uint32_t now, const Input &in) {
    Output out;
    const bool person = in.link && in.person;
    const bool heart = in.link && in.heart;
    const bool hot = in.link && in.temperatureKnown && in.hot;
    const bool waterOK = in.waterKnown && !in.emptyWater;   // any water detected: pump allowed
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
        bursts_ = 0;
        inBurst_ = false;
      }
      if (mode_ == Mode::Grace && uint32_t(now - phaseStarted_) >= GRACE_MS) {
        mode_ = Mode::Alarm;
        phaseStarted_ += GRACE_MS;
      }
      if (mode_ == Mode::Alarm) {
        // Bursts at 0-1, 2-3, 4-5 s; automatic spray after the third pause (6 s).
        const uint32_t elapsed = now - phaseStarted_;
        if (elapsed >= 2 * PRE_SPRAY_BURSTS * BURST_MS) {
          mode_ = Mode::AutoSpray;
          phaseStarted_ = now;
          sprayAnnounced_ = false;
        } else {
          out.alarm = burst(elapsed);
        }
      }
      if (mode_ == Mode::AutoSpray) {
        if (waterOK) {
          phaseStarted_ = now;                     // no-water alarm restarts from here
          inBurst_ = false;
          if (!sprayAnnounced_ && out.voice == Voice::None) {
            out.voice = Voice::Spray;              // "Putting the fire out."
            sprayAnnounced_ = true;
          }
        } else {
          // Cannot spray: keep calling people back, up to the 10-burst cap.
          out.alarm = burst(now - phaseStarted_);
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
    // Tank full: say so once (wait if another prompt is playing this tick).
    const bool tankFull = in.waterKnown && in.fullWater;
    if (!tankFull) fullAnnounced_ = false;
    else if (!fullAnnounced_ && out.voice == Voice::None) {
      out.voice = Voice::Full;
      fullAnnounced_ = true;
    }
    out.mode = mode_;
    return out;
  }

 private:
  // 1 s on / 1 s off; each new "on" second uses one of the MAX_BURSTS allowed per episode.
  bool burst(uint32_t elapsed) {
    const bool on = (elapsed / BURST_MS) % 2 == 0;
    if (!on) { inBurst_ = false; return false; }
    if (!inBurst_ && bursts_ < MAX_BURSTS) { ++bursts_; inBurst_ = true; }
    return inBurst_;
  }
  Mode mode_ = Mode::Monitor;
  unsigned bursts_ = 0;
  bool inBurst_ = false;
  uint32_t phaseStarted_ = 0, waterVoiceAt_ = 0;
  bool previousHeart_ = false, waterVoiceSent_ = false, sprayAnnounced_ = false, fullAnnounced_ = false;
};
