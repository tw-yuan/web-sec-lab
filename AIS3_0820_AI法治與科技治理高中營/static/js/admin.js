/* 後臺主控頁。ADMIN_TOKEN 存在 sessionStorage（關掉分頁就沒了，不留在硬碟）。 */
import { el, onEnterSubmit } from './common.js';

const KEY = 'ctf_admin_token';
const main = document.getElementById('main');
let timer = null;

const getTok = () => sessionStorage.getItem(KEY) || '';
const setTok = (t) => sessionStorage.setItem(KEY, t);
const clearTok = () => sessionStorage.removeItem(KEY);

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: { 'X-Admin-Token': getTok(), 'Content-Type': 'application/json', ...(opts.headers || {}) },
  });
  if (res.status === 401 || res.status === 404) {
    clearTok();
    renderLogin('ADMIN_TOKEN 不正確，或後端未設定 ADMIN_TOKEN。');
    throw new Error('unauthorized');
  }
  return res.json();
}

function header() {
  const host = document.getElementById('hdr');
  host.replaceChildren(el('div', { class: 'inner' },
    el('div', { class: 'brand' }, '後臺主控', el('small', {}, 'AI Security CTF')),
    el('div', { class: 'spacer' }),
    el('nav', { class: 'nav' },
      el('a', { href: '/' }, '題目'),
      el('a', { href: '/leaderboard.html' }, '排行榜'),
      el('a', { href: '/prompts.html' }, 'Prompt 紀錄')),
    getTok() ? el('button', {
      class: 'ghost', style: 'padding:4px 10px;font-size:12px',
      onclick: () => { clearTok(); location.reload(); },
    }, '登出') : null));
}

function renderLogin(msg) {
  if (timer) { clearInterval(timer); timer = null; }
  header();
  main.className = 'login-wrap';
  main.replaceChildren(el('div', { class: 'card' },
    el('h1', {}, '後臺主控'),
    el('p', { class: 'muted small' }, '輸入 .env 裡的 ADMIN_TOKEN。'),
    msg ? el('div', { class: 'notice bad', text: msg }) : null,
    el('div', { style: 'margin:14px 0' },
      el('input', {
        type: 'password', id: 'tok', placeholder: 'ADMIN_TOKEN',
        autocomplete: 'off', style: 'font-family:var(--mono)',
      })),
    el('button', { id: 'go', style: 'width:100%' }, '進入')));

  const inp = document.getElementById('tok');
  const go = async () => {
    if (!inp.value.trim()) return;
    setTok(inp.value.trim());
    try { await api('/api/admin/overview'); boot(); } catch { /* renderLogin 已處理 */ }
  };
  document.getElementById('go').addEventListener('click', go);
  onEnterSubmit(inp, go);
  inp.focus();
}

/* ---------------- 元件 ---------------- */

function statTile(label, value, sub, tone) {
  return el('div', { class: 'card', style: 'padding:12px 14px' },
    el('div', { class: 'small muted' }, label),
    el('div', { style: `font-size:24px;font-weight:700;line-height:1.25${tone ? `;color:var(--${tone})` : ''}` },
      String(value)),
    sub ? el('div', { class: 'small muted' }, sub) : null);
}

function bar(ratio, tone) {
  const pct = Math.max(0, Math.min(1, ratio || 0)) * 100;
  return el('div', { class: 'progress', style: 'margin:0;width:110px' },
    el('i', { style: `width:${pct}%${tone ? `;background:var(--${tone})` : ''}` }));
}

