const express = require("express");
const cookieParser = require("cookie-parser");
const app = express();
const PORT = 10006;

app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(cookieParser());

const FLAG = "AIS3{0p3n_r3d1r3ct_ph1sh1ng_tr4p}";

// ===== CSS =====
const CSS = `
  * { margin: 0; padding: 0; box-sizing: border-box; }
  :root {
    --bg: #0f1117; --card: #1a1f2e; --border: #252d3d;
    --accent: #f59e0b; --text: #e2e8f0; --text-dim: #8892a4;
    --danger: #ef4444; --success: #22c55e;
  }
  body { font-family: system-ui, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
  nav { background: #090c12; border-bottom: 1px solid var(--border); padding: 0 2rem; height: 56px; display: flex; align-items: center; justify-content: space-between; }
  .logo { font-weight: 700; font-size: 1.05rem; color: var(--accent); }
  .logo span { color: var(--text-dim); font-weight: 400; font-size: 0.78rem; margin-left: 0.5rem; }
  nav .right { font-size: 0.85rem; display: flex; align-items: center; gap: 1rem; }
  nav a { color: var(--text-dim); text-decoration: none; transition: color 0.2s; }
  nav a:hover { color: var(--accent); }
  .container { max-width: 820px; margin: 0 auto; padding: 2rem; }
  code { background: rgba(245,158,11,0.1); color: var(--accent); padding: 0.1rem 0.4rem; border-radius: 3px; font-size: 0.85rem; font-family: monospace; }
  .hero { text-align: center; padding: 3rem 2rem 2rem; }
  .hero .badge { display: inline-block; background: rgba(245,158,11,0.15); color: var(--accent); border: 1px solid rgba(245,158,11,0.3); padding: 0.25rem 0.8rem; border-radius: 20px; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.08em; margin-bottom: 1rem; }
  .hero h1 { font-size: 2rem; margin-bottom: 0.8rem; }
  .hero h1 span { color: var(--accent); }
  .hero p { color: var(--text-dim); max-width: 600px; margin: 0 auto; line-height: 1.7; font-size: 0.95rem; }
  .card { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 1.5rem; margin-bottom: 1.2rem; }
  .card h3 { font-size: 1rem; margin-bottom: 0.8rem; color: var(--accent); }
  .card p { font-size: 0.88rem; color: var(--text-dim); line-height: 1.7; margin-bottom: 0.6rem; }
  .card p:last-child { margin-bottom: 0; }
  .step-list { list-style: none; counter-reset: step; }
  .step-list li { counter-increment: step; display: flex; align-items: flex-start; gap: 0.8rem; margin-bottom: 0.7rem; font-size: 0.88rem; color: var(--text-dim); line-height: 1.6; }
  .step-list li::before { content: counter(step); background: rgba(245,158,11,0.15); color: var(--accent); border: 1px solid rgba(245,158,11,0.3); min-width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 700; margin-top: 0.1rem; }
  .input-row { display: flex; gap: 0.6rem; }
  .input-row input { flex: 1; padding: 0.7rem 1rem; background: #0a0d14; border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 0.9rem; font-family: monospace; outline: none; transition: border-color 0.2s; }
  .input-row input:focus { border-color: var(--accent); }
  .input-row button { padding: 0.7rem 1.4rem; background: var(--accent); color: #090c12; border: none; border-radius: 6px; font-weight: 700; font-size: 0.9rem; cursor: pointer; white-space: nowrap; transition: opacity 0.2s; }
  .input-row button:hover { opacity: 0.88; }
  #result { margin-top: 1rem; padding: 1rem 1.2rem; border-radius: 8px; font-size: 0.88rem; display: none; line-height: 1.6; }
  #result.ok { background: rgba(34,197,94,0.08); border: 1px solid rgba(34,197,94,0.3); color: var(--success); }
  #result.fail { background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.3); color: var(--danger); }
  #result .flag { font-family: monospace; font-size: 1rem; margin-top: 0.4rem; }
  .link-row { display: flex; gap: 0.6rem; align-items: center; flex-wrap: wrap; margin-top: 0.6rem; }
  .link-row a { display: inline-block; padding: 0.45rem 1rem; border-radius: 6px; font-size: 0.82rem; text-decoration: none; font-weight: 600; transition: opacity 0.2s; }
  .link-row a:hover { opacity: 0.82; }
  .btn-outline { border: 1px solid var(--border); color: var(--text-dim); background: transparent; }
  .btn-accent { background: rgba(245,158,11,0.15); color: var(--accent); border: 1px solid rgba(245,158,11,0.3); }
  /* Evil page */
  .evil-wrap { min-height: 100vh; display: flex; align-items: center; justify-content: center; }
  .evil-box { background: rgba(239,68,68,0.06); border: 2px solid rgba(239,68,68,0.3); border-radius: 16px; padding: 3rem; text-align: center; max-width: 520px; }
  .evil-icon { font-size: 3.5rem; margin-bottom: 1rem; }
  .evil-box h2 { font-size: 1.6rem; color: var(--danger); margin-bottom: 1rem; }
  .evil-box p { color: var(--text-dim); font-size: 0.9rem; line-height: 1.7; margin-bottom: 0.5rem; }
  /* Dashboard */
  .dash-wrap { min-height: calc(100vh - 56px); display: flex; align-items: center; justify-content: center; }
  .dash-box { text-align: center; }
  .dash-box .ok-icon { font-size: 3rem; margin-bottom: 1rem; }
  .dash-box h2 { font-size: 1.5rem; color: var(--success); margin-bottom: 0.5rem; }
  .dash-box p { color: var(--text-dim); font-size: 0.9rem; line-height: 1.6; }
`;

