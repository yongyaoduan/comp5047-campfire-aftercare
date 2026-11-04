# Mac backup vision program (demo-day fallback)

Use this only if the Raspberry Pi 3B+ is too slow or fails on the day. It replaces
the Pi's camera + MediaPipe step with Apple Vision on a MacBook; the FireBeetle
firmware, sensors, pump, LEDs and speaker are unchanged and still make every
safety decision.

* Same BLE service/characteristic as `pi/app.py`
  (`A6E40001-…` / `A6E40002-…`), same one-byte commands:
  `0/1` person absent/present (re-sent every 1 s, because the firmware drops the
  link after 2 s of silence), `4` heart held (every 0.2 s while held), `5` heart
  released, `6` STOP.
* Two-hand heart only. Waves are still detected for the on-screen log but are
  **not** sent (the final firmware ignores command `2`).
* "Nobody" is declared 1.5 s after the last person detection (the Pi takes
  longer because it runs at ~1 FPS). The firmware's 20 s grace is unchanged.

## Run

1. Quit the Pi program first (only one central may connect to the FireBeetle):
   `ssh campfire@campfire.local 'pkill -f app.py'`
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
