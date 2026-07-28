const express = require("express");
const cookieParser = require("cookie-parser");
const app = express();
const PORT = 10002;

app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());

// ===== Data =====

const USERS = {
  user1: { password: "user1", name: "小明" },
  user2: { password: "user2", name: "小華" },
  admin: { password: "admin123", name: "管理員" },
};

const SHELVES = {
  user1: {
    title: "小明的書櫃",
    books: [],
    message: "你的書櫃是空的，去圖書館借點書吧！",
  },
  user2: {
    title: "小華的書櫃",
    books: [
      { name: "駭客與畫家", author: "Paul Graham", cover: "\uD83D\uDCD8" },
      { name: "資安風暴", author: "張瑞雄", cover: "\uD83D\uDCD5" },
      { name: "刺客教條：密碼學", author: "不存在的人", cover: "\uD83D\uDCD7" },
    ],
    message: null,
  },
  admin: {
    title: "管理員的秘密書櫃",
    books: [
      { name: "系統管理員密碼本", author: "IT Department", cover: "\uD83D\uDCD3" },
      { name: "Flag Collection Vol.1", author: "AIS3", cover: "\uD83D\uDEA9" },
      { name: "How to Hide Secrets", author: "Nobody", cover: "\uD83D\uDCD4" },
    ],
    message: null,
    flag: "AIS3{1d0r_b00ksh3lf_1s_n0t_y0urs}",
  },
};

// ===== Styles =====

const CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;600;700&family=Playfair+Display:wght@700&display=swap');

  * { margin: 0; padding: 0; box-sizing: border-box; }

  :root {
    --bg: #1a1612;
    --card: #2a2420;
    --card-hover: #352e28;
    --accent: #c8956c;
    --accent-dim: #8a6244;
    --text: #e8ddd3;
    --text-dim: #9a8e83;
    --danger: #c45c4a;
    --success: #5a9a6a;
  }

  body {
    font-family: 'Noto Sans TC', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }

  nav {
    background: #0f0d0b;
    border-bottom: 1px solid #3a3430;
    padding: 0 2rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 60px;
  }
  nav .logo {
    font-family: 'Playfair Display', serif;
    font-size: 1.3rem;
    color: var(--accent);
    letter-spacing: 0.05em;
  }
  nav .logo span { color: var(--text-dim); font-size: 0.8rem; margin-left: 0.5rem; }
  nav .user-info { display: flex; align-items: center; gap: 1rem; font-size: 0.9rem; color: var(--text-dim); }
  nav a { color: var(--accent-dim); text-decoration: none; font-size: 0.85rem; transition: color 0.2s; }
  nav a:hover { color: var(--accent); }

  .container { max-width: 800px; margin: 0 auto; padding: 2rem; }

  .login-wrap {
    display: flex; align-items: center; justify-content: center;
    min-height: calc(100vh - 60px);
  }
  .login-box {
    background: var(--card);
    border: 1px solid #3a3430;
    border-radius: 12px;
    padding: 2.5rem;
    width: 360px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.4);
  }
  .login-box h2 {
    font-family: 'Playfair Display', serif;
    font-size: 1.6rem;
    color: var(--accent);
    margin-bottom: 0.3rem;
  }
  .login-box p.sub { color: var(--text-dim); font-size: 0.85rem; margin-bottom: 1.8rem; }
  .field { margin-bottom: 1.2rem; }
  .field label { display: block; font-size: 0.8rem; color: var(--text-dim); margin-bottom: 0.4rem; text-transform: uppercase; letter-spacing: 0.08em; }
  .field input {
    width: 100%; padding: 0.7rem 0.9rem;
    background: #1a1612; border: 1px solid #3a3430; border-radius: 6px;
    color: var(--text); font-size: 0.95rem; outline: none; transition: border-color 0.2s;
    font-family: 'Noto Sans TC', sans-serif;
  }
  .field input:focus { border-color: var(--accent); }
  .btn {
    width: 100%; padding: 0.75rem;
    background: var(--accent); color: #1a1612; border: none; border-radius: 6px;
    font-size: 0.95rem; font-weight: 600; cursor: pointer; transition: background 0.2s;
    margin-top: 0.5rem;
  }
  .btn:hover { background: #d4a57c; }
  .error { background: rgba(196,92,74,0.15); border: 1px solid var(--danger); color: var(--danger); padding: 0.6rem 0.9rem; border-radius: 6px; font-size: 0.85rem; margin-bottom: 1rem; }

  .shelf-header { margin-bottom: 2rem; }
  .shelf-header h1 { font-family: 'Playfair Display', serif; font-size: 1.8rem; color: var(--accent); }
  .shelf-header .path { font-size: 0.8rem; color: var(--text-dim); margin-top: 0.3rem; font-family: monospace; }

  .empty-shelf {
    background: var(--card); border: 2px dashed #3a3430; border-radius: 12px;
    padding: 3rem; text-align: center; color: var(--text-dim);
  }
  .empty-shelf .icon { font-size: 3rem; margin-bottom: 1rem; }

  .book-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1rem; }
  .book-card {
    background: var(--card); border: 1px solid #3a3430; border-radius: 10px;
    padding: 1.5rem; transition: all 0.2s;
  }
  .book-card:hover { background: var(--card-hover); border-color: var(--accent-dim); transform: translateY(-2px); }
  .book-card .cover { font-size: 2.5rem; margin-bottom: 0.8rem; }
  .book-card .title { font-weight: 600; font-size: 0.95rem; margin-bottom: 0.3rem; }
  .book-card .author { font-size: 0.8rem; color: var(--text-dim); }

  .flag-banner {
    margin-top: 2rem; padding: 1rem 1.5rem;
    background: rgba(90,154,106,0.12); border: 1px solid var(--success); border-radius: 8px;
    font-family: monospace; font-size: 0.95rem; color: var(--success);
  }