function page(nav, body) {
  return `<!DOCTYPE html>
<html lang="zh-TW">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIS3 SSO — 單一登入系統</title>
<style>${CSS}</style></head>
<body>
<nav>
  <div class="logo">AIS3 SSO<span>單一登入系統</span></div>
  <div class="right">${nav}</div>
</nav>
${body}
</body></html>`;
}

// ===== Routes =====

app.get("/", (req, res) => {
  res.send(page(
    `<a href="/login?next=/dashboard">測試登入</a>`,
    `<div class="container">
      <div class="hero">
        <div class="badge">OPEN REDIRECT LAB</div>
        <h1>AIS3 <span>SSO</span> 登入系統</h1>
        <p>這套 SSO（Single Sign-On）系統在登入後會把使用者導向 <code>?next=</code> 參數指定的頁面。<br>
        後端沒有驗證 <code>next</code> 的值，這會有什麼問題？</p>
      </div>

      <div class="card">
        <h3>&#127919; 挑戰目標</h3>
        <p>製造一個「看起來是合法 AIS3 SSO 連結」，但實際上會把使用者帶到攻擊者的網站（<code>/evil</code>）的 URL。</p>
        <p>這就是<strong>釣魚攻擊</strong>的基礎：受害者以為連結是安全的，點下去後才發現被導向惡意網站。</p>
      </div>

      <div class="card">
        <h3>&#128161; 提示</h3>
        <ol class="step-list">
          <li>先試試正常的登入流程：點右上角「測試登入」，觀察 URL 變化。</li>
          <li>注意登入時的 URL：<code>http://localhost:${PORT}/login?next=/dashboard</code></li>
          <li>如果把 <code>next</code> 的值換成別的網址，會發生什麼？</li>
          <li>試試讓 <code>next</code> 指向本站的 <code>/evil</code> 頁面，或是外部網址。</li>
          <li>把你製造出來的 URL 貼到下面驗證框，取得 flag。</li>
        </ol>
      </div>

      <div class="card">
        <h3>&#128203; 提交答案</h3>
        <p>把你製造的惡意跳轉 URL（以 <code>http://localhost:${PORT}</code> 開頭）貼在這裡：</p>
        <div class="input-row" style="margin-top:0.8rem">
          <input type="text" id="url-input" placeholder="http://localhost:${PORT}/login?next=..." spellcheck="false">
          <button onclick="check()">驗證</button>
        </div>
        <div id="result"></div>
      </div>

      <div class="card">
        <h3>&#128279; 快速測試連結</h3>
        <div class="link-row">
          <a href="/login?next=/dashboard" class="btn-outline">&#10003; 正常登入 → /dashboard</a>
          <a href="/evil" class="btn-outline">直接前往 /evil</a>
        </div>
      </div>
    </div>

    <script>
    async function check() {
      const url = document.getElementById('url-input').value.trim();
      const res = document.getElementById('result');
      if (!url) return;
      const r = await fetch('/check', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });
      const data = await r.json();
      res.style.display = 'block';
      if (data.ok) {
        res.className = 'ok';
        res.innerHTML = '&#127881; 成功！你製造出了有效的 Open Redirect 釣魚連結。<div class="flag">' + data.flag + '</div>';
      } else {
        res.className = 'fail';
        res.textContent = data.msg;
      }
    }
    document.getElementById('url-input').addEventListener('keydown', e => { if (e.key === 'Enter') check(); });
    </script>`
  ));
});

