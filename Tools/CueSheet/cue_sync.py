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
    elif command == 'selftest':
        sys.exit(selftest())
    else:
        print(__doc__)
        sys.exit(2)
