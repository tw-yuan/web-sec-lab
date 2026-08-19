/* Web 實戰靶場頁。這裡的頁面「故意有漏洞」，但 flag 永遠不在前端 ——
   漏洞的破關判定與 flag 發放都在後端 /api/weblab/*（見 app/weblabs.py）。
   所有 DOM 都用 JS 建構，所以「檢視原始碼」看不到任何有用的東西。 */

import { requireSession, el, apiGet, apiPost, mountHeader } from '../js/common.js';

const S = requireSession();
const params = new URLSearchParams(location.search);
const ID = params.get('id') || '';
const root = document.getElementById('lab');

mountHeader('list');

/* ---- 共用小工具 ---------------------------------------------------- */

function f12Hint(text) {
  return el('div', { class: 'notice', style: 'margin-bottom:14px' },
    '🛠️ 先按 ', el('b', {}, 'F12'), ' 打開開發者工具。', text ? ' ' + text : '');
}

function backLink() {
  return el('p', { style: 'margin-top:18px' },
    el('a', { href: `/challenge.html?id=${encodeURIComponent(ID)}` }, '← 回題目頁提交旗標'));
}

function flagBox(r) {
  if (r && r.solved && r.flag) {
    return el('div', { class: 'notice ok' },
      el('div', { style: 'font-weight:700;font-size:16px' }, '🎉 漏洞利用成功！'),
      r.message ? el('div', { class: 'small', style: 'margin:6px 0' }, r.message) : null,
      el('div', { style: 'margin-top:6px' }, '你的旗標：',
        el('code', { style: 'user-select:all' }, r.flag)),
      el('div', { class: 'small muted', style: 'margin-top:6px' },
        '把這一整串（含 FLAG{}）貼回題目頁的「提交旗標」框送出。每個人的旗標都不一樣，貼別人的不會過。'));
  }
  return el('div', { class: 'notice' }, (r && r.message) || '沒有觸發漏洞，再想想。');
}

function showResult(host, r) { host.replaceChildren(flagBox(r)); }
function showError(host, e) {
  host.replaceChildren(el('div', { class: 'notice bad', text: e.message || '發生錯誤' }));
}

function card(...kids) { return el('div', { class: 'card' }, ...kids); }
function h1(t) { return el('h1', {}, t); }

/* ================================================================== */
/* Lab A — 前端不可信                                                 */
/* ================================================================== */

function labA1() {
  const out = el('div', { style: 'margin-top:14px' });
  const buyBtn = el('button', {
    disabled: 'disabled',
    onclick: async () => {
      try { showResult(out, await apiPost('/api/weblab/a1/buy', { session_id: S.session_id, plan: 'vip' })); }
      catch (e) { showError(out, e); }
    },
  }, '立即購買');

  root.replaceChildren(
    h1('宅宅購物 — VIP 限量商品'),
    f12Hint('用 Elements 面板找那顆買不了的按鈕。'),
    card(
      el('div', { class: 'row wrapped' },
        el('div', {},
          el('div', { style: 'font-size:18px;font-weight:700' }, '限量聯名公仔（VIP 專屬）'),
          el('div', { class: 'muted' }, 'NT$3,000'),
          el('div', { class: 'badge', style: 'margin-top:8px' }, '限量已售完')),
        el('span', { class: 'spacer' }),
        buyBtn),
      el('p', { class: 'small muted', style: 'margin-top:10px' },
        '這顆按鈕現在是灰的（disabled）。但後端從來沒檢查過「售完」這件事……')),
    out, backLink());
}

