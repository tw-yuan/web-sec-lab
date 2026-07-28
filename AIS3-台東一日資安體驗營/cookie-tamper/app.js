const express = require("express");
const cookieParser = require("cookie-parser");
const app = express();
const PORT = 10004;

app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());

const FLAG = "AIS3{c00k13_r0l3_1s_n0t_s3cur1ty}";

// ===== CSS =====
const CSS = `
  * { margin: 0; padding: 0; box-sizing: border-box; }
  :root {
    --bg: #0f1117; --card: #1a1f2e; --border: #252d3d;
    --accent: #4a9eff; --text: #e2e8f0; --text-dim: #8892a4;
    --danger: #ef4444; --success: #22c55e; --warning: #f59e0b;
  }
  body { font-family: system-ui, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
  nav { background: #090c12; border-bottom: 1px solid var(--border); padding: 0 2rem; height: 56px; display: flex; align-items: center; justify-content: space-between; }
  .logo { font-weight: 700; font-size: 1.05rem; color: var(--accent); }
  .logo span { color: var(--text-dim); font-weight: 400; font-size: 0.78rem; margin-left: 0.5rem; }
  nav .right { font-size: 0.85rem; display: flex; align-items: center; gap: 1rem; }
  nav a { color: var(--text-dim); text-decoration: none; transition: color 0.2s; }
  nav a:hover { color: var(--accent); }
  .container { max-width: 860px; margin: 0 auto; padding: 2rem; }
  .center { min-height: calc(100vh - 56px); display: flex; align-items: center; justify-content: center; }
  .box { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 2.5rem; width: 380px; }
  .box h2 { font-size: 1.4rem; color: var(--accent); margin-bottom: 0.25rem; }
  .box .sub { color: var(--text-dim); font-size: 0.85rem; margin-bottom: 2rem; }
  .field { margin-bottom: 1.1rem; }
  .field label { display: block; font-size: 0.72rem; color: var(--text-dim); margin-bottom: 0.35rem; text-transform: uppercase; letter-spacing: 0.08em; }
  .field input { width: 100%; padding: 0.65rem 0.9rem; background: #0a0d14; border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 0.9rem; outline: none; transition: border-color 0.2s; }
  .field input:focus { border-color: var(--accent); }
  .btn { width: 100%; padding: 0.7rem; background: var(--accent); color: #090c12; border: none; border-radius: 6px; font-size: 0.95rem; font-weight: 700; cursor: pointer; margin-top: 0.4rem; transition: opacity 0.2s; }
  .btn:hover { opacity: 0.88; }
  .info-box { background: rgba(74,158,255,0.07); border: 1px solid rgba(74,158,255,0.2); border-radius: 8px; padding: 0.9rem 1.1rem; margin-top: 1.4rem; font-size: 0.82rem; color: var(--text-dim); line-height: 1.6; }
  .info-box strong { color: var(--accent); }
  code { background: rgba(74,158,255,0.1); color: var(--accent); padding: 0.1rem 0.4rem; border-radius: 3px; font-size: 0.82rem; font-family: monospace; }
  .err { background: rgba(239,68,68,0.1); border: 1px solid rgba(239,68,68,0.3); color: var(--danger); padding: 0.6rem 0.9rem; border-radius: 6px; font-size: 0.85rem; margin-bottom: 1rem; }
  .page-title { margin-bottom: 2rem; }
  .page-title h1 { font-size: 1.5rem; color: var(--accent); }
  .page-title p { color: var(--text-dim); font-size: 0.88rem; margin-top: 0.3rem; }
  .section { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 1.5rem; margin-bottom: 1.2rem; }
  .section h3 { font-size: 0.78rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.09em; margin-bottom: 1rem; }
  .cookie-row { display: flex; align-items: center; gap: 1rem; padding: 0.55rem 0; border-bottom: 1px solid var(--border); font-family: monospace; font-size: 0.88rem; }
  .cookie-row:last-child { border-bottom: none; }
  .ck { color: var(--accent); min-width: 110px; }
  .cv-user { color: var(--warning); }
  .cv-admin { color: var(--success); }
  .badge { display: inline-block; padding: 0.15rem 0.55rem; border-radius: 4px; font-size: 0.72rem; font-weight: 700; }
  .badge-user { background: rgba(245,158,11,0.15); color: var(--warning); border: 1px solid rgba(245,158,11,0.3); }
  .badge-admin { background: rgba(34,197,94,0.15); color: var(--success); border: 1px solid rgba(34,197,94,0.3); }
  .grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 1.2rem; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 1.2rem; }
  .card .icon { font-size: 1.8rem; margin-bottom: 0.5rem; }
  .card h4 { font-size: 0.9rem; margin-bottom: 0.25rem; }
  .card p { font-size: 0.8rem; color: var(--text-dim); }
  .locked { background: rgba(239,68,68,0.04); border: 2px dashed rgba(239,68,68,0.22); border-radius: 8px; padding: 1.8rem; text-align: center; color: var(--text-dim); }
  .locked .lock { font-size: 2rem; margin-bottom: 0.6rem; }
  .locked .hint { margin-top: 0.8rem; font-size: 0.82rem; line-height: 1.7; }
  .flag-box { background: rgba(34,197,94,0.08); border: 1px solid rgba(34,197,94,0.3); border-radius: 8px; padding: 1.2rem 1.5rem; }
  .flag-box .fl { font-size: 0.72rem; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 0.5rem; }
  .flag-box .flag { font-family: monospace; font-size: 1rem; color: var(--success); }
  .flag-box .msg { font-size: 0.85rem; color: var(--text-dim); margin-top: 0.5rem; }
`;

