const express = require("express");
const app = express();
const PORT = 10008;

const FLAG = "AIS3{d1r_l1st1ng_l34ks_3v3ryth1ng}";

// ===== Virtual Filesystem =====
// Simulates a web server with directory listing accidentally left enabled.
// The flag is buried inside /files/internal/flag.txt

const VFS = {
  "/files": {
    type: "dir", mtime: "2025-02-01 08:30",
    children: ["annual_report_2024.pdf", "public", "internal", "temp"],
  },
  "/files/annual_report_2024.pdf": {
    type: "file", mtime: "2025-02-01 08:30", size: "2.4M",
    content: "AIS3 Corp — 2024 Annual Report\n\nThis document is for authorized personnel only.\n\n[Binary PDF content — use a PDF viewer to read.]",
  },
  "/files/public": {
    type: "dir", mtime: "2025-01-10 11:20",
    children: ["company_brochure.pdf", "press_release_q4.txt", "logo_guidelines.pdf"],
  },
  "/files/public/company_brochure.pdf": {
    type: "file", mtime: "2025-01-08 09:15", size: "4.1M",
    content: "[Binary PDF — AIS3 Corp Company Brochure]",
  },
  "/files/public/press_release_q4.txt": {
    type: "file", mtime: "2024-12-31 17:00", size: "1.2K",
    content: "FOR IMMEDIATE RELEASE\n\nAIS3 Corp Reports Record Q4 2024 Results\n\nRevenue up 32% YoY. Security division leads growth.\nFull report available at investor.ais3corp.com.\n",
  },
  "/files/public/logo_guidelines.pdf": {
    type: "file", mtime: "2025-01-02 10:00", size: "890K",
    content: "[Binary PDF — Brand & Logo Usage Guidelines]",
  },
  "/files/internal": {
    type: "dir", mtime: "2025-03-01 10:44",
    children: ["employee_directory.csv", "salary_review_2025.xlsx", "flag.txt"],
  },
  "/files/internal/employee_directory.csv": {
    type: "file", mtime: "2025-02-28 16:22", size: "8.7K",
    content: "id,name,dept,title,email,salary\n" +
             "1001,Alice Chen,Engineering,Senior Engineer,alice@ais3corp.com,REDACTED\n" +
             "1002,Bob Wang,Marketing,Marketing Manager,bob@ais3corp.com,REDACTED\n" +
             "1003,Carol Liu,HR,HR Specialist,carol@ais3corp.com,REDACTED\n" +
             "1004,David Tsai,Security,Penetration Tester,david@ais3corp.com,REDACTED\n" +
             "1005,Eve Lin,Finance,Financial Analyst,eve@ais3corp.com,REDACTED\n",
  },
  "/files/internal/salary_review_2025.xlsx": {
    type: "file", mtime: "2025-03-01 09:58", size: "43K",
    content: "[Binary XLSX — Salary Review 2025]\n\n（此為二進位格式，需用 Excel 開啟）",
  },
  "/files/internal/flag.txt": {
    type: "file", mtime: "2025-03-01 10:44", size: "44",
    content: FLAG + "\n",
  },
  "/files/temp": {
    type: "dir", mtime: "2025-02-28 23:59",
    children: ["debug_20250228.log", "db_backup_20250201.sql.gz"],
  },
  "/files/temp/debug_20250228.log": {
    type: "file", mtime: "2025-02-28 23:59", size: "156K",
    content: "[2025-02-28 23:47:01] INFO  Server started on 0.0.0.0:80\n" +
             "[2025-02-28 23:47:01] INFO  Loading config from /etc/app/config.yml\n" +
             "[2025-02-28 23:52:14] WARN  Slow query detected: 2340ms\n" +
             "[2025-02-28 23:58:33] ERROR Unhandled exception in /api/report\n" +
             "[2025-02-28 23:59:01] INFO  Graceful shutdown initiated\n",
  },
  "/files/temp/db_backup_20250201.sql.gz": {
    type: "file", mtime: "2025-02-01 03:00", size: "128M",
    content: "[Binary gzip — Database backup. Do not open directly.]",
  },
};

