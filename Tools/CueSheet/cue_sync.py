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
  python Tools/CueSheet/cue_sync.py export <cuebook.json>         webpull, render, then cb3 surtitles when present
  python Tools/CueSheet/cue_sync.py print <preset> [--from SEG --to SEG] [--include-cut]
                                                               write a compact browser-to-PDF cue list
  python Tools/CueSheet/cue_sync.py webbase                       record working.csv as the page's merge base (after seeding)
  python Tools/CueSheet/cue_sync.py tocuebook                     write a changes file for the Cue Book (pull does this too)

Project -> Cue Book: `tocuebook` (run automatically after every `pull`) writes Docs/CueSheet/to_cuebook/
cuebook_changes_<time>.json: every field where working.csv differs from what the Cue Book was last known to hold
(web_baseline.json), new rows (page key "W" + the row's Key), and rows gone from the working copy (proposed as
"cut"). Gary loads it on the page (Backup > Choose a backup file): it lists every change, applies nothing until he
confirms, and applies them as ordinary logged edits, so a field someone changed on the page comes back as a
conflict to decide instead of being overwritten.

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
import hashlib
import html
import io
import itertools
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIR = os.path.join(ROOT, 'Docs', 'CueSheet')
WORKING = os.path.join(DIR, 'working.csv')
SNAPSHOT = os.path.join(DIR, 'shared_snapshot.csv')
REPORT = os.path.join(DIR, 'sync_report.md')
RENDER = os.path.join(DIR, 'PUSS_CUE_LIST.md')
EXPORT = os.path.join(ROOT, 'Content', 'InfinityStage', 'CueSheet', 'Puss_Master_cue_sheet.csv')
DIRECTOR = 'Director notes'
AT = 'At'
GO = 'GO'
PAUSE = 'Pause possible'   # 'yes' = an ambience moment where a pause is possible (Gary 9 Oct)
WEB_BASELINE = os.path.join(DIR, 'web_baseline.json')
WEB_REPORT = os.path.join(DIR, 'web_report.md')
SURTITLES_EXPORT = os.path.join(ROOT, 'Content', 'InfinityStage', 'CueSheet', 'Puss_Surtitles.csv')
SURTITLES_BASE = os.path.join(DIR, 'surtitles_base.csv')
SEGMENT_MAP = os.path.join(ROOT, 'Tools', 'CueBook', 'segment_map.json')
PRINT_PRESETS = os.path.join(ROOT, 'Tools', 'CueBook', 'site', 'print_presets.json')
PRINT_DIR = os.path.join(DIR, 'print')
# page field -> working.csv column
WEB_FIELDS = {'light': 'Light', 'soundTech': 'Sound tech', 'action': 'Action', 'soundCue': 'Sound cue',
              'videoCue': 'Video Cue', 'klara': 'Speaker: Klara', 'gary': 'Speaker: Gary',
              'cameron': 'Speaker: Cameron', 'beats': 'Beats', 'notes': 'Notes', 'at': AT, 'go': GO,
              'pause': PAUSE}
CUT_MARK = '[CUT on the Cue Book]'
TIME_FIELD = re.compile(r'^[+]?(?:\d+(?:\.\d*)?|\.\d+)$')
# BREATH = a breath-pause point (design 0d2ae74); the transport has no BREATH yet, so marker sync skips it.
GO_FIELD = re.compile(r'^([0-9]+(?:\.[0-9]+)?)(?:\s+(HOLD|PASS|BREATH))?$')
SURTITLE_FIELDS = ('segment', 'in', 'out', 'speaker', 'text', 'notes')
SURTITLE_HEADERS = ('Segment', 'In', 'Out', 'Speaker', 'Text', 'Notes', 'Key')


def parse_cue_time(text, fps=25.0):
    """Surtitles-compatible segment-relative time -> seconds; raises ValueError on a bad value."""
    raw = str(text).strip()
    fields = raw.split(':')
    if not raw or not 1 <= len(fields) <= 4 or fps <= 0:
        raise ValueError('bad cue time %r' % text)
    if any(not TIME_FIELD.fullmatch(field.strip()) for field in fields):
        raise ValueError('bad cue time %r' % text)
    values = [float(field.strip()) for field in fields]
    if len(values) == 1:
        seconds = values[0]
    elif len(values) == 2:
        seconds = values[0] * 60.0 + values[1]
    elif len(values) == 3:
        seconds = values[0] * 3600.0 + values[1] * 60.0 + values[2]
    else:
        if values[3] >= fps:
            raise ValueError('frame field must be below %g in %r' % (fps, text))
        seconds = values[0] * 3600.0 + values[1] * 60.0 + values[2] + values[3] / fps
    return seconds


