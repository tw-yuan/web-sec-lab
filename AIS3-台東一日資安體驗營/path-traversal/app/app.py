import os
from flask import Flask, request, abort

app = Flask(__name__)

FILES_DIR = "/app/files"

AVAILABLE_FILES = ["report.txt", "manual.txt", "notice.txt"]

# ===== CSS =====
CSS = """
  * { margin: 0; padding: 0; box-sizing: border-box; }
  :root {
    --bg: #0f1117; --card: #1a1f2e; --border: #252d3d;
    --accent: #34d399; --text: #e2e8f0; --text-dim: #8892a4;
    --danger: #ef4444; --success: #22c55e;
  }
  body { font-family: system-ui, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
  nav { background: #090c12; border-bottom: 1px solid var(--border); padding: 0 2rem; height: 56px; display: flex; align-items: center; justify-content: space-between; }
  .logo { font-weight: 700; font-size: 1.05rem; color: var(--accent); }
  .logo span { color: var(--text-dim); font-weight: 400; font-size: 0.78rem; margin-left: 0.5rem; }
  nav a { color: var(--text-dim); text-decoration: none; font-size: 0.85rem; }
  nav a:hover { color: var(--accent); }
  .container { max-width: 820px; margin: 0 auto; padding: 2rem; }
  code { background: rgba(52,211,153,0.1); color: var(--accent); padding: 0.1rem 0.4rem; border-radius: 3px; font-size: 0.85rem; font-family: monospace; }
  .hero { margin-bottom: 2rem; }
  .hero .badge { display: inline-block; background: rgba(52,211,153,0.12); color: var(--accent); border: 1px solid rgba(52,211,153,0.3); padding: 0.2rem 0.7rem; border-radius: 20px; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em; margin-bottom: 0.8rem; }
  .hero h1 { font-size: 1.7rem; color: var(--accent); margin-bottom: 0.3rem; }
  .hero p { color: var(--text-dim); font-size: 0.9rem; line-height: 1.7; }
  .section { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 1.5rem; margin-bottom: 1.2rem; }
  .section h3 { font-size: 0.8rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.09em; margin-bottom: 1rem; }
  .file-list { list-style: none; }
  .file-list li { display: flex; align-items: center; justify-content: space-between; padding: 0.7rem 0; border-bottom: 1px solid var(--border); }
  .file-list li:last-child { border-bottom: none; }
  .file-name { font-family: monospace; font-size: 0.9rem; display: flex; align-items: center; gap: 0.5rem; }
  .file-name .icon { color: var(--accent); }
  .dl-btn { padding: 0.35rem 0.9rem; border-radius: 5px; background: rgba(52,211,153,0.12); color: var(--accent); border: 1px solid rgba(52,211,153,0.3); text-decoration: none; font-size: 0.8rem; font-weight: 600; transition: opacity 0.2s; }
  .dl-btn:hover { opacity: 0.78; }
  .hint-box { background: rgba(52,211,153,0.06); border: 1px solid rgba(52,211,153,0.2); border-radius: 8px; padding: 1rem 1.2rem; font-size: 0.83rem; color: var(--text-dim); line-height: 1.7; }
  .hint-box strong { color: var(--accent); }
  .step-list { list-style: none; counter-reset: step; padding-left: 0; }
  .step-list li { counter-increment: step; display: flex; align-items: flex-start; gap: 0.7rem; margin-bottom: 0.5rem; font-size: 0.85rem; color: var(--text-dim); line-height: 1.6; }
  .step-list li::before { content: counter(step); background: rgba(52,211,153,0.12); color: var(--accent); border: 1px solid rgba(52,211,153,0.3); min-width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.72rem; font-weight: 700; margin-top: 0.15rem; flex-shrink: 0; }
  /* File view */
  .file-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem; }
  .file-header h2 { font-size: 1.2rem; color: var(--accent); }
  .back-btn { color: var(--text-dim); text-decoration: none; font-size: 0.85rem; }
  .back-btn:hover { color: var(--accent); }
  .file-content { background: #090c12; border: 1px solid var(--border); border-radius: 8px; padding: 1.5rem 1.8rem; font-family: monospace; font-size: 0.88rem; line-height: 1.8; white-space: pre-wrap; word-break: break-all; }
  .path-display { font-family: monospace; font-size: 0.78rem; color: var(--text-dim); background: rgba(52,211,153,0.05); border: 1px solid var(--border); border-radius: 5px; padding: 0.4rem 0.8rem; margin-bottom: 1rem; }
  .flag-highlight { color: #22c55e; font-weight: 700; }
  .err { background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.3); color: var(--danger); padding: 1rem 1.2rem; border-radius: 8px; font-size: 0.88rem; }
"""