// ===== Directory listing renderer (nginx autoindex style) =====
function renderDir(urlPath, node) {
  const parent = urlPath === "/files" ? null : urlPath.split("/").slice(0, -1).join("/") || "/files";

  const rows = node.children.map((name) => {
    const childPath = `${urlPath}/${name}`;
    const child = VFS[childPath];
    if (!child) return "";

    const isDir = child.type === "dir";
    const displayName = isDir ? name + "/" : name;
    const href = isDir ? childPath + "/" : childPath;
    const sizeStr = isDir ? "-" : child.size || "-";

    return `<tr>
      <td class="col-name"><a href="${href}" class="${isDir ? "link-dir" : "link-file"}">${displayName}</a></td>
      <td class="col-mtime">${child.mtime}</td>
      <td class="col-size">${sizeStr}</td>
    </tr>`;
  }).join("\n");

  const parentRow = parent
    ? `<tr><td class="col-name"><a href="${parent}/" class="link-parent">../</a></td><td></td><td></td></tr>`
    : "";

  return `<!DOCTYPE html>
<html lang="zh-TW">
<head><meta charset="UTF-8"><title>Index of ${urlPath}/</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0f1117; color: #c9d1d9; font-family: 'Courier New', monospace; font-size: 0.88rem; padding: 2rem 2.5rem; min-height: 100vh; }
  h1 { font-size: 1rem; font-weight: 400; color: #8892a4; margin-bottom: 1.5rem; padding-bottom: 0.8rem; border-bottom: 1px solid #252d3d; }
  h1 span { color: #e2e8f0; }
  table { border-collapse: collapse; width: 100%; max-width: 760px; }
  thead tr { border-bottom: 1px solid #252d3d; }
  th { text-align: left; padding: 0.3rem 2.5rem 0.3rem 0; color: #4a5568; font-weight: 400; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; }
  th:last-child { text-align: right; padding-right: 0; }
  td { padding: 0.25rem 2.5rem 0.25rem 0; }
  td:last-child { text-align: right; padding-right: 0; color: #4a5568; }
  .col-name { min-width: 280px; }
  .col-mtime { color: #4a5568; min-width: 160px; }
  .col-size { color: #4a5568; }
  a { text-decoration: none; }
  a:hover { text-decoration: underline; }
  .link-dir    { color: #34d399; }
  .link-file   { color: #4a9eff; }
  .link-parent { color: #8892a4; }
  .server-sig { margin-top: 2rem; padding-top: 0.8rem; border-top: 1px solid #252d3d; color: #4a5568; font-size: 0.78rem; }
</style>
</head>
<body>
<h1>Index of <span>${urlPath}/</span></h1>
<table>
  <thead><tr><th>Name</th><th>Last Modified</th><th>Size</th></tr></thead>
  <tbody>
    ${parentRow}
    ${rows}
  </tbody>
</table>
<div class="server-sig">nginx/1.24.0</div>
</body></html>`;
}

