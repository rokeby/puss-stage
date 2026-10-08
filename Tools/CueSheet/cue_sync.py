"""Puss cue list: keep Gary's WORKING copy in sync with the shared Google Sheet (Gary, 8 Oct).

The shared Sheet stays the source of truth and is never written. The working copy lives in the repo
and carries Gary's extra detail; the Cue Director reads an export of it.

Files (Docs/CueSheet/):
  working.csv          Key, Origin, the Sheet's columns, plus "Director notes". Gary's copy.
  shared_snapshot.csv  Key + the Sheet's columns as of the last pull (the merge base).
  sync_report.md       what the last pull changed, and every CONFLICT for Gary to decide.
  PUSS_CUE_LIST.md     a readable rendering of working.csv, grouped by segment.
Export for Unreal: Content/InfinityStage/CueSheet/Puss_Master_cue_sheet.csv (Director notes folded into Notes).

Usage:
  python Tools/CueSheet/cue_sync.py pull <downloaded_sheet.csv>   three-way merge into working.csv
  python Tools/CueSheet/cue_sync.py render                        rebuild PUSS_CUE_LIST.md + the Unreal export
  python Tools/CueSheet/cue_sync.py selftest                      offline harness (+/- controls)
  python Tools/CueSheet/cue_sync.py note R0012 "text"             set a row's Director notes (re-renders)
  python Tools/CueSheet/cue_sync.py insert R0012 "Column=text" ...  add a LOCAL row after R0012 (re-renders)
  python Tools/CueSheet/cue_sync.py cuebook                       fetch the online Cue Book and merge it (needs CUEBOOK_PASS)
  python Tools/CueSheet/cue_sync.py webpull <dir or .json>        merge a saved Cue Book export / backup file
  python Tools/CueSheet/cue_sync.py webbase                       record working.csv as the page's merge base (after seeding)

The online Cue Book (Tools/CueBook: a GitHub Pages site whose data lives in a private Google Sheet behind an Apps
Script, for Klara and Cameron) keeps its own copy of the list. `cuebook` downloads it (the raw download is kept in
Docs/CueSheet/pulls/ as another backup) and merges it; web_baseline.json is the merge base. Same rule as the Sheet:
edited on both sides keeps the working copy and is a CONFLICT in web_report.md. New cues from the page become
Origin "web" rows after the cue they were added after; a cue marked as cut there is flagged in Director notes,
never deleted.

Merge rule (Gary: "show me both, I decide"): a row changed in the Sheet AND in the working copy keeps the
working version and is listed as a CONFLICT with the Sheet's version beside it. Nothing local is ever lost.
"""
import csv
import difflib
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIR = os.path.join(ROOT, 'Docs', 'CueSheet')
WORKING = os.path.join(DIR, 'working.csv')
SNAPSHOT = os.path.join(DIR, 'shared_snapshot.csv')
REPORT = os.path.join(DIR, 'sync_report.md')
RENDER = os.path.join(DIR, 'PUSS_CUE_LIST.md')
EXPORT = os.path.join(ROOT, 'Content', 'InfinityStage', 'CueSheet', 'Puss_Master_cue_sheet.csv')
DIRECTOR = 'Director notes'
WEB_BASELINE = os.path.join(DIR, 'web_baseline.json')
WEB_REPORT = os.path.join(DIR, 'web_report.md')
# page field -> working.csv column
WEB_FIELDS = {'light': 'Light', 'soundTech': 'Sound tech', 'action': 'Action', 'soundCue': 'Sound cue',
              'videoCue': 'Video Cue', 'klara': 'Speaker: Klara', 'gary': 'Speaker: Gary',
              'cameron': 'Speaker: Cameron', 'beats': 'Beats', 'notes': 'Notes'}
CUT_MARK = '[CUT on the Cue Book]'


