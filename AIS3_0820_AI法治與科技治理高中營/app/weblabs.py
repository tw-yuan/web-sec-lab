"""Web 實戰靶場（前端驗證繞過 / IDOR）的後端。

設計原則（對應課程規格書 §0）：
- flag 絕不落在前端：HTML/JS/CSS/一般 API 回應都不含 flag。
- flag 只在「漏洞被實際利用」的條件成立時，由後端回傳。
- 每關獨立、per-user flag：沿用 app/flags.py 的 flag_for()，貼別人的無效。
- 這些題都是**唯讀 / 無副作用**：不寫 DB、不改共享狀態，多人同打互不干擾，免重置。
  IDOR 的「別人資料」由 user_id 決定性衍生，所以每個學生打到的 target 都帶自己的 flag。

破關判定全部是後端的決定性規則（不經 LLM），與平臺其餘部分一致。
"""

from __future__ import annotations

import base64
import binascii
import hashlib

from fastapi import APIRouter

from . import flags as flagmod

router = APIRouter(prefix="/api/weblab", tags=["weblab"])


# --- 由 main.py 在啟動時注入，避免與 main 產生循環匯入 -----------------------
class _Ctx:
    st = None
    require_user = None
    ApiError = None


_ctx = _Ctx()


def configure(*, st, require_user, api_error_cls) -> None:
    _ctx.st = st
    _ctx.require_user = require_user
    _ctx.ApiError = api_error_cls


def _err(status: int, code: str, message: str):
    return _ctx.ApiError(status, code, message)


async def _auth(session_id: str, cid: str) -> dict:
    """驗證 session，並確認 cid 確實是一道啟用中的 weblab 題。"""
    st = _ctx.st
    user = await _ctx.require_user(session_id)
    ch = st.challenges.get(cid) if st.challenges else None
    if ch is None or ch.win.get("kind") != "weblab":
        raise _err(404, "unknown_challenge", "找不到這道靶場題。")
    return user


def _flag(user: dict, cid: str) -> str:
    return flagmod.flag_for(_ctx.st.settings.server_secret, user["user_id"], cid)


def _win(user: dict, cid: str, message: str) -> dict:
    """漏洞利用成立 → 回傳該使用者這一題的 flag。"""
    return {"solved": True, "flag": _flag(user, cid), "message": message}


def _to_int(raw, field: str) -> int:
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        raise _err(400, "bad_input", f"{field} 必須是數字。")


# 一批有真實感的假訂單，讓學生體會「這是別人的隱私」（§B 設計提醒）。
# 這些是**公開可讀**的誘餌資料，本身不含 flag；帶 flag 的只有 target。
_FAKE_ORDERS = {
    1001: {"name": "王小明", "item": "藍牙耳機", "amount": 1290},
    1002: {"name": "陳美玲", "item": "行動電源 10000mAh", "amount": 690},
    1003: {"name": "林建宏", "item": "機械鍵盤", "amount": 2480},
    1004: {"name": "張雅婷", "item": "USB-C 快充線", "amount": 220},
    1005: {"name": "黃志偉", "item": "27 吋螢幕", "amount": 5990},
}
_B1_TARGET = 1337       # B-1 / 帶 flag 的訂單
_WEB2_TARGET = 2087     # Web-2 / 帶 flag 的私訊
_B3_TARGET_EMAIL = "principal@ncse.example"   # B-3 / 從公開成員頁可取得


def _fake_order(oid: int) -> dict | None:
    if oid in _FAKE_ORDERS:
        return dict(_FAKE_ORDERS[oid])
    return None


# ===========================================================================
# Lab A — 前端不可信（前端驗證繞過）
# ===========================================================================


@router.post("/a1/buy")
async def a1_buy(body: dict):
    """A-1：VIP 方案標示『已售完』且按鈕 disabled，但後端根本沒檢查售完狀態。"""
    user = await _auth(body.get("session_id", ""), "a1")
    plan = str(body.get("plan", "")).strip().lower()
    if plan == "vip":
        return _win(user, "a1", "後端收到了 VIP 方案的下單請求 —— 它從來沒檢查過『已售完』！")
    raise _err(400, "no_exploit", "這個方案本來就買得到，沒有觸發漏洞。試試那個被鎖住的 VIP 方案。")