def parse_go(text):
    """Cue Book GO field -> (number, optional HOLD/PASS, canonical field text)."""
    raw = str(text).strip()
    match = GO_FIELD.fullmatch(raw)
    if match is None:
        raise ValueError('bad GO %r (expected "<number> [HOLD|PASS|BREATH]")' % text)
    number, mode = match.groups()
    return number, mode, number + ((' ' + mode) if mode else '')


def _segment_map():
    """cb2 label -> transport key map, when that stream has supplied it; otherwise empty."""
    if not os.path.exists(SEGMENT_MAP):
        return {}
    with open(SEGMENT_MAP, encoding='utf-8') as handle:
        data = json.load(handle)
    if isinstance(data, dict):
        data = data.get('segments', data)
    if isinstance(data, list):
        pairs = ((item.get('label') or item.get('name'), item.get('key') or item.get('id'))
                 for item in data if isinstance(item, dict))
    elif isinstance(data, dict):
        pairs = data.items()
    else:
        return {}
    return {str(label).strip(): str(key).strip() for label, key in pairs if label and isinstance(key, str) and key.strip()}


def cuebook_segments(cues):
    labels = ['Prologue']
    for cue in sorted(cues, key=lambda item: float(item.get('ord') or 0)):
        label = str(cue.get('videoCue') or '').strip().split('\n', 1)[0]
        if label and not cue.get('cut'):
            labels.append(label)
    mapping = _segment_map()
    known = set(labels) | {mapping[label] for label in labels if label in mapping}
    return known, mapping


def validate_surtitle_line(line, known_segments=None):
    segment = str(line.get('segment') or '').strip()
    in_text = str(line.get('in') or '').strip()
    out_text = str(line.get('out') or '').strip()
    if not segment:
        raise ValueError('a surtitle line has no segment')
    if known_segments is not None and segment not in known_segments:
        raise ValueError('unknown surtitle segment %r' % segment)
    in_seconds = parse_cue_time(in_text)
    if out_text:
        out_seconds = parse_cue_time(out_text)
        if out_seconds <= in_seconds:
            raise ValueError('surtitle Out must be after In (%r <= %r)' % (out_text, in_text))
    return segment


def surtitles_csv(lines, known_segments=None, segment_map=None):
    """Cue Book lines -> RFC-4180 sheet accepted by InfinityStageSurtitles.cpp:100,233-324,345-379."""
    segment_map = segment_map or {}
    output = io.StringIO(newline='')
    writer = csv.writer(output, lineterminator='\r\n')
    writer.writerow(SURTITLE_HEADERS)
    live = [line for line in lines if not line.get('cut')]
    live.sort(key=lambda line: (str(line.get('segment') or ''), parse_cue_time(line.get('in') or ''),
                                float(line.get('ord') or 0), str(line.get('key') or '')))
    for line in live:
        segment = validate_surtitle_line(line, known_segments)
        segment = segment_map.get(segment, segment)
        writer.writerow([segment, str(line.get('in') or '').strip(), str(line.get('out') or '').strip(),
                         str(line.get('speaker') or ''), str(line.get('text') or ''),
                         str(line.get('notes') or ''), str(line.get('key') or '')])
    return output.getvalue()


def parse_surtitles_csv(text):
    """Port of branch parser column/time rules for offline export/merge verification.

    Source: InfinityStageSurtitles.cpp:100-119,233-324,345-379 on branch ``surtitles``.
    Returns (accepted rows, warnings); an invalid Out holds to next line, matching the C++ parser.
    """
    table = list(csv.reader(io.StringIO(str(text).lstrip('\ufeff'))))
    header_i = next((i for i, row in enumerate(table)
                     if any(cell.strip().lower() == 'segment' for cell in row)), None)
    if header_i is None:
        return [], ['no header row (a cell "Segment")']
    header = [cell.strip().lower() for cell in table[header_i]]
    def column(*names):
        lowered = [name.lower() for name in names]
        return next((i for i, name in enumerate(header) if name in lowered), None)
    cols = {'segment': column('Segment'), 'in': column('In', 'Start'), 'out': column('Out', 'End'),
            'speaker': column('Speaker'), 'text': column('Text', 'Surtitle', 'Line'), 'key': column('Key'),
            'notes': column('Notes')}
    if cols['in'] is None or cols['text'] is None:
        return [], ['the header needs In and Text columns']
    def cell(row, name):
        index = cols[name]
        return row[index].strip() if index is not None and index < len(row) else ''
    rows, warnings, carried = [], [], ''
    for offset, source in enumerate(table[header_i + 1:], header_i + 2):
        segment = cell(source, 'segment')
        if segment:
            carried = segment
        in_text, line_text = cell(source, 'in'), cell(source, 'text')
        if not in_text:
            if line_text:
                warnings.append('row %d: text with no In time, skipped' % offset)
            continue
        if not carried:
            warnings.append('row %d: no Segment yet, skipped' % offset)
            continue
        try:
            in_seconds = parse_cue_time(in_text)
        except ValueError:
            warnings.append('row %d: In %r is not a time, skipped' % (offset, in_text))
            continue
        out_text = cell(source, 'out')
        if out_text:
            try:
                out_seconds = parse_cue_time(out_text)
            except ValueError:
                warnings.append('row %d: Out %r is not a time; held to the next line' % (offset, out_text))
                out_text = ''
            else:
                if out_seconds <= in_seconds:
                    warnings.append('row %d: Out is not after In, skipped' % offset)
                    continue
        rows.append({'segment': carried, 'in': in_text, 'out': out_text, 'speaker': cell(source, 'speaker'),
                     'text': line_text, 'notes': cell(source, 'notes'), 'key': cell(source, 'key')})
    return rows, warnings


