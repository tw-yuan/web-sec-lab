import {
  apiGet, apiPost, el, getSession, setSession, mountHeader, renderMarkdown,
  onEnterSubmit, ApiError,
} from './common.js';

const main = document.getElementById('main');

function renderLogin(msg) {
  document.getElementById('hdr').replaceChildren();
  main.className = 'login-wrap';
  main.replaceChildren(
    el('div', { class: 'card' },
      el('h1', {}, 'AI Security 體驗營 CTF'),
      el('p', { class: 'muted small' },
        '請輸入工作人員發給你的參賽代碼（例如 ABCD-2345）。'),
      msg ? el('div', { class: 'notice bad', text: msg }) : null,
      el('div', { style: 'margin:14px 0' },
        el('input', {
          type: 'text', id: 'tok', placeholder: 'ABCD-2345',
          autocomplete: 'off', autocapitalize: 'characters', spellcheck: 'false',
          style: 'font-family:var(--mono);letter-spacing:2px;text-align:center;font-size:18px',
        })),
      el('button', { id: 'go', style: 'width:100%' }, '進入'),
      el('p', { class: 'muted small', style: 'margin-top:16px' },
        '⚠️ 本平臺刻意內含 AI 安全漏洞，僅供教學演練。請勿用於攻擊真實系統。'),
    ));

  const tok = document.getElementById('tok');
  const go = document.getElementById('go');
  const submit = async () => {
    const v = tok.value.trim();
    if (!v) return;
    go.disabled = true;
    try {
      setSession(await apiPost('/api/login', { token: v }));
      location.reload();
    } catch (e) {
      renderLogin(e instanceof ApiError ? e.message : '登入失敗，請再試一次。');
    }
  };
  go.addEventListener('click', submit);
  onEnterSubmit(tok, submit);
  tok.focus();
}

function chalCard(c) {
  return el('a', {
    class: 'chal' + (c.solved ? ' solved' : ''),
    href: `/challenge.html?id=${encodeURIComponent(c.challenge_id)}`,
  },
    el('div', { class: 't' }, c.title),
    el('div', { class: 'm' },
      el('span', { class: 'badge grp' }, c.challenge_id.toUpperCase()),
      el('span', { class: 'badge pt' }, `${c.points} 分`),
      c.solved ? el('span', { class: 'badge ok' }, '✓ 已破關') : null,
      c.input_mode === 'locked_doc' ? el('span', { class: 'badge' }, '資料通道') : null,
      c.input_mode === 'xss_render' ? el('span', { class: 'badge' }, '沙箱渲染') : null,
      c.input_mode === 'defense' ? el('span', { class: 'badge' }, '防守方') : null,
      c.input_mode === 'weblab' ? el('span', { class: 'badge' }, 'Web 實戰') : null,
    ));
}

async function renderList() {
  const s = getSession();
  mountHeader('list');
  main.className = 'wrap';
  main.replaceChildren(el('p', { class: 'muted' }, '載入中…'));

  let data;
  try {
    data = await apiGet('/api/challenges', { session_id: s.session_id });
  } catch (e) {
    main.replaceChildren(el('div', { class: 'notice bad' }, e.message));
    return;
  }

  const pct = data.total_points ? Math.round(100 * data.score / data.total_points) : 0;
  const nodes = [
    el('h1', {}, `你好，${s.display_name || s.user_id}`),
    el('div', { class: 'card', style: 'margin-top:8px' },
      el('div', { class: 'row wrapped' },
        el('div', {},
          el('div', { class: 'small muted' }, '目前總分'),
          el('div', { style: 'font-size:26px;font-weight:700' },
            `${data.score} / ${data.total_points}`)),
        el('div', { class: 'spacer' }),
        el('button', { class: 'ghost', id: 'rename' }, '改暱稱'),
        el('a', { class: 'btn', href: '/leaderboard.html', style: 'text-decoration:none' }, '看排行榜')),
      el('div', { class: 'progress' }, el('i', { style: `width:${pct}%` }))),
    data.final_open
      ? el('div', { class: 'notice ok' }, '🏁 綜合挑戰（FINAL）已開放，分數更高，衝吧！')
      : el('div', { class: 'notice' }, '綜合挑戰（FINAL）尚未開放，先把前面的關卡練熟。'),
  ];

  for (const g of data.groups) {
    const items = data.challenges
      .filter((c) => c.group === g.group)
      .sort((a, b) => a.order - b.order);
    if (!items.length) continue;
    const done = items.filter((c) => c.solved).length;
    nodes.push(
      el('div', { class: 'group-head' },
        el('h2', { style: 'margin:0' }, g.title),
        el('span', { class: 'badge' }, `${done}/${items.length}`)),
      el('div', { class: 'md muted small', html: renderMarkdown(g.description_md || '') }),
      el('div', { class: 'grid' }, items.map(chalCard)),
    );
  }
  main.replaceChildren(...nodes.filter(Boolean));

  document.getElementById('rename').addEventListener('click', async () => {
    const name = prompt('輸入你要顯示在排行榜上的暱稱：', s.display_name || '');
    if (!name) return;
    try {
      const r = await apiPost('/api/me/display-name', {
        session_id: s.session_id, display_name: name,
      });
      setSession({ ...s, display_name: r.display_name });
      location.reload();
    } catch (e) { alert(e.message); }
  });
}

if (getSession()) renderList(); else renderLogin('');
