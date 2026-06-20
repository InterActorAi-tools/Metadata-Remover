#!/usr/bin/env bash
# Build "Metadata Remover.app" and a distributable .dmg — fully offline.
# Usage: ./build.sh        (builds app + dmg, ad-hoc signed so it runs locally)
#        DEV_ID="Developer ID Application: Your Name (TEAMID)" ./build.sh   (real sign)
set -euo pipefail
cd "$(dirname "$0")"
APP="Metadata Remover"
PY="${PYTHON:-python3}"

echo "==> 1/6  Python venv + dependencies"
[ -d .venv ] || "$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt pyinstaller

echo "==> 2/6  Bundle ffmpeg (arch-correct, from imageio-ffmpeg)"
FFMPEG_SRC="$(python -c 'import imageio_ffmpeg,sys; sys.stdout.write(imageio_ffmpeg.get_ffmpeg_exe())')"
mkdir -p bin
cp -f "$FFMPEG_SRC" bin/ffmpeg
chmod +x bin/ffmpeg
echo "    ffmpeg: $(./bin/ffmpeg -version 2>/dev/null | head -1)"

echo "==> 3/6  App icon (.icns from the extension artwork)"
ICON_SRC="icon-source.png"
if [ -f "$ICON_SRC" ] && command -v iconutil >/dev/null; then
  rm -rf icon.iconset && mkdir icon.iconset
  for s in 16 32 64 128 256 512 1024; do
    sips -z $s $s "$ICON_SRC" --out "icon.iconset/icon_${s}x${s}.png" >/dev/null 2>&1 || true
  done
  # retina (@2x) variants iconutil expects
  cp icon.iconset/icon_32x32.png   icon.iconset/icon_16x16@2x.png   2>/dev/null || true
  cp icon.iconset/icon_64x64.png   icon.iconset/icon_32x32@2x.png   2>/dev/null || true
  cp icon.iconset/icon_256x256.png icon.iconset/icon_128x128@2x.png 2>/dev/null || true
  cp icon.iconset/icon_512x512.png icon.iconset/icon_256x256@2x.png 2>/dev/null || true
  cp icon.iconset/icon_1024x1024.png icon.iconset/icon_512x512@2x.png 2>/dev/null || true
  iconutil -c icns icon.iconset -o icon.icns || true
fi
ICON_FLAG=""; [ -f icon.icns ] && ICON_FLAG="--icon icon.icns"

echo "==> 4/6  PyInstaller build"
rm -rf build dist
# shellcheck disable=SC2086
pyinstaller --noconfirm --windowed --name "$APP" $ICON_FLAG \
  --add-binary "bin/ffmpeg:bin" \
  --collect-submodules webview \
  --osx-bundle-identifier "actor.tools.metadataremover" \
  app.py

echo "==> 5/6  Stamp version + copyright, then sign"
APP_VER="$(grep -E '^VERSION[[:space:]]*=' app.py | sed -E 's/.*"([^"]+)".*/\1/')"
APP_VER="${APP_VER:-1.0.0}"
COPYRIGHT="© $(date +%Y) Interactor — tools-inter.actor"
PLIST="dist/$APP.app/Contents/Info.plist"
PB=/usr/libexec/PlistBuddy
$PB -c "Set :CFBundleShortVersionString $APP_VER" "$PLIST" 2>/dev/null || $PB -c "Add :CFBundleShortVersionString string $APP_VER" "$PLIST"
$PB -c "Set :CFBundleVersion $APP_VER"            "$PLIST" 2>/dev/null || $PB -c "Add :CFBundleVersion string $APP_VER" "$PLIST"
$PB -c "Set :NSHumanReadableCopyright $COPYRIGHT" "$PLIST" 2>/dev/null || $PB -c "Add :NSHumanReadableCopyright string $COPYRIGHT" "$PLIST"
echo "    version $APP_VER · $COPYRIGHT"
if [ -n "${DEV_ID:-}" ]; then
  echo "    signing with Developer ID + hardened runtime…"
  codesign --deep --force --options runtime --timestamp \
    --entitlements entitlements.plist --sign "$DEV_ID" "dist/$APP.app"
else
  codesign --deep --force --sign - "dist/$APP.app" 2>/dev/null || true   # ad-hoc → opens locally
fi

echo "==> 6/6  Build .dmg"
STAGE="$(mktemp -d)"
cp -R "dist/$APP.app" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
rm -f "dist/$APP.dmg"
hdiutil create -volname "$APP" -srcfolder "$STAGE" -ov -format UDZO "dist/$APP.dmg" >/dev/null
rm -rf "$STAGE"

echo ""
echo "✅ Done:"
echo "   App: dist/$APP.app"
echo "   DMG: dist/$APP.dmg"
if [ -z "${DEV_ID:-}" ]; then echo "   (Unsigned for distribution — recipients right-click → Open the first time. See README to notarize.)"; fi