function labA2() {
  const out = el('div', { style: 'margin-top:14px' });
  // 故意的漏洞：價格存在一個「看不見」的欄位裡，結帳時前端把它原封不動送給後端。
  const priceInput = el('input', { type: 'hidden', id: 'price', name: 'price', value: '3000' });
  const checkout = el('button', {
    onclick: async () => {
      const price = document.getElementById('price').value;   // 讀「當下」的值 → DevTools 改了就生效
      try {
        showResult(out, await apiPost('/api/weblab/a2/checkout',
          { session_id: S.session_id, price, qty: 1 }));
      } catch (e) { showError(out, e); }
    },
  }, '結帳');

  root.replaceChildren(
    h1('宅宅購物 — 結帳'),
    f12Hint('在 Elements 用 Ctrl+F 搜 price，找那個 type=hidden 的欄位。'),
    card(
      priceInput,
      el('div', { class: 'row wrapped' },
        el('div', {},
          el('div', { style: 'font-size:18px;font-weight:700' }, '藍牙機械鍵盤'),
          el('div', { class: 'muted' }, '應付金額：NT$3,000 × 1')),
        el('span', { class: 'spacer' }),
        checkout),
      el('p', { class: 'small muted', style: 'margin-top:10px' },
        '「隱藏」不等於「安全」—— 那個 hidden 欄位的值照樣在你手上。')),
    out, backLink());
}

function labA3() {
  const out = el('div', { style: 'margin-top:14px' });
  const qty = el('input', { type: 'number', id: 'qty', value: '1', min: '1', style: 'width:120px' });
  const order = el('button', {
    onclick: async () => {
      const q = parseInt(document.getElementById('qty').value, 10) || 0;
      // 前端驗證：這一段只在「你的電腦上」跑。
      if (q > 5) { alert('每人限購 5 件，數量不得超過 5。'); return; }
      if (q <= 0) { alert('數量要大於 0。'); return; }
      try {
        showResult(out, await apiPost('/api/weblab/a3/order', { session_id: S.session_id, qty: q }));
      } catch (e) { showError(out, e); }
    },
  }, '下單');

  root.replaceChildren(
    h1('宅宅購物 — 每人限購 5 件'),
    f12Hint('先送一筆正常的訂單，去 Network 面板把它「Copy as fetch」。'),
    card(
      el('div', { class: 'row', style: 'align-items:center;gap:10px' },
        el('span', {}, '購買數量：'), qty, order),
      el('p', { class: 'small muted', style: 'margin-top:10px' },
        '直接改數量欄位再按下單是沒用的（送出時 JS 會重新讀值擋你）。'
        + '你得繞過這段 JS，直接把請求送給後端。')),
    out, backLink());
}

/* ================================================================== */
/* Lab B — IDOR                                                       */
/* ================================================================== */

/* 讀網址上的 oid、查一筆訂單並顯示。教學重點是「改網址那個 oid」。 */
function idorViewer({ title, endpoint, oidHint, extraNote }) {
  const oid = params.get('oid') || '';
  const out = el('div', { style: 'margin-top:14px' });
  const box = el('div', { class: 'card', style: 'margin-top:14px' },
    el('p', { class: 'muted', style: 'margin:0' }, '載入中…'));

  // 讓學生也能在頁內改 oid（等同改網址）
  const input = el('input', { type: 'text', value: oid, style: 'font-family:var(--mono);width:220px' });
  const go = el('button', {
    onclick: () => {
      const v = input.value.trim();
      location.href = `${location.pathname}?id=${encodeURIComponent(ID)}&oid=${encodeURIComponent(v)}`;
    },
  }, '查詢');

  async function load() {
    try {
      const r = await apiGet(endpoint, { session_id: S.session_id, oid });
      if (r.solved) { showResult(out, r); box.replaceChildren(el('p', { class: 'muted', style: 'margin:0' }, '（這筆就是目標）')); return; }
      const o = r.order || {};
      box.replaceChildren(
        el('div', { class: 'small muted' }, `訂單 #${o.id}`),
        el('div', { style: 'font-size:16px;font-weight:700;margin-top:4px' }, o.name || '（無姓名）'),
        el('div', { class: 'muted' }, `${o.item || ''}　NT$${o.amount ?? ''}`),
        r.message ? el('div', { class: 'notice', style: 'margin-top:10px' }, r.message) : null);
      out.replaceChildren();
    } catch (e) {
      box.replaceChildren(el('div', { class: 'notice bad' }, e.message || '查詢失敗'));
      out.replaceChildren();
    }
  }

  root.replaceChildren(
    h1(title),
    f12Hint(oidHint),
    card(
      el('div', { class: 'small muted' }, '目前查詢的編號（oid）'),
      el('div', { class: 'row', style: 'align-items:center;gap:10px;margin-top:6px' }, input, go),
      extraNote ? el('p', { class: 'small muted', style: 'margin-top:8px' }, extraNote) : null),
    box, out, backLink());
  load();
}

