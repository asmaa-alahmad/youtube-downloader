
from flask import Flask, request, render_template_string, jsonify
from pathlib import Path
from urllib.parse import urlparse
from threading import Thread, Lock
import yt_dlp
import time
import os
import subprocess
import sys

app = Flask(__name__)

DOWNLOAD_DIR = Path.home() / "Downloads" / "YouTube"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

lock = Lock()
progress = {
    "active": False,
    "status": "idle",
    "percent": 0,
    "downloaded": 0,
    "total": 0,
    "speed": 0,
    "eta": None,
    "message": "",
    "title": "",
}

def valid_url(url):
    try:
        p = urlparse(url)
        host = (p.hostname or "").lower()
        return p.scheme == "https" and host in {
            "youtube.com", "www.youtube.com", "m.youtube.com",
            "music.youtube.com", "youtu.be",
            "www.youtube-nocookie.com",
        }
    except ValueError:
        return False


def download_video(url):
    global progress

    def hook(data):
        status = data.get("status")

        with lock:
            if status == "downloading":
                downloaded = data.get("downloaded_bytes", 0) or 0
                total = (
                    data.get("total_bytes")
                    or data.get("total_bytes_estimate")
                    or 0
                )

                progress.update({
                    "status": "downloading",
                    "downloaded": downloaded,
                    "total": total,
                    "percent": round(downloaded / total * 100, 1)
                    if total else 0,
                    "speed": data.get("speed") or 0,
                    "eta": data.get("eta"),
                    "message": "جارٍ تنزيل الفيديو...",
                })

            elif status == "finished":
                progress.update({
                    "status": "merging",
                    "percent": 100,
                    "message": "اكتمل التنزيل، جارٍ دمج الصوت والفيديو...",
                })

    try:
        options = {
            "noplaylist": True,
            "format": "bv*+ba/b",
            "merge_output_format": "mp4",
            "outtmpl": str(
                DOWNLOAD_DIR / "%(title).180s [%(id)s].%(ext)s"
            ),
            "progress_hooks": [hook],
        }

        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])

        with lock:
            progress.update({
                "active": False,
                "status": "complete",
                "percent": 100,
                "message": "تم التحميل والدمج بنجاح!",
                "speed": 0,
                "eta": 0,
            })

    except Exception as exc:
        with lock:
            progress.update({
                "active": False,
                "status": "error",
                "message": str(exc)[:500],
            })


