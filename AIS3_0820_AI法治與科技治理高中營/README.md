# NCSE AI Security CTF

一個以 **LLM / 提示注入安全**為主題的 CTF 平臺。學員以「參賽代碼」登入,對每一關被灌了防護的 AI 客服/助理發動攻擊(prompt leak、間接注入、工具濫用、XSS…),把該關的 per-user flag 逼出來提交得分;另有一關反過來要學員**當防守方**寫系統提示去擋攻擊。

- 後端:FastAPI(全非同步)+ SQLite(WAL)+ OpenRouter LLM,單一 uvicorn worker。
- 前端:純靜態 HTML/CSS/JS(`static/`),無打包步驟。
- UI 文案為繁體中文(zh-TW)。

> ⚠️ 這是一個**攻擊教學靶場**,題目本身就是刻意可被攻破的 AI 系統,僅供授權的教學活動使用。

---

## 快速開始

```bash
# 1. 準備環境變數(內含金鑰,勿進版控)
cp .env .env.local   # 或直接編輯 .env

# 2. 建置並啟動(前景 8002 對外)
docker compose up --build -d

# 3. 確認存活
curl -s localhost:8002/api/health      # -> {"ok": true}
```

- 對外埠 `8002` → 容器內 `8000`。
- 資料(SQLite、`users.csv`、`server_secret`)存在具名 volume `ais-ctf-data`(掛到 `/srv/data`)。

本機開發(不用 Docker):

```bash
pip install -r requirements.txt
DATA_DIR=./data uvicorn app.main:app --reload --host 0.0.0.0 --port 8002
```

沒有測試套件;「驗證」= 起 app 實際走一遍流程。

---

## 參賽代碼(usercode)

登入靠的是每位學員一組的**參賽代碼**,即 `users` 表的 `token`,格式 `XXXX-XXXX`(去掉易混淆的 `0/O/1/I/L`)。登入不分大小寫、有沒有連字號都可以。

### 產生代碼

```bash
# 產生 80 組(寫入 DB,並把清單附加到 ${DATA_DIR}/users.csv)
docker compose exec app python scripts/gen_users.py --count 80

# 順便印出每人每題的 flag(對答案用,機密,勿外流)
docker compose exec app python scripts/gen_users.py --count 80 --show-flags
```

- `gen_users.py` 是**附加**的:會從目前已有的人數往後接續編號(`u001`, `u002`, …),`users.csv` 也是 append。要「乾淨的 N 組」請先清掉舊 DB 與舊 `users.csv`(見下方「重置」)。
- `SEED_USERS` 環境變數:app **啟動時**若 DB 一個 user 都沒有,會自動建立 `SEED_USERS` 組。目前設 `80`,所以在全新的 volume 上第一次開機就會自動有 80 組。手動 `gen_users` 與這條自動路徑二擇一即可(DB 非空時自動建立不會觸發)。

`users.csv` 欄位:`user_id, display_name, token`,可直接列印裁切發放。

### 重置(活動前清場)

保留代碼、只清解題進度/排行榜(flag 不變,因為 flag = `SERVER_SECRET + user_id + challenge_id` 算出來的):

```bash
docker compose exec app python scripts/reset_progress.py --yes           # 先不加 --yes 可預覽
docker compose exec app python scripts/reset_progress.py --yes --drop-users u079 u080   # 只砍測試帳號
```

**連使用者一起砍掉重來**(已發出的代碼會全部失效,需重印):

```bash
docker compose exec app python scripts/reset_progress.py --yes --drop-all-users
# 之後重新產生,並記得刪掉舊的 users.csv 再 gen_users
```

---

## 題目一覽(`challenges.json`,共 30 關)

### LLM / 提示注入題(20 關)

| 分類 | 關卡 | 攻擊型態 |
|---|---|---|
| 熱身 leak | `l1a`–`l1d` | 直接/繞過系統提示,把機密逼出來 |
| 進階 leak | `l2a`–`l2c` | 偷規則、裝傻客服、跨使用者資料 |
| 間接注入 / 工具 | `l3a`–`l3d` | 文件夾帶指令、誘導助理寄信/呼叫工具(`indirect_leak` / `tool_exfil` / `tool_call`) |
| XSS | `l4a`, `l4b` | 讓注入的 HTML/JS 真的跑起來 |
| 決賽 | `final1`–`final6` | 多層過濾、代理人上鉤、`onerror` 封印下的 XSS(300–500 分) |
| 防守 | `def` | 反過來寫系統提示擋掉攻擊 payload(取歷次最佳分) |

### Web 實戰題(10 關,`type: "weblab"`)

零基礎友善的經典 Web 漏洞,只用瀏覽器開發者工具(F12)即可全破。破關判定與 flag 發放都在後端(`app/weblabs.py`),**不經 LLM**。

| 題組 | 關卡 | 攻擊型態 |
|---|---|---|
| WEB — 前端不可信 | `a1`(解鎖 disabled 按鈕)、`a2`(改 hidden 價格)、`a3`(繞過 JS 數量驗證) | 前端驗證繞過:後端**故意信任**前端送的 price / qty / 售完狀態 |
| WEB — 越權(IDOR) | `b1`(明文 id)、`b2`(Base64 id)、`b3`(email 的 MD5) | 後端**故意不檢查資源歸屬**,改 `oid` 就能讀別人的訂單;編碼/難猜都不是安全 |
| WEBX — Mini CTF | `web1`(解鎖優惠)、`web2`(Base64 IDOR 私訊)、`web3`(繞過網域限制)、`web4`(前端繞過＋參數竄改**組合題**,壓軸 400 分) | A/B 招式的變體與組合 |