function labB1() {
  idorViewer({
    title: '線上訂單查詢系統',
    endpoint: '/api/weblab/b1/order',
    oidHint: '看網址列的 oid，把它換成別的數字。',
    extraNote: '你可以直接改網址列的 oid，或用上面的框查詢。目標訂單是 1337。',
  });
}

function labB2() {
  idorViewer({
    title: '線上訂單查詢系統（進階）',
    endpoint: '/api/weblab/b2/msg',
    oidHint: 'oid 結尾的 == 是 Base64 的味道。Console 用 atob() 解、btoa() 編回去。',
    extraNote: 'oid 是 Base64 編碼。解開 → 改成 1337 → 編回去。可在 Console 用 atob(\'...\') / btoa(\'1337\')。',
  });
}

function labB3() {
  const out = el('div', { style: 'margin-top:14px' });
  const membersBox = el('div', { class: 'card', style: 'margin-top:14px' },
    el('p', { class: 'muted', style: 'margin:0' }, '載入成員列表中…'));
  const oidInput = el('input', { type: 'text', placeholder: '32 位 MD5', style: 'font-family:var(--mono);width:280px' });
  const lookup = el('button', {
    onclick: async () => {
      const v = oidInput.value.trim();
      if (!v) return;
      try { showResult(out, await apiGet('/api/weblab/b3/record', { session_id: S.session_id, oid: v })); }
      catch (e) { showError(out, e); }
    },
  }, '查詢紀錄');

  root.replaceChildren(
    h1('會員紀錄查詢系統'),
    f12Hint('訂單編號 = email 的 MD5。從下面的公開成員列表拿到目標 email，自己算 MD5。'),
    membersBox,
    card(
      el('div', { class: 'small muted' }, '用紀錄編號（email 的 MD5）查詢'),
      el('div', { class: 'row', style: 'align-items:center;gap:10px;margin-top:6px' }, oidInput, lookup),
      el('p', { class: 'small muted', style: 'margin-top:8px' },
        '算 MD5 可用線上工具，或終端機：echo -n \'someone@ncse.example\' | md5sum')),
    out, backLink());

  (async () => {
    try {
      const r = await apiGet('/api/weblab/b3/members', { session_id: S.session_id });
      membersBox.replaceChildren(
        el('div', { class: 'small muted', style: 'margin-bottom:6px' }, '公開成員列表'),
        ...r.members.map((m) => el('div', { class: 'row wrapped', style: 'gap:10px' },
          el('b', {}, m.name),
          el('span', { class: 'badge' }, m.role),
          el('code', {}, m.email))),
        r.hint ? el('div', { class: 'small muted', style: 'margin-top:8px' }, r.hint) : null);
    } catch (e) {
      membersBox.replaceChildren(el('div', { class: 'notice bad' }, e.message));
    }
  })();
}

/* ================================================================== */
/* Mini CTF                                                           */
/* ================================================================== */

function labWeb1() {
  const out = el('div', { style: 'margin-top:14px' });
  const btn = el('button', {
    disabled: 'disabled',
    onclick: async () => {
      try { showResult(out, await apiPost('/api/weblab/web1/reveal', { session_id: S.session_id })); }
      catch (e) { showError(out, e); }
    },
  }, '查看隱藏優惠');
  root.replaceChildren(
    h1('會員專屬 — 隱藏優惠'),
    f12Hint('那顆按鈕身上有個屬性讓它變灰。'),
    card(
      el('div', { class: 'row wrapped' },
        el('div', { class: 'muted' }, '本優惠僅限特定會員查看。'),
        el('span', { class: 'spacer' }), btn)),
    out, backLink());
}