@router.post("/a2/checkout")
async def a2_checkout(body: dict):
    """A-2：後端直接採用前端送來的 price，不與真實售價比對。"""
    user = await _auth(body.get("session_id", ""), "a2")
    price = _to_int(body.get("price"), "price")
    qty = _to_int(body.get("qty", 1), "qty")
    real_price = 3000
    total = price * qty
    if total < real_price:
        return _win(
            user, "a2",
            f"後端照單全收：你用 {total} 元買到了原價 {real_price} 元的商品。",
        )
    return {
        "solved": False,
        "total": total,
        "message": f"以 {total} 元成立訂單，沒有佔到便宜。回 Elements 把 price 改小一點？",
    }


@router.post("/a3/order")
async def a3_order(body: dict):
    """A-3：前端 JS 擋『數量 > 5』，但後端未做上限檢查。"""
    user = await _auth(body.get("session_id", ""), "a3")
    qty = _to_int(body.get("qty"), "qty")
    if qty <= 0:
        raise _err(400, "bad_input", "數量要大於 0。")
    if qty > 5:
        return _win(
            user, "a3",
            f"後端接受了 {qty} 件的訂單 —— 前端那句『最多 5 件』只是在你的電腦上跑而已。",
        )
    return {
        "solved": False,
        "message": f"{qty} 件在前端允許的範圍內，這樣送出不會觸發漏洞。"
                   "得想辦法不經過前端 JS，直接把請求送給後端。",
    }


# ===========================================================================
# Lab B — IDOR 越權存取
# ===========================================================================


@router.get("/b1/order")
async def b1_order(session_id: str = "", oid: str = ""):
    """B-1：訂單 id 為明文流水號，後端只驗登入、未驗歸屬。"""
    user = await _auth(session_id, "b1")
    n = _to_int(oid, "oid")
    if n == _B1_TARGET:
        return _win(
            user, "b1",
            "你讀到了不屬於你的訂單 #1337。系統確認了『你有登入』，卻沒確認『這筆是不是你的』。",
        )
    o = _fake_order(n)
    if o is None:
        raise _err(404, "no_order", "查無此訂單編號。")
    return {"solved": False, "order": {"id": n, **o},
            "message": "這是別人的訂單 —— 你連問都沒問就看到了。換個編號繼續找目標。"}


@router.get("/b2/msg")
async def b2_msg(session_id: str = "", oid: str = ""):
    """B-2：id 經 Base64 編碼，但編碼不是加密，後端解碼後仍未驗歸屬。"""
    user = await _auth(session_id, "b2")
    try:
        decoded = base64.b64decode(oid.strip(), validate=True).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        raise _err(400, "bad_input", "這個編號看起來像 Base64，但解不開。結尾的 == 是提示。")
    n = _to_int(decoded, "oid")
    if n == _B1_TARGET:
        return _win(
            user, "b2",
            "Base64 只是換個樣子、不是上鎖。你解開 → 改成 1337 → 編回去，就讀到了目標。",
        )
    o = _fake_order(n)
    if o is None:
        raise _err(404, "no_order", "查無此訂單編號。")
    return {"solved": False, "order": {"id": n, **o},
            "message": f"解出來是 {n}，這是別人的訂單。目標訂單是 1337。"}


@router.get("/b3/members")
async def b3_members(session_id: str = ""):
    """B-3：公開成員頁，任何人都看得到 email（其中包含 target）。"""
    await _auth(session_id, "b3")
    return {
        "members": [
            {"name": "系統管理員", "email": _B3_TARGET_EMAIL, "role": "校長"},
            {"name": "王小明", "email": "ming@ncse.example", "role": "學生"},
            {"name": "陳美玲", "email": "meiling@ncse.example", "role": "老師"},
        ],
        "hint": "訂單編號 = 使用者 email 的 MD5。難猜不代表安全。",
    }