function page(nav, body) {
  return `<!DOCTYPE html>
<html lang="zh-TW">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIS3 Corp — 員工入口</title>
<style>${CSS}</style></head>
<body>
<nav>
  <div class="logo">AIS3 Corp<span>員工入口網站</span></div>
  <div class="right">${nav}</div>
</nav>
${body}
</body></html>`;
}

// ===== Routes =====

app.get("/", (req, res) => {
  if (req.cookies.username) return res.redirect("/dashboard");
  res.redirect("/login");
});

app.get("/login", (req, res) => {
  const err = req.query.error ? '<div class="err">帳號或密碼錯誤，請再試一次。</div>' : "";
  res.send(page("", `<div class="center"><div class="box">
    <h2>員工登入</h2>
    <p class="sub">請輸入您的帳號密碼進入公司系統</p>
    ${err}
    <form method="POST" action="/login">
      <div class="field"><label>帳號</label><input name="username" autocomplete="off" autofocus></div>
      <div class="field"><label>密碼</label><input name="password" type="password"></div>
      <button class="btn">登入系統</button>
    </form>
    <div class="info-box">
      <strong>測試帳號</strong><br>
      帳號：<code>employee</code>&nbsp;&nbsp;密碼：<code>1234</code>
    </div>
  </div></div>`));
});

app.post("/login", (req, res) => {
  const { username, password } = req.body;
  if (username === "employee" && password === "1234") {
    // VULNERABLE: role is stored as plaintext in a non-httpOnly cookie.
    // Anyone can edit it directly in the browser's DevTools.
    res.cookie("username", username, { httpOnly: false });
    res.cookie("role", "user", { httpOnly: false });
    return res.redirect("/dashboard");
  }
  res.redirect("/login?error=1");
});

app.get("/logout", (req, res) => {
  res.clearCookie("username");
  res.clearCookie("role");
  res.redirect("/login");
});

app.get("/dashboard", (req, res) => {
  const username = req.cookies.username;
  const role = req.cookies.role || "(未設定)";
  if (!username) return res.redirect("/login");

  const isAdmin = role === "admin";

  const badge = isAdmin
    ? '<span class="badge badge-admin">admin</span>'
    : '<span class="badge badge-user">user</span>';

  const adminArea = isAdmin
    ? `<div class="flag-box">
        <div class="fl">Flag</div>
        <div class="flag">${FLAG}</div>
        <div class="msg">成功！你修改了 Cookie，讓伺服器以為你是管理員。</div>
       </div>`
    : `<div class="locked">
        <div class="lock">&#128274;</div>
        <p>管理員專屬區域。你目前的身份是 <strong>user</strong>，沒有權限。</p>
        <div class="hint">
          提示：打開 F12 → <strong>Application</strong>（或 Storage）→ <strong>Cookies</strong><br>
          找到 <code>role</code> 這個 Cookie，把值從 <code style="color:var(--warning)">${role}</code> 改成 <code style="color:var(--success)">admin</code>，再重新整理頁面。
        </div>
       </div>`;

  res.send(page(
    `<span>${username}</span> ${badge} <a href="/logout">登出</a>`,
    `<div class="container">
      <div class="page-title">
        <h1>員工儀表板</h1>
        <p>歡迎回來，${username}。目前身份：${badge}</p>
      </div>

      <div class="section">
        <h3>目前的 Cookie（httpOnly = false，瀏覽器開發者工具可直接讀寫）</h3>
        <div class="cookie-row">
          <span class="ck">username</span>
          <span>${username}</span>
        </div>
        <div class="cookie-row">
          <span class="ck">role</span>
          <span class="${isAdmin ? "cv-admin" : "cv-user"}">${role}</span>
        </div>
      </div>

      <div class="grid3">
        <div class="card"><div class="icon">&#128203;</div><h4>出勤紀錄</h4><p>查看本月出勤狀況與請假申請</p></div>
        <div class="card"><div class="icon">&#128188;</div><h4>薪資查詢</h4><p>查看薪資明細與扣繳資料</p></div>
        <div class="card"><div class="icon">&#128230;</div><h4>設備管理</h4><p>查看公司配發的設備資產</p></div>
      </div>

      <div class="section">
        <h3>&#128274; 管理員專區</h3>
        ${adminArea}
      </div>
    </div>`
  ));
});

app.listen(PORT, () => {
  console.log(`\n================================================`);
  console.log(`  Cookie Tamper Lab  —  http://localhost:${PORT}`);
  console.log(`================================================`);
  console.log(`  Login:  employee / 1234`);
  console.log(`  Goal:   DevTools -> Application -> Cookies`);
  console.log(`          change 'role' from 'user' to 'admin'`);
  console.log(``);
});