// ===== File content renderer =====
function renderFile(urlPath, node) {
  const filename = urlPath.split("/").pop();
  const ext = filename.split(".").pop().toLowerCase();
  const isBinary = ["pdf", "xlsx", "gz", "zip", "png", "jpg"].includes(ext);

  const parent = urlPath.split("/").slice(0, -1).join("/");

  return `<!DOCTYPE html>
<html lang="zh-TW">
<head><meta charset="UTF-8"><title>${filename}</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0f1117; color: #c9d1d9; font-family: 'Courier New', monospace; font-size: 0.88rem; padding: 2rem 2.5rem; min-height: 100vh; }
  .header { display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem; padding-bottom: 0.8rem; border-bottom: 1px solid #252d3d; }
  .header a { color: #8892a4; text-decoration: none; font-size: 0.82rem; }
  .header a:hover { color: #4a9eff; }
  .header h1 { font-size: 0.95rem; font-weight: 400; color: #e2e8f0; }
  .meta { font-size: 0.78rem; color: #4a5568; margin-bottom: 1.2rem; }
  pre { background: #090c12; border: 1px solid #252d3d; border-radius: 6px; padding: 1.2rem 1.5rem; line-height: 1.75; white-space: pre-wrap; word-break: break-all; color: #c9d1d9; }
  .flag-line { color: #22c55e; font-weight: 700; }
  .binary-note { color: #4a5568; font-style: italic; }
</style>
</head>
<body>
<div class="header">
  <a href="${parent}/">&larr; ${parent}/</a>
  <h1>${filename}</h1>
</div>
<div class="meta">Size: ${node.size || "?"}  &nbsp;|&nbsp;  Last Modified: ${node.mtime}</div>
<pre>${node.content.split("\n").map(line =>
    line.startsWith("AIS3{")
      ? `<span class="flag-line">${line}</span>`
      : isBinary
        ? `<span class="binary-note">${line}</span>`
        : line
  ).join("\n")}</pre>
</body></html>`;
}

// ===== Routes =====

