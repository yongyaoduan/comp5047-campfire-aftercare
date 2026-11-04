#!/usr/bin/env python3
"""Fetch versioned official MediaPipe model assets and verify their contents."""

from hashlib import sha256
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent / "models"
MODELS = {
    "selfie_multiclass_256x256.tflite": (
        "https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_multiclass_256x256/float32/1/selfie_multiclass_256x256.tflite",
        "c6748b1253a99067ef71f7e26ca71096cd449baefa8f101900ea23016507e0e0",
    ),
    "efficientdet_lite0.tflite": (
        "https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float16/1/efficientdet_lite0.tflite",
        "4b59100025bea1235a84c1038879a6cccc9f6c49f5e41144e91e74d99e780993",
    ),
    "blaze_face_short_range.tflite": (
        "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite",
        "b4578f35940bf5a1a655214a1cce5cab13eba73c1297cd78e1a04c2380b0152f",
    ),
    "hand_landmarker.task": (
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
        "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1",
    ),
    "pose_landmarker_lite.task": (
        "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task",
        "59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a",
    ),
}


def download() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    for filename, (url, digest) in MODELS.items():
        target = ROOT / filename
        if target.is_file() and sha256(target.read_bytes()).hexdigest() == digest:
            print(f"Verified {target}")
            continue
        temporary = ROOT / (filename + ".part")
        print(f"Downloading {filename} ...")
        try:
            with urlopen(url, timeout=60) as source, temporary.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
            if sha256(temporary.read_bytes()).hexdigest() != digest:
                raise RuntimeError(f"SHA-256 mismatch for {filename}")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        print(f"Ready: {target}")


if __name__ == "__main__":
    download()