HTML = r"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Violet Downloader</title>
<style>
:root {
  --bg:#100d18; --panel:#191322; --field:#21192d;
  --text:#f7f2ff; --muted:#b8a8d0;
  --purple:#9b5cff; --border:#39284b;
}
body.light {
  --bg:#f5f0fc; --panel:#fff; --field:#f0e8fa;
  --text:#241633; --muted:#746382;
  --purple:#7739ce; --border:#ded0ef;
}
* {box-sizing:border-box}
body {
  margin:0; min-height:100vh;
  font-family:"Segoe UI",Tahoma,Arial,sans-serif;
  background:radial-gradient(ellipse at 50% 0%,#52258255,transparent 55%),var(--bg);
  color:var(--text); transition:.25s;
}
header {
  display:flex; align-items:center; justify-content:space-between;
  padding:22px 7%; border-bottom:1px solid var(--border);
}
.brand {display:flex;align-items:center;gap:12px}
.logo {
  width:44px;height:44px;border-radius:14px;
  display:grid;place-items:center;
  background:linear-gradient(135deg,#bd78ff,#7137d7);
  color:white;font-size:23px
}
h2 {margin:0;font-size:19px}
small,.muted {color:var(--muted)}
button {font:inherit;cursor:pointer}
.theme {
  background:var(--panel);color:var(--text);
  border:1px solid var(--border);border-radius:12px;padding:10px 14px
}
main {width:min(620px,92%);margin:65px auto;text-align:center}
.eyebrow {color:#c49aff;font-size:13px;margin-bottom:18px}
h1 {font-size:clamp(30px,5vw,43px);margin:0 0 16px}
.description {color:var(--muted);line-height:1.9;margin-bottom:30px}
.card {
  background:var(--panel);border:1px solid var(--border);
  padding:25px;border-radius:22px;text-align:right;
  box-shadow:0 20px 65px #0002
}
label {display:block;margin-bottom:12px;font-weight:600}
input {
  width:100%;padding:16px;border:1px solid var(--border);
  background:var(--field);color:var(--text);
  border-radius:12px;outline:none;font-size:15px
}
input:focus {border-color:var(--purple)}
.download {
  margin-top:15px;width:100%;padding:15px;border:0;
  border-radius:12px;color:white;font-weight:700;font-size:16px;
  background:linear-gradient(100deg,#a45aff,#7439d2)
}
.download:disabled {opacity:.6;cursor:wait}
.hint {color:var(--muted);font-size:12px;margin-top:14px}
#progressBox {
  display:none;margin-top:22px;padding:18px;
  background:var(--field);border:1px solid var(--border);
  border-radius:16px
}
.progress-head,.stats {
  display:flex;justify-content:space-between;
  align-items:center;gap:10px;flex-wrap:wrap
}
.percent {font-size:25px;font-weight:800;color:var(--purple)}
.track {
  height:12px;background:var(--border);
  border-radius:20px;overflow:hidden;margin:17px 0
}
#bar {
  height:100%;width:0%;
  background:linear-gradient(90deg,#7739d2,#c084fc);
  border-radius:20px;transition:width .25s
}
.stats {font-size:12px;color:var(--muted);line-height:1.8}
#status {margin-top:14px;line-height:1.8;overflow-wrap:anywhere}
.features {
  display:flex;flex-wrap:wrap;justify-content:center;
  gap:12px;margin-top:25px
}
.feature {
  color:var(--muted);border:1px solid var(--border);
  background:var(--panel);border-radius:30px;
  padding:10px 14px;font-size:13px
}
footer {text-align:center;color:var(--muted);padding:20px;font-size:12px}
</style>
</head>
<body>
<header>
  <div class="brand">
    <div class="logo">▶</div>
    <div><h2>Violet Downloader</h2><small>تحميل بسيط وسريع</small></div>
  </div>
  <button class="theme" id="themeBtn" onclick="toggleTheme()">☀️ الوضع الفاتح</button>
</header>

<main>
  <div class="eyebrow">✦ VIDEO DOWNLOADER</div>
  <h1>فيديوهاتك، <span style="color:var(--purple)">بلمسة واحدة.</span></h1>
  <p class="description">أدخل رابط YouTube وتابع نسبة التحميل والسرعة والوقت المتبقي مباشرة.</p>

  <form class="card" id="form">
    <label for="url">رابط الفيديو</label>
    <input id="url" type="url" required
      placeholder="https://www.youtube.com/watch?v=...">
    <button class="download" id="btn" type="submit">⬇　تحميل الفيديو</button>
    <div class="hint">يتم حفظ الفيديو على جهازك في مجلد Downloads\YouTube.</div>

    <section id="progressBox" aria-live="polite">
      <div class="progress-head">
        <strong id="progressTitle">تجهيز التحميل</strong>
        <span class="percent" id="percent">0%</span>
      </div>
      <div class="track"><div id="bar"></div></div>
      <div class="stats">
        <span id="size">0 MB / --</span>
        <span id="speed">السرعة: --</span>
        <span id="eta">المتبقي: --</span>
      </div>
      
<div id="status">جارٍ الاتصال...</div>

<button type="button" id="folderBtn"
  onclick="openDownloadFolder()"
  style="display:none; margin-top:15px; width:100%;
  padding:13px; border:1px solid #9b5cff;
  border-radius:12px; background:transparent;
  color:var(--text); font-weight:700;">
  📂 فتح مجلد التحميلات
</button>

<button type="button" id="closeBtn"
  onclick="closeInterface()"
  style="display:none; margin-top:10px; width:100%;
  padding:13px; border:0; border-radius:12px;
  background:#dc3545; color:white; font-weight:700;">
  ✖ إغلاق الواجهة
</button>

    </section>
  </form>

  <div class="features">
    <div class="feature">✦ أسود وموف</div>
    <div class="feature">◉ تقدم مباشر</div>
    <div class="feature">♫ دمج الصوت والفيديو</div>
  </div>
</main>
<footer>Violet Downloader</footer>

<script>
function toggleTheme() {
  const light = document.body.classList.toggle('light');
  document.getElementById('themeBtn').textContent =
    light ? '🌙 الوضع الداكن' : '☀️ الوضع الفاتح';
  try { localStorage.setItem('violet-theme', light ? 'light' : 'dark'); } catch(e) {}
}
try {
  if (localStorage.getItem('violet-theme') === 'light') {
    document.body.classList.add('light');
    document.getElementById('themeBtn').textContent = '🌙 الوضع الداكن';
  }
} catch(e) {}

let polling = false;
let timer = null;

function fmtBytes(n) {
  if (n == null) return '--';
  const units = ['B','KB','MB','GB','TB'];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return n.toFixed(i === 0 ? 0 : 1) + ' ' + units[i];
}
function fmtTime(s) {
  if (s == null || !Number.isFinite(Number(s))) return '--';
  s = Math.max(0, Math.round(Number(s)));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h) return `${h} ساعة ${m} دقيقة`;
  if (m) return `${m} دقيقة ${sec} ثانية`;
  return `${sec} ثانية`;
}
function showProgress(p) {

document.getElementById('closeBtn').style.display =
  p.status === 'complete' ? 'block' : 'none';
  document.getElementById('folderBtn').style.display =
  p.status === 'complete' ? 'block' : 'none';
  document.getElementById('progressBox').style.display = 'block';
  const pct = Math.max(0, Math.min(100, Number(p.percent) || 0));
  document.getElementById('percent').textContent = pct.toFixed(1) + '%';
  document.getElementById('bar').style.width = pct + '%';
  document.getElementById('size').textContent =
    fmtBytes(p.downloaded) + ' / ' + fmtBytes(p.total || null);
  document.getElementById('speed').textContent =
    'السرعة: ' + (p.speed ? fmtBytes(p.speed) + '/s' : '--');
  document.getElementById('eta').textContent =
    'المتبقي: ' + (p.status === 'complete' ? '0 ثانية' : fmtTime(p.eta));
  document.getElementById('status').textContent = p.message || '';
  document.getElementById('progressTitle').textContent =
    p.status === 'merging' ? 'جارٍ دمج الملفات' :
    p.status === 'complete' ? 'اكتمل التحميل' :
    p.status === 'error' ? 'تعذّر التحميل' : 'تقدم التحميل';

  if (p.status === 'complete' || p.status === 'error') {
    clearInterval(timer);
    timer = null;
    polling = false;
    document.getElementById('btn').disabled = false;
    document.getElementById('btn').textContent = '⬇　تحميل فيديو آخر';
  }
}
async function poll() {
  try {
    const res = await fetch('/progress');
    const p = await res.json();
    showProgress(p);
    if (!p.active && p.status !== 'complete' && p.status !== 'error') {
      clearInterval(timer);
      timer = null;
      polling = false;
    }
  } catch(e) {
    document.getElementById('status').textContent = 'انقطع الاتصال؛ جارٍ إعادة المحاولة...';
  }
}
document.getElementById('form').addEventListener('submit', async e => {
  e.preventDefault();
  if (polling) return;

  const url = document.getElementById('url').value.trim();
  const btn = document.getElementById('btn');
  btn.disabled = true;
  btn.textContent = '⏳ جارٍ بدء التحميل...';
  document.getElementById('progressBox').style.display = 'block';
  document.getElementById('status').textContent = 'جارٍ بدء التحميل...';
  document.getElementById('progressTitle').textContent = 'تهيئة الفيديو';

  try {
    const res = await fetch('/start', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({url})
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.message || 'تعذر بدء التحميل');

    polling = true;
    btn.textContent = '⏳ جارٍ التحميل...';
    await poll();
    if (polling) timer = setInterval(poll, 1000);
  } catch(err) {
    document.getElementById('status').textContent = err.message;
    btn.disabled = false;
    btn.textContent = 'إعادة المحاولة';
  }
});


async function openDownloadFolder() {
  try {
    const response = await fetch('/open-folder', {
      method: 'POST'
    });

    const data = await response.json();

    if (!response.ok) {
      alert(data.message || 'تعذر فتح المجلد');
    }
  } catch (error) {
    alert('تعذر الاتصال بالتطبيق');
  }
}
function closeInterface() {
  window.close();

  // إذا منع المتصفح إغلاق التبويب، نعرض رسالة
  setTimeout(() => {
    document.getElementById('status').textContent =
      'يمكنك إغلاق هذا التبويب يدويًا.';
  }, 300);
}
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/start", methods=["POST"])
def start_download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()

    if not valid_url(url):
        return jsonify(message="يرجى إدخال رابط YouTube صحيح."), 400

    with lock:
        if progress["active"]:
            return jsonify(message="يوجد تحميل جارٍ بالفعل. انتظر حتى ينتهي."), 409

        progress.update({
            "active": True,
            "status": "starting",
            "percent": 0,
            "downloaded": 0,
            "total": 0,
            "speed": 0,
            "eta": None,
            "message": "جارٍ تجهيز الفيديو...",
            "title": "",
        })

    Thread(target=download_video, args=(url,), daemon=True).start()
    return jsonify(message="بدأ التحميل")


@app.route("/progress")
def get_progress():
    with lock:
        return jsonify(progress.copy())


@app.route("/open-folder", methods=["POST"])
def open_folder():
    try:
        if sys.platform == "win32":
            os.startfile(str(DOWNLOAD_DIR))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(DOWNLOAD_DIR)])
        else:
            subprocess.Popen(["xdg-open", str(DOWNLOAD_DIR)])

        return jsonify(message="تم فتح مجلد التحميلات")

    except Exception as exc:
        return jsonify(message=f"تعذر فتح المجلد: {exc}"), 500

if __name__ == "__main__":
    print("مجلد الحفظ:", DOWNLOAD_DIR)
    print("افتح: http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
