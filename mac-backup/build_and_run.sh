#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
APP_DIR="$BUILD_DIR/Campfire LED + Pump Demo.app"
CONTENTS_DIR="$APP_DIR/Contents"

mkdir -p "$CONTENTS_DIR/MacOS" "$CONTENTS_DIR/Resources"

swiftc \
  -swift-version 5 \
  -O \
  -framework AppKit \
  -framework AVFoundation \
  -framework CoreBluetooth \
  -framework Vision \
  -framework CoreMedia \
  -framework CoreVideo \
  "$SCRIPT_DIR"/Sources/*.swift \
  -o "$CONTENTS_DIR/MacOS/CampfireVisionDemo"

cp "$SCRIPT_DIR/Info.plist" "$CONTENTS_DIR/Info.plist"
codesign --force --deep --sign - \
  --entitlements "$SCRIPT_DIR/Entitlements.plist" \
  "$APP_DIR" >/dev/null

echo "Built: $APP_DIR"
open "$APP_DIR" --args "$@"
