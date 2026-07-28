# AIS3 台東一日資安體驗營

給初學者的 Web 資安實作靶場，共 **9 個題目**、涵蓋 12 個常見的 Web 弱點。

> ⚠️ 這些程式都是**刻意寫成有漏洞**的教學範例，請只在本機或隔離環境執行。

---

## 題目一覽

| # | 題目 | Port | 主題 | 技術 |
|---|------|------|------|------|
| 1 | `http_method` | 10000 | 非標準 HTTP Method 探索 | Node.js（raw TCP + Express） |
| 2 | `robots.txt` | 10001 | robots.txt 資訊洩漏 | Node.js / Express |
| 3 | `idor` | 10002 | IDOR（越權存取他人資源） | Node.js / Express |
| 4 | `injection` | 10003 | Command Injection、XSS、SSTI、SQLi | Python / Flask（Docker） |
| 5 | `cookie-tamper` | 10004 | Cookie 竄改提權 | Node.js / Express |
| 6 | `path-traversal` | 10005 | 路徑穿越讀任意檔案 | Python / Flask（Docker） |
| 7 | `open-redirect` | 10006 | 開放重新導向（釣魚跳板） | Node.js / Express |
| 8 | `file-upload` | 10007 | 上傳限制繞過 → Webshell RCE | PHP / Apache（Docker） |
| 9 | `directory-listing` | 10008 | 目錄列表洩漏內部檔案 | Node.js / Express |

所有 flag 格式皆為 `AIS3{...}`。

---

## 啟動方式

### Node.js 題目（1、2、3、5、7、9）

只需要 `express`（`cookie-tamper` 另外用到 `cookie-parser`）：

```bash
npm install express cookie-parser
```

進到題目資料夾直接跑：

```bash
cd idor
node app.js
# 開啟瀏覽器 → http://localhost:10002
```

其他題目同理，port 對照上面的表格。

### Docker 題目（4、6、8）

```bash
cd injection
docker compose up -d
# 開啟瀏覽器 → http://localhost:10003

# 結束後
docker compose down
```

---

## 各題簡介

### 1. HTTP Method（:10000）
`OPTIONS` 回應裡藏著一個不存在於標準規範中的 method。學員要學會用 `curl -X` 逐一試出正確的動詞。
> 因為 Node 的 HTTP parser 會直接拒絕非標準 method，這題底層是自己開 TCP socket 偷看 request line 再決定怎麼處理。

### 2. robots.txt（:10001）
`robots.txt` 的 `Disallow` 不是存取控制，它只是「請爬蟲不要來」的告示牌——反而把隱藏路徑主動告訴了攻擊者。

### 3. IDOR（:10002）
登入後網址是 `/<userId>`。把 ID 換成別人的，就能看到不屬於自己的書架——後端從頭到尾沒有驗證「這個資源是不是你的」。

### 4. Injection Lab（:10003）
一站四題，模擬一間公司的內部系統：

| 路徑 | 弱點 |
|------|------|
| `/network-tool` | Command Injection |
| `/feedback` | Reflected XSS |
| `/report` | SSTI（Jinja2 模板注入） |
| `/employee-search` | SQL Injection |

完整解題步驟見 [`WRITEUP.md`](injection/WRITEUP.md)。

### 5. Cookie Tamper（:10004）
登入後 cookie 裡直接放著 `role=user`。把它改成 `admin`，後端就照單全收——身分驗證的狀態不該交給客戶端保管。

### 6. Path Traversal（:10005）
`/download?file=` 把使用者輸入直接接到檔案路徑上。用 `../` 一路往上跳，就能讀到 webroot 外的 `/flag.txt`。
> 頁面會同時顯示「要求的路徑」與「實際讀取的路徑」，讓學員直接看見穿越的過程。

### 7. Open Redirect（:10006）
SSO 登入頁的 `?next=` 參數沒有做任何白名單檢查，可以把使用者導向任意外部網站——這正是釣魚攻擊最愛的跳板。

### 8. File Upload（:10007）
上傳檢查只看客戶端送來的 `Content-Type`，而那是可以隨手偽造的。偽裝成 `image/jpeg` 上傳一個 PHP webshell，就能拿到指令執行。

### 9. Directory Listing（:10008）
沒關掉的目錄列表功能，讓 `/files/` 底下的內部文件、暫存備份全部一覽無遺，包含藏在 `internal/` 裡的 flag。

---

## Flags（劇透注意）

<details>
<summary>點開看答案</summary>

| 題目 | Flag |
|------|------|
| http_method | `AIS3{m30w_http_m3th0d_m4st3r}` |
| robots.txt | `AIS3{r0b0ts_txt_1s_n0t_s3cur1ty}` |
| idor | `AIS3{1d0r_b00ksh3lf_1s_n0t_y0urs}` |
| injection — Command Injection | `AIS3{c0mm4nd_1nj3ct10n_g1v3s_y0u_sh3ll}` |
| injection — XSS | `AIS3{xss_st34ls_c00k13s_l1k3_c4ndy}` |
| injection — SSTI | `AIS3{sst1_t3mpl4t3_1nj3ct10n_pwn3d}` |
| injection — SQLi | `AIS3{sql_1nj3ct10n_byp4ss_3v3ryth1ng}` |
| cookie-tamper | `AIS3{c00k13_r0l3_1s_n0t_s3cur1ty}` |
| path-traversal | `AIS3{p4th_tr4v3rs4l_3sc4p3d_th3_s4ndb0x}` |
| open-redirect | `AIS3{0p3n_r3d1r3ct_ph1sh1ng_tr4p}` |
| file-upload | `AIS3{f1l3_upl04d_byp4ss_RCE_pwn3d}` |
| directory-listing | `AIS3{d1r_l1st1ng_l34ks_3v3ryth1ng}` |

</details>