// Main homepage
app.get("/", (req, res) => {
  res.send(`<!DOCTYPE html>
<html lang="zh-TW">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIS3 Corp — 官方網站</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  :root { --bg: #0f1117; --card: #1a1f2e; --border: #252d3d; --accent: #a78bfa; --text: #e2e8f0; --text-dim: #8892a4; }
  body { font-family: system-ui, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); }
  nav { background: #090c12; border-bottom: 1px solid var(--border); padding: 0 2.5rem; height: 60px; display: flex; align-items: center; justify-content: space-between; }
  .logo { font-weight: 800; font-size: 1.15rem; color: var(--accent); letter-spacing: -0.02em; }
  nav ul { list-style: none; display: flex; gap: 2rem; }
  nav a { color: var(--text-dim); text-decoration: none; font-size: 0.88rem; transition: color 0.2s; }
  nav a:hover { color: var(--accent); }
  .hero { text-align: center; padding: 6rem 2rem 4rem; }
  .hero .tag { display: inline-block; background: rgba(167,139,250,0.12); color: var(--accent); border: 1px solid rgba(167,139,250,0.3); padding: 0.3rem 0.9rem; border-radius: 20px; font-size: 0.78rem; font-weight: 700; letter-spacing: 0.08em; margin-bottom: 1.2rem; }
  .hero h1 { font-size: 3rem; font-weight: 800; margin-bottom: 1rem; letter-spacing: -0.03em; }
  .hero h1 span { color: var(--accent); }
  .hero p { color: var(--text-dim); font-size: 1rem; max-width: 520px; margin: 0 auto 2.5rem; line-height: 1.7; }
  .btn { display: inline-block; padding: 0.7rem 1.8rem; background: var(--accent); color: #090c12; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 0.9rem; transition: opacity 0.2s; }
  .btn:hover { opacity: 0.88; }
  .btn-ghost { background: transparent; border: 1px solid var(--border); color: var(--text-dim); margin-left: 0.8rem; }
  .btn-ghost:hover { border-color: var(--accent); color: var(--accent); }
  .container { max-width: 1100px; margin: 0 auto; padding: 0 2rem; }
  .services { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.2rem; padding: 0 2.5rem 5rem; max-width: 1000px; margin: 0 auto; }
  .service-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 1.8rem; }
  .service-card .icon { font-size: 2rem; margin-bottom: 0.8rem; }
  .service-card h3 { font-size: 1.05rem; margin-bottom: 0.5rem; }
  .service-card p { font-size: 0.85rem; color: var(--text-dim); line-height: 1.6; }
  .download-section { background: var(--card); border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); padding: 3rem 2.5rem; margin-bottom: 0; }
  .download-section h2 { font-size: 1.4rem; margin-bottom: 0.4rem; }
  .download-section p { color: var(--text-dim); font-size: 0.88rem; margin-bottom: 1.5rem; }
  .dl-list { display: flex; flex-direction: column; gap: 0.7rem; max-width: 520px; }
  .dl-item { display: flex; align-items: center; justify-content: space-between; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 0.8rem 1.2rem; }
  .dl-item .dl-name { font-size: 0.88rem; display: flex; align-items: center; gap: 0.5rem; }
  .dl-item a { font-size: 0.8rem; color: var(--accent); text-decoration: none; border: 1px solid rgba(167,139,250,0.3); padding: 0.25rem 0.7rem; border-radius: 5px; }
  .dl-item a:hover { opacity: 0.78; }
  footer { text-align: center; padding: 2rem; color: var(--text-dim); font-size: 0.8rem; border-top: 1px solid var(--border); }
</style>
</head>
<body>
<nav>
  <div class="logo">AIS3 Corp</div>
  <ul>
    <li><a href="/">首頁</a></li>
    <li><a href="#">關於我們</a></li>
    <li><a href="#">服務項目</a></li>
    <li><a href="#">聯絡我們</a></li>
  </ul>
</nav>

<div class="hero">
  <div class="tag">CYBERSECURITY LEADER</div>
  <h1>守護企業<span>數位安全</span></h1>
  <p>AIS3 Corp 提供全方位的資訊安全解決方案，從滲透測試到資安稽核，守護您的數位資產。</p>
  <a href="#download" class="btn">下載文件</a>
  <a href="#services" class="btn btn-ghost">了解服務</a>
</div>

<div class="services" id="services">
  <div class="service-card"><div class="icon">&#128270;</div><h3>滲透測試</h3><p>模擬真實攻擊，找出系統弱點，在駭客之前發現問題。</p></div>
  <div class="service-card"><div class="icon">&#128203;</div><h3>資安稽核</h3><p>全面審查您的資安政策與控制措施，確保符合法規要求。</p></div>
  <div class="service-card"><div class="icon">&#128736;</div><h3>事件應變</h3><p>24/7 資安事件偵測與應變，將損害降到最低。</p></div>
</div>

<div class="download-section" id="download">
  <h2>&#128196; 文件下載中心</h2>
  <p>以下提供公開文件供合作夥伴與客戶下載。</p>
  <div class="dl-list">
    <div class="dl-item">
      <span class="dl-name">&#128196; 2024 年度報告</span>
      <a href="/files/annual_report_2024.pdf">下載</a>
    </div>
    <div class="dl-item">
      <span class="dl-name">&#128196; 公司簡介</span>
      <a href="/files/public/company_brochure.pdf">下載</a>
    </div>
    <div class="dl-item">
      <span class="dl-name">&#128196; Q4 新聞稿</span>
      <a href="/files/public/press_release_q4.txt">下載</a>
    </div>
  </div>
</div>

<footer>&copy; 2025 AIS3 Corp. All rights reserved.</footer>
</body></html>`);
});

// Handle /files and all subdirectories
app.get(/^\/files(\/.*)?$/, (req, res) => {
  // Normalize: strip trailing slash, default to /files
  let urlPath = req.path.replace(/\/$/, "") || "/files";

  const node = VFS[urlPath];

  if (!node) {
    return res.status(404).send(`<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>404</title>
<style>body{background:#0f1117;color:#8892a4;font-family:monospace;padding:2rem}</style>
</head><body><h1 style="color:#ef4444">404 Not Found</h1><p>${urlPath}</p>
<p><a href="/files/" style="color:#4a9eff">&larr; /files/</a></p></body></html>`);
  }

  if (node.type === "dir") {
    return res.send(renderDir(urlPath, node));
  } else {
    return res.send(renderFile(urlPath, node));
  }
});

app.listen(PORT, () => {
  console.log(`\n================================================`);
  console.log(`  Directory Listing Lab  —  http://localhost:${PORT}`);
  console.log(`================================================`);
  console.log(`  Start: visit the homepage, find the file server`);
  console.log(`  Flag:  /files/internal/flag.txt`);
  console.log(``);
});
