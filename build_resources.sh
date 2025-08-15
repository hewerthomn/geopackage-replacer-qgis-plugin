#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Candidate QGIS bundles on macOS (adjust if needed)
CAND=(
  "/Applications/QGIS-LTR.app/Contents/MacOS/bin"
  "/Applications/QGIS.app/Contents/MacOS/bin"
  "/Applications/QGIS3.app/Contents/MacOS/bin"
)

# 1) Prefer the bundle's python + PyQt5.pyrcc_main
for d in "${CAND[@]}"; do
  if [ -x "$d/python3" ] && "$d/python3" -c "import PyQt5.pyrcc_main" >/dev/null 2>&1; then
    echo "[build] Using: $d/python3 -m PyQt5.pyrcc_main"
    "$d/python3" -m PyQt5.pyrcc_main -o resources_rc.py resources.qrc
    echo "[build] OK: resources_rc.py"
    exit 0
  fi
done

# 2) Try the real binary with the bundle's Python
for d in "${CAND[@]}"; do
  if [ -x "$d/python3" ] && [ -f "$d/pyrcc5.bin" ]; then
    echo "[build] Using: $d/python3 $d/pyrcc5.bin"
    "$d/python3" "$d/pyrcc5.bin" -o resources_rc.py resources.qrc
    echo "[build] OK: resources_rc.py"
    exit 0
  fi
done

# 3) Fallback: pyrcc5 from PATH (Linux/Windows/conda etc.)
if command -v pyrcc5 >/dev/null 2>&1; then
  echo "[build] Using: $(command -v pyrcc5)"
  pyrcc5 -o resources_rc.py resources.qrc
  echo "[build] OK: resources_rc.py"
  exit 0
fi

# 4) Last resort: local python3 with PyQt5 available
if python3 -c "import PyQt5.pyrcc_main" >/dev/null 2>&1; then
  echo "[build] Using: python3 -m PyQt5.pyrcc_main"
  python3 -m PyQt5.pyrcc_main -o resources_rc.py resources.qrc
  echo "[build] OK: resources_rc.py"
  exit 0
fi

echo "[build] ERROR: could not generate resources_rc.py."
echo "       Try running manually:
       /Applications/QGIS-LTR.app/Contents/MacOS/bin/python3 -m PyQt5.pyrcc_main -o resources_rc.py resources.qrc"
exit 1