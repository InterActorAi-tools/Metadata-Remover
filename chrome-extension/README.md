# Metadata Remover — Chrome extension (Manifest V3)

Drag a file into the popup and it's sent to the hosted Metadata Remover web tool,
stripped in memory (never stored), and the clean copy is downloaded back.

> Unlike the macOS app, the extension is a thin client — it calls a hosted
> backend endpoint. To use your own backend, change the URLs in `manifest.json`
> (`host_permissions`) and `popup.js`.

## Install (unpacked, for development)
1. Open `chrome://extensions`
2. Enable **Developer mode** (top right)
3. Click **Load unpacked** and select this folder

## Files
- `manifest.json` — MV3 manifest (popup action + host permission for the backend).
- `popup.html` / `popup.css` / `popup.js` — the drag-and-drop UI and upload logic.
- `icons/` — toolbar/store icons.
