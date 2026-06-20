# Metadata Remover

Strip hidden metadata — EXIF/GPS, author, device & app info, XMP, document
properties, and video tags — from your files.

This repository contains two open-source clients:

- **[`mac-app/`](mac-app/)** — a fully **offline** native macOS app (PyWebView +
  Python). Files are read, cleaned, and saved locally; nothing is uploaded.
- **[`chrome-extension/`](chrome-extension/)** — a Chrome (Manifest V3) extension
  that cleans files via the hosted Metadata Remover web tool.

## Supported files
Images (JPEG, PNG, TIFF, BMP, WebP, GIF), PDF, Office (docx, xlsx, pptx), and
video (MP4, MOV, MKV, WebM, AVI).

## How it strips metadata
- **Images** — rebuilt from pixel data only (kills EXIF/XMP/ICC/text/GPS).
- **PDF** — drops the document-info dictionary and XMP metadata.
- **Office** — removes `docProps/*` and their references so the file stays valid.
- **Video** — `ffmpeg` stream-copy with all metadata, chapters, and data streams
  dropped (timed GPS lives there on some phones).

The core engine is [`mac-app/metadata.py`](mac-app/metadata.py).

See each folder's README for build/install instructions.

## License
MIT — see [LICENSE](LICENSE).
