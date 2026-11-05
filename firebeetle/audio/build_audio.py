"""Build AudioSamples.h from the committed WAV prompts.

The WAVs were made once with macOS `say` (pass --tts to remake them). Each clip is
high-passed (a 3 cm speaker cannot play bass), compressed with a soft limiter and
scaled to the full 8-bit DAC range so the prompts are as loud as the DAC allows.
"""
from pathlib import Path
import math
import struct
import sys
import subprocess
import tempfile
import wave

ROOT = Path(__file__).resolve().parent
PHRASES = [('water', 'I need some water.'),
           ('fire', "Fire's still burning. Make a heart, I'll put it out."),
           ('love', 'I love you too.'),
           ('spray', 'Putting the fire out.'),
           ('full', 'Enough water, thank you.')]
RATE = 16000        # WAV rate
PLAY_RATE = 15200   # DAC rate: 5% slower than the WAVs, for a calmer voice
HIGHPASS_HZ = 300   # below this the small speaker only wastes amplitude
DRIVE = 16.0        # soft-limiter drive: higher = louder but harsher
PEAK = 127          # 8-bit DAC: 128 +/- 127


def loudness(pcm):
    """High-pass, soft-limit and normalise 16-bit PCM to unsigned 8-bit samples."""
    peak = max(1, max(map(abs, pcm)))
    x = [v / peak for v in pcm]
    a = 1 / (1 + 2 * math.pi * HIGHPASS_HZ / RATE)
    y, prev_x, prev_y = [], 0.0, 0.0
    for v in x:
        prev_y = a * (prev_y + v - prev_x)
        prev_x = v
        y.append(prev_y)
    peak = max(1e-9, max(map(abs, y)))
    y = [math.tanh(DRIVE * v / peak) for v in y]
    peak = max(1e-9, max(map(abs, y)))
    return [128 + round(v * PEAK / peak) for v in y]

def main():
    lines = ['#pragma once', '#include <stdint.h>',
             f'static constexpr unsigned AUDIO_RATE = {PLAY_RATE};']
    with tempfile.TemporaryDirectory() as tmp:
        for name, text in PHRASES:
            aiff = Path(tmp) / f'{name}.aiff'
            wav = ROOT / f'{name}.wav'
            if '--tts' in sys.argv or not wav.exists():
                subprocess.run(['say', '-v', 'Samantha', '-r', '100', '-o', str(aiff), text], check=True)
                subprocess.run(['afconvert', '-f', 'WAVE', '-d', f'LEI16@{RATE}', '-c', '1', str(aiff), str(wav)], check=True)
            with wave.open(str(wav), 'rb') as f:
                assert (f.getnchannels(), f.getsampwidth(), f.getframerate()) == (1, 2, RATE)
                pcm = [x[0] for x in struct.iter_unpack('<h', f.readframes(f.getnframes()))]
            samples = [128] * 400 + loudness(pcm) + [128] * 400
            lines.append(f'static const uint8_t AUDIO_{name.upper()}[] = {{')
            lines.extend('  ' + ','.join(map(str, samples[i:i+32])) + ',' for i in range(0, len(samples), 32))
            lines.append('};')
            print(f'{name}: {len(samples)/PLAY_RATE:.2f} s')
    (ROOT.parent / 'AudioSamples.h').write_text('\n'.join(lines) + '\n')

if __name__ == '__main__':
    main()
