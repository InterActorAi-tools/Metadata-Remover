# Metadata Remover — macOS app

A fully **offline** native macOS app that strips hidden metadata from your files.
It wraps the in-memory strip engine (`metadata.py`) in a native window
(PyWebView / WKWebView). Files are read, cleaned, and a clean copy is written
locally — nothing is ever uploaded. `ffmpeg` for video is bundled at build time.

## Run in development
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# bundle a local ffmpeg for video (optional in dev):
mkdir -p bin
cp "$(python -c 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())')" bin/ffmpeg
python app.py
```

## Build the .app and .dmg
```bash
./build.sh
```
Creates the venv, bundles an arch-correct `ffmpeg` (via `imageio-ffmpeg`), builds
the icon, runs PyInstaller, and packages a DMG into `dist/`.

## Code signing & notarization (optional, for distribution)
An unsigned build runs locally; recipients must right-click → **Open** the first
time. To distribute it so it opens with no Gatekeeper warning, sign it with an
Apple **"Developer ID Application"** certificate and notarize it:
```bash
DEV_ID="Developer ID Application: Your Name (TEAMID)" ./build.sh
xcrun notarytool submit "dist/Metadata Remover.dmg" --keychain-profile <profile> --wait
xcrun stapler staple "dist/Metadata Remover.dmg"
```
`entitlements.plist` is included — a PyInstaller/Python app needs those keys
(disable-library-validation, allow-jit) to pass notarization under the hardened
runtime.

## Privacy
- Files are processed **in memory**; the cleaned copy is written next to the
  original (dragged-in files go to `~/Downloads`).
- Video needs a brief temp file (ffmpeg can't stream-copy MOV/MP4 purely in
  memory); it's written to the system temp dir and **deleted immediately**.
- The only network call is an optional update check (`UPDATE_URL` in `app.py`) —
  change or remove it for your own fork.

## Files
- `app.py` — the app shell, native bridge, and embedded UI.
- `metadata.py` — the strip engine (pure Python for images/PDF/Office; ffmpeg for video).
- `build.sh` — one-command build → `.app` + `.dmg`.
- `entitlements.plist` — hardened-runtime entitlements for notarization.
- `requirements.txt` — Python dependencies.