def validate_cuebook_docs(docs):
    problems = []
    for index, doc in enumerate(docs, 1):
        key = doc.get('key') or doc.get('id') or '#%d' % index
        at, go = str(doc.get('at') or '').strip(), str(doc.get('go') or '').strip()
        try:
            if at:
                parse_cue_time(at)
            if go:
                parse_go(go)
            if go and not at:
                problems.append('%s: GO has no At time' % key)
            if str(doc.get('pause') or '') not in ('', 'yes'):
                problems.append('%s: pause must be yes or empty' % key)
        except ValueError as error:
            problems.append('%s: %s' % (key, error))
    if problems:
        raise ValueError('Cue Book timing fields refused: ' + ' | '.join(problems))


def with_cuebook_fields(fields):
    """At/GO are Cue Book-only columns and are always appended, never inserted into the Sheet layout."""
    return list(fields) + [name for name in (AT, GO, PAUSE) if name not in fields]


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
    save_csv(WORKING, with_cuebook_fields(fields + extra), work)
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
    return {'rows': len(rows), 'md': RENDER, 'export': EXPORT}


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

    # Three-way merge the order before the field merge. Baseline dict order is the page order recorded by the
    # previous pull; web_docs is the current page order; rows is Gary's current order. New page cues are handled
    # below and do not participate until their first baseline has been written.
    page_to_work = {}
    for page_key in base_rows:
        work_key = web_keys.get(page_key, page_key)
        if work_key not in by_key and page_key[:1] == 'W' and page_key[1:] in by_key:
            work_key = page_key[1:]
        if work_key in by_key:
            page_to_work[page_key] = work_key
    base_order = [key for key in base_rows if key in page_to_work]
    current_page_keys = [doc.get('key') or doc.get('id') for doc in sorted(web_docs, key=lambda d: d.get('ord', 0))]
    page_order = [key for key in current_page_keys if key in page_to_work]
    work_to_page = {work_key: page_key for page_key, work_key in page_to_work.items()}
    work_order = [work_to_page[row['Key']] for row in rows if row['Key'] in work_to_page]
    comparable = set(base_order) == set(page_order) == set(work_order)
    if comparable and page_order != base_order:
        if work_order == base_order:
            reordered = iter([by_key[page_to_work[key]] for key in page_order])
            slots = set(page_to_work.values())
            rows = [next(reordered) if row['Key'] in slots else row for row in rows]
            moved = [key for index, key in enumerate(page_order) if base_order[index] != key]
            log.append('cue order: page move applied (%s)' % ', '.join(moved))
        elif work_order != page_order:
            conflicts.append(('_order', 'cue order changed on both the page and in the working copy (kept the working order)'))
    for doc in sorted(web_docs, key=lambda d: d.get('ord', 0)):
        page_key = doc.get('key') or doc.get('id')
        now = web_fields(doc)
        work_key = web_keys.get(page_key, page_key)
        if work_key not in by_key and page_key[:1] == 'W' and page_key[1:] in by_key:
            work_key = page_key[1:]                        # a row the project sent to the page (tocuebook)
            web_keys[page_key] = work_key
            base_rows = dict(base_rows)
            base_rows.setdefault(page_key, base_rows.get(work_key, web_fields(web_doc(by_key[work_key], 0))))
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


