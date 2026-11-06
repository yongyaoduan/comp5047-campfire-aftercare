#include <math.h>
#include "../ControlState.h"
#include "../WaterLevelState.h"
#include "../TemperatureState.h"
#include <cassert>
#include <cstdio>

using C = ControlState;
C::Input ready(bool person = false) {
  C::Input in;
  in.link = in.temperatureKnown = in.waterKnown = in.hot = true;
  in.person = person;
  return in;
}

int main() {
  { // Nobody ever seen: 5 s silence, three 1 s bursts, then automatic spray.
    C c; auto in = ready();
    assert(!c.tick(0, in).pump);
    assert(!c.tick(4999, in).alarm);
    assert(c.tick(5000, in).alarm);
    assert(!c.tick(6000, in).alarm);
    assert(c.tick(7000, in).alarm);
    assert(!c.tick(8000, in).alarm);
    assert(c.tick(9000, in).alarm);
    assert(!c.tick(10000, in).alarm);
    assert(!c.tick(10999, in).pump);
    auto out = c.tick(11000, in);
    assert(out.pump && out.red && out.voice == C::Voice::Spray); // LEDs stay on; announce once
    assert(c.tick(11001, in).voice == C::Voice::None);
    in.hot = false;                                            // bowl cooled
    out = c.tick(11002, in);
    assert(!out.pump && out.mode == C::Mode::Monitor);
    in.hot = true;                                             // re-ignites: cycle restarts
    assert(c.tick(11003, in).mode == C::Mode::Grace);
    assert(!c.tick(16002, in).pump && c.tick(16003, in).alarm);
  }
  { // Back within the 5 s grace: nothing happens (no prompt, no alarm).
    C c; auto in = ready(); c.tick(0, in);
    in.person = true;
    auto out = c.tick(3000, in);
    assert(!out.pump && !out.alarm && out.voice == C::Voice::None && out.green);
  }
  { // Back during the alarm: alarm stops, prompt once, then normal use.
    C c; auto in = ready(); c.tick(0, in);
    assert(c.tick(5000, in).alarm);
    in.person = true;
    auto out = c.tick(5500, in);
    assert(!out.pump && !out.alarm && out.voice == C::Voice::Fire);
    out = c.tick(6000, in);
    assert(!out.pump && out.voice == C::Voice::None && out.mode == C::Mode::Monitor);
  }
  { // Person walks in during an automatic spray without a heart: pump stops at once.
    C c; auto in = ready(); c.tick(0, in);
    assert(c.tick(11000, in).pump);
    in.person = true;
    auto out = c.tick(11100, in);
    assert(!out.pump && out.voice == C::Voice::Fire);
    in.heart = true;                                           // ...unless they hold a heart
    out = c.tick(11200, in);
    assert(out.pump && out.voice == C::Voice::Love);
  }
  { // Heart works at any time while hot, but only while it is held.
    C c; auto in = ready(true); c.tick(0, in);
    in.heart = true;
    auto out = c.tick(10, in);
    assert(out.pump && out.green && out.red && out.voice == C::Voice::Love);
    assert(c.tick(20, in).voice == C::Voice::None);            // "I love you too" once
    in.heart = false;
    out = c.tick(30, in);
    assert(!out.pump);                                           // hands down: pump off
    in.heart = true;
    assert(c.tick(40, in).voice == C::Voice::Love);            // new gesture, new reply
    in.hot = false;
    out = c.tick(50, in);
    assert(!out.pump && !out.red);                               // fire out: no water
  }
  { // Low water: no spray anywhere, but the station never goes silent.
    C c; auto in = ready(true); in.lowWater = true; in.heart = true;
    auto out = c.tick(0, in);
    assert(!out.pump && out.red && out.green);                   // no LED for low water: voice only
    assert(out.voice == C::Voice::Water);
    assert(c.tick(4999, in).voice == C::Voice::None);
    assert(c.tick(5000, in).voice == C::Voice::Water);
    // Nobody here and dry: after the bursts the alarm keeps repeating.
    C d; auto dry = ready(); dry.lowWater = true; d.tick(0, dry);
    assert(!d.tick(11000, dry).pump && d.tick(11000, dry).alarm);
    assert(!d.tick(12000, dry).alarm && d.tick(13000, dry).alarm && !d.tick(13000, dry).pump);
    dry.lowWater = false;                                      // refilled while still alone
    out = d.tick(13500, dry);
    assert(out.pump && out.voice == C::Voice::Spray);
  }
  { // Tank full: "Enough water, thank you" once, again only after it was not full.
    C c; auto in = ready(true); in.hot = false; in.fullWater = true;
    assert(c.tick(0, in).voice == C::Voice::Full);
    assert(c.tick(100, in).voice == C::Voice::None);
    in.fullWater = false; c.tick(200, in);
    in.fullWater = true; assert(c.tick(300, in).voice == C::Voice::Full);
  }
  { // No fire: heart says "I love you too", no water, no alarm.
    C c; auto in = ready(true); in.hot = false; in.heart = true;
    auto out = c.tick(0, in);
    assert(!out.pump && !out.alarm && !out.red && out.voice == C::Voice::Love);
    in.link = false;
    out = c.tick(1, in);
    assert(!out.pump && !out.green);
  }
  { // Disconnect resets the cycle; reconnect cannot resume spraying.
    C c; auto in = ready(); c.tick(0, in); c.tick(11000, in);
    in.link = false; assert(!c.tick(11001, in).pump);
    in.link = true; assert(!c.tick(11002, in).pump);
    assert(!c.tick(16001, in).alarm);
  }
  { // Clock wrap: unsigned duration arithmetic remains valid.
    C c; auto in = ready();
    c.tick(0xfffff000u, in);
    assert(c.tick(uint32_t(0xfffff000u + 5000u), in).alarm);
  }
  { // Sensors: stale water is not "empty"; temperature is relative to the room (+10 / +7 C).
    WaterLevelState water; uint8_t raw[20] = {};
    water.update(raw, false, 0); assert(!water.fresh(0));
    water.update(raw, true, 10); assert(!water.settled());
    water.update(raw, true, 20); assert(water.settled() && water.dry(20));
    raw[3] = 249; water.update(raw, true, 30);
    assert(water.levelMM() == 0); // Isolated upper film ignored.
    raw[0] = 249; water.update(raw, true, 31); water.update(raw, true, 32);
    assert(water.levelMM() == 5 && water.dry(32));   // one section: still low
    raw[1] = 249; water.update(raw, true, 33); water.update(raw, true, 34);
    assert(water.levelMM() == 10 && !water.dry(34)); // two sections: OK
    raw[0] = raw[1] = 0;
    assert(!water.fresh(2000));
    { // Sensor fault: a sudden all-dry reading after a real level stays suspect until real data returns.
      WaterLevelState w; uint8_t r[20] = {};
      for (int i = 0; i < 6; ++i) r[i] = 249;
      w.update(r, true, 0); w.update(r, true, 250); assert(!w.dry(250) && w.levelMM() == 30);
      for (auto &v : r) v = 0;
      w.update(r, true, 500); w.update(r, true, 750); assert(w.suspect() && !w.dry(750));
      w.update(r, true, 60000); assert(w.suspect() && !w.dry(60000));      // still not "low"
      for (int i = 0; i < 4; ++i) r[i] = 249;
      w.update(r, true, 60250); assert(!w.suspect() && w.levelMM() == 20); // recovers
      // Gradual draining is believed at once.
      WaterLevelState g; uint8_t q[20] = {};
      q[0] = q[1] = 249; g.update(q, true, 0); g.update(q, true, 250);
      q[1] = 0; g.update(q, true, 500); g.update(q, true, 750); assert(!g.suspect() && g.dry(750));
    }
    // Full tank: 15 contiguous wet sections twice; clears only below 13 sections.
    for (int i = 0; i < 20; ++i) raw[i] = i < 15 ? 249 : 0;
    water.update(raw, true, 40); assert(!water.full(40));
    water.update(raw, true, 50); assert(water.full(50) && water.levelMM() == 75);
    raw[14] = raw[13] = 0; water.update(raw, true, 60); assert(water.full(60));   // 13 wet: hold
    raw[12] = 0; water.update(raw, true, 70); assert(!water.full(70));            // 12 wet: clear
    TemperatureState temp;
    // Calibration: 10 s of room readings at 4 Hz -> room = mean (22.5 C here).
    uint32_t t = 0;
    for (; t <= 10000; t += 250) {
      temp.update((t / 250) % 2 ? 22.4f : 22.6f, 22, true, t);
      if (t < 10000) assert(!temp.calibrated() && !temp.hot(t));
    }
    assert(temp.calibrated() && fabsf(temp.room() - 22.5f) < 0.01f);
    auto feed = [&](float c, int n) { for (int i = 0; i < n; ++i) { t += 250; temp.update(c, 22, true, t); } };
    feed(31.2f, 8);  assert(!temp.hot(t));        // 30 cm candle: +8.7 C, not fire
    feed(38.f, 1);   feed(24.f, 3); assert(!temp.hot(t));   // single spike ignored
    feed(55.f, 3);   assert(!temp.hot(t));        // 3 samples: not yet
    feed(55.f, 1);   assert(temp.hot(t));         // 4th sample (1 s): fire
    feed(30.f, 8);   assert(temp.hot(t));         // between +7 and +10: stays hot
    feed(26.f, 3);   assert(temp.hot(t));
    feed(26.f, 1);   assert(!temp.hot(t));        // below +7 for 1 s: cleared
    feed(32.4f, 8);  assert(!temp.hot(t));        // must reach room + 10 again
    assert(!temp.hot(t + 2000));                  // stale reading is not hot
    // A warm object in view at power-up restarts the calibration window.
    TemperatureState warm;
    warm.update(22.6f, 22, true, 0);
    warm.update(40.f, 22, true, 250);             // spread > 2 C: restart from here
    for (uint32_t u = 500; u <= 10000; u += 250) warm.update(40.f, 22, true, u);
    assert(!warm.calibrated() && warm.calibrationRestarts() == 1);
    warm.update(40.f, 22, true, 10250);
    assert(warm.calibrated() && fabsf(warm.room() - 40.f) < 0.01f);
  }
  puts("Control tests passed (12 scenario groups)");
}
