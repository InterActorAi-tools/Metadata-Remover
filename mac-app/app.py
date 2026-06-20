"""Metadata Remover — offline macOS app.

A native window (PyWebView/WKWebView) over the same in-memory strip engine used by
the web tool (metadata.py). Everything happens on-device: files are read, cleaned,
and written locally — nothing is uploaded anywhere. ffmpeg for video is bundled in
./bin and put on PATH so metadata.py finds it.
"""

import base64
import json
import os
import shutil
import subprocess
import sys
import urllib.request

VERSION = "1.0.1"
UPDATE_URL = "https://tools-inter.actor/app/metadata-remover/latest.json"


def _vtuple(s):
    out = []
    for p in str(s).split("."):
        try:
            out.append(int(p))
        except ValueError:
            out.append(0)
    return tuple(out)


def _res(name):
    """Locate a bundled resource (works in dev and inside a PyInstaller .app)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


# Put the bundled ffmpeg/ffprobe on PATH BEFORE importing the strip engine,
# so metadata.py's shutil.which("ffmpeg") finds it.
_BIN = _res("bin")
if os.path.isdir(_BIN):
    os.environ["PATH"] = _BIN + os.pathsep + os.environ.get("PATH", "")

import webview          # noqa: E402
import metadata         # noqa: E402


def _outpath(folder, name):
    """A non-clobbering output path: 'photo (clean).jpg'."""
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    suffix = ("." + ext) if ext else ""
    cand = os.path.join(folder, "%s (clean)%s" % (stem, suffix))
    i = 2
    while os.path.exists(cand):
        cand = os.path.join(folder, "%s (clean %d)%s" % (stem, i, suffix))
        i += 1
    return cand


class Api:
    """Bridge exposed to the page as window.pywebview.api.*"""

    def pick_clean(self):
        win = webview.windows[0]
        paths = win.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True)
        if not paths:
            return {"cancelled": True}
        return {"results": [self._do_path(p) for p in paths]}

    def clean_dropped(self, name, dataurl):
        try:
            data = base64.b64decode(dataurl.split(",", 1)[-1])
        except Exception:
            return {"results": [{"name": name, "error": "Could not read the dropped file."}]}
        folder = os.path.expanduser("~/Downloads")
        return {"results": [self._do_bytes(name, data, folder)]}

    def reveal(self, path):
        try:
            subprocess.run(["open", "-R", path], check=False)
        except Exception:
            pass
        return True

    # ---- updates (the only part that touches the network) ----
    def check_update(self):
        try:
            req = urllib.request.Request(UPDATE_URL, headers={"User-Agent": "MetadataRemover/%s" % VERSION})
            with urllib.request.urlopen(req, timeout=8) as r:
                m = json.load(r)
        except Exception:
            return {"ok": False, "update": False}   # offline / unreachable
        latest = str(m.get("version", "0"))
        if _vtuple(latest) > _vtuple(VERSION):
            return {"ok": True, "update": True, "version": latest,
                    "notes": m.get("notes", ""), "url": m.get("url", "")}
        return {"ok": True, "update": False, "version": VERSION}

    def install_update(self, url):
        if not url:
            return {"ok": False, "error": "No download link was provided."}
        try:
            dest = os.path.expanduser("~/Downloads/Metadata Remover Update.dmg")
            req = urllib.request.Request(url, headers={"User-Agent": "MetadataRemover/%s" % VERSION})
            with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as f:
                shutil.copyfileobj(r, f)
            subprocess.run(["open", dest], check=False)   # mount the DMG for the user
            return {"ok": True, "path": dest}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ---- internals ----
    def _do_path(self, path):
        try:
            with open(path, "rb") as f:
                data = f.read()
        except Exception as e:
            return {"name": os.path.basename(path), "error": str(e)}
        return self._do_bytes(os.path.basename(path), data, os.path.dirname(path))

    def _do_bytes(self, name, data, folder):
        try:
            clean, report = metadata.strip_metadata(name, data)
        except metadata.UnsupportedFile as e:
            return {"name": name, "error": str(e)}
        except metadata.ProcessingError as e:
            return {"name": name, "error": str(e)}
        except Exception:
            return {"name": name, "error": "Could not process this file."}
        try:
            out = _outpath(folder, name)
            with open(out, "wb") as f:
                f.write(clean)
        except Exception as e:
            return {"name": name, "error": "Could not save the cleaned file: %s" % e}
        return {"name": name, "out": out, "removed": report.get("removed") or []}


HTML = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--ink:#0f172a;--muted:#64748b;--line:#e2e8f0;--teal:#10b981;--cyan:#06b6d4}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{font-family:-apple-system,'SF Pro Text',system-ui,sans-serif;color:var(--ink);
  background:linear-gradient(135deg,#ecfdf5,#ecfeff,#eff6ff);min-height:100vh}
.wrap{max-width:680px;margin:0 auto;padding:26px 22px 36px}
.head{display:flex;align-items:center;gap:13px;margin-bottom:6px}
.logo{width:46px;height:46px;border-radius:14px;display:grid;place-items:center;font-size:24px;
  background:linear-gradient(135deg,var(--teal),var(--cyan));box-shadow:0 10px 24px rgba(6,182,212,.35)}
h1{font-size:21px;margin:0;font-family:'SF Pro Display',system-ui;letter-spacing:-.3px}
.sub{color:var(--muted);font-size:13px;margin:2px 0 0}
.priv{background:linear-gradient(135deg,#ecfdf5,#ecfeff);border:1px solid #a7f3d0;border-radius:14px;
  padding:12px 15px;margin:16px 0;font-size:12.5px;color:#0f5132;line-height:1.6}
.priv b{color:#065f46}
.card{background:#fff;border:1px solid var(--line);border-radius:20px;padding:22px;
  box-shadow:0 18px 50px rgba(15,23,42,.08)}
.drop{border:2px dashed #a7f3d0;border-radius:16px;padding:34px 18px;text-align:center;cursor:pointer;
  background:#f8fffd;transition:border .15s,background .15s}
.drop.over,.drop:hover{border-color:var(--teal);background:#ecfdf5}
.dropicon{font-size:40px;line-height:1}
.drop p{margin:8px 0 0;font-weight:600}
.drop .hint{font-weight:400;color:var(--muted);font-size:12.5px;margin-top:3px}
.btn{margin-top:14px;width:100%;border:0;border-radius:13px;padding:13px;font-weight:700;font-size:15px;
  color:#fff;background:linear-gradient(135deg,var(--teal),var(--cyan));cursor:pointer;
  box-shadow:0 10px 24px rgba(6,182,212,.32)}
.btn:active{transform:translateY(1px)}
.res{margin-top:16px;display:flex;flex-direction:column;gap:10px}
.row{border:1px solid var(--line);border-radius:14px;padding:13px 15px;background:#fcfffe}
.row.err{border-color:#fecaca;background:#fff5f5}
.row .nm{font-weight:700;font-size:14px;display:flex;align-items:center;gap:8px}
.row .meta{font-size:12px;color:var(--muted);margin-top:4px;line-height:1.5}
.tags{margin-top:6px;display:flex;flex-wrap:wrap;gap:5px}
.tag{font-size:10.5px;font-weight:600;background:#eef2ff;color:#4338ca;border-radius:999px;padding:3px 9px}
.reveal{margin-top:8px;font-size:12px;font-weight:600;color:var(--cyan);background:none;border:1px solid #cffafe;
  border-radius:9px;padding:6px 11px;cursor:pointer}
.reveal:hover{background:#ecfeff}
.foot{text-align:center;color:var(--muted);font-size:11.5px;margin-top:22px}
.upd{background:linear-gradient(135deg,#eef2ff,#ecfeff);border:1px solid #c7d2fe;border-radius:14px;
  padding:13px 15px;margin-bottom:14px}
.updt{font-size:14px;color:#3730a3}
.updn{font-size:12px;color:#475569;margin-top:5px;line-height:1.5}
.updb{margin-top:10px;border:0;border-radius:10px;padding:9px 14px;font-weight:700;font-size:13px;color:#fff;
  background:linear-gradient(135deg,#6366f1,#06b6d4);cursor:pointer}
.updb:disabled{opacity:.6}
.spin{display:inline-block;width:13px;height:13px;border:2px solid #cbd5e1;border-top-color:var(--teal);
  border-radius:50%;animation:sp .8s linear infinite;vertical-align:-2px}
@keyframes sp{to{transform:rotate(360deg)}}
</style></head><body>
<div class="wrap">
  <div id="upd" style="display:none"></div>
  <div class="head">
    <div class="logo">&#129529;</div>
    <div><h1>Metadata Remover</h1><p class="sub">Strip hidden data from your files &mdash; fully offline.</p></div>
  </div>
  <div class="priv">
    <b>&#128274; Nothing leaves your Mac.</b> Files are read, cleaned in memory, and a clean copy is
    saved next to the original (dropped files go to Downloads). No internet, no servers, no uploads.
  </div>
  <div class="card">
    <div class="drop" id="drop">
      <div class="dropicon">&#128228;</div>
      <p>Drop files here</p>
      <p class="hint">images &middot; PDF &middot; Office &middot; video (MP4, MOV&hellip;)</p>
    </div>
    <button class="btn" id="pick">Choose files&hellip;</button>
    <div class="res" id="res"></div>
  </div>
  <div class="foot">Removes EXIF/GPS, author, device &amp; app info, XMP, document properties, and video metadata.<br>
    <span style="opacity:.7">v__VERSION__</span> &middot;
    <a href="#" id="ucheck" style="color:var(--cyan);text-decoration:none;font-weight:600">Check for updates</a>
    <span id="ustatus" style="opacity:.75;margin-left:4px"></span></div>
</div>
<script>
var ready=false;
window.addEventListener('pywebviewready', function(){ ready=true; checkUpdate(false); });
function api(){ return window.pywebview.api; }
function ustat(t){ var s=document.getElementById('ustatus'); if(s) s.textContent=t||''; }

// manual=true when the user clicks "Check for updates" (shows up-to-date / offline status).
async function checkUpdate(manual){
  if(manual) ustat('Checking…');
  var u; try{ u=await api().check_update(); }catch(e){ u={ok:false}; }
  if(!u || !u.ok){ if(manual) ustat('Couldn’t check — you may be offline.'); return; }
  if(u.update){
    if(!manual){ try{ if(localStorage.getItem('mr_skip')===u.version) return; }catch(e){} }
    ustat(''); renderUpdate(u);
  }else{
    if(manual) ustat('You’re up to date ✓');
    var bar=document.getElementById('upd'); if(bar) bar.style.display='none';
  }
}
function renderUpdate(u){
  var bar=document.getElementById('upd'); bar.className='upd'; bar.style.display='block'; bar.innerHTML='';
  var t=document.createElement('div'); t.className='updt';
  t.innerHTML='&#11014;&#65039; <b>Update available</b> &mdash; version '+esc(u.version); bar.appendChild(t);
  if(u.notes){ var n=document.createElement('div'); n.className='updn'; n.textContent=u.notes; bar.appendChild(n); }
  var row=document.createElement('div'); row.style.display='flex'; row.style.gap='8px'; row.style.marginTop='10px'; row.style.flexWrap='wrap';
  var b=document.createElement('button'); b.className='updb'; b.textContent='Download & Install';
  b.onclick=async function(){
    b.disabled=true; b.textContent='Downloading…';
    var r=await api().install_update(u.url);
    var d=document.createElement('div'); d.className='updn';
    if(r&&r.ok){ b.textContent='Installer opened';
      d.textContent='Downloaded. In the window that opened, drag the new app onto Applications to replace this one, then reopen it.'; }
    else{ b.disabled=false; b.textContent='Download & Install'; d.style.color='#b91c1c';
      d.textContent=(r&&r.error)||'Download failed. Try again, or download from the website.'; }
    bar.appendChild(d);
  };
  var later=document.createElement('button'); later.className='updb'; later.textContent='Later';
  later.style.background='#e2e8f0'; later.style.color='#334155';
  later.onclick=function(){ bar.style.display='none'; };
  row.appendChild(b); row.appendChild(later); bar.appendChild(row);
  var skip=document.createElement('a'); skip.href='#'; skip.textContent='Skip this version';
  skip.style.cssText='display:inline-block;margin-top:9px;font-size:11.5px;color:#64748b;text-decoration:none';
  skip.onclick=function(e){ e.preventDefault(); try{ localStorage.setItem('mr_skip',u.version); }catch(_){}; bar.style.display='none'; };
  bar.appendChild(skip);
}
var resEl=document.getElementById('res');
var dropEl=document.getElementById('drop');
var pickEl=document.getElementById('pick');

function esc(s){ var d=document.createElement('div'); d.textContent=(s==null?'':String(s)); return d.innerHTML; }

function busy(label){
  var r=document.createElement('div'); r.className='row';
  r.innerHTML='<div class="nm"><span class="spin"></span> '+esc(label)+'</div>';
  resEl.prepend(r); return r;
}
function shortPath(p){ if(!p)return ''; var parts=p.split('/'); return parts.slice(-2).join('/'); }

function renderResult(rr){
  var r=document.createElement('div'); r.className='row'+(rr.error?' err':'');
  var nm=document.createElement('div'); nm.className='nm';
  nm.innerHTML=(rr.error?'⚠️ ':'✅ ')+esc(rr.name);
  r.appendChild(nm);
  var meta=document.createElement('div'); meta.className='meta';
  if(rr.error){ meta.textContent=rr.error; }
  else{
    var removed=(rr.removed||[]);
    var clean=removed.length && String(removed[0]).indexOf('(no')!==0;
    meta.textContent = clean ? ('Saved to '+shortPath(rr.out)) : ('Already clean — a fresh copy was saved to '+shortPath(rr.out));
    r.appendChild(meta);
    if(clean){
      var tags=document.createElement('div'); tags.className='tags';
      removed.forEach(function(t){ var s=document.createElement('span'); s.className='tag'; s.textContent=t; tags.appendChild(s); });
      r.appendChild(tags);
    }
    var rev=document.createElement('button'); rev.className='reveal'; rev.textContent='Reveal in Finder';
    rev.onclick=function(){ api().reveal(rr.out); };
    r.appendChild(rev);
  }
  if(rr.error) r.appendChild(meta);
  return r;
}
function showResults(out){
  if(!out||out.cancelled) return;
  (out.results||[]).forEach(function(rr){ resEl.prepend(renderResult(rr)); });
}

pickEl.addEventListener('click', async function(){
  if(!ready) return;
  var b=busy('Cleaning…');
  try{ var out=await api().pick_clean(); b.remove(); showResults(out); }
  catch(e){ b.remove(); }
});

function readAsDataURL(file){ return new Promise(function(res,rej){
  var fr=new FileReader(); fr.onload=function(){res(fr.result);}; fr.onerror=rej; fr.readAsDataURL(file);
}); }

async function handleFiles(files){
  if(!ready) return;
  for(var i=0;i<files.length;i++){
    var f=files[i]; var b=busy('Cleaning '+esc(f.name)+'…');
    try{ var url=await readAsDataURL(f); var out=await api().clean_dropped(f.name,url); b.remove(); showResults(out); }
    catch(e){ b.remove(); var r=document.createElement('div'); r.className='row err';
      r.innerHTML='<div class="nm">⚠️ '+esc(f.name)+'</div><div class="meta">Could not read this file.</div>';
      resEl.prepend(r); }
  }
}
['dragenter','dragover'].forEach(function(ev){ dropEl.addEventListener(ev,function(e){ e.preventDefault(); dropEl.classList.add('over'); }); });
['dragleave','drop'].forEach(function(ev){ dropEl.addEventListener(ev,function(e){ e.preventDefault(); dropEl.classList.remove('over'); }); });
dropEl.addEventListener('drop', function(e){ var f=e.dataTransfer&&e.dataTransfer.files; if(f&&f.length) handleFiles(f); });
dropEl.addEventListener('click', function(){ pickEl.click(); });
document.getElementById('ucheck').addEventListener('click', function(e){ e.preventDefault(); checkUpdate(true); });
</script>
</body></html>"""


def main():
    webview.create_window("Metadata Remover", html=HTML.replace("__VERSION__", VERSION), js_api=Api(),
                          width=860, height=720, min_size=(660, 560))
    webview.start()


if __name__ == "__main__":
    main()