def webpull(path, render_after=True):
    fields, rows = load_csv(WORKING)
    with open(WEB_BASELINE, encoding='utf-8') as f:
        baseline = json.load(f)
    docs = read_web_dir(path)
    if not docs:
        raise SystemExit('no page documents under %s' % path)
    try:
        validate_cuebook_docs(docs)
    except ValueError as error:
        raise SystemExit(str(error))
    out, new_base, log, conflicts = web_merge(baseline, docs, rows)
    save_csv(WORKING, with_cuebook_fields(fields), out)
    with open(WEB_BASELINE, 'w', encoding='utf-8') as f:
        json.dump(new_base, f, ensure_ascii=False, indent=1)
    # Keep the last actionable report byte-stable when a repeated pull is a no-op.
    if log or conflicts or not os.path.exists(WEB_REPORT):
        with open(WEB_REPORT, 'w', encoding='utf-8') as f:
            f.write('# Cue Book pull (%d page cues)\n\n## Conflicts (%d): Gary decides\n\n' % (len(docs), len(conflicts)))
            f.writelines('- **%s** %s\n' % c for c in conflicts)
            f.write('\n## Applied (%d)\n\n' % len(log))
            f.writelines('- %s\n' % line for line in log)
    if render_after:
        render()
    print('CUE_SYNC_WEBPULL_OK docs=%d applied=%d conflicts=%d' % (len(docs), len(log), len(conflicts)))
    return {'docs': len(docs), 'applied': len(log), 'conflicts': len(conflicts)}


def _bytes(path):
    if not os.path.exists(path):
        return b''
    with open(path, 'rb') as handle:
        return handle.read()


def _changed_rows(before, after, path):
    if before == after:
        return 0
    if path.lower().endswith('.csv'):
        old = list(csv.reader(io.StringIO(before.decode('utf-8-sig')))) if before else []
        new = list(csv.reader(io.StringIO(after.decode('utf-8-sig')))) if after else []
    else:
        old = before.decode('utf-8', errors='replace').splitlines()
        new = after.decode('utf-8', errors='replace').splitlines()
    return sum(1 for a, b in itertools.zip_longest(old, new) if a != b)


def _base36(number):
    alphabet = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    out = ''
    while number:
        number, digit = divmod(number, 36)
        out = alphabet[digit] + out
    return out or '0'


def _unreal_line_key(line, row_index):
    material = json.dumps([row_index] + [line.get(field, '') for field in SURTITLE_FIELDS],
                          ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return 'T' + _base36(int(hashlib.sha1(material).hexdigest()[:13], 16))[:11]


def unreal_surtitle_changes(base_text, live_text, cuebook_lines):
    """Return the field changes/adds still needed in the Cue Book for Unreal's version of the CSV."""
    base_rows, base_warnings = parse_surtitles_csv(base_text)
    live_rows, live_warnings = parse_surtitles_csv(live_text)
    if base_warnings or live_warnings:
        raise ValueError('cannot merge surtitle CSV with parser warnings: base=%r live=%r' %
                         (base_warnings, live_warnings))
    base_by_key = {row['key']: row for row in base_rows if row['key']}
    current = {str(line.get('key') or ''): line for line in cuebook_lines if line.get('key')}
    changes, adds, seen, previous = [], [], set(), ''
    for index, row in enumerate(live_rows, 1):
        key = row.get('key') or _unreal_line_key(row, index)
        base = base_by_key.get(key)
        now = current.get(key)
        if base is None:
            fields = {field: row.get(field, '') for field in SURTITLE_FIELDS}
            if not now or any(str(now.get(field) or '') != value for field, value in fields.items()) or now.get('cut'):
                adds.append({'key': key, 'after': previous, 'fields': fields})
        else:
            seen.add(key)
            for field in SURTITLE_FIELDS:
                old, new = base.get(field, ''), row.get(field, '')
                if old != new and (not now or str(now.get(field) or '') != new):
                    changes.append({'key': key, 'field': field, 'from': old, 'to': new})
        previous = key
    for key, base in base_by_key.items():
        if key not in seen:
            now = current.get(key)
            if not now or not now.get('cut'):
                changes.append({'key': key, 'field': 'cut', 'from': False, 'to': True,
                                'why': 'row removed in Unreal'})
    return changes, adds


def write_surtitle_changes(changes, adds):
    import datetime
    out_dir = os.path.join(DIR, 'to_cuebook')
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y-%m-%dT%H%M%S')
    out = os.path.join(out_dir, 'cuebook_surtitle_changes_%s.json' % stamp)
    payload = {'app': 'puss-cue-book', 'kind': 'changes', 'target': 'surtitles',
               'created': datetime.datetime.now().isoformat(),
               'source': 'Content/InfinityStage/CueSheet/Puss_Surtitles.csv',
               'changes': changes, 'adds': adds}
    with open(out, 'w', encoding='utf-8') as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)
    return out


def atomic_write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = path + '.tmp'
    with open(temp, 'w', encoding='utf-8', newline='') as handle:
        handle.write(text)
    os.replace(temp, path)