每題 flag 是**每人不同**的(綁 `user_id`),所以抄別人的 flag 無效;提交別人的 flag 會被記為可疑(`flag_submissions.suspected_owner`),管理端看得到。

**Web 靶場的反作弊設計(對應課程規格書 §0.1)**:flag 絕不落在前端(HTML/JS/CSS/一般 API 回應都沒有),只有「漏洞被實際利用」時後端才回傳;靶場 DOM 由 JS 建構,「檢視原始碼」看不到任何提示。IDOR 的「別人資料」由 `user_id` 決定性衍生,所以**唯讀、無副作用、免重置**,多人同打互不干擾。靶場頁在 `static/labs/lab.html?id=<關卡>`,學生從題目頁點「開啟靶場」進入,打出 flag 後貼回題目頁提交。

---

## 設定(`.env`)

由 `app/config.py` 讀取。全部有預設值;金鑰只留在後端,永不下發前端、不寫 log。

| 變數 | 說明 |
|---|---|
| `SERVER_SECRET` | **最關鍵**。所有 per-user flag 從它推導,必須跨重啟穩定。刪掉會讓所有人的 flag 改變。未設時會 fallback 到 `DATA_DIR/server_secret` 檔或自動產生。 |
| `ADMIN_TOKEN` | 管理端(`/admin.html`、`/api/admin/*`)的權杖。 |
| `OPENROUTER_API_KEY` / `OPENROUTER_URL` / `OPENROUTER_MODEL` | LLM 端點。預設模型 `meta-llama/llama-3.1-8b-instruct`。 |
| `FAKE_LLM` | `1` = 不打 OpenRouter、回傳假回覆(**只能開發用,活動禁用**)。 |
| `SEED_USERS` | 啟動時自動建立的代碼組數(DB 為空時才觸發)。目前 `80`。 |
| `GLOBAL_TOKEN_BUDGET` | 全域 token 預算,`0` = 無上限。活動當天限流全設 0 時,這是唯一的成本閘門。 |
| `RATE_*` / `MAX_*` / `DEF_*` | 各種限流與長度上限,`0` = 不限。 |
| `SESSION_TTL_SECONDS` / `XSS_NONCE_TTL_SECONDS` | session 與 XSS 一次性 nonce 的存活時間。 |

> 🔐 `.env` 內含真實金鑰(`SERVER_SECRET` / `ADMIN_TOKEN` / `OPENROUTER_API_KEY`),**不要 commit 進 git**。

---

## API 一覽

- 學員:`POST /api/login`(用代碼換 session)、`GET /api/me`、`GET /api/challenges`、`GET /api/challenges/{id}`、`POST /api/chat`、`POST /api/hint`、`POST /api/submit-flag`、`POST /api/xss-callback`、`POST /api/defense/submit`、`GET /api/defense/payloads`、`GET /api/leaderboard`。
- Web 實戰題(`/api/weblab/*`,漏洞被利用時才回傳該使用者的 flag):`a1/buy`、`a2/checkout`、`a3/order`、`b1/order`、`b2/msg`、`b3/members`、`b3/record`、`web1/reveal`、`web2/msg`、`web3/feedback`、`web4/register`。
- 管理(需 `ADMIN_TOKEN`):`GET /api/admin/stats`、`/api/admin/users`、`/api/admin/overview`、`POST /api/admin/final-open`、`POST /api/admin/seed-users`。
- 靜態頁:`/`(登入/題目)、`/challenge.html`、`/leaderboard.html`、`/admin.html`、`/sandbox.html`。

---

## 目錄結構

```
ais3-0828/
├── app/                # FastAPI 後端
│   ├── main.py         # 路由 + 啟動 lifespan(依 SEED_USERS 自動建碼)
│   ├── config.py       # 環境變數設定
│   ├── db.py           # SQLite 儲存層(schema、seed_users、reset)
│   ├── challenges.py   # 讀 challenges.json(含 weblab 題型 schema)
│   ├── flags.py        # per-user flag 推導(SERVER_SECRET+user_id+challenge_id)
│   ├── filters.py      # 各關的輸出過濾器
│   ├── judging.py      # LLM 題的破關判定
│   ├── weblabs.py      # Web 實戰題(前端繞過 / IDOR)的漏洞端點與 flag 發放
│   ├── llm.py          # OpenRouter 客戶端
│   ├── payloads.py     # 防守關的攻擊 payload 集
│   ├── ratelimit.py    # 限流
│   └── schemas.py      # Pydantic 請求/回應
├── static/             # 純前端(html/css/js)
│   └── labs/           # Web 實戰靶場頁(lab.html + lab.js,故意有漏洞)
├── scripts/            # gen_users / reset_progress / verify_* / gen_users …
├── challenges.json     # 題目定義(20 關)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env                # 金鑰(勿進版控)
```

---

## 資料與持久化

- SQLite `ctf.db`(WAL 模式)在 `${DATA_DIR}`,預設 `/srv/data`(容器)/ `./data`(本機)。
- **`server_secret` 檔與整個 volume 千萬別刪**:一旦 `SERVER_SECRET` 改變,所有已發出的 flag 全部失效。正式活動請用環境變數固定它。
- `users.csv` 是可列印的代碼發放清單。