# ---------------------------------------------------------------- reading the Sheet
def read_sheet(text):
    """-> (columns, speaker_names, rows). columns are unique names; the row under the header names speakers."""
    table = list(csv.reader(io.StringIO(text)))
    header_i = next((i for i, r in enumerate(table) if any(c.strip().lower() == 'light' for c in r)), None)
    if header_i is None:
        raise ValueError('no header row (no cell "Light"): is this the master cue sheet?')
    header = [c.strip() for c in table[header_i]]
    names = table[header_i + 1] if header_i + 1 < len(table) else []
    columns, seen = [], {}
    for i, h in enumerate(header):
        name = h or ('#' if i == 0 else 'Col%d' % i)
        if name.lower() == 'speaker' and i < len(names) and names[i].strip():
            name = 'Speaker: ' + names[i].strip()
        seen[name] = seen.get(name, 0) + 1
        columns.append(name if seen[name] == 1 else '%s (%d)' % (name, seen[name]))
    first = header_i + 2 if any(c.strip() for c in names) else header_i + 1
    rows = []
    for r in table[first:]:
        cells = [c.strip() for c in r] + [''] * (len(columns) - len(r))
        if any(cells[:len(columns)]):
            rows.append(dict(zip(columns, cells[:len(columns)])))
    return columns, [n.strip() for n in names if n.strip()], rows


def signature(row, columns):
    return '\x1f'.join(row.get(c, '') for c in columns)


# ---------------------------------------------------------------- files
def load_csv(path):
    if not os.path.exists(path):
        return [], []
    with open(path, encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def save_csv(path, fields, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in fields})


def next_key(existing):
    n = 1 + max([int(k[1:]) for k in existing if k[:1] == 'R' and k[1:].isdigit()] or [0])
    return 'R%04d' % n


# ---------------------------------------------------------------- the merge
def merge(base_rows, new_rows, work_rows, columns):
    """Three-way merge. base_rows/work_rows carry 'Key'; new_rows do not. Returns (work, snapshot, log, conflicts)."""
    log, conflicts = [], []
    base_sig = [signature(r, columns) for r in base_rows]
    new_sig = [signature(r, columns) for r in new_rows]
    keys_in_use = {r['Key'] for r in base_rows} | {r['Key'] for r in work_rows}
    new_keyed = [None] * len(new_rows)          # key for each new Sheet row
    changed, deleted = {}, set()

    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, base_sig, new_sig, autojunk=False).get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                new_keyed[j1 + k] = base_rows[i1 + k]['Key']
            continue
        # replace: pair rows in order as edits; the surplus are deletions or insertions
        pairs = min(i2 - i1, j2 - j1) if tag == 'replace' else 0
        for k in range(pairs):
            key = base_rows[i1 + k]['Key']
            new_keyed[j1 + k] = key
            changed[key] = new_rows[j1 + k]
        for i in range(i1 + pairs, i2):
            deleted.add(base_rows[i]['Key'])
        for j in range(j1 + pairs, j2):
            key = next_key(keys_in_use)
            keys_in_use.add(key)
            new_keyed[j] = key

    base_by_key = {r['Key']: r for r in base_rows}
    out = []
    work_keys = set()
    for row in work_rows:
        key = row['Key']
        work_keys.add(key)
        if row.get('Origin') == 'local' or key not in base_by_key:
            out.append(row)
            continue
        base = base_by_key[key]
        locally_edited = signature(row, columns) != signature(base, columns)
        if key in deleted:
            if locally_edited or row.get(DIRECTOR):
                conflicts.append((key, 'deleted in the Sheet, but you have local detail; kept', row, None))
                out.append(row)
            else:
                log.append('%s removed (deleted in the Sheet)' % key)
            continue
        if key in changed:
            if not locally_edited:
                updated = dict(row)
                updated.update({c: changed[key].get(c, '') for c in columns})
                out.append(updated)
                log.append('%s updated from the Sheet' % key)
            elif signature(row, columns) == signature(changed[key], columns):
                out.append(row)   # both made the same change
            else:
                conflicts.append((key, 'changed in the Sheet AND here; kept yours', row, changed[key]))
                out.append(row)
            continue
        out.append(row)

    # insert new Sheet rows after the working row holding the previous Sheet row's key
    for j, row in enumerate(new_rows):
        key = new_keyed[j]
        if key in work_keys:
            continue
        fresh = dict(row)
        fresh.update({'Key': key, 'Origin': 'shared', DIRECTOR: ''})
        prev = next((new_keyed[p] for p in range(j - 1, -1, -1) if new_keyed[p] in {r['Key'] for r in out}), None)
        at = 0 if prev is None else 1 + next(i for i, r in enumerate(out) if r['Key'] == prev)
        # Local rows Gary added after a line stay attached to it: new Sheet rows go after them.
        while at < len(out) and out[at].get('Origin') == 'local':
            at += 1
        out.insert(at, fresh)
        log.append('%s added from the Sheet' % key)

    snapshot = []
    for j, row in enumerate(new_rows):
        snap = dict(row)
        snap['Key'] = new_keyed[j]
        snapshot.append(snap)
    return out, snapshot, log, conflicts


