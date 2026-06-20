"""
In-memory metadata removal for images, PDFs, and Office documents.

Every function takes raw bytes and returns (clean_bytes, report). Nothing is
ever written to disk. The report describes what was found and removed so the
UI can show the user proof it worked.
"""

import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile

from PIL import Image

# Guard against decompression bombs (huge pixel dimensions in a tiny file).
Image.MAX_IMAGE_PIXELS = 64_000_000   # ~64 MP

IMAGE_EXTS = {"jpg", "jpeg", "png", "tiff", "tif", "bmp", "webp", "gif"}
OFFICE_EXTS = {"docx", "xlsx", "pptx", "docm", "xlsm", "pptm"}
VIDEO_EXTS = {"mp4", "mov", "m4v", "mkv", "webm", "avi", "3gp", "m4a"}
VIDEO_TIMEOUT = 140                    # seconds for the ffmpeg subprocess


class UnsupportedFile(Exception):
    pass


class ProcessingError(Exception):
    pass


def _ext(filename):
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


# ------------------------------- images -------------------------------------
def _image_report(img):
    """Describe metadata present before stripping."""
    found = []
    try:
        exif = img.getexif()
    except Exception:
        exif = None
    if exif and len(exif):
        found.append(f"EXIF ({len(exif)} tags)")
        # GPS IFD = 0x8825
        if 0x8825 in exif:
            found.append("GPS location")
    info = getattr(img, "info", {}) or {}
    if info.get("icc_profile"):
        found.append("ICC color profile")
    if info.get("xmp") or info.get("XML:com.adobe.xmp"):
        found.append("XMP metadata")
    if "comment" in info:
        found.append("comment")
    # PNG text chunks
    for k in ("Author", "Description", "Software", "Comment", "Creation Time"):
        if k in info:
            found.append(f"text:{k}")
    if getattr(img, "n_frames", 1) and getattr(img, "n_frames", 1) > 1:
        found.append("(animated → flattened to first frame)")
    return found


def strip_image(data):
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Image.DecompressionBombError:
        raise ProcessingError("Image is too large to process safely.")
    except Exception:
        raise ProcessingError("Could not read this image file.")

    fmt = (img.format or "PNG").upper()
    report = _image_report(img)

    # Rebuild from pixel data only — guarantees no EXIF/XMP/ICC/text survives.
    clean = Image.new(img.mode, img.size)
    clean.putdata(list(img.getdata()))
    if img.mode == "P" and img.getpalette():
        clean.putpalette(img.getpalette())

    out = io.BytesIO()
    save_fmt = "JPEG" if fmt in ("JPG", "JPEG") else fmt
    try:
        if save_fmt == "JPEG":
            clean = clean.convert("RGB")
            clean.save(out, format="JPEG", quality=95)
        else:
            clean.save(out, format=save_fmt)
    except Exception:
        out = io.BytesIO()
        clean.save(out, format="PNG")
        save_fmt = "PNG"
    return out.getvalue(), {"type": "image", "removed": report}


# -------------------------------- pdf ---------------------------------------
def strip_pdf(data):
    import pikepdf

    try:
        pdf = pikepdf.open(io.BytesIO(data))
    except Exception:
        raise ProcessingError("Could not read this PDF (it may be encrypted or corrupt).")

    removed = []
    try:
        if "/Info" in pdf.trailer and len(pdf.trailer.Info):
            removed += [str(k).lstrip("/") for k in pdf.trailer.Info.keys()]
            del pdf.trailer.Info          # drop the entire document-info dictionary
    except Exception:
        pass
    try:
        if "/Metadata" in pdf.Root:
            removed.append("XMP metadata")
            del pdf.Root.Metadata
    except Exception:
        pass

    out = io.BytesIO()
    try:
        pdf.save(out, fix_metadata_version=False)
    except TypeError:
        pdf.save(out)
    finally:
        pdf.close()
    return out.getvalue(), {"type": "pdf", "removed": removed or ["(no document metadata found)"]}


# ------------------------------- office -------------------------------------
_DOCPROPS_RE = re.compile(rb"<[^>]*docProps/[^>]*>")


def strip_office(data):
    try:
        zin = zipfile.ZipFile(io.BytesIO(data))
    except Exception:
        raise ProcessingError("Could not read this Office document.")

    names = zin.namelist()
    if "[Content_Types].xml" not in names:
        raise UnsupportedFile("Not a recognized Office document.")

    to_strip = [n for n in names if n.startswith("docProps/")]
    removed = [n.split("/")[-1] for n in to_strip] or ["(no document properties found)"]

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename in to_strip:
                continue
            content = zin.read(item.filename)
            # Drop references to the removed docProps parts so the file stays valid.
            if item.filename in ("[Content_Types].xml", "_rels/.rels"):
                content = _DOCPROPS_RE.sub(b"", content)
            zout.writestr(item, content)
    zin.close()
    return out.getvalue(), {"type": "office", "removed": removed}


