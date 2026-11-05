#!/bin/bash
# Unit tests + photo-regression build for the laptop (Apple Vision) program.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"; B="$DIR/build/tests"; mkdir -p "$B"
swiftc -swift-version 5 "$DIR/Sources/HeartDetector.swift" "$DIR/Tests/HeartDetectorTests.swift" -o "$B/HeartDetectorTests"
"$B/HeartDetectorTests"
swiftc -swift-version 5 -O -framework Vision -framework AppKit \
  "$DIR/Sources/HeartDetector.swift" "$DIR/Sources/VisionPipeline.swift" "$DIR/Tools/PhotoRegression.swift" \
  -o "$B/PhotoRegression"
swiftc -swift-version 5 -typecheck -framework AppKit -framework AVFoundation -framework CoreBluetooth \
  -framework Vision -framework CoreMedia -framework CoreVideo "$DIR"/Sources/*.swift
echo "Laptop program: unit tests pass, app and PhotoRegression build"
echo "Photo regression: $B/PhotoRegression <corpus-with-results.json> <out.json>"
