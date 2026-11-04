"""Offline profile regression. Never opens a camera or connects to hardware."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import time

import cv2
import mediapipe
import numpy as np
from PIL import Image

from app import WebcamProcessor
from gesture_core import GestureState, PI3_TIMING

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=('full', 'pi3'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--ids', nargs='*')
    args = parser.parse_args()
    data = ROOT / 'tests/web-expanded'
    samples = json.loads((data / 'results.json').read_text())['samples']
    if args.ids:
        samples = [s for s in samples if s['id'] in args.ids]
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def run(sample):
        # OpenCV 4.11 cannot decode one GIF in the corpus; use its first frame.
        frame = cv2.imread(str(data / sample['path']))
        if frame is None:
            frame = cv2.cvtColor(np.array(Image.open(data / sample['path']).convert('RGB')),
                                 cv2.COLOR_RGB2BGR)
        h, w = frame.shape[:2]
        scale = min(640/w, 480/h)
        resized = cv2.resize(frame, (round(w*scale), round(h*scale)))
        canvas = np.zeros((480, 640, 3), dtype=np.uint8)
        y, x = (480-resized.shape[0])//2, (640-resized.shape[1])//2
        canvas[y:y+resized.shape[0], x:x+resized.shape[1]] = resized
        processor = WebcamProcessor('0', 640, 480, 15,
            ROOT/'models/hand_landmarker.task', ROOT/'models/pose_landmarker_lite.task',
            False, open_camera=False, profile=args.profile)
        state, frames = GestureState(PI3_TIMING if args.profile == "pi3" else None), []
        try:
            for i in range(5):
                start = time.perf_counter()
                obs = processor.analyze(canvas, i*.1)
                elapsed = time.perf_counter()-start
                # Logical timestamps isolate classification from hardware speed.
                state.observe(replace(obs, completed_at=i*.1))
                frames.append(dict(green=state.safe_person(i*.1),
                                   pump=state.safe_heart(i*.1), seconds=elapsed))
        finally:
            processor.close()
        row = dict(id=sample['id'], expected_person=sample['expected_person'],
                   expected_heart=sample['expected_heart'],
                   green=any(f['green'] for f in frames),
                   pump=any(f['pump'] for f in frames), frames=frames)
        print(sample['id'], row['green'], row['pump'], flush=True)
        return row

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(run, samples))
    summary = dict(samples=len(rows),
        person_positives=sum(r['expected_person'] is True for r in rows),
        person_true_positive=sum(r['expected_person'] is True and r['green'] for r in rows),
        person_negatives=sum(r['expected_person'] is False for r in rows),
        green_false_positive=sum(r['expected_person'] is False and r['green'] for r in rows),
        heart_positives=sum(r['expected_heart'] is True for r in rows),
        heart_true_positive=sum(r['expected_heart'] is True and r['pump'] for r in rows),
        heart_negatives=sum(r['expected_heart'] is False for r in rows),
        pump_false_positive=sum(r['expected_heart'] is False and r['pump'] for r in rows))
    result = dict(profile=args.profile, mediapipe=mediapipe.__version__,
        code_hash=hashlib.sha256((ROOT/'app.py').read_bytes()+(ROOT/'gesture_core.py').read_bytes()).hexdigest(),
        policy='640x480 letterbox, independently reset per image, five frames with virtual timestamps; not a realtime or independent accuracy benchmark',
        summary=summary, samples=rows)
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