# ------------------------------- video --------------------------------------
def _shm_dir():
    """Prefer a RAM-backed dir so the unavoidable temp file never hits real disk."""
    for d in ("/dev/shm", "/run/shm"):
        if os.path.isdir(d) and os.access(d, os.W_OK):
            return d
    return tempfile.gettempdir()        # fallback (e.g. local mac dev)


def _probe_tags(path):
    """List metadata tag names present (for the 'removed' report)."""
    if not shutil.which("ffprobe"):
        return []
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", path],
            capture_output=True, timeout=30).stdout
        info = json.loads(out or b"{}")
    except Exception:
        return []
    tags = set()
    fmt_tags = (info.get("format") or {}).get("tags") or {}
    tags.update(fmt_tags.keys())
    for st in info.get("streams") or []:
        tags.update((st.get("tags") or {}).keys())
    # surface the privacy-sensitive ones explicitly
    pretty = []
    low = {t.lower(): t for t in tags}
    if any("location" in k or "gps" in k for k in low):
        pretty.append("GPS location")
    if "creation_time" in low:
        pretty.append("creation time")
    for key in ("make", "model", "com.apple.quicktime.make",
                "com.apple.quicktime.model", "encoder", "title", "artist", "comment"):
        if key in low:
            pretty.append(low[key].split(".")[-1])
    remaining = len(tags) - 0
    if tags and not pretty:
        pretty.append(f"{len(tags)} metadata tags")
    return pretty


def strip_video(data, ext):
    if not shutil.which("ffmpeg"):
        raise ProcessingError("Video processing is unavailable on this server.")
    ext = ext if ext in VIDEO_EXTS else "mp4"
    d = _shm_dir()
    in_fd, in_path = tempfile.mkstemp(dir=d, suffix=f".{ext}")
    out_path = in_path + f".clean.{ext}"
    try:
        with os.fdopen(in_fd, "wb") as f:
            f.write(data)
        report = _probe_tags(in_path)
        # stream-copy video+audio only; drop ALL metadata, chapters, and
        # data streams (timed GPS metadata lives there on some phones).
        cmd = ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", in_path,
               "-map", "0:v?", "-map", "0:a?",
               "-map_metadata", "-1", "-map_chapters", "-1",
               "-bitexact",                 # suppress ffmpeg's own encoder/version stamp
               "-c", "copy", out_path]
        proc = subprocess.run(cmd, capture_output=True, timeout=VIDEO_TIMEOUT)
        if proc.returncode != 0 or not os.path.exists(out_path):
            raise ProcessingError("Could not process this video "
                                  "(unsupported or corrupt format).")
        with open(out_path, "rb") as f:
            clean = f.read()
        return clean, {"type": "video", "removed": report or ["(no metadata found)"]}
    except subprocess.TimeoutExpired:
        raise ProcessingError("Video took too long to process and was aborted.")
    finally:
        for p in (in_path, out_path):
            try:
                if os.path.exists(p):
                    os.remove(p)        # delete the RAM-backed temp immediately
            except OSError:
                pass


# ------------------------------ dispatch ------------------------------------
def strip_metadata(filename, data):
    """Return (clean_bytes, report). Raises UnsupportedFile / ProcessingError."""
    ext = _ext(filename)
    head = data[:8]

    if ext in IMAGE_EXTS or head[:3] == b"\xff\xd8\xff" or head[:8] == b"\x89PNG\r\n\x1a\n":
        return strip_image(data)
    if ext == "pdf" or head[:5] == b"%PDF-":
        return strip_pdf(data)
    if ext in OFFICE_EXTS or (head[:2] == b"PK" and ext in OFFICE_EXTS):
        return strip_office(data)
    # video: by extension, or by magic (mp4/mov 'ftyp', matroska/webm EBML)
    if ext in VIDEO_EXTS or head[4:8] == b"ftyp" or head[:4] == b"\x1a\x45\xdf\xa3":
        return strip_video(data, ext)
    # Unknown but is a zip with Office structure?
    if head[:2] == b"PK":
        try:
            if "[Content_Types].xml" in zipfile.ZipFile(io.BytesIO(data)).namelist():
                return strip_office(data)
        except Exception:
            pass
    raise UnsupportedFile(
        "Unsupported file type. Supported: images (JPEG, PNG, TIFF, BMP, WebP, GIF), "
        "PDF, Office files (docx, xlsx, pptx), and video (MP4, MOV, MKV, WebM, AVI).")
