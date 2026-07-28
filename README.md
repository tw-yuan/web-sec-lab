# Web Security Labs

我在講課、帶工作坊時做過的 Web 資安 lab 集合。

每一個資料夾是一場課程或活動，裡面收錄該場次用到的所有題目。
所有題目都是獨立可跑的小網站，內建情境說明與提示，讓學員從「看得到、摸得到」的畫面裡自己找出漏洞。

> ⚠️ **警告**：這裡的程式都是**刻意寫成有漏洞**的教學範例。
> 請只在本機或隔離環境執行，**絕對不要**部署到公開的網際網路上。

---

## 場次一覽

| 場次 | 題數 | 涵蓋主題 | 說明 |
|------|------|----------|------|
| [AIS3 台東一日資安體驗營](AIS3-台東一日資安體驗營/) | 9 題 | HTTP method、robots.txt、IDOR、Cookie 竄改、Open Redirect、Directory Listing、Command Injection、XSS、SSTI、SQLi、Path Traversal、File Upload RCE | [題目說明](AIS3-台東一日資安體驗營/README.md) |

---

## 環境需求

依題目而定，大致上是這兩種：

| 類型 | 需要的東西 |
|------|-----------|
| Node.js 題 | Node.js 18+、`npm install express cookie-parser` |
| Docker 題 | Docker + Docker Compose |

---

## 通用啟動方式

**Node.js 題目** — 進到題目資料夾直接跑：

```bash
cd <場次資料夾>/<題目>
node app.js
```

**Docker 題目** — 有 `docker-compose.yml` 的題目：

```bash
cd <場次資料夾>/<題目>
docker compose up -d
# 結束後
docker compose down
```

各題實際的 port 請看該場次的 README。

---

## 目錄慣例

新增場次時照這個結構放，root 的場次一覽再加一列即可：

```
<場次名稱>/
├── README.md              該場次的題目一覽、port 對照、解題提示
├── <題目 A>/
│   └── app.js             單檔 Node.js 題目
└── <題目 B>/
    ├── docker-compose.yml
    ├── Dockerfile
    └── app/               容器化題目
```

- 每題自帶情境與提示，學員不用看 README 也能開始解
- port 從 10000 開始往上編，同場次內不重複
- flag 統一用 `AIS3{...}` 格式（沿用第一場的慣例）

---

## 授權與用途

僅供資安教育與授權測試使用。請勿將此處學到的技術用於未經授權的系統。