def describe(row, columns):
    parts = ['%s: %s' % (c, row[c].replace('\n', ' / ')) for c in columns if row.get(c)]
    return '; '.join(parts) if parts else '(empty)'


# ---------------------------------------------------------------- commands
def pull(sheet_csv_path):
    with open(sheet_csv_path, encoding='utf-8') as f:
        columns, speakers, new_rows = read_sheet(f.read())
    snap_fields, base_rows = load_csv(SNAPSHOT)
    work_fields, work_rows = load_csv(WORKING)
    if not work_rows:
        # first import: the working copy starts as the Sheet
        for i, r in enumerate(new_rows):
            r['Key'] = 'R%04d' % (i + 1)
            r['Origin'] = 'shared'
            r[DIRECTOR] = ''
        work, snapshot, log, conflicts = new_rows, [dict(r) for r in new_rows], ['first import: %d rows' % len(new_rows)], []
    else:
        work, snapshot, log, conflicts = merge(base_rows, new_rows, work_rows, columns)
    fields = ['Key', 'Origin'] + columns + [DIRECTOR]
    extra = [f for f in work_fields if f and f not in fields]    # columns Gary added himself stay
    save_csv(WORKING, fields + extra, work)
    save_csv(SNAPSHOT, ['Key'] + columns, snapshot)
    lines = ['# Cue sheet sync report', '', 'Source: %s' % os.path.basename(sheet_csv_path),
             'Speakers: %s' % ', '.join(speakers), '',
             '## Conflicts (%d): you decide' % len(conflicts), '']
    for key, why, mine, theirs in conflicts:
        lines += ['### %s: %s' % (key, why), '', '- **Yours (kept):** %s' % describe(mine, columns)]
        lines += ['- **Sheet:** %s' % (describe(theirs, columns) if theirs else '(row deleted in the Sheet)'), '']
    lines += ['## Changes applied (%d)' % len(log), ''] + ['- ' + l for l in log] + ['']
    with open(REPORT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    render()
    print('CUE_SYNC_PULL_OK rows=%d changes=%d conflicts=%d' % (len(work), len(log), len(conflicts)))


def render():
    fields, rows = load_csv(WORKING)
    if not rows:
        raise SystemExit('no working.csv yet: run pull first')
    sheet_cols = [f for f in fields if f not in ('Key', 'Origin', DIRECTOR)]
    video = next((c for c in sheet_cols if c.lower().startswith('video')), None)
    out = ['# Puss cue list (working copy)', '',
           'Generated from `Docs/CueSheet/working.csv` by `Tools/CueSheet/cue_sync.py render`. Edit the CSV or ask Claude;',
           'the shared Google Sheet is never written. *Local* = a row added here; **Director notes** = your detail.', '']
    segment = 'Pre-show'
    out += ['## ' + segment, '']
    for r in rows:
        if video and r.get(video):
            segment = r[video]
            out += ['', '## ' + segment, '']
        bits = []
        if r.get('#'):
            bits.append('**[cue %s]**' % r['#'])
        for c in sheet_cols:
            if c in ('#',) or not r.get(c):
                continue
            label = c.replace('Speaker: ', '').upper() if c.startswith('Speaker: ') else c
            bits.append('**%s:** %s' % (label, r[c].replace('\n', ' / ')))
        if r.get(DIRECTOR):
            bits.append('**Director notes:** %s' % r[DIRECTOR].replace('\n', ' / '))
        if r.get('Origin') == 'local':
            bits.append('*local*')
        out.append('- `%s` %s' % (r['Key'], ' | '.join(bits) if bits else '(number only)'))
    with open(RENDER, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out) + '\n')
    # the Unreal export: the Sheet's layout, with Director notes folded into Notes
    notes = next((c for c in sheet_cols if c.lower().startswith('note')), None)
    header = [('' if c == '#' else ('Speaker' if c.startswith('Speaker: ') else c.split(' (')[0])) for c in sheet_cols]
    names = [(c.replace('Speaker: ', '') if c.startswith('Speaker: ') else '') for c in sheet_cols]
    os.makedirs(os.path.dirname(EXPORT), exist_ok=True)
    with open(EXPORT, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerow(names)
        for r in rows:
            cells = [r.get(c, '') for c in sheet_cols]
            if notes and r.get(DIRECTOR):
                i = sheet_cols.index(notes)
                cells[i] = (cells[i] + ' | ' if cells[i] else '') + 'GZ: ' + r[DIRECTOR]
            w.writerow(cells)
    print('CUE_SYNC_RENDER_OK rows=%d md=%s export=%s' % (len(rows), RENDER, EXPORT))


def note(key, text):
    fields, rows = load_csv(WORKING)
    row = next((r for r in rows if r['Key'] == key), None)
    if row is None:
        raise SystemExit('no row %s' % key)
    row[DIRECTOR] = text
    save_csv(WORKING, fields, rows)
    render()
    print('CUE_SYNC_NOTE_OK key=%s' % key)


def insert(after_key, assignments):
    fields, rows = load_csv(WORKING)
    at = next((i for i, r in enumerate(rows) if r['Key'] == after_key), None)
    if at is None:
        raise SystemExit('no row %s' % after_key)
    fresh = {f: '' for f in fields}
    fresh.update({'Key': next_key({r['Key'] for r in rows}), 'Origin': 'local'})
    for item in assignments:
        column, _, value = item.partition('=')
        match = next((f for f in fields if f.lower() == column.strip().lower()
                      or f.lower() == 'speaker: ' + column.strip().lower()), None)
        if match is None or match in ('Key', 'Origin'):
            raise SystemExit('unknown column %r (columns: %s)' % (column, ', '.join(fields[2:])))
        fresh[match] = value
    rows.insert(at + 1, fresh)
    save_csv(WORKING, fields, rows)
    render()
    print('CUE_SYNC_INSERT_OK key=%s after=%s' % (fresh['Key'], after_key))


# ---------------------------------------------------------------- the online Cue Book
def web_doc(row, ord_value):
    d = {'key': row['Key'], 'ord': ord_value, 'origin': row.get('Origin', ''), 'num': row.get('#', ''),
         'cut': False, 'director': row.get(DIRECTOR, '')}
    d.update({f: row.get(c, '') for f, c in WEB_FIELDS.items()})
    return d


def web_fields(doc):
    out = {f: (doc.get(f) or '') for f in WEB_FIELDS}
    out['cut'] = bool(doc.get('cut'))
    return out


def web_merge(baseline, web_docs, work_rows):
    """baseline: {'rows': {page key: fields}, 'web_keys': {page key: working Key}}. web_docs: page documents.
    Returns (work_rows, new_baseline, log, conflicts). Pure: no files."""
    log, conflicts = [], []
    rows = [dict(r) for r in work_rows]
    by_key = {r['Key']: r for r in rows}
    web_keys = dict(baseline.get('web_keys', {}))
    base_rows = baseline.get('rows', {})
    new_base = {}
    for doc in sorted(web_docs, key=lambda d: d.get('ord', 0)):
        page_key = doc.get('key') or doc.get('id')
        now = web_fields(doc)
        work_key = web_keys.get(page_key, page_key)
        row = by_key.get(work_key)
        if row is None:
            if page_key in base_rows:
                new_base[page_key] = now
                conflicts.append((page_key, 'the row is gone from the working copy but the page still has it'))
                continue
            if not any(now[f] for f in WEB_FIELDS):
                continue                                   # an empty cue added and never filled in: pick it up later
            new_base[page_key] = now
            after = web_keys.get(doc.get('after', ''), doc.get('after', ''))
            at = next((i for i, r in enumerate(rows) if r['Key'] == after), len(rows) - 1)
            while at + 1 < len(rows) and rows[at + 1].get('Origin') == 'web':
                at += 1                                    # cues added after the same cue keep page order
            fresh = {k: '' for k in rows[0]} if rows else {}
            fresh.update({'Key': next_key(set(by_key)), 'Origin': 'web'})
            fresh.update({c: now[f] for f, c in WEB_FIELDS.items()})
            if now['cut']:
                fresh[DIRECTOR] = CUT_MARK
            rows.insert(at + 1, fresh)
            by_key[fresh['Key']] = fresh
            web_keys[page_key] = fresh['Key']
            log.append('%s: new cue from the page (after %s)' % (fresh['Key'], after))
            continue
        new_base[page_key] = now
        base = base_rows.get(page_key)
        if base is None:
            continue
        for f, c in WEB_FIELDS.items():
            if now[f] == base.get(f, ''):
                continue
            mine = row.get(c, '')
            if mine == base.get(f, '') or mine == now[f]:
                if mine != now[f]:
                    row[c] = now[f]
                    log.append('%s %s: %r -> %r' % (row['Key'], c, mine[:60], now[f][:60]))
            else:
                conflicts.append((row['Key'], '%s: working copy %r, page %r (kept the working copy)' % (c, mine, now[f])))
        if now['cut'] != bool(base.get('cut')):
            note_text = row.get(DIRECTOR, '')
            if now['cut'] and CUT_MARK not in note_text:
                row[DIRECTOR] = (CUT_MARK + ' ' + note_text).strip()
            elif not now['cut']:
                row[DIRECTOR] = note_text.replace(CUT_MARK, '').strip()
            log.append('%s: %s on the page' % (row['Key'], 'marked as cut' if now['cut'] else 'restored'))
    return rows, {'rows': new_base, 'web_keys': web_keys}, log, conflicts


def read_web_dir(path):
    import glob
    import json
    if os.path.isfile(path):                               # a Cue Book download or a backup file: {"cues": [...]}
        with open(path, encoding='utf-8') as f:
            return [dict(c) for c in json.load(f).get('cues', [])]
    docs = []
    for p in glob.glob(os.path.join(path, '**', '*.json'), recursive=True):
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
        if not isinstance(d, dict):
            continue
        data = dict(d.get('data', d))
        data.setdefault('key', d.get('id') or os.path.splitext(os.path.basename(p))[0])
        docs.append(data)
    return docs


def webpull(path):
    import json
    fields, rows = load_csv(WORKING)
    with open(WEB_BASELINE, encoding='utf-8') as f:
        baseline = json.load(f)
    docs = read_web_dir(path)
    if not docs:
        raise SystemExit('no page documents under %s' % path)
    out, new_base, log, conflicts = web_merge(baseline, docs, rows)
    save_csv(WORKING, fields, out)
    with open(WEB_BASELINE, 'w', encoding='utf-8') as f:
        json.dump(new_base, f, ensure_ascii=False, indent=1)
    with open(WEB_REPORT, 'w', encoding='utf-8') as f:
        f.write('# Cue Book pull (%d page cues)\n\n## Conflicts (%d): Gary decides\n\n' % (len(docs), len(conflicts)))
        f.writelines('- **%s** %s\n' % c for c in conflicts)
        f.write('\n## Applied (%d)\n\n' % len(log))
        f.writelines('- %s\n' % line for line in log)
    render()
    print('CUE_SYNC_WEBPULL_OK docs=%d applied=%d conflicts=%d' % (len(docs), len(log), len(conflicts)))


def cuebook_pull():
    """Download the live Cue Book (URL from Tools/CueBook/site/config.js, passcode from CUEBOOK_PASS) and merge it."""
    import datetime
    import json
    import re
    import urllib.request
    with open(os.path.join(ROOT, 'Tools', 'CueBook', 'site', 'config.js'), encoding='utf-8') as f:
        m = re.search(r'CUEBOOK_API\s*=\s*"([^"]+)"', f.read())
    if not m:
        raise SystemExit('no CUEBOOK_API URL in Tools/CueBook/site/config.js')
    password = os.environ.get('CUEBOOK_PASS')
    if not password:
        raise SystemExit('set CUEBOOK_PASS to the Cue Book passcode')
    body = json.dumps({'pass': password, 'action': 'list'}).encode('utf-8')
    req = urllib.request.Request(m.group(1), data=body, headers={'Content-Type': 'text/plain;charset=utf-8'})
    with urllib.request.urlopen(req, timeout=60) as r:
        res = json.loads(r.read().decode('utf-8'))
    if not res.get('ok'):
        raise SystemExit('the Cue Book refused: %s' % (res.get('message') or res.get('code')))
    os.makedirs(os.path.join(DIR, 'pulls'), exist_ok=True)
    out = os.path.join(DIR, 'pulls', 'cuebook_%s.json' % datetime.datetime.now().strftime('%Y-%m-%dT%H%M'))
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'app': 'puss-cue-book', 'saved': datetime.datetime.now().isoformat(), 'cues': res['cues']}, f,
                  ensure_ascii=False, indent=1)
    print('CUE_SYNC_CUEBOOK_DOWNLOADED cues=%d file=%s' % (len(res['cues']), out))
    webpull(out)


