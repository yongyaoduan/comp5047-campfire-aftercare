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
  { // Nobody ever seen: 20 s silence, three 5 s bursts, then automatic spray.
    C c; auto in = ready();
    assert(!c.tick(0, in).pump);
    assert(!c.tick(19999, in).alarm);
    assert(c.tick(20000, in).alarm);
    assert(!c.tick(25000, in).alarm);
    assert(c.tick(30000, in).alarm);
    assert(!c.tick(35000, in).alarm);
    assert(c.tick(40000, in).alarm);
    assert(!c.tick(45000, in).alarm);
    assert(!c.tick(49999, in).pump);
    auto out = c.tick(50000, in);
    assert(out.pump && out.red && out.voice == C::Voice::Spray); // LEDs stay on; announce once
    assert(c.tick(50001, in).voice == C::Voice::None);
    in.hot = false;                                            // bowl cooled
    out = c.tick(50002, in);
    assert(!out.pump && out.mode == C::Mode::Monitor);
    in.hot = true;                                             // re-ignites: cycle restarts
    assert(c.tick(50003, in).mode == C::Mode::Grace);
    assert(!c.tick(70002, in).pump && c.tick(70003, in).alarm);
  }
  { // Back within the 20 s grace: nothing happens (no prompt, no alarm).
    C c; auto in = ready(); c.tick(0, in);
    in.person = true;
    auto out = c.tick(10000, in);
    assert(!out.pump && !out.alarm && out.voice == C::Voice::None && out.green);
  }
  { // Back during the alarm: alarm stops, prompt once, then normal use.
    C c; auto in = ready(); c.tick(0, in);
    assert(c.tick(20000, in).alarm);
    in.person = true;
    auto out = c.tick(21000, in);
    assert(!out.pump && !out.alarm && out.voice == C::Voice::Fire);
    out = c.tick(22000, in);
    assert(!out.pump && out.voice == C::Voice::None && out.mode == C::Mode::Monitor);
  }
  { // Person walks in during an automatic spray without a heart: pump stops at once.
    C c; auto in = ready(); c.tick(0, in);
    assert(c.tick(50000, in).pump);
    in.person = true;
    auto out = c.tick(50100, in);
    assert(!out.pump && out.voice == C::Voice::Fire);
    in.heart = true;                                           // ...unless they hold a heart
    out = c.tick(50200, in);
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
    assert(!d.tick(50000, dry).pump && d.tick(50000, dry).alarm);
    assert(!d.tick(55000, dry).alarm && d.tick(60000, dry).alarm && !d.tick(60000, dry).pump);
    dry.lowWater = false;                                      // refilled while still alone
    out = d.tick(61000, dry);
    assert(out.pump && out.voice == C::Voice::Spray);
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
    C c; auto in = ready(); c.tick(0, in); c.tick(50000, in);
    in.link = false; assert(!c.tick(50001, in).pump);
    in.link = true; assert(!c.tick(50002, in).pump);
    assert(!c.tick(70001, in).alarm);
  }
  { // Clock wrap: unsigned duration arithmetic remains valid.
    C c; auto in = ready();
    c.tick(0xfffff000u, in);
    assert(c.tick(uint32_t(0xfffff000u + 20000u), in).alarm);
  }
  { // Sensors: stale water is not "empty"; temperature has 45/40 °C hysteresis.
    WaterLevelState water; uint8_t raw[20] = {};
    water.update(raw, false, 0); assert(!water.fresh(0));
    water.update(raw, true, 10); assert(!water.settled());
    water.update(raw, true, 20); assert(water.settled() && water.dry(20));
    raw[3] = 249; water.update(raw, true, 30);
    assert(water.levelMM() == 0); // Isolated upper film ignored.
    assert(!water.fresh(2000));
    TemperatureState temp;
    temp.update(44.9f, 20, true, 0); assert(!temp.hot(0));
    temp.update(45, 20, true, 1);    assert(temp.hot(1));
    temp.update(41, 20, true, 2);    assert(temp.hot(2));     // still hot above 40
    temp.update(39.9f, 20, true, 3); assert(!temp.hot(3));
    temp.update(44, 20, true, 4);    assert(!temp.hot(4));    // must reach 45 again
  }
  puts("Control tests passed (10 scenario groups)");
}
