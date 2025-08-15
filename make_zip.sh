#!/usr/bin/env bash
set -euo pipefail
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR_NAME="geopackage_replacer"
ZIP_NAME="${PLUGIN_DIR_NAME}.zip"

cd "$BASE_DIR"

# Build resources WITHOUT using the broken wrapper
if [ -f resources.qrc ]; then
  ./build_resources.sh
fi

# Ensure resources_rc.py exists
if [ ! -f resources_rc.py ]; then
  echo "[zip] ERROR: resources_rc.py was not generated."
  exit 1
fi

# Clean caches
find "$BASE_DIR" -name "__pycache__" -type d -exec rm -rf {} + || true

# Build temporary tree and zip
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

mkdir -p "$TMPDIR/$PLUGIN_DIR_NAME"
cp -r __init__.py metadata.txt geopackage_replacer.py resources.qrc resources_rc.py README.md LICENSE resources "$TMPDIR/$PLUGIN_DIR_NAME"/

(
  cd "$TMPDIR"
  zip -r "$ZIP_NAME" "$PLUGIN_DIR_NAME" -x "*.DS_Store" > /dev/null
)

# Overwrite any previous zip in the plugin directory
mv -f "$TMPDIR/$ZIP_NAME" "$BASE_DIR/$ZIP_NAME"

echo "[zip] OK: package generated at $BASE_DIR/$ZIP_NAME"