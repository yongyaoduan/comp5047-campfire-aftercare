"""Generate clear English prompts on macOS; WAV files and header are committed.
Playback/building firmware does not require macOS or a network connection.
"""
from pathlib import Path
import struct
import subprocess
import tempfile
import wave

ROOT = Path(__file__).resolve().parent
PHRASES = [('water', 'I need more water.'),
           ('fire', "The fire is burning. Show me a heart, I'll put it out."),
           ('love', 'I love you.')]
RATE = 16000

def main():
    lines = ['#pragma once', '#include <stdint.h>',
             f'static constexpr unsigned AUDIO_RATE = {RATE};']
    with tempfile.TemporaryDirectory() as tmp:
        for name, text in PHRASES:
            aiff = Path(tmp) / f'{name}.aiff'
            wav = ROOT / f'{name}.wav'
            subprocess.run(['say', '-v', 'Samantha', '-r', '155', '-o', str(aiff), text], check=True)
            subprocess.run(['afconvert', '-f', 'WAVE', '-d', f'LEI16@{RATE}', '-c', '1', str(aiff), str(wav)], check=True)
            with wave.open(str(wav), 'rb') as f:
                assert (f.getnchannels(), f.getsampwidth(), f.getframerate()) == (1, 2, RATE)
                pcm = [x[0] for x in struct.iter_unpack('<h', f.readframes(f.getnframes()))]
            peak = max(1, max(map(abs, pcm)))
            samples = [128] * 400 + [128 + round(x * 72 / peak) for x in pcm] + [128] * 400
            lines.append(f'static const uint8_t AUDIO_{name.upper()}[] = {{')
            lines.extend('  ' + ','.join(map(str, samples[i:i+32])) + ',' for i in range(0, len(samples), 32))
            lines.append('};')
            print(f'{name}: {len(samples)/RATE:.2f} s')
    (ROOT.parent / 'AudioSamples.h').write_text('\n'.join(lines) + '\n')

if __name__ == '__main__':
    main()