def cuebook_export(path):
    """Saved Cue Book -> merge -> render -> optional cb3 surtitle export, with deterministic summaries."""
    with open(path, encoding='utf-8') as handle:
        payload = json.load(handle)
    surtitle_text = None
    if 'surtitles' in payload:
        known_segments, mapping = cuebook_segments(payload.get('cues') or [])
        surtitle_text = surtitles_csv(payload.get('surtitles') or [], known_segments, mapping)
        if os.path.exists(SURTITLES_EXPORT):
            live = _bytes(SURTITLES_EXPORT)
            base = _bytes(SURTITLES_BASE) if os.path.exists(SURTITLES_BASE) else surtitles_csv([]).encode('utf-8')
            if live != base:
                changes, adds = unreal_surtitle_changes(base.decode('utf-8-sig'), live.decode('utf-8-sig'),
                                                        payload.get('surtitles') or [])
                if changes or adds:
                    change_file = write_surtitle_changes(changes, adds)
                    rel = os.path.relpath(change_file, ROOT).replace('\\', '/')
                    print('CUE_SYNC_SURTITLES_UNREAL_EDITS|n=%d|file=%s' % (len(changes) + len(adds), rel))
                    return {'blocked': True, 'unreal_edits': len(changes) + len(adds), 'changes_file': rel,
                            'changed_files': [rel]}
    candidates = [WORKING, WEB_BASELINE, WEB_REPORT, RENDER, EXPORT]
    if surtitle_text is not None:
        candidates += [SURTITLES_EXPORT, SURTITLES_BASE]
    before = {p: _bytes(p) for p in candidates}
    summary = webpull(path, render_after=False)
    render()
    if surtitle_text is not None:
        atomic_write(SURTITLES_EXPORT, surtitle_text)
        atomic_write(SURTITLES_BASE, surtitle_text)
    changed = []
    for output in candidates:
        after = _bytes(output)
        if before[output] == after:
            continue
        changed.append(os.path.relpath(output, ROOT).replace('\\', '/'))
        print('CUE_SYNC_EXPORT_FILE|path=%s|changed_rows=%d|bytes_before=%d|bytes_after=%d|sha256=%s' %
              (changed[-1], _changed_rows(before[output], after, output), len(before[output]), len(after),
               hashlib.sha256(after).hexdigest()))
    surtitle_count = len([line for line in payload.get('surtitles', []) if not line.get('cut')])
    print('CUE_SYNC_EXPORT_OK|cues=%d|surtitles=%d|changed_files=%s' %
          (summary['docs'], surtitle_count, json.dumps(changed, separators=(',', ':'))))
    return {'cues': summary['docs'], 'surtitles': surtitle_count, 'changed_files': changed}


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
        json.dump({'app': 'puss-cue-book', 'saved': datetime.datetime.now().isoformat(), 'cues': res['cues'],
                   'surtitles': res.get('surtitles', [])}, f,
                  ensure_ascii=False, indent=1)
    print('CUE_SYNC_CUEBOOK_DOWNLOADED cues=%d surtitles=%d file=%s' %
          (len(res['cues']), len(res.get('surtitles', [])), out))
    webpull(out)


def cuebook_changes(baseline, work_rows):
    """What the Cue Book needs so it matches working.csv. Pure. -> (changes, adds, gone)."""
    to_page = {v: k for k, v in baseline.get('web_keys', {}).items()}
    base_rows = baseline.get('rows', {})
    changes, adds, seen = [], [], set()
    prev_page_key = ''
    for row in work_rows:
        page_key = to_page.get(row['Key'], row['Key'])
        mine = web_fields(web_doc(row, 0))
        mine['cut'] = CUT_MARK in row.get(DIRECTOR, '')
        base = base_rows.get(page_key)
        if base is None:
            page_key = 'W' + row['Key']
            base = base_rows.get(page_key)
        if base is None:
            if any(mine[f] for f in WEB_FIELDS):
                adds.append({'key': page_key, 'after': prev_page_key, 'fields': {f: mine[f] for f in WEB_FIELDS}})
        else:
            seen.add(page_key)
            for f in list(WEB_FIELDS) + ['cut']:
                was = base.get(f, False if f == 'cut' else '')
                if mine[f] != was:
                    changes.append({'key': page_key, 'field': f, 'from': was, 'to': mine[f]})
        prev_page_key = page_key
    gone = [k for k in base_rows if k not in seen and not base_rows[k].get('cut')
            and k not in {a['key'] for a in adds} and to_page.get(k, k) not in {r['Key'] for r in work_rows}
            and k[1:] not in {r['Key'] for r in work_rows}]
    for k in gone:
        changes.append({'key': k, 'field': 'cut', 'from': False, 'to': True, 'why': 'no longer in the working copy'})
    return changes, adds, gone


