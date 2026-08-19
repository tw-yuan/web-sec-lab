import { apiGet, el, requireSession, mountHeader } from './common.js';

const S = requireSession();
const main = document.getElementById('main');
mountHeader('lb');

let challengeOrder = [];

async function loadChallengeOrder() {
  try {
    const d = await apiGet('/api/challenges', { session_id: S.session_id });
    challengeOrder = d.challenges
      .sort((a, b) => (a.group + String(a.order).padStart(3, '0'))
        .localeCompare(b.group + String(b.order).padStart(3, '0')))
      .map((c) => c.challenge_id);
  } catch { /* 排行榜仍可顯示 */ }
}

function dots(solvedList) {
  const set = new Set(solvedList || []);
  return el('div', { class: 'solvedots', title: (solvedList || []).join(', ') },
    challengeOrder.map((cid) =>
      el('i', { class: set.has(cid) ? 'on' : '', title: cid })));
}

async function refresh() {
  let d;
  try {
    d = await apiGet('/api/leaderboard', { session_id: S.session_id });
  } catch (e) {
    main.replaceChildren(el('div', { class: 'notice bad' }, e.message));
    return;
  }

  const rows = d.entries.map((e, i) => {
    const isMe = e.display_name === (S.display_name || '');
    return el('tr', { class: isMe ? 'me' : '' },
      el('td', { class: 'rank' }, `#${i + 1}`),
      el('td', {}, e.display_name),
      el('td', {}, dots(e.solved)),
      el('td', { class: 'score' }, String(e.score)));
  });

  main.replaceChildren(
    el('h1', {}, '排行榜'),
    el('p', { class: 'small muted' },
      `滿分 ${d.total_points} 分　·　每 8 秒自動更新`,
      d.final_open ? '　·　🏁 FINAL 已開放' : ''),
    el('div', { class: 'card' },
      el('table', { class: 'lb' },
        el('thead', {}, el('tr', {},
          el('th', {}, '#'), el('th', {}, '暱稱'),
          el('th', {}, '完成進度'), el('th', { style: 'text-align:right' }, '總分'))),
        el('tbody', {}, rows))),
    el('p', { class: 'small muted' },
      '每個人的旗標都不一樣（per-user canary），貼別人的旗標不會得分。'),
    el('p', {}, el('a', { href: '/' }, '← 回題目列表')));
}

await loadChallengeOrder();
await refresh();
setInterval(refresh, 8000);