// VULNERABLE: redirects to any URL without validation
app.get("/login", (req, res) => {
  const next = req.query.next || "/dashboard";
  res.cookie("session", "user_token_abc123", { httpOnly: false });
  // No validation of 'next' — can redirect anywhere
  return res.redirect(next);
});

app.get("/dashboard", (req, res) => {
  res.send(page(
    `<a href="/">回首頁</a>`,
    `<div class="dash-wrap"><div class="dash-box">
      <div class="ok-icon">&#10003;</div>
      <h2>登入成功</h2>
      <p>你進入了正常的 /dashboard 頁面。<br>
      這是 next=/dashboard 的預期結果。<br><br>
      如果 next 換成別的網址，會導向哪裡呢？</p>
    </div></div>`
  ));
});

// Simulated attacker's page
app.get("/evil", (req, res) => {
  const fromRedirect = (req.headers.referer || "").includes(`localhost:${PORT}/login`);
  res.send(page(
    `<a href="/">回首頁</a>`,
    `<div class="evil-wrap"><div class="evil-box">
      <div class="evil-icon">&#9888;&#65039;</div>
      <h2>攻擊者的網站</h2>
      <p>你已經被重新導向到「攻擊者的網站」了！</p>
      <p>在真實攻擊中，這個頁面可能會偽裝成 AIS3 登入頁，<br>誘騙你再次輸入帳號密碼。</p>
      ${fromRedirect
        ? '<p style="margin-top:1rem;color:var(--success)">你確實是透過 /login 的 redirect 來到這裡的。</p>'
        : '<p style="margin-top:1rem;font-size:0.8rem">（你是直接輸入 URL 來到這裡的，不是透過 redirect。）</p>'}
      <p style="margin-top:1rem;font-size:0.8rem">把你的 URL 貼到首頁的驗證框，取得 flag。</p>
    </div></div>`
  ));
});

// Flag validation endpoint
app.post("/check", (req, res) => {
  const url = req.body.url || "";
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return res.json({ ok: false, msg: "無效的 URL 格式，請確認是完整的網址。" });
  }

  // Must appear to be from our domain
  if (parsed.hostname !== "localhost" || parsed.port !== String(PORT)) {
    return res.json({ ok: false, msg: `URL 必須以 http://localhost:${PORT} 開頭（讓受害者以為是合法的 SSO 連結）。` });
  }

  // Must use the redirect endpoint
  if (!parsed.pathname.includes("/login")) {
    return res.json({ ok: false, msg: `URL 路徑要是 /login（這才是看起來合法的入口），再加上 ?next= 參數。` });
  }

  // Extract redirect destination
  const next = parsed.searchParams.get("next") || parsed.searchParams.get("redirect") || parsed.searchParams.get("url");
  if (!next) {
    return res.json({ ok: false, msg: "找不到跳轉參數（next=），試試 /login?next=..." });
  }

  let nextParsed;
  try {
    nextParsed = new URL(next, `http://localhost:${PORT}`);
  } catch {
    return res.json({ ok: false, msg: "next 參數不是有效的 URL。" });
  }

  // Check if it redirects outside (external domain or /evil path)
  const isExternal = nextParsed.hostname !== "localhost" || nextParsed.port !== String(PORT);
  const isEvil = nextParsed.pathname === "/evil";

  if (isExternal || isEvil) {
    return res.json({ ok: true, flag: FLAG });
  }

  return res.json({ ok: false, msg: `next 還是指向本站的一般頁面（${next}）。試試讓它指向 /evil 或外部網址。` });
});

app.listen(PORT, () => {
  console.log(`\n================================================`);
  console.log(`  Open Redirect Lab  —  http://localhost:${PORT}`);
  console.log(`================================================`);
  console.log(`  Exploit: /login?next=/evil`);
  console.log(`        or /login?next=https://example.com`);
  console.log(``);
});