def page(body):
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIS3 Corp — 文件下載系統</title>
<style>{CSS}</style></head>
<body>
<nav>
  <div class="logo">AIS3 Corp<span>內部文件下載系統</span></div>
  <a href="/">文件列表</a>
</nav>
{body}
</body></html>"""


@app.route("/")
def index():
    files_html = ""
    for f in AVAILABLE_FILES:
        files_html += f"""<li>
          <span class="file-name"><span class="icon">&#128196;</span>{f}</span>
          <a href="/download?file={f}" class="dl-btn">下載</a>
        </li>"""

    return page(f"""<div class="container">
      <div class="hero">
        <div class="badge">PATH TRAVERSAL LAB</div>
        <h1>內部文件下載系統</h1>
        <p>這個系統讓員工下載內部文件。請選擇下方的文件進行下載。<br>
        <strong style="color:var(--accent)">你的任務</strong>：讀取系統上的 <code>/flag.txt</code>。</p>
      </div>

      <div class="section">
        <h3>&#128196; 可下載的文件</h3>
        <ul class="file-list">{files_html}</ul>
      </div>

      <div class="section">
        <h3>&#128161; 提示</h3>
        <div class="hint-box">
          <strong>觀察下載連結的 URL：</strong><br>
          <code>/download?file=report.txt</code><br><br>
          後端直接用這個 <code>file</code> 參數來決定要讀哪個檔案。<br>
          如果你在檔名裡放入 <code>../</code>，能不能讓它往上跳出目前的目錄？<br><br>
          <strong>目標</strong>：讀取 <code>/flag.txt</code>（在 <code>/app/files/</code> 外面）
        </div>
      </div>
    </div>""")


@app.route("/download")
def download():
    filename = request.args.get("file", "")
    if not filename:
        return page('<div class="container"><div class="err">請提供 file 參數。</div></div>'), 400

    # VULNERABLE: user input concatenated directly into file path, no sanitization
    filepath = os.path.join(FILES_DIR, filename)

    try:
        with open(filepath, "r", errors="replace") as f:
            content = f.read()
    except FileNotFoundError:
        return page(f'<div class="container"><div class="err">找不到檔案：<code>{filename}</code></div></div>'), 404
    except PermissionError:
        return page(f'<div class="container"><div class="err">沒有權限讀取：<code>{filename}</code></div></div>'), 403
    except Exception as e:
        return page(f'<div class="container"><div class="err">錯誤：{e}</div></div>'), 500

    # Highlight flag lines
    highlighted = ""
    for line in content.splitlines(keepends=True):
        if line.startswith("AIS3{"):
            highlighted += f'<span class="flag-highlight">{line}</span>'
        else:
            highlighted += line

    # Show the resolved path to make the vulnerability visible
    resolved = os.path.realpath(filepath)

    return page(f"""<div class="container">
      <div class="file-header">
        <h2>&#128196; {filename}</h2>
        <a href="/" class="back-btn">&larr; 回文件列表</a>
      </div>
      <div class="path-display">
        要求路徑：<code>/app/files/{filename}</code> &nbsp;&#8594;&nbsp; 實際讀取：<code>{resolved}</code>
      </div>
      <div class="file-content">{highlighted}</div>
    </div>""")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
