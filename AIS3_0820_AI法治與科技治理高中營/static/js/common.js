/* 共用工具：session、API 呼叫、極簡 markdown。
   注意：前端絕不持有任何金鑰，所有模型呼叫都經後端代理（spec §3.1）。 */

const SKEY = 'ctf_session';

export function getSession() {
  try { return JSON.parse(localStorage.getItem(SKEY) || 'null'); } catch { return null; }
}
export function setSession(s) { localStorage.setItem(SKEY, JSON.stringify(s)); }
export function clearSession() { localStorage.removeItem(SKEY); }

export function requireSession() {
  const s = getSession();
  if (!s || !s.session_id) { location.href = '/'; throw new Error('no session'); }
  return s;
}

export class ApiError extends Error {
  constructor(code, message, status, body) {
    super(message); this.code = code; this.status = status; this.body = body || {};
  }
}

async function handle(res) {
  let body = {};
  try { body = await res.json(); } catch { /* noop */ }
  if (!res.ok) {
    const e = body.error || {};
    if (res.status === 401 && (e.code === 'invalid_session')) {
      clearSession();
      location.href = '/';
    }
    throw new ApiError(e.code || 'error', e.message || '發生錯誤，請稍後再試。', res.status, body);
  }
  return body;
}

export async function apiGet(path, params) {
  const url = new URL(path, location.origin);
  Object.entries(params || {}).forEach(([k, v]) => url.searchParams.set(k, v));
  return handle(await fetch(url, { headers: { 'Accept': 'application/json' } }));
}

export async function apiPost(path, body) {
  return handle(await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify(body || {}),
  }));
}

/* ---- 極簡 markdown：先跳脫 HTML，再處理少數語法。
   主站絕不使用 innerHTML 放未跳脫內容（XSS 只准發生在 L4 的沙箱裡）。 ---- */
export function escapeHtml(s) {
  return String(s ?? '')
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#39;');
}

export function renderMarkdown(src) {
  const lines = escapeHtml(src || '').split('\n');
  const out = [];
  let inList = false;
  const inline = (t) => t
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, '<em>$1</em>');

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (/^\s*[-*]\s+/.test(line)) {
      if (!inList) { out.push('<ul>'); inList = true; }
      out.push('<li>' + inline(line.replace(/^\s*[-*]\s+/, '')) + '</li>');
      continue;
    }
    if (inList) { out.push('</ul>'); inList = false; }
    if (!line.trim()) continue;
    if (/^&gt;\s?/.test(line)) { out.push('<blockquote>' + inline(line.replace(/^&gt;\s?/, '')) + '</blockquote>'); continue; }
    if (/^###\s+/.test(line)) { out.push('<h3>' + inline(line.replace(/^###\s+/, '')) + '</h3>'); continue; }
    if (/^##\s+/.test(line)) { out.push('<h2>' + inline(line.replace(/^##\s+/, '')) + '</h2>'); continue; }
    out.push('<p>' + inline(line) + '</p>');
  }
  if (inList) out.push('</ul>');
  return out.join('');
}

/* 用 Enter 送出，但**不能吃掉輸入法組字時的 Enter**。

   注音／倉頡／拼音在選字時是用 Enter 確認候選字的。如果直接聽 keydown 的 Enter，
   學員字還沒打完就被送出去了。

   三道防線，因為各家瀏覽器／輸入法的事件順序不一致：
     1. 自己追蹤 compositionstart / compositionend
     2. e.isComposing（標準屬性，多數瀏覽器可用）
     3. e.keyCode === 229（舊版 / 部分 IME 的慣例值）
   另外有些 IME（Safari 較常見）會先送 compositionend 再送 keydown，
   這時前三道都失效，所以再加一個「剛結束組字」的時間窗。 */
export function onEnterSubmit(elem, handler) {
  let composing = false;
  let endedAt = 0;

  elem.addEventListener('compositionstart', () => { composing = true; });
  elem.addEventListener('compositionend', () => {
    composing = false;
    endedAt = Date.now();
  });

  elem.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') return;
    if (e.shiftKey || e.ctrlKey || e.metaKey || e.altKey) return;   // Shift+Enter 換行
    if (composing || e.isComposing || e.keyCode === 229) return;    // 正在選字
    if (Date.now() - endedAt < 120) return;                         // 剛選完字的那一下
    e.preventDefault();
    handler();
  });
}

export function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') n.className = v;
    else if (k === 'text') n.textContent = v;
    else if (k === 'html') n.innerHTML = v;   // 只用於已跳脫的 markdown 輸出
    else if (k.startsWith('on') && typeof v === 'function') n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    n.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return n;
}

export function mountHeader(active) {
  const s = getSession();
  const host = document.getElementById('hdr');
  if (!host) return;
  host.append(
    el('div', { class: 'inner' },
      el('div', { class: 'brand' }, 'AI Security 體驗營 CTF',
        el('small', {}, 'LLM 安全實戰')),
      el('div', { class: 'spacer' }),
      el('nav', { class: 'nav' },
        el('a', { href: '/', class: active === 'list' ? 'active' : '' }, '題目'),
        el('a', { href: '/leaderboard.html', class: active === 'lb' ? 'active' : '' }, '排行榜')),
      s ? el('div', { class: 'userbox' },
        el('b', { text: s.display_name || s.user_id }),
        el('button', {
          class: 'ghost', style: 'padding:4px 10px;font-size:12px',
          onclick: () => { clearSession(); location.href = '/'; },
        }, '登出')) : null,
    ));
}
