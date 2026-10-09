// Test harness only (never deployed): just enough of Google's Apps Script services to run the REAL Code.gs in a
// browser. The fake spreadsheet behaves like Sheets where it matters here: a leading apostrophe marks text and is
// not part of the value; text that looks like a number becomes a number. It persists in localStorage so reloads
// keep the "server" data. window.MOCK_OFFLINE = true makes every call fail like a dropped connection.
(function () {
  var KEY = 'mock.spreadsheet';
  var data = {};
  try { data = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { data = {}; }
  function persist() { localStorage.setItem(KEY, JSON.stringify(data)); }
  function store(v) {
    if (typeof v === 'string') {
      if (v.charAt(0) === "'") return v.slice(1);
      if (v !== '' && !isNaN(Number(v))) return Number(v);
    }
    return v;
  }
  function Sheet(name) { this.name = name; }
  Sheet.prototype.rows = function () { return data[this.name]; };
  Sheet.prototype.getLastRow = function () { return this.rows().length; };
  Sheet.prototype.getMaxRows = function () { return Math.max(1000, this.rows().length); };
  Sheet.prototype.setFrozenRows = function () {};
  Sheet.prototype.getRange = function (r, c, nr, nc) {
    var sh = this; nr = nr || 1; nc = nc || 1;
    return {
      getValues: function () {
        var out = [];
        for (var i = 0; i < nr; i++) {
          var row = sh.rows()[r - 1 + i] || [];
          var o = [];
          for (var j = 0; j < nc; j++) o.push(row[c - 1 + j] === undefined ? '' : row[c - 1 + j]);
          out.push(o);
        }
        return out;
      },
      setValues: function (vals) {
        if (vals.length !== nr || vals[0].length !== nc) throw new Error('setValues: size mismatch');
        for (var i = 0; i < nr; i++) {
          var row = sh.rows()[r - 1 + i] || (sh.rows()[r - 1 + i] = []);
          for (var j = 0; j < nc; j++) row[c - 1 + j] = store(vals[i][j]);
        }
        persist();
        return this;
      },
      setFontWeight: function () { return this; },
      setNumberFormat: function () { return this; }
    };
  };
  var ss = {
    getSheetByName: function (n) { return data[n] ? new Sheet(n) : null; },
    insertSheet: function (n) { data[n] = []; persist(); return new Sheet(n); },
    getId: function () { return 'mock'; }
  };
  window.SpreadsheetApp = { getActiveSpreadsheet: function () { return ss; } };
  window.PropertiesService = { getScriptProperties: function () { return { getProperty: function (k) { return k === 'PASSCODE' ? 'test-pass' : null; } }; } };
  window.LockService = { getScriptLock: function () { return { waitLock: function () {}, releaseLock: function () {} }; } };
  window.Utilities = { sleep: function () {}, formatDate: function () { return 'now'; } };
  window.ContentService = { MimeType: { JSON: 'json' }, createTextOutput: function (s) { return { text: s, setMimeType: function () { return this; } }; } };
  window.MOCK_OFFLINE = false;
  window.MOCK_OLD_DEPLOYMENT = false;
  window.MOCK_CALLS = 0;
  window.mockReset = function () { data = {}; persist(); };
  // The page calls this instead of fetch. JSON round-trips both ways, like the network.
  window.CUEBOOK_API = function (req) {
    return new Promise(function (resolve, reject) {
      setTimeout(function () {
        window.MOCK_CALLS++;
        if (window.MOCK_OFFLINE) return reject(Object.assign(new Error('offline'), { code: 'network' }));
        if (window.MOCK_OLD_DEPLOYMENT && req.action === 'move') return resolve({ ok: false, code: 'bad_request', message: 'Unknown action move' });
        var out = JSON.parse(doPost({ postData: { contents: JSON.stringify(req) } }).text);
        if (window.MOCK_OLD_DEPLOYMENT && req.action === 'list') { delete out.surtitles; delete out.actions; delete out.fields; }
        resolve(out);
      }, 120);
    });
  };
})();