def tocuebook():
    import datetime
    import json
    _, rows = load_csv(WORKING)
    with open(WEB_BASELINE, encoding='utf-8') as f:
        baseline = json.load(f)
    changes, adds, gone = cuebook_changes(baseline, rows)
    if not changes and not adds:
        print('CUE_SYNC_TOCUEBOOK_OK nothing to send (the Cue Book already matches the working copy as last known)')
        return None
    out_dir = os.path.join(DIR, 'to_cuebook')
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y-%m-%dT%H%M')
    out = os.path.join(out_dir, 'cuebook_changes_%s.json' % stamp)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'app': 'puss-cue-book', 'kind': 'changes', 'created': datetime.datetime.now().isoformat(),
                   'source': 'Docs/CueSheet/working.csv', 'changes': changes, 'adds': adds}, f,
                  ensure_ascii=False, indent=1)
    print('CUE_SYNC_TOCUEBOOK_OK changes=%d adds=%d cuts=%d file=%s' % (len(changes), len(adds), len(gone), out))
    return out


def web_seed_baseline():
    """Record working.csv as the page's merge base (run once, right after seeding the page from it)."""
    import json
    _, rows = load_csv(WORKING)
    base = {'rows': {r['Key']: web_fields(web_doc(r, 0)) for r in rows}, 'web_keys': {}}
    with open(WEB_BASELINE, 'w', encoding='utf-8') as f:
        json.dump(base, f, ensure_ascii=False, indent=1)
    print('CUE_SYNC_WEBBASE_OK rows=%d' % len(rows))


# ---------------------------------------------------------------- printable cue lists (P54)
PRINT_LABELS = {
    'num': '#', 'key': 'Key', 'segment': 'Segment', 'at': 'At', 'klara': 'Klara', 'gary': 'Gary',
    'cameron': 'Cameron', 'light': 'Light', 'soundTech': 'Sound tech', 'soundCue': 'Sound cue',
    'videoCue': 'Video cue', 'action': 'Action', 'beats': 'Beats', 'go': 'GO', 'pause': 'Pause',
    'notes': 'Notes', 'director': 'Director notes'
}
PRINT_COLUMNS = {
    'num': '#', 'key': 'Key', 'klara': 'Speaker: Klara', 'gary': 'Speaker: Gary',
    'cameron': 'Speaker: Cameron', 'light': 'Light', 'soundTech': 'Sound tech',
    'soundCue': 'Sound cue', 'videoCue': 'Video Cue', 'action': 'Action', 'beats': 'Beats',
    'notes': 'Notes', 'director': DIRECTOR, 'at': AT, 'go': GO, 'pause': PAUSE
}
PRINT_SPEAKERS = ('klara', 'gary', 'cameron')


def load_print_presets(path=None):
    with open(path or PRINT_PRESETS, encoding='utf-8') as handle:
        data = json.load(handle)
    presets = data.get('presets') if isinstance(data, dict) else None
    if not isinstance(presets, dict) or not presets:
        raise ValueError('print preset file has no presets')
    for name, preset in presets.items():
        if not isinstance(preset.get('fields'), list) or not preset.get('label'):
            raise ValueError('bad print preset %r' % name)
    return presets


def print_cues_from_working(path=None):
    """Translate working.csv rows to the same field names used by the Cue Book page."""
    _fields, rows = load_csv(path or WORKING)
    cues = []
    for index, row in enumerate(rows):
        cue = {field: str(row.get(column) or '') for field, column in PRINT_COLUMNS.items()}
        cue.update({'ord': index + 1, 'cut': CUT_MARK in str(row.get(DIRECTOR) or '')})
        cues.append(cue)
    return cues


def print_segments(cues):
    """Group cues exactly like the page: a live Video cue begins and belongs to a segment."""
    segments = [{'label': 'Prologue', 'cues': []}]
    current = segments[0]
    for cue in sorted(cues, key=lambda item: float(item.get('ord') or 0)):
        label = str(cue.get('videoCue') or '').strip().split('\n', 1)[0]
        if label and not cue.get('cut'):
            current = {'label': label, 'cues': []}
            segments.append(current)
        current['cues'].append(cue)
    if segments and not segments[0]['cues']:
        segments.pop(0)
    return segments


def select_print_segments(cues, preset, include_cut=False, from_segment=None, to_segment=None):
    """Pure print selection shared in behaviour with the page renderer."""
    segments = print_segments(cues)
    labels = [segment['label'] for segment in segments]
    try:
        first = labels.index(from_segment) if from_segment else 0
        last = labels.index(to_segment) if to_segment else len(segments) - 1
    except ValueError as error:
        raise ValueError('unknown print segment %r' % error.args[0])
    if first > last:
        raise ValueError('print segment range is backwards')
    relevance = preset.get('relevance', [])
    result = []
    for segment in segments[first:last + 1]:
        eligible = [cue for cue in segment['cues'] if include_cut or not cue.get('cut')]
        if preset.get('hide_empty') is False:
            chosen = [(cue, False) for cue in eligible]
        else:
            primary = {i for i, cue in enumerate(eligible)
                       if any(str(cue.get(field) or '').strip() for field in relevance)}
            context = set()
            if preset.get('previous_speaker_context'):
                for index in primary:
                    before = index - 1
                    if before >= 0 and any(str(eligible[before].get(field) or '').strip()
                                           for field in PRINT_SPEAKERS):
                        context.add(before)
            chosen = [(cue, index in context and index not in primary)
                      for index, cue in enumerate(eligible) if index in primary or index in context]
        if chosen:
            result.append({'label': segment['label'], 'cues': chosen})
    return result