function labWeb2() {
  idorViewer({
    title: '站內私訊查詢',
    endpoint: '/api/weblab/web2/msg',
    oidHint: 'oid 是 Base64。Console 用 atob()/btoa()。',
    extraNote: 'oid 是 Base64 編碼的訊息編號。目標私訊編號是 2087。',
  });
}

function labWeb3() {
  const out = el('div', { style: 'margin-top:14px' });
  const email = el('input', { type: 'email', placeholder: 'you@school.edu.tw', style: 'width:260px' });
  const submit = el('button', {
    onclick: async () => {
      const v = email.value.trim();
      const domain = v.split('@')[1] || '';
      // 前端限制：只有校內信箱能提交（這段只在瀏覽器裡跑）。
      if (domain.toLowerCase() !== 'school.edu.tw') {
        alert('只有 @school.edu.tw 的校內信箱可以提交意見。');
        return;
      }
      try { showResult(out, await apiPost('/api/weblab/web3/feedback', { session_id: S.session_id, email: v })); }
      catch (e) { showError(out, e); }
    },
  }, '提交意見');
  root.replaceChildren(
    h1('校園意見信箱'),
    f12Hint('先用校內信箱送一次，去 Network 把請求 Copy as fetch。'),
    card(
      el('p', { class: 'small muted', style: 'margin-top:0' }, '本表單僅開放 @school.edu.tw 校內信箱。'),
      el('div', { class: 'row', style: 'align-items:center;gap:10px' },
        el('span', {}, 'Email：'), email, submit),
      el('p', { class: 'small muted', style: 'margin-top:10px' },
        '這個網域限制只在前端 JavaScript 裡 —— 後端其實什麼信箱都收。')),
    out, backLink());
}

function labWeb4() {
  const out = el('div', { style: 'margin-top:14px' });
  const reg = el('button', {
    disabled: 'disabled',
    onclick: async () => {
      try {
        const r = await apiPost('/api/weblab/web4/register', { session_id: S.session_id });
        out.replaceChildren(flagBox(r),
          el('p', { class: 'small muted', style: 'margin-top:8px' },
            r.solved ? '' : '看到你被分到哪個 slot 了嗎？去 Network 把這個報名請求 Copy as fetch，加上 slot:0 再送。'));
      } catch (e) { showError(out, e); }
    },
  }, '我要報名');
  root.replaceChildren(
    h1('資安體驗營 — 報名'),
    f12Hint('名額已滿、按鈕是灰的。先解鎖送出，再觀察回應裡的 slot。'),
    card(
      el('div', { class: 'row wrapped' },
        el('div', {},
          el('div', { style: 'font-size:18px;font-weight:700' }, '2026 暑期資安體驗營'),
          el('div', { class: 'badge', style: 'margin-top:8px' }, '名額已滿')),
        el('span', { class: 'spacer' }), reg),
      el('p', { class: 'small muted', style: 'margin-top:10px' },
        '兩步：① 繞過 disabled 送出報名（會被丟到候補 slot=99）② 把報名請求的 slot 改成 0（VIP 名額）。')),
    out, backLink());
}

/* ---- dispatch ------------------------------------------------------ */

const LABS = {
  a1: labA1, a2: labA2, a3: labA3,
  b1: labB1, b2: labB2, b3: labB3,
  web1: labWeb1, web2: labWeb2, web3: labWeb3, web4: labWeb4,
};

const fn = LABS[ID];
if (fn) {
  fn();
} else {
  root.replaceChildren(
    el('div', { class: 'notice bad' }, `未知的靶場：${ID}`),
    el('p', {}, el('a', { href: '/' }, '← 回題目列表')));
}