function challengeTable(d) {
  const rows = d.challenges.map((c) => {
    // 「卡關指數」：點了幾次提示 ÷ 破關人數。越高代表大家越卡。
    const stuck = c.solves ? c.hints_taken / c.solves : (c.hints_taken ? 9 : 0);
    const hot = stuck >= 2 || (c.attempts > 30 && c.solve_rate < 0.25);
    return el('tr', { class: hot ? 'me' : '' },
      el('td', {}, el('code', {}, c.challenge_id),
        !c.enabled ? el('span', { class: 'badge', style: 'margin-left:6px' }, '已停用') : null,
        c.release_stage === 'final' ? el('span', { class: 'badge grp', style: 'margin-left:6px' }, 'FINAL') : null),
      el('td', {}, c.title),
      el('td', { style: 'text-align:right' }, String(c.points)),
      el('td', {}, el('div', { class: 'row', style: 'gap:8px' },
        bar(c.solve_rate, c.solve_rate >= 0.6 ? 'ok' : (c.solve_rate < 0.25 ? 'bad' : 'warn')),
        el('span', { class: 'small muted' }, `${c.solves}/${d.active_users || 0}`))),
      el('td', { style: 'text-align:right' }, String(c.attempts)),
      el('td', { style: 'text-align:right' },
        el('span', { class: hot ? 'badge pt' : 'small muted' }, String(c.hints_taken))));
  });
  return el('div', { class: 'card' },
    el('table', { class: 'lb' },
      el('thead', {}, el('tr', {},
        el('th', {}, '題號'), el('th', {}, '標題'),
        el('th', { style: 'text-align:right' }, '分數'),
        el('th', {}, '破關率'),
        el('th', { style: 'text-align:right' }, '嘗試'),
        el('th', { style: 'text-align:right' }, '提示'))),
      el('tbody', {}, rows)),
    el('p', { class: 'small muted', style: 'margin:10px 0 0' },
      '標色的列 = 大家卡住的題（提示點很多次，或嘗試多但破關率低）。'));
}

function progressTable(d) {
  const ids = d.challenges.map((c) => c.challenge_id);
  const rows = d.entries.slice(0, 120).map((e, i) => {
    const set = new Set(e.solved);
    return el('tr', {},
      el('td', { class: 'rank' }, `#${i + 1}`),
      el('td', {}, e.display_name, el('span', { class: 'small muted' }, ` ${e.user_id}`)),
      el('td', {}, el('div', { class: 'solvedots' },
        ids.map((cid) => el('i', { class: set.has(cid) ? 'on' : '', title: cid })))),
      el('td', { style: 'text-align:right' }, `${e.solved.length}/${ids.length}`),
      el('td', { class: 'score' }, String(e.score)));
  });
  return el('div', { class: 'card' },
    el('table', { class: 'lb' },
      el('thead', {}, el('tr', {},
        el('th', {}, '#'), el('th', {}, '學員'), el('th', {}, '完成進度'),
        el('th', { style: 'text-align:right' }, '題數'),
        el('th', { style: 'text-align:right' }, '總分'))),
      el('tbody', {}, rows)),
    d.entries.length > 120
      ? el('p', { class: 'small muted', style: 'margin:10px 0 0' },
        `只顯示前 120 名（共 ${d.entries.length} 人）`) : null);
}

function suspiciousBox(d) {
  if (!d.suspicious.length) {
    return el('div', { class: 'notice ok' }, '✅ 沒有偵測到 flag 分享。');
  }
  return el('div', { class: 'card' },
    el('table', { class: 'lb' },
      el('thead', {}, el('tr', {},
        el('th', {}, '提交者'), el('th', {}, '題目'), el('th', {}, 'flag 實際擁有者'), el('th', {}, '時間'))),
      el('tbody', {}, d.suspicious.slice(0, 40).map((x) => el('tr', {},
        el('td', {}, el('code', {}, x.user_id)),
        el('td', {}, el('code', {}, x.challenge_id)),
        el('td', {}, el('code', {}, x.suspected_owner)),
        el('td', { class: 'small muted' }, x.ts))))));
}

function limitsBox(d) {
  const L = d.limits;
  const fmt = (v) => (v > 0 ? String(v) : '不限');
  const items = [
    ['每題每分鐘', L.rate_per_challenge_per_min],
    ['每人每分鐘', L.rate_per_user_per_min],
    ['登入嘗試/分', L.rate_login_per_min],
    ['每題總嘗試', L.max_attempts_per_challenge],
    ['DEF 提交次數', L.def_max_submissions],
    ['DEF 每分鐘', L.def_rate_per_min],
  ];
  const allOff = items.every(([, v]) => !v) && !d.budget.limit;
  return el('div', { class: 'card' },
    el('h2', { style: 'margin-top:0' }, '限流設定'),
    el('table', { class: 'lb' }, el('tbody', {}, items.map(([k, v]) => el('tr', {},
      el('td', {}, k),
      el('td', { style: 'text-align:right' },
        el('span', { class: v > 0 ? 'badge' : 'badge ok' }, fmt(v))))))),
    allOff
      ? el('div', { class: 'notice warn', style: 'margin:12px 0 0' },
        '⚠️ 所有限流與 token 預算都已關閉。平臺不會擋任何用量，'
        + '請自行在 OpenRouter 後臺設定用量上限與告警。')
      : null,
    el('p', { class: 'small muted', style: 'margin:10px 0 0' },
      '改 .env 後 ', el('code', {}, 'docker compose up -d'), ' 即可生效。'));
}