`;

// ===== HTML Helpers =====

function layout(navHtml, body) {
  return '<!DOCTYPE html>' +
    '<html lang="zh-TW"><head>' +
    '<meta charset="UTF-8">' +
    '<meta name="viewport" content="width=device-width, initial-scale=1.0">' +
    '<title>AIS3 Library</title>' +
    '<style>' + CSS + '</style>' +
    '</head><body>' +
    '<nav>' + navHtml + '</nav>' +
    body +
    '</body></html>';
}

function navBar(username) {
  var left = '<div class="logo">AIS3 Library<span>圖書館管理系統</span></div>';
  if (!username) return left;
  var displayName = USERS[username] ? USERS[username].name : username;
  return left +
    '<div class="user-info">' +
    '<span>歡迎，' + displayName + '</span>' +
    '<a href="/logout">登出</a>' +
    '</div>';
}

// ===== Routes =====

// Login page
app.get("/login", function (req, res) {
  var errorHtml = req.query.error
    ? '<div class="error">帳號或密碼錯誤</div>'
    : "";
  res.send(layout(navBar(null),
    '<div class="login-wrap"><div class="login-box">' +
    '<h2>登入</h2>' +
    '<p class="sub">請輸入帳號密碼進入圖書館系統</p>' +
    errorHtml +
    '<form method="POST" action="/login">' +
    '<div class="field"><label>帳號</label><input type="text" name="username" autocomplete="off" autofocus></div>' +
    '<div class="field"><label>密碼</label><input type="password" name="password"></div>' +
    '<button class="btn" type="submit">登入</button>' +
    '</form>' +
    '</div></div>'
  ));
});

// Login handler
app.post("/login", function (req, res) {
  var username = req.body.username;
  var password = req.body.password;
  var user = USERS[username];
  if (user && user.password === password) {
    res.cookie("session", username, { httpOnly: true });
    return res.redirect("/" + username);
  }
  res.redirect("/login?error=1");
});

// Logout
app.get("/logout", function (req, res) {
  res.clearCookie("session");
  res.redirect("/login");
});

// Root
app.get("/", function (req, res) {
  var user = req.cookies.session;
  if (user && USERS[user]) return res.redirect("/" + user);
  res.redirect("/login");
});

// ===== Bookshelf (IDOR: only checks if logged in, NOT if you own this shelf) =====

app.get("/:userId", function (req, res) {
  var loggedIn = req.cookies.session;
  if (!loggedIn || !USERS[loggedIn]) return res.redirect("/login");

  var target = req.params.userId;
  var shelf = SHELVES[target];

  if (!shelf) {
    return res.status(404).send(layout(navBar(loggedIn),
      '<div class="container"><h1>404</h1><p>找不到這個書櫃。</p></div>'));
  }

  var content = "";
  if (shelf.books.length === 0) {
    content =
      '<div class="empty-shelf">' +
      '<div class="icon">\uD83D\uDCDA</div>' +
      '<p>' + shelf.message + '</p>' +
      '</div>';
  } else {
    var cards = shelf.books.map(function (b) {
      return '<div class="book-card">' +
        '<div class="cover">' + b.cover + '</div>' +
        '<div class="title">' + b.name + '</div>' +
        '<div class="author">' + b.author + '</div>' +
        '</div>';
    }).join("");
    content = '<div class="book-grid">' + cards + '</div>';
  }

  var flagHtml = shelf.flag
    ? '<div class="flag-banner">\uD83D\uDEA9 ' + shelf.flag + '</div>'
    : "";

  res.send(layout(navBar(loggedIn),
    '<div class="container">' +
    '<div class="shelf-header">' +
    '<h1>' + shelf.title + '</h1>' +
    '<div class="path">/' + target + '</div>' +
    '</div>' +
    content +
    flagHtml +
    '</div>'
  ));
});

// ===== Start =====

app.listen(PORT, function () {
  console.log("");
  console.log("==================================================");
  console.log("  Lab4 - AIS3 Library System");
  console.log("  http://localhost:" + PORT);
  console.log("==================================================");
  console.log("");
  console.log("  Login:  user1 / user1");
  console.log("  IDOR:   try /user2 and /admin");
  console.log("");
});