def _print_short(value, limit=None):
    text = re.sub(r'\s+', ' ', str(value or '')).strip()
    if limit and len(text) > limit:
        return text[:max(1, limit - 1)].rstrip() + '\u2026'
    return text


def _print_context(cue):
    lines = ['%s: %s' % (PRINT_LABELS[field], _print_short(cue.get(field), 60))
             for field in PRINT_SPEAKERS if str(cue.get(field) or '').strip()]
    return ' / '.join(lines)


def render_print_html(cues, preset_name, presets=None, include_cut=False, from_segment=None,
                      to_segment=None, printed_date=None):
    """Return a deterministic, dependency-free printable HTML document."""
    import datetime
    presets = presets or load_print_presets()
    if preset_name not in presets:
        raise ValueError('unknown print preset %r (choose %s)' % (preset_name, ', '.join(presets)))
    preset = presets[preset_name]
    selected = select_print_segments(cues, preset, include_cut, from_segment, to_segment)
    date_text = printed_date or datetime.date.today().isoformat()
    title = 'Puss cue list - %s' % preset['label']
    classes = 'print-list columns-%d' % int(preset.get('columns') or 1)
    out = ['<!doctype html>', '<html lang="en">', '<head>', '<meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width,initial-scale=1">',
           '<title>%s</title>' % html.escape(title), '<style>',
           '@page { size: A4 portrait; margin: 11mm 10mm 14mm; }',
           '* { box-sizing: border-box; } body { margin: 0; color: #000; background: #fff; font: 9pt/1.25 Arial,sans-serif; }',
           'h1 { margin: 0 0 3mm; font-size: 15pt; } .print-list { column-gap: 7mm; }',
           '.columns-2 { column-count: 2; } .segment { break-inside: auto; }',
           '.segment h2 { break-after: avoid; margin: 3mm 0 1mm; padding-bottom: .8mm; border-bottom: .35mm solid #000; font-size: 11pt; }',
           '.cue { break-inside: avoid; border-bottom: .2mm solid #aaa; padding: 1.2mm 0; }',
           '.cue.cut { opacity: .6; text-decoration: line-through; } .cue.context { color: #444; font-style: italic; }',
           '.cue-id { font-weight: 700; margin-right: 2mm; } .field { display: block; } .field b { font-size: 7.5pt; text-transform: uppercase; }',
           '.print-footer { position: fixed; left: 0; right: 0; bottom: -9mm; border-top: .2mm solid #777; padding-top: 1mm; font-size: 7.5pt; }',
           '.print-footer .page::after { content: counter(page); }',
           '@media screen { body { max-width: 210mm; margin: 0 auto; padding: 14px; } .print-footer { position: static; margin-top: 12px; } }',
           '@media screen and (max-width: 600px) { .columns-2 { column-count: 1; } body { padding: 10px; font-size: 10pt; } }',
           '</style>', '</head>', '<body>', '<h1>%s</h1>' % html.escape(title), '<main class="%s">' % classes]
    truncate = preset.get('truncate', {})
    for segment in selected:
        out.append('<section class="segment"><h2>%s</h2>' % html.escape(segment['label']))
        for cue, is_context in segment['cues']:
            cue_classes = 'cue' + (' context' if is_context else '') + (' cut' if cue.get('cut') else '')
            out.append('<article class="%s" data-key="%s">' %
                       (cue_classes, html.escape(str(cue.get('key') or ''), quote=True)))
            identity = str(cue.get('num') or '\u00b7')
            if 'key' in preset['fields'] and cue.get('key'):
                identity += ' ' + str(cue['key'])
            out.append('<span class="cue-id">%s</span>' % html.escape(identity))
            if is_context:
                out.append('<span class="field context-line"><b>Context</b> %s</span>' % html.escape(_print_context(cue)))
            else:
                for field in preset['fields']:
                    if field in ('num', 'key', 'segment'):
                        continue
                    value = cue.get(field)
                    if field == 'pause':
                        value = 'PAUSE POSSIBLE' if str(value or '').strip() == 'yes' else ''
                    value = _print_short(value, truncate.get(field))
                    if value:
                        out.append('<span class="field field-%s"><b>%s</b> %s</span>' %
                                   (field, html.escape(PRINT_LABELS[field]), html.escape(value)))
            out.append('</article>')
        out.append('</section>')
    if not selected:
        out.append('<p>No cues match this preset and range.</p>')
    out.extend(['</main>', '<footer class="print-footer">Puss cue list \u00b7 %s \u00b7 printed %s \u00b7 page <span class="page"></span></footer>' %
                (html.escape(preset['label']), html.escape(date_text)), '</body>', '</html>', ''])
    return '\n'.join(out)


