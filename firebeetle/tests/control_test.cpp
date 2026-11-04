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
  { // Three alarm bursts after 20 s, then automatic spray after all three pauses.
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
    assert(out.pump && out.red); // Pump does not blank status LEDs.
    in.lowWater = true;
    assert(!c.tick(50001, in).pump && c.tick(50002, in).yellow);
    in.lowWater = false;
    assert(c.tick(50003, in).pump);
    in.hot = false;
    assert(!c.tick(50004, in).pump);
  }
  { // A return cancels alarm/automatic spray and requires a fresh heart.
    C c; auto in = ready(); c.tick(0, in);
    assert(c.tick(20000, in).alarm);
    in.person = true;
    auto out = c.tick(21000, in);
    assert(!out.pump && !out.alarm && out.green && out.red && out.voice == C::Voice::Fire);
    in.person = false; c.tick(22000, in); c.tick(72000, in);
    in.person = true;
    assert(!c.tick(72001, in).pump);
  }
  { // Heart authorises attended spray until cool; release changes only blue.
    C c; auto in = ready(true); c.tick(0, in);
    in.heart = true;
    auto out = c.tick(10, in);
    assert(out.pump && out.green && out.red && out.blue && out.voice == C::Voice::Love);
    in.heart = false;
    assert(c.tick(20, in).pump && !c.tick(21, in).blue);
    in.hot = false;
    assert(!c.tick(30, in).pump);
  }
  { // Dry water blocks every spray, voice repeats at 5 s only while attended.
    C c; auto in = ready(true); in.lowWater = true; in.heart = true;
    auto out = c.tick(0, in);
    assert(!out.pump && out.yellow && out.blue && out.red && out.green);
    assert(out.voice == C::Voice::Water);
    assert(c.tick(4999, in).voice == C::Voice::None);
    assert(c.tick(5000, in).voice == C::Voice::Water);
    in.waterKnown = false;
    assert(!c.tick(5100, in).pump);
    in.waterKnown = true; in.lowWater = false;
    assert(c.tick(5200, in).pump);
    in.temperatureKnown = false;
    assert(!c.tick(5300, in).pump);
  }
  { // No fire: heart lights blue but cannot start water.
    C c; auto in = ready(true); in.hot = false; in.heart = true;
    auto out = c.tick(0, in);
    assert(out.blue && !out.pump && !out.alarm);
    in.link = false;
    out = c.tick(1, in);
    assert(!out.pump && !out.green && !out.blue);
  }
  { // Disconnect resets unattended grace; reconnect cannot resume spraying.
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
  { // Invalid/stale samples are not reported as an empty tank.
    WaterLevelState water; uint8_t raw[20] = {};
    water.update(raw, false, 0); assert(!water.fresh(0));
    water.update(raw, true, 10); assert(!water.settled());
    water.update(raw, true, 20); assert(water.settled() && water.dry(20));
    raw[3] = 249; water.update(raw, true, 30);
    assert(water.levelMM() == 0); // Isolated upper film ignored.
    assert(!water.fresh(2000));
    TemperatureState temp; temp.update(45, 20, true, 0);
    assert(temp.hot(0)); temp.update(44.99f, 20, true, 1);
    assert(!temp.hot(1));
  }
  puts("Four-LED/voice control tests passed (8 scenario groups)");
}
