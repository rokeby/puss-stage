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
  const clickWithin = (selector, text) => {
    const host = document.querySelector(selector);
    const node = host && [...host.querySelectorAll('button')].find(item => item.textContent.trim().startsWith(text));
    if (!node) throw new Error(`missing button ${text} in ${selector}`);
    node.click();
  };
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
    if (localStorage.getItem(PHASE) === 'offline-undo-reload') {
      const checks = JSON.parse(localStorage.getItem('browserHarness.checks') || '[]');
      await wait(() => window.__cuebook && window.__cuebook.outbox.length === 0, 'offline undo sent after reload');
      const afterUndo = await api({ action: 'list' });
      if (afterUndo.cues.find(cue => cue.key === 'R0002').notes !== '') throw new Error('offline undo did not restore the old value');
      checks.push('offline undo survived reload and restored the field');

      window.MOCK_OFFLINE = true;
      click('Running order');
      await wait(() => document.querySelector('.run-cue[data-key="R0002"]'), 'R0002 in running order after reload');
      document.querySelector('.run-cue[data-key="R0002"]').click();
      await wait(() => document.querySelector('[aria-label="Move R0002 down one cue"]'), 'moved cue button after reload');
      document.querySelector('[aria-label="Move R0002 down one cue"]').click();
      await wait(() => window.__cuebook.outbox.length === 1, 'offline move outbox');
      localStorage.setItem('browserHarness.checks', JSON.stringify(checks));
      localStorage.setItem(PHASE, 'offline-move-reload');
      location.reload();
      return;
    }

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
      window.__cuebook.renderPrintView('stage-manager');
      if (document.querySelectorAll('.print-cue').length !== 4) throw new Error('old deployment print failed');
      document.querySelector('.print-actions .btn:not(.primary)').click();
      checks.push('old deployment still renders the stage-manager print view');
      report(true, checks);
      return;
    }

    if (localStorage.getItem(PHASE) === 'offline-move-reload') {
      const checks = JSON.parse(localStorage.getItem('browserHarness.checks') || '[]');
      await wait(() => window.__cuebook && window.__cuebook.outbox.length === 0, 'offline move sent after reload');
      const listAfterMove = await api({ action: 'list' });
      const order = listAfterMove.cues.slice().sort((a, b) => a.ord - b.ord).map(cue => cue.key).filter(key => /^R/.test(key));
      if (order.join(',') !== 'R0001,R0003,R0004,R0002,R0005') throw new Error('offline move order wrong: ' + order.join(','));
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

      document.querySelector('#undoBtn').click();
      await wait(() => window.__cuebook.outbox.length === 0 && window.__cuebook.surtitles.find(x => x.key === key).cut, 'line add undo');
      checks.push('surtitle add undo marked the line as cut without deleting it');

      click('Edit');
      click('Restore line');
      await wait(() => window.__cuebook.outbox.length === 0 && !window.__cuebook.surtitles.find(x => x.key === key).cut, 'line restore');
      document.querySelector('#undoBtn').click();
      await wait(() => window.__cuebook.outbox.length === 0 && window.__cuebook.surtitles.find(x => x.key === key).cut, 'line cut undo');
      checks.push('surtitle cut/restore undo applied the opposite change');

      click('Edit');
      click('Restore line');
      await wait(() => window.__cuebook.outbox.length === 0 && !window.__cuebook.surtitles.find(x => x.key === key).cut, 'line restore for edit');
      click('Edit');
      input('textarea[name="text"]', 'Rumble revised');
      document.querySelector('.surtitle form').requestSubmit();
      await wait(() => window.__cuebook.surtitles.some(x => x.key === key && x.text === 'Rumble revised') && !window.__cuebook.outbox.length, 'line edit');
      document.querySelector('#undoBtn').click();
      await wait(() => window.__cuebook.outbox.length === 0 && window.__cuebook.surtitles.some(x => x.key === key && x.text === 'First rumble'), 'line edit undo');
      checks.push('surtitle line save undo restored the old text');

      click('Edit');
      input('textarea[name="text"]', 'Rumble revised');
      document.querySelector('.surtitle form').requestSubmit();
      await wait(() => window.__cuebook.surtitles.some(x => x.key === key && x.text === 'Rumble revised') && !window.__cuebook.outbox.length, 'line edit for conflict');
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
    Object.keys(localStorage).filter(key => key.startsWith('cuebook.undo.')).forEach(key => localStorage.removeItem(key));
    ['cuebook.who', 'cuebook.pass', 'cuebook.outbox', 'cuebook.conflicts', 'cuebook.drafts', 'cuebook.lineDrafts', 'cuebook.showSurtitles', 'cuebook.runningOrder'].forEach(key => localStorage.removeItem(key));
    window.__cuebook.clearUndo();
    await api({ action: 'seed', op: 'browser-seed', cues: [
      { key: 'R0001', ord: 10, version: 1, cut: false, num: '1', origin: 'shared', director: '', after: '', videoCue: 'S5 Mountains', klara: 'A mountain speaks', light: 'Warm state' },
      { key: 'R0002', ord: 20, version: 1, cut: false, num: '2', origin: 'shared', director: '', after: '', soundCue: 'Rumble', gary: 'Listen', at: '1', go: '2 HOLD' },
      { key: 'R0003', ord: 30, version: 1, cut: false, num: '3', origin: 'shared', director: '', after: '', videoCue: 'Passage 6', pause: 'yes', soundTech: 'Fade' },
      { key: 'R0004', ord: 40, version: 1, cut: true, num: '4', origin: 'shared', director: '', after: '', at: '2', go: '9 HOLD', cameron: 'Cut line' },
      { key: 'R0005', ord: 50, version: 1, cut: false, num: '5', origin: 'shared', director: '', after: '', cameron: 'Cameron line' }
    ] });
    document.querySelector('#gName').value = 'Gary';
    document.querySelector('#gPass').value = 'test-pass';
    document.querySelector('#gateForm').requestSubmit();
    const checks = [];
    await wait(() => document.querySelector('#gate').hidden && button('Running order') && document.querySelector('[aria-label="Move R0002 up one cue"]') && document.querySelectorAll('#printPreset option').length === 7, 'sign in');
    window.print = () => {};
    click('Print…');
    if (document.querySelector('#printPanel').hidden) throw new Error('print panel did not open');
    click('Cancel');
    const printCounts = { full: 4, 'stage-manager': 4, klara: 1, gary: 2, cameron: 1, lighting: 3, sound: 2 };
    for (const [preset, expected] of Object.entries(printCounts)) {
      window.__cuebook.renderPrintView(preset);
      const actual = document.querySelectorAll('.print-cue').length;
      if (actual !== expected) throw new Error(`print ${preset}: expected ${expected}, got ${actual}`);
      if ([...document.querySelectorAll('.print-cue')].some(row => row.dataset.key === 'R0004')) throw new Error(`print ${preset} included cut cue`);
      document.querySelector('.print-actions .btn:not(.primary)').click();
    }
    checks.push('all seven print presets match expected visible-cue counts and hide cut cues');
    document.querySelector('#printCuts').checked = true;
    window.__cuebook.renderPrintView('full');
    if (document.querySelectorAll('.print-cue').length !== 5) throw new Error('include-cut control did not reveal cut cue');
    document.querySelector('.print-actions .btn:not(.primary)').click();
    document.querySelector('#printCuts').checked = false;
    checks.push('include-cut control reveals cut cues only when selected');
    click('Running order');
    await wait(() => document.querySelectorAll('.run-cue').length === 5, 'running order');
    const runKeys = [...document.querySelectorAll('.run-cue')].map(row => row.dataset.key);
    if (new Set(runKeys).size !== 5) throw new Error('running order duplicates: ' + runKeys.join(','));
    checks.push('running order lists every seed cue exactly once');
    click('Running order');

    clickWithin('#cue-R0002', 'Edit');
    const described = ['at', 'go', 'pause'].map(field => document.querySelector(`[name="${field}"]`));
    if (described.some(control => !control || !document.getElementById(control.getAttribute('aria-describedby')) || !control.title)) throw new Error('At/GO/pause help is not connected');
    [...document.querySelectorAll('#cue-R0002 .help-toggle')].forEach(node => node.click());
    if (document.querySelectorAll('#cue-R0002 .help-more:not([hidden])').length !== 3) throw new Error('At/GO/pause longer help did not open');
    if (document.documentElement.scrollWidth > document.documentElement.clientWidth) throw new Error(`horizontal scroll with help open: ${document.documentElement.scrollWidth}/${document.documentElement.clientWidth}`);
    checks.push('At, GO and pause show linked hints/tooltips, toggled help, and no horizontal scroll');

    const textarea = document.querySelector('#cue-R0002 textarea[name="notes"]');
    const undoBeforeTyping = window.__cuebook.undoCount;
    textarea.dispatchEvent(new KeyboardEvent('keydown', { key: 'z', ctrlKey: true, bubbles: true, cancelable: true }));
    if (window.__cuebook.undoCount !== undoBeforeTyping) throw new Error('Ctrl+Z inside textarea triggered page undo');
    checks.push('Ctrl+Z inside a textarea stays with normal text editing');

    input('#cue-R0002 textarea[name="notes"]', 'Field to undo');
    document.querySelector('#cue-R0002 form').requestSubmit();
    await wait(() => window.__cuebook.outbox.length === 0 && document.querySelector('#undoBtn').textContent.includes('Notes on R0002'), 'field save');
    document.querySelector('#undoBtn').click();
    await wait(() => window.__cuebook.outbox.length === 0, 'field undo');
    const fieldUndoList = await api({ action: 'list' }), fieldUndoLog = await api({ action: 'log', limit: 20 });
    if (fieldUndoList.cues.find(cue => cue.key === 'R0002').notes !== '' || !fieldUndoLog.log.some(entry => entry.key === 'R0002' && entry.field === 'notes' && entry.before === 'Field to undo' && entry.after === '')) throw new Error('field undo or audit missing');
    checks.push('field save undo restored the old value through a logged normal change');

    document.querySelector('[aria-label="Move R0002 up one cue"]').click();
    await wait(() => window.__cuebook.outbox.length === 0, 'move up');
    document.querySelector('#undoBtn').click();
    await wait(() => window.__cuebook.outbox.length === 0, 'move undo');
    const moveLog = await api({ action: 'log', limit: 20 });
    if (moveLog.log.filter(entry => entry.field === '_move').length !== 2) throw new Error('up/down move audit missing');
    checks.push('move undo restored cue order with _move audits');

    clickWithin('#cue-R0002', 'Add cue');
    await wait(() => window.__cuebook.outbox.length === 0 && document.querySelector('#undoBtn').textContent.includes('add W'), 'cue add');
    const addedKey = document.querySelector('#undoBtn').textContent.match(/W[A-Z0-9]+/)[0];
    document.querySelector('#undoBtn').click();
    await wait(() => window.__cuebook.outbox.length === 0, 'add undo');
    const afterAddUndo = await api({ action: 'list' });
    if (!afterAddUndo.cues.some(cue => cue.key === addedKey && cue.cut === true)) throw new Error('undo add did not mark the cue as cut');
    checks.push('add undo marked the added cue as cut without deleting it');

    clickWithin('#cue-R0002', 'Edit');
    clickWithin('#cue-R0002', 'Mark as cut');
    await wait(() => window.__cuebook.outbox.length === 0, 'cue cut');
    document.querySelector('#undoBtn').click();
    await wait(() => window.__cuebook.outbox.length === 0, 'cue cut undo');
    const afterCutUndo = await api({ action: 'list' });
    if (afterCutUndo.cues.find(cue => cue.key === 'R0002').cut) throw new Error('cut undo did not restore cue');
    checks.push('cut undo restored the cue');

    clickWithin('#cue-R0002', 'Edit');
    input('#cue-R0002 textarea[name="light"]', 'Undo conflict base');
    document.querySelector('#cue-R0002 form').requestSubmit();
    await wait(() => window.__cuebook.outbox.length === 0, 'conflict source save');
    await api({ action: 'save', key: 'R0002', patch: { light: 'Someone else now' }, base: { light: 'Undo conflict base' }, who: 'Other', client: 'browser-other', op: 'browser-undo-conflict' });
    document.querySelector('#undoBtn').click();
    await wait(() => !!window.__cuebook.conflicts.R0002, 'undo conflict');
    const afterUndoConflict = await api({ action: 'list' });
    if (afterUndoConflict.cues.find(cue => cue.key === 'R0002').light !== 'Someone else now') throw new Error('undo conflict overwrote the other edit');
    checks.push('stale undo showed the normal conflict and overwrote nothing');
    click('Keep theirs');

    await api({ action: 'move', key: 'R0002', after: 'R0003', base: { ord: 20, before: 'R0001', after: addedKey }, who: 'Other', client: 'browser-other', op: 'browser-move-conflict' });
    document.querySelector('[aria-label="Move R0002 down one cue"]').click();
    await wait(() => !!window.__cuebook.conflicts.R0002, 'move conflict');
    checks.push('simultaneous cue move produced a conflict instead of a shuffle');
    click('Next');
    await wait(() => document.querySelector('#cue-R0002 .conf'), 'moved cue conflict visible');
    click('Keep theirs');

    clickWithin('#cue-R0002', 'Edit');
    input('#cue-R0002 textarea[name="notes"]', 'Offline undo source');
    document.querySelector('#cue-R0002 form').requestSubmit();
    await wait(() => window.__cuebook.outbox.length === 0, 'offline undo source save');
    window.MOCK_OFFLINE = true;
    document.querySelector('#undoBtn').click();
    await wait(() => window.__cuebook.outbox.length === 1, 'offline undo outbox');
    localStorage.setItem('browserHarness.checks', JSON.stringify(checks));
    localStorage.setItem(PHASE, 'offline-undo-reload');
    location.reload();
  } catch (error) {
    report(false, [], error);
  }
})();