def print_cue_list(preset_name, from_segment=None, to_segment=None, include_cut=False):
    import datetime
    presets = load_print_presets()
    text = render_print_html(print_cues_from_working(), preset_name, presets, include_cut,
                             from_segment, to_segment)
    date_text = datetime.date.today().isoformat()
    filename = 'PussCueList_%s_%s.html' % (preset_name.replace('-', '_'), date_text)
    output = os.path.join(PRINT_DIR, filename)
    atomic_write(output, text)
    relative = os.path.relpath(output, ROOT).replace('\\', '/')
    count = text.count('<article class="cue')
    print('CUE_SYNC_PRINT_OK|preset=%s|cues=%d|file=%s' % (preset_name, count, relative))
    return output


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
    # project -> Cue Book
    tbase = {'rows': {'R0001': {**{f: '' for f in WEB_FIELDS}, 'light': 'A', 'cut': False},
                      'R0002': {**{f: '' for f in WEB_FIELDS}, 'light': 'B', 'cut': False},
                      'R0003': {**{f: '' for f in WEB_FIELDS}, 'light': 'C', 'cut': False}}, 'web_keys': {}}
    twork = [{'Key': 'R0001', 'Light': 'A2', DIRECTOR: ''}, {'Key': 'R0002', 'Light': 'B', DIRECTOR: ''},
             {'Key': 'R0009', 'Light': 'new', DIRECTOR: ''}]
    tch, tadd, tgone = cuebook_changes(tbase, twork)
    checks += [
        ('to page: a changed field is sent with its old value', tch[0] == {'key': 'R0001', 'field': 'light', 'from': 'A', 'to': 'A2'}),
        ('to page: an unchanged row sends nothing', not any(c['key'] == 'R0002' for c in tch)),
        ('to page: a new row is added after its neighbour as W+Key', tadd == [{'key': 'WR0009', 'after': 'R0002', 'fields': {**{f: '' for f in WEB_FIELDS}, 'light': 'new'}}]),
        ('to page: a row gone from the project is proposed as cut, not deleted', tgone == ['R0003'] and tch[-1]['to'] is True),
    ]
    tbase2 = {'rows': dict(tbase['rows'], R0001={**tbase['rows']['R0001'], 'light': 'A2'},
                           WR0009={**{f: '' for f in WEB_FIELDS}, 'light': 'new', 'cut': False},
                           R0003={**tbase['rows']['R0003'], 'cut': True}), 'web_keys': {}}
    tch2, tadd2, _ = cuebook_changes(tbase2, twork)
    checks.append(('to page control: once the page matches, nothing is sent', not tch2 and not tadd2))
    tpage = [{'key': 'WR0009', 'ord': 25, 'light': 'new (page edit)', 'cut': False}]
    tw2, tnb, tl2, tc2 = web_merge(tbase2, tpage, twork)
    checks.append(('page -> project: the W+Key cue maps back onto its row, no duplicate',
                   len(tw2) == 3 and tw2[2]['Light'] == 'new (page edit)' and tnb['web_keys'].get('WR0009') == 'R0009'))
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
        if os.path.exists(WEB_BASELINE):
            tocuebook()
    elif command == 'render':
        render()
    elif command == 'note' and len(sys.argv) == 4:
        note(sys.argv[2], sys.argv[3])
    elif command == 'insert' and len(sys.argv) >= 4:
        insert(sys.argv[2], sys.argv[3:])
    elif command == 'webpull' and len(sys.argv) == 3:
        webpull(sys.argv[2])
    elif command == 'tocuebook':
        tocuebook()
    elif command == 'cuebook':
        cuebook_pull()
    elif command == 'export' and len(sys.argv) == 3:
        cuebook_export(sys.argv[2])
    elif command == 'webbase':
        web_seed_baseline()
    elif command == 'selftest':
        sys.exit(selftest())
    elif command == 'print' and len(sys.argv) >= 3:
        args = sys.argv[3:]
        values = {'--from': None, '--to': None}
        include_cut = False
        while args:
            option = args.pop(0)
            if option == '--include-cut':
                include_cut = True
            elif option in values and args:
                values[option] = args.pop(0)
            else:
                raise SystemExit('bad print option %r' % option)
        try:
            print_cue_list(sys.argv[2], values['--from'], values['--to'], include_cut)
        except ValueError as error:
            raise SystemExit(str(error))
    else:
        print(__doc__)
        sys.exit(2)