/* ---------------- 主畫面 ---------------- */

async function render() {
  let d;
  try { d = await api('/api/admin/overview'); } catch { return; }

  const s = d.stats;
  const budget = d.budget.limit > 0
    ? `${(100 * d.budget.used / d.budget.limit).toFixed(0)}% 已用`
    : '無上限';

  main.className = 'wrap wide';
  main.replaceChildren(
    el('h1', {}, '後臺主控'),

    el('div', { class: 'grid', style: 'grid-template-columns:repeat(auto-fill,minmax(150px,1fr))' },
      statTile('學員', s.users, `${d.active_users} 人已破關`),
      statTile('總解題數', s.solves, `滿分 ${d.total_points}`),
      statTile('模型呼叫', s.attempts, `DEF 提交 ${s.defense_submissions}`),
      statTile('token 用量', s.tokens_used.toLocaleString(), budget,
        d.budget.limit > 0 && d.budget.used / d.budget.limit > 0.8 ? 'bad' : null),
      statTile('FINAL', d.final_open ? '已開放' : '未開放', '',
        d.final_open ? 'ok' : 'muted'),
      statTile('提示', d.hints_open === false ? '已關閉' : '開放中', '',
        d.hints_open === false ? 'bad' : 'ok')),

    el('div', { class: 'card', style: 'margin-top:14px' },
      el('div', { class: 'row wrapped' },
        el('div', {},
          el('div', { style: 'font-weight:650' }, 'FINAL 綜合挑戰'),
          el('div', { class: 'small muted' },
            d.final_open ? '學員現在看得到 FINAL 題組' : '活動尾聲再開放')),
        el('div', { class: 'spacer' }),
        el('button', {
          class: d.final_open ? 'ghost' : '',
          onclick: async (ev) => {
            ev.target.disabled = true;
            await api('/api/admin/final-open', {
              method: 'POST', body: JSON.stringify({ open: !d.final_open }),
            });
            render();
          },
        }, d.final_open ? '關閉 FINAL' : '開放 FINAL'),
        el('button', {
          class: d.hints_open === false ? '' : 'ghost',
          onclick: async (ev) => {
            ev.target.disabled = true;
            await api('/api/admin/hints-open', {
              method: 'POST', body: JSON.stringify({ open: d.hints_open === false }),
            });
            render();
          },
        }, d.hints_open === false ? '開啟提示' : '關閉提示'),
        el('button', {
          class: 'ghost',
          onclick: async (ev) => {
            const n = prompt('要加開幾組參賽代碼？', '10');
            if (!n) return;
            ev.target.disabled = true;
            const r = await api(`/api/admin/seed-users?count=${encodeURIComponent(n)}`,
              { method: 'POST' });
            alert(`已建立 ${r.created.length} 組：\n`
              + r.created.map((u) => `${u.user_id}  ${u.token}`).join('\n'));
            render();
          },
        }, '加開參賽代碼'),
        el('button', {
          class: 'ghost',
          onclick: async () => {
            const r = await api('/api/admin/users');
            const csv = 'user_id,display_name,token\n'
              + r.users.map((u) => `${u.user_id},${u.display_name},${u.token}`).join('\n');
            const a = document.createElement('a');
            a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
            a.download = 'users.csv';
            a.click();
            URL.revokeObjectURL(a.href);
          },
        }, '下載參賽代碼 CSV'))),

    el('h2', {}, '各題狀況'),
    challengeTable(d),

    el('h2', {}, '疑似 flag 分享'),
    suspiciousBox(d),

    el('h2', {}, '學員進度'),
    progressTable(d),

    el('h2', {}, '設定'),
    limitsBox(d),

    el('p', { class: 'small muted', style: 'margin-top:18px' }, '每 10 秒自動更新。'),
  );
}

function boot() {
  header();
  render();
  if (timer) clearInterval(timer);
  timer = setInterval(render, 10000);
}

if (getTok()) boot(); else renderLogin('');
