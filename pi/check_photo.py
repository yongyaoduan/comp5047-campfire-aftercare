#!/usr/bin/env python3
"""Run the same person/heart recognizer on a still image, without camera or BLE."""

import argparse
from pathlib import Path

import cv2

from app import WebcamProcessor
from gesture_core import classify_heart


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--max-height", type=int, default=1024)
    args = parser.parse_args()
    frame = cv2.imread(str(args.image))
    if frame is None:
        raise SystemExit(f"Cannot read image: {args.image}")
    if frame.shape[0] > args.max_height:
        width = round(frame.shape[1] * args.max_height / frame.shape[0])
        frame = cv2.resize(frame, (width, args.max_height))
    root = Path(__file__).resolve().parent
    recognizer = WebcamProcessor("0", 640, 480, 15,
                                 root / "models/hand_landmarker.task",
                                 root / "models/pose_landmarker_lite.task",
                                 mirror=False, open_camera=False)
    try:
        result = recognizer.analyze(frame)
    finally:
        recognizer.close()
    print(f"person={result.person} people={result.people_count} pose={result.pose is not None} "
          f"hands={len(result.hands)} heart={classify_heart(result.hands) or 'none'}")


if __name__ == "__main__":
    main()