@router.get("/b3/record")
async def b3_record(session_id: str = "", oid: str = ""):
    """B-3：id 是 email 的 MD5。學生從公開成員頁拿到 target email、自算 MD5 即可構造。"""
    user = await _auth(session_id, "b3")
    target = hashlib.md5(_B3_TARGET_EMAIL.encode("utf-8")).hexdigest()
    if oid.strip().lower() == target:
        return _win(
            user, "b3",
            "你從公開資訊推出了『難猜』的編號 —— security by obscurity 一被推出來就等於沒防。",
        )
    raise _err(404, "no_record", "查無此紀錄。（提示：算算看某位成員 email 的 MD5）")


# ===========================================================================
# Mini CTF — Web 題組
# ===========================================================================


@router.post("/web1/reveal")
async def web1_reveal(body: dict):
    """Web-1（A-1 變體）：disabled 的『查看隱藏優惠』按鈕，解鎖點擊後後端就發 flag。"""
    user = await _auth(body.get("session_id", ""), "web1")
    return _win(user, "web1", "隱藏優惠被你解鎖了 —— disabled 只是畫面上的鎖。")


@router.get("/web2/msg")
async def web2_msg(session_id: str = "", oid: str = ""):
    """Web-2（B-2 變體）：私訊查詢，id 為 Base64，讀取 target 的私訊拿 flag。"""
    user = await _auth(session_id, "web2")
    try:
        decoded = base64.b64decode(oid.strip(), validate=True).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        raise _err(400, "bad_input", "訊息編號看起來是 Base64，但解不開。")
    n = _to_int(decoded, "oid")
    if n == _WEB2_TARGET:
        return _win(user, "web2", "你讀到了別人的私訊 #2087。編碼不是加密。")
    return {"solved": False, "message": f"這是 #{n} 的訊息，不是目標。目標私訊編號是 2087。"}


@router.post("/web3/feedback")
async def web3_feedback(body: dict):
    """Web-3（A-3 變體）：前端 JS 限定只有 @school.edu.tw 能提交，後端沒擋。"""
    user = await _auth(body.get("session_id", ""), "web3")
    email = str(body.get("email", "")).strip().lower()
    if "@" not in email:
        raise _err(400, "bad_input", "請填一個 email。")
    domain = email.rsplit("@", 1)[-1]
    if domain != "school.edu.tw":
        return _win(
            user, "web3",
            f"你用校外信箱（{domain}）提交成功了 —— 前端那條網域限制只在瀏覽器裡，後端根本沒擋。",
        )
    return {"solved": False,
            "message": "你用的是校內信箱，這是正常提交、沒有觸發漏洞。試試繞過限制、用校外信箱送。"}


@router.post("/web4/register")
async def web4_register(body: dict):
    """Web-4（壓軸，A+B 組合）：名額已滿（前端 disabled）＋ 報名 API 帶 slot 參數。

    先繞前端 disabled 才送得出報名（第一階段，被分到候補 slot=99，尚無 flag）；
    再把 slot 改成 0（VIP 名額），後端未驗證該 slot 是否可指定 → 發 flag。
    """
    user = await _auth(body.get("session_id", ""), "web4")
    if "slot" not in body or body.get("slot") in (None, ""):
        # 第一階段：繞過 disabled 後的正常報名，被丟到候補。
        return {
            "solved": False, "slot": 99,
            "message": "報名成功，但你被分配到候補區（slot=99）。你能不能自己指定要哪個 slot？",
        }
    slot = _to_int(body.get("slot"), "slot")
    if slot == 0:
        return _win(
            user, "web4",
            "你把 slot 改成 0，插隊到 VIP 名額 —— 兩個小漏洞串起來就讓你搶到位子。",
        )
    return {"solved": False, "slot": slot,
            "message": f"你被分到 slot={slot}。VIP 名額是 slot 0，改改看？"}
