const STRIP_URL = "https://tools-inter.actor/api/strip";
const MAX = 200 * 1024 * 1024;

const el = (id) => document.getElementById(id);
const drop = el("drop"), fileInput = el("file");
let cleanBlob = null, cleanName = "clean";

drop.onclick = () => fileInput.click();
fileInput.onchange = () => { if (fileInput.files[0]) handle(fileInput.files[0]); };
["dragover", "dragenter"].forEach((e) =>
  drop.addEventListener(e, (ev) => { ev.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((e) =>
  drop.addEventListener(e, (ev) => { ev.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (ev) => { if (ev.dataTransfer.files[0]) handle(ev.dataTransfer.files[0]); });
el("save").onclick = saveClean;

function showBar(indet) {
  el("bar").classList.remove("hide");
  el("bar").classList.toggle("indet", !!indet);
  if (!indet) el("fill").style.width = "0%";
}
function setBar(p) { el("bar").classList.remove("indet"); el("fill").style.width = p + "%"; }
function hideBar() { el("bar").classList.add("hide"); el("bar").classList.remove("indet"); }

async function handle(file) {
  const msg = el("msg"); msg.className = "msg"; el("result").classList.add("hide");
  if (file.size > MAX) { msg.className = "msg err"; msg.textContent = "File too large (max 200 MB)."; return; }
  el("dtitle").textContent = file.name;
  el("dsub").textContent = (file.size / 1024).toFixed(0) + " KB";
  showBar(false);

  const xhr = new XMLHttpRequest();
  xhr.open("POST", STRIP_URL);
  xhr.responseType = "blob";
  try { xhr.setRequestHeader("X-Filename", encodeURIComponent(file.name).replace(/%20/g, " ")); } catch (e) {}
  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) {
      const p = Math.round((e.loaded / e.total) * 100);
      if (p < 100) { setBar(p); msg.textContent = "Uploading… " + p + "%"; }
      else { showBar(true); msg.textContent = "Cleaning in memory…"; }
    }
  };
  xhr.upload.onload = () => { showBar(true); msg.textContent = "Cleaning in memory…"; };
  xhr.onload = () => {
    hideBar();
    if (xhr.status >= 200 && xhr.status < 300) {
      cleanBlob = xhr.response;
      const cd = xhr.getResponseHeader("Content-Disposition") || "";
      const mm = cd.match(/filename="(.+?)"/); cleanName = mm ? mm[1] : "clean_" + file.name;
      let report = {};
      try { report = JSON.parse(decodeURIComponent(xhr.getResponseHeader("X-Metadata-Report") || "%7B%7D")); } catch (e) {}
      const removed = report.removed || [];
      el("what").textContent =
        removed.length && removed[0].indexOf("no ") !== 0
          ? "Removed: " + removed.join(", ")
          : "No hidden metadata found — a fresh, clean copy is ready.";
      msg.textContent = ""; el("result").classList.remove("hide");
    } else {
      xhr.response.text().then((t) => {
        let e = "Failed."; try { e = JSON.parse(t).error || e; } catch (_) {}
        msg.className = "msg err"; msg.textContent = e;
      }).catch(() => { msg.className = "msg err"; msg.textContent = "Failed."; });
    }
  };
  xhr.onerror = () => { hideBar(); msg.className = "msg err"; msg.textContent = "Couldn't reach the server."; };
  xhr.send(file);
}

function saveClean() {
  if (!cleanBlob) return;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(cleanBlob);
  a.download = cleanName;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1500);
}
