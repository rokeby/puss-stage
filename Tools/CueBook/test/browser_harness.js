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
    if (localStorage.getItem(PHASE) === 'offline-reload') {
      const checks = JSON.parse(localStorage.getItem('browserHarness.checks') || '[]');
      await wait(() => window.__cuebook && window.__cuebook.outbox.length === 0 && window.__cuebook.surtitles.some(x => x.text === 'Offline kept'), 'offline write sent after reload');
      checks.push('offline line edit survived reload and was sent');
      window.MOCK_OLD_DEPLOYMENT = true;
      await window.__cuebook.refresh();
      await wait(() => document.body.textContent.includes('Surtitles need the updated script'), 'old deployment message');
      checks.push('old deployment keeps cues working and explains the missing surtitles script');
      report(true, checks);
      return;
    }

    window.mockReset();
    ['cuebook.who', 'cuebook.pass', 'cuebook.outbox', 'cuebook.conflicts', 'cuebook.drafts', 'cuebook.lineDrafts', 'cuebook.showSurtitles'].forEach(key => localStorage.removeItem(key));
    await api({ action: 'seed', op: 'browser-seed', cues: [{ key: 'R0001', ord: 10, version: 1, cut: false,
      num: '1', origin: 'shared', director: '', after: '', videoCue: 'S5 Mountains', klara: 'A mountain speaks' }] });
    document.querySelector('#gName').value = 'Gary';
    document.querySelector('#gPass').value = 'test-pass';
    document.querySelector('#gateForm').requestSubmit();
    await wait(() => document.querySelector('#gate').hidden && button('Surtitles'), 'sign in');
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
    const checks = [];
    if (!listAfterAdd.surtitles.some(x => x.key === key) || !logAfterAdd.log.some(x => x.field === 'sub:_new')) throw new Error('add did not reach real Code.gs/log');
    checks.push('line add reached the surtitles sheet with sub:_new audit');

    click('Edit');
    input('textarea[name="text"]', 'Rumble revised');
    document.querySelector('.surtitle form').requestSubmit();
    await wait(() => window.__cuebook.surtitles.some(x => x.key === key && x.text === 'Rumble revised') && !window.__cuebook.outbox.length, 'line edit');
    checks.push('line edit saved through the page');

    click('Edit');
    await api({ action: 'saveLine', key, patch: { text: 'Their edit' }, base: { text: 'Rumble revised' }, who: 'Other', client: 'browser-other', op: 'browser-conflict' });
    input('textarea[name="text"]', 'My edit');
    document.querySelector('.surtitle form').requestSubmit();
    await wait(() => !!window.__cuebook.conflicts[key], 'field conflict');
    checks.push('simultaneous line edit produced a field conflict');
    click('Keep theirs');

    click('Edit');
    input('textarea[name="text"]', 'Offline kept');
    window.MOCK_OFFLINE = true;
    document.querySelector('.surtitle form').requestSubmit();
    await wait(() => window.__cuebook.outbox.length === 1, 'offline outbox');
    localStorage.setItem('browserHarness.checks', JSON.stringify(checks));
    localStorage.setItem(PHASE, 'offline-reload');
    location.reload();
  } catch (error) {
    report(false, [], error);
  }
})();
