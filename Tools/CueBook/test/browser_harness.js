// Loaded only into test/_build by build_test_site.py. It drives the real page and real Code.gs in Chrome.
(async function () {
  'use strict';
  const PHASE = 'browserHarness.phase';
  const wait = async (predicate, label, timeout = 8000) => {
    const until = Date.now() + timeout;
    while (Date.now() < until) {
      if (predicate()) return;
      await new Promise(resolve => setTimeout(resolve, 40));
    }
    throw new Error('timeout: ' + label);
  };
  const input = (selector, value) => {
    const node = document.querySelector(selector);
    if (!node) throw new Error('missing ' + selector);
    node.value = value;
    node.dispatchEvent(new Event('input', { bubbles: true }));
    return node;
  };
  const button = text => [...document.querySelectorAll('button')].find(node => node.textContent.trim().startsWith(text));
  const click = text => { const node = button(text); if (!node) throw new Error('missing button ' + text); node.click(); };
  const api = req => window.CUEBOOK_API(Object.assign({ pass: 'test-pass' }, req));
  const report = (ok, checks, error) => {
    const pre = document.createElement('pre');
    pre.id = 'browser-harness-result';
    pre.textContent = ok ? `CUEBOOK_BROWSER_HARNESS_OK ${checks.length}/${checks.length}\n` + checks.map(x => 'PASS ' + x).join('\n')
      : 'CUEBOOK_BROWSER_HARNESS_FAILED\n' + String(error && (error.stack || error));
    document.body.replaceChildren(pre);
    localStorage.removeItem(PHASE);
  };
  try {
    if (localStorage.getItem(PHASE) === 'offline-line-reload') {
      const checks = JSON.parse(localStorage.getItem('browserHarness.checks') || '[]');
      await wait(() => window.__cuebook && window.__cuebook.outbox.length === 0 && window.__cuebook.surtitles.some(x => x.text === 'Offline kept'), 'offline write sent after reload');
      checks.push('offline line edit survived reload and was sent');
      window.MOCK_OLD_DEPLOYMENT = true;
      await window.__cuebook.refresh();
      await wait(() => document.body.textContent.includes('Surtitles need the updated script'), 'old deployment message');
      checks.push('old deployment keeps cues working and explains the missing surtitles script');
      click('Show cues');
      await wait(() => !document.querySelector('.movebtn'), 'old deployment move buttons hidden');
      checks.push('old deployment hides move buttons instead of sending unsupported actions');
      report(true, checks);
      return;
    }

    if (localStorage.getItem(PHASE) === 'offline-move-reload') {
      const checks = JSON.parse(localStorage.getItem('browserHarness.checks') || '[]');
      await wait(() => window.__cuebook && window.__cuebook.outbox.length === 0, 'offline move sent after reload');
      const listAfterMove = await api({ action: 'list' });
      const order = listAfterMove.cues.slice().sort((a, b) => a.ord - b.ord).map(cue => cue.key);
      if (order.join(',') !== 'R0001,R0002,R0003,R0004') throw new Error('offline move order wrong: ' + order.join(','));
      checks.push('offline cue move survived reload and was sent');

      click('Surtitles');
      click('+ Add a surtitle line');
      input('input[name="in"]', '1:14.5');
      input('input[name="speaker"]', 'Mountain left');
      input('textarea[name="text"]', 'First rumble');
      document.querySelector('.surtitle form').requestSubmit();
      await wait(() => window.__cuebook.surtitles.some(x => x.text === 'First rumble') && !window.__cuebook.outbox.length, 'line add');
      const key = window.__cuebook.surtitles.find(x => x.text === 'First rumble').key;
      const listAfterAdd = await api({ action: 'list' });
      const logAfterAdd = await api({ action: 'log', limit: 20 });
      if (!listAfterAdd.surtitles.some(x => x.key === key) || !logAfterAdd.log.some(x => x.field === 'sub:_new')) throw new Error('add did not reach real Code.gs/log');
      checks.push('line add reached the surtitles sheet with sub:_new audit');

      click('Edit');
      input('textarea[name="text"]', 'Rumble revised');
      document.querySelector('.surtitle form').requestSubmit();
      await wait(() => window.__cuebook.surtitles.some(x => x.key === key && x.text === 'Rumble revised') && !window.__cuebook.outbox.length, 'line edit');
      checks.push('line edit saved through the page');

      click('Edit');
      await api({ action: 'saveLine', key, patch: { text: 'Their edit' }, base: { text: 'Rumble revised' }, who: 'Other', client: 'browser-other', op: 'browser-line-conflict' });
      input('textarea[name="text"]', 'My edit');
      document.querySelector('.surtitle form').requestSubmit();
      await wait(() => !!window.__cuebook.conflicts[key], 'field conflict');
      checks.push('simultaneous line edit produced a field conflict');
      click('Keep theirs');

      click('Edit');
      input('textarea[name="text"]', 'Offline kept');
      window.MOCK_OFFLINE = true;
      document.querySelector('.surtitle form').requestSubmit();
      await wait(() => window.__cuebook.outbox.length === 1, 'offline line outbox');
      localStorage.setItem('browserHarness.checks', JSON.stringify(checks));
      localStorage.setItem(PHASE, 'offline-line-reload');
      location.reload();
      return;
    }

    window.mockReset();
    ['cuebook.who', 'cuebook.pass', 'cuebook.outbox', 'cuebook.conflicts', 'cuebook.drafts', 'cuebook.lineDrafts', 'cuebook.showSurtitles', 'cuebook.runningOrder'].forEach(key => localStorage.removeItem(key));
    await api({ action: 'seed', op: 'browser-seed', cues: [
      { key: 'R0001', ord: 10, version: 1, cut: false, num: '1', origin: 'shared', director: '', after: '', videoCue: 'S5 Mountains', klara: 'A mountain speaks' },
      { key: 'R0002', ord: 20, version: 1, cut: false, num: '2', origin: 'shared', director: '', after: '', soundCue: 'Rumble' },
      { key: 'R0003', ord: 30, version: 1, cut: false, num: '3', origin: 'shared', director: '', after: '', videoCue: 'Passage 6', pause: 'yes' },
      { key: 'R0004', ord: 40, version: 1, cut: true, num: '4', origin: 'shared', director: '', after: '', at: '2', go: '9 HOLD', cameron: 'Cut line' }
    ] });
    document.querySelector('#gName').value = 'Gary';
    document.querySelector('#gPass').value = 'test-pass';
    document.querySelector('#gateForm').requestSubmit();
    const checks = [];
    await wait(() => document.querySelector('#gate').hidden && button('Running order') && document.querySelector('[aria-label="Move R0002 up one cue"]'), 'sign in');
    click('Running order');
    await wait(() => document.querySelectorAll('.run-cue').length === 4, 'running order');
    const runKeys = [...document.querySelectorAll('.run-cue')].map(row => row.dataset.key);
    if (new Set(runKeys).size !== 4) throw new Error('running order duplicates: ' + runKeys.join(','));
    checks.push('running order lists every seed cue exactly once');
    click('Running order');

    document.querySelector('[aria-label="Move R0002 up one cue"]').click();
    await wait(() => window.__cuebook.outbox.length === 0, 'move up');
    document.querySelector('[aria-label="Move R0002 down one cue"]').click();
    await wait(() => window.__cuebook.outbox.length === 0, 'move down');
    const moveLog = await api({ action: 'log', limit: 20 });
    if (moveLog.log.filter(entry => entry.field === '_move').length !== 2) throw new Error('up/down move audit missing');
    checks.push('move up and down reached the cue sheet with _move audits');

    await api({ action: 'move', key: 'R0002', after: '', base: { ord: 20, before: 'R0001', after: 'R0003' }, who: 'Other', client: 'browser-other', op: 'browser-move-conflict' });
    document.querySelector('[aria-label="Move R0002 down one cue"]').click();
    await wait(() => !!window.__cuebook.conflicts.R0002, 'move conflict');
    checks.push('simultaneous cue move produced a conflict instead of a shuffle');
    click('Keep theirs');

    window.MOCK_OFFLINE = true;
    document.querySelector('[aria-label="Move R0002 down one cue"]').click();
    await wait(() => window.__cuebook.outbox.length === 1, 'offline move outbox');
    localStorage.setItem('browserHarness.checks', JSON.stringify(checks));
    localStorage.setItem(PHASE, 'offline-move-reload');
    location.reload();
  } catch (error) {
    report(false, [], error);
  }
})();
