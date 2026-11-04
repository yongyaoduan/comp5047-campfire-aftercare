"""Continuously save 10 Hz board samples and refresh the last 10 minutes plot."""
import csv
import json
import os
from pathlib import Path
import signal
import time
from collections import deque

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import serial

OUT = Path(__file__).resolve().parent / 'recording'
OUT.mkdir(exist_ok=True)
FIELDS = ['seq', 'start_us', 'read_us', 'valid', 'level_mm', 'wet_segments',
          'isolated_segments'] + [f'r{i}' for i in range(20)]
running = True
def stop(*_):
    global running
    running = False
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)

def plot(rows, count):
    if len(rows) < 2:
        return
    a = np.asarray(rows, dtype=float)
    t = (a[:, 1] - a[0, 1]) / 1e6
    valid = a[:, 3] == 1
    level = np.where(valid, a[:, 4], np.nan)
    intervals = np.diff(a[:, 1]) / 1000
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True,
                             gridspec_kw={'height_ratios': [2, 2, 1]})
    axes[0].plot(t, level, color='#147d92', lw=1.5, label='Bottom-contiguous level, raw threshold >100')
    axes[0].set_ylabel('Estimated level (mm)')
    axes[0].set_ylim(-3, 105)
    axes[0].legend(loc='upper right', fontsize=8)
    axes[0].set_title('Water sensor: 100 ms polling | pump held OFF\n'
                      'Residual water film can cause false level; readings are not corrected')
    axes[1].plot(t, np.where(valid, a[:, 7], np.nan), label='Bottom segment raw', lw=1.2)
    axes[1].plot(t, np.where(valid, a[:, 8:].max(axis=1), np.nan),
                 label='Maximum raw of other 19 segments', alpha=.7, lw=1)
    axes[1].axhline(100, color='gray', ls='--', label='Detection threshold')
    axes[1].set_ylim(-5, 265)
    axes[1].set_ylabel('Raw sensor value')
    axes[1].legend(loc='upper right', fontsize=8)
    axes[2].plot(t[1:], intervals, lw=.8, color='#9456a6')
    axes[2].axhline(100, color='gray', ls='--')
    axes[2].set_ylabel('Interval (ms)')
    axes[2].set_xlabel('Seconds from start of displayed window (last 10 minutes)')
    for ax in axes:
        ax.grid(True, alpha=.2)
    fig.tight_layout()
    tmp = OUT / 'latest.tmp.png'
    fig.savefig(tmp, dpi=140)
    plt.close(fig)
    os.replace(tmp, OUT / 'latest.png')
    stats = {'updated_local': time.strftime('%Y-%m-%d %H:%M:%S %z'),
             'total_samples': count, 'window_samples': len(rows),
             'interval_median_ms': float(np.median(intervals)),
             'interval_min_ms': float(intervals.min()),
             'interval_max_ms': float(intervals.max()),
             'latest_level_mm': int(a[-1, 4]),
             'invalid_samples_in_window': int((~valid).sum()),
             'sequence_gaps_in_window': int(np.maximum(np.diff(a[:, 0])-1, 0).sum())}
    (OUT / 'status.json').write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats), flush=True)

(OUT / 'live.html').write_text('''<!doctype html><meta charset="utf-8">
<meta http-equiv="refresh" content="5"><title>Water sensor live plot</title>
<body style="font-family:system-ui;margin:20px;background:#f7f8fa">
<h2>Water sensor — 100 ms polling</h2><p>Refreshes every 5 seconds while the recorder runs.
Raw readings may include residual water film. Pump held OFF.</p>
<img src="latest.png" style="width:100%;max-width:1200px"><p><a href="samples.csv">Raw CSV</a></p></body>''')

rows = deque(maxlen=6000)
count = 0
last_plot = time.monotonic()
with serial.Serial('/dev/cu.wchusbserial110', 115200, timeout=.3) as port, \
        (OUT / 'samples.csv').open('w', newline='', buffering=1) as handle:
    port.dtr = False
    port.rts = False
    writer = csv.writer(handle)
    writer.writerow(['host_unix_s'] + FIELDS)
    while running:
        line = port.readline().decode(errors='replace').strip()
        parts = line.split(',')
        if len(parts) == len(FIELDS):
            try:
                values = [int(v) for v in parts]
            except ValueError:
                continue
            rows.append(values)
            writer.writerow([f'{time.time():.6f}'] + values)
            count += 1
        if time.monotonic() - last_plot >= 5:
            plot(list(rows), count)
            last_plot = time.monotonic()
    plot(list(rows), count)