def web_seed_baseline():
    """Record working.csv as the page's merge base (run once, right after seeding the page from it)."""
    import json
    _, rows = load_csv(WORKING)
    base = {'rows': {r['Key']: web_fields(web_doc(r, 0)) for r in rows}, 'web_keys': {}}
    with open(WEB_BASELINE, 'w', encoding='utf-8') as f:
        json.dump(base, f, ensure_ascii=False, indent=1)
    print('CUE_SYNC_WEBBASE_OK rows=%d' % len(rows))


def selftest():
    cols = ['#', 'Light', 'Speaker: Klara']
    def rows(*specs):
        return [dict(zip(cols, s)) for s in specs]
    base = rows(('1', 'Black out', ''), ('', '', 'Once upon a time'), ('', '', 'old man'), ('2', 'State 1', ''))
    for i, r in enumerate(base):
        r['Key'] = 'R%04d' % (i + 1)
    work = [dict(r, Origin='shared', **{DIRECTOR: ''}) for r in base]
    work[1][DIRECTOR] = 'slow here'                      # local detail only (no conflict)
    work[2]['Speaker: Klara'] = 'old man (GZ edit)'      # local edit of a line...
    work.insert(3, {'Key': 'R0099', 'Origin': 'local', '#': '', 'Light': 'LX check', 'Speaker: Klara': '', DIRECTOR: ''})
    new = rows(('1', 'Black out FAST', ''), ('', '', 'Once upon a time'), ('', '', 'old man, revised'),
               ('', '', 'NEW LINE'), ('2', 'State 1', ''))
    out, snap, log, conflicts = merge(base, new, work, cols)
    keys = [r['Key'] for r in out]
    checks = [
        ('Sheet edit on an untouched row is applied', out[0]['Light'] == 'Black out FAST'),
        ('local Director notes survive', out[1][DIRECTOR] == 'slow here'),
        ('edit on both sides keeps yours', out[2]['Speaker: Klara'] == 'old man (GZ edit)'),
        ('...and is reported as a conflict', len(conflicts) == 1 and conflicts[0][0] == 'R0003'),
        ('a local row stays in place', keys.index('R0099') == 3),
        ('a new Sheet row arrives after its neighbour', any(r.get('Speaker: Klara') == 'NEW LINE' for r in out)),
        ('snapshot keeps keys for the next merge', [r['Key'] for r in snap][:3] == ['R0001', 'R0002', 'R0003']),
    ]
    # control: no Sheet change -> nothing changes
    out2, _, log2, conf2 = merge(base, [dict((k, v) for k, v in r.items() if k != 'Key') for r in base], work, cols)
    checks.append(('control: an unchanged Sheet changes nothing', not log2 and not conf2 and len(out2) == len(work)))
    # control: Sheet deletes a row Gary annotated -> kept + conflict
    out3, _, _, conf3 = merge(base, [dict((k, v) for k, v in r.items() if k != 'Key') for r in base if r['Key'] != 'R0002'], work, cols)
    checks.append(('control: deleting an annotated row is a conflict, not a loss', any(c[0] == 'R0002' for c in conf3) and any(r['Key'] == 'R0002' for r in out3)))
    # the online Cue Book
    wbase = {'rows': {'R0001': {'light': 'A', 'klara': 'x', 'cut': False}, 'R0002': {'light': 'B', 'klara': 'y', 'cut': False}},
             'web_keys': {}}
    wwork = [{'Key': 'R0001', 'Origin': 'shared', 'Light': 'A', 'Speaker: Klara': 'x', DIRECTOR: ''},
             {'Key': 'R0002', 'Origin': 'shared', 'Light': 'B GZ', 'Speaker: Klara': 'y', DIRECTOR: ''}]
    wdocs = [{'key': 'R0001', 'ord': 10, 'light': 'A', 'klara': 'x (Klara edit)', 'cut': False},
             {'key': 'R0002', 'ord': 20, 'light': 'B page', 'klara': 'y', 'cut': True},
             {'key': 'WABC', 'ord': 15, 'after': 'R0001', 'cameron': 'foley: door', 'cut': False},
             {'key': 'WDEF', 'ord': 16, 'after': 'R0001', 'cut': False}]
    wout, wnb, wlog, wconf = web_merge(wbase, wdocs, wwork)
    checks += [
        ('web: a page edit on an untouched field is applied', wout[0]['Speaker: Klara'] == 'x (Klara edit)'),
        ('web: edited on both sides keeps the working copy', any(r['Light'] == 'B GZ' for r in wout)),
        ('web: ...and is a conflict', len(wconf) == 1 and wconf[0][0] == 'R0002'),
        ('web: a cut is flagged, not deleted', any(CUT_MARK in r[DIRECTOR] for r in wout) and len(wout) == 3),
        ('web: a new page cue lands after its cue', wout[1].get('Speaker: Cameron') == 'foley: door' and wout[1]['Origin'] == 'web'),
        ('web: an empty new cue waits', 'WDEF' not in wnb['web_keys'] and 'WDEF' not in wnb['rows']),
        ('web: the new cue is remembered for the next pull', wnb['web_keys'].get('WABC') == wout[1]['Key']),
    ]
    again, _, alog, aconf = web_merge(wnb, wdocs, wout)
    checks.append(('web control: pulling the same page twice changes nothing',
                   not alog and not aconf and again == wout))
    ok = all(c for _, c in checks)
    for name, c in checks:
        print(('PASS ' if c else 'FAIL ') + name)
    print('CUE_SYNC_SELFTEST_%s %d/%d' % ('OK' if ok else 'FAILED', sum(1 for _, c in checks if c), len(checks)))
    return 0 if ok else 1


if __name__ == '__main__':
    command = sys.argv[1] if len(sys.argv) > 1 else ''
    if command == 'pull' and len(sys.argv) == 3:
        pull(sys.argv[2])
    elif command == 'render':
        render()
    elif command == 'note' and len(sys.argv) == 4:
        note(sys.argv[2], sys.argv[3])
    elif command == 'insert' and len(sys.argv) >= 4:
        insert(sys.argv[2], sys.argv[3:])
    elif command == 'webpull' and len(sys.argv) == 3:
        webpull(sys.argv[2])
    elif command == 'cuebook':
        cuebook_pull()
    elif command == 'webbase':
        web_seed_baseline()
    elif command == 'selftest':
        sys.exit(selftest())
    else:
        print(__doc__)
        sys.exit(2)
