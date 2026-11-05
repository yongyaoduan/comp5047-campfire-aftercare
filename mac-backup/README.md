# Laptop vision program (Apple Vision) — used for the final demo

Since 5 Nov 2026 this is the station's vision program. The Raspberry Pi 3B+
(`../pi/`, kept unchanged) ran at 0.5–0.8 FPS, reported undervoltage and
rebooted under load, so the camera + MediaPipe step moved to a MacBook running
Apple Vision; the FireBeetle
firmware, sensors, pump, LEDs and speaker are unchanged and still make every
safety decision.

* Same BLE service/characteristic as `pi/app.py`
  (`A6E40001-…` / `A6E40002-…`), same one-byte commands:
  `0/1` person absent/present (re-sent every 1 s, because the firmware drops the
  link after 2 s of silence), `4` heart held (every 0.2 s while held), `5` heart
  released, `6` STOP.
* Anyone in view counts as "someone here": a full-body person box, a face or a
  visible hand (animal boxes from `VNRecognizeAnimalsRequest` are removed).
  Any pair of up to 8 hands forming a two-hand heart counts (one person, or two
  people sharing one); if the full frame shows no heart, hands are searched again
  in each person's region and in three tiles. Shared code: `Sources/VisionPipeline.swift`.
* If the camera or vision stalls for 2 s, the program sends `6` (STOP) instead of
  repeating an old presence, as the Pi does.
* An external USB webcam (the Brio 100) is preferred; without one the built-in
  camera is used.
* Two-hand heart only. Waves are still detected for the on-screen log but are
  **not** sent (the final firmware ignores command `2`).
* "Nobody" is declared 1.5 s after the last person detection (the Pi takes
  longer because it runs at ~1 FPS). The firmware's 5 s grace is unchanged.

## Tests

```bash
./verify.sh   # heart-rule unit tests, builds the app and the photo regression
build/tests/PhotoRegression <corpus-dir-with-results.json> out.json
```

On the team's 264-photo corpus (5 Nov 2026, MacBook Air, the same corpus the rules
were tuned on, so a regression check rather than an independent test): people
128/139, false "person" 3/125 (two dogs, a pile of clothes), hearts 52/73, false
heart 0/190; median 21 ms per frame (p90 50 ms).

## Run

1. Make sure the Pi program is not running (only one central may connect to the
   FireBeetle); its start-on-boot service is disabled since 5 Nov:
   `ssh campfire@campfire.local 'systemctl --user stop campfire'`
2. Plug the Brio 100 into the Mac (or use the built-in camera) and run:

```bash
./build_and_run.sh            # real outputs
./build_and_run.sh --dry-run  # camera + detection only, nothing sent
```

Grant Camera and Bluetooth permission when macOS asks. The window should show
`Bluetooth: FireBeetle connected`.

Origin: adapted on 2026-11-05 from the team's October Mac prototype
(`final/mac-vision-gesture-led-pump-demo`), whose old firmware/pins (green 25,
yellow 14) are **not** used any more – flash `../firebeetle/` as usual.
