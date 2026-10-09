"""Authored breaths: keep the cue list in step when a breath of D seconds is inserted into a Passage at F.

Gary, 9 Oct: the breath is AUTHORED during rehearsal ("a kind of authored breath that can be authored into
different parts during rehearsal"); the music truly pauses and the show gets longer. Finishing touches' P45
(breath_insert) makes the Unreal change; this keeps the project's cue list honest afterwards.

Times are segment-relative (At on cues; In/Out on surtitles), so a breath in Passage 3 moves only Passage 3's
times at or after F. Later segments are untouched by construction.

  python Tools/CueSheet/breath_shift.py candidates                       pause-possible cues -> breath_candidates.json
  python Tools/CueSheet/breath_shift.py shift DRY  "<passage>" <F> <D>    what would move
  python Tools/CueSheet/breath_shift.py shift APPLY "<passage>" <F> <D> --confirm APPLY_BREATH_SHIFT
  python Tools/CueSheet/breath_shift.py revert <record.json> --confirm REVERT_BREATH_SHIFT

<passage> is a Cue Book segment name ("Passage 3") or its transport key ("P03" via segment_map.json). F and D are
seconds (F accepts the At forms: 74.5, 1:14.5, ...). APPLY writes Docs/CueSheet/breaths/<run>.json BEFORE changing
anything, then working.csv and the surtitle CSV (atomically), re-renders the Unreal cue sheet and writes a Cue Book
changes file (tocuebook), so the page picks the new times up. REVERT puts back the exact original strings, and
refuses any row someone changed since the shift. Markers: BREATH_SHIFT_DRY_OK / _APPLY_OK / _REVERT_OK / _STOPPED.
"""
import datetime
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cue_sync as cs  # noqa: E402

BREATHS = os.path.join(cs.DIR, 'breaths')
CANDIDATES = os.path.join(cs.DIR, 'breath_candidates.json')
VIDEO = 'Video Cue'


def fmt_like(original, seconds):
    """New time in the same style as the original string (m:ss.s style if it had a colon, else plain seconds)."""
    seconds = round(seconds, 3)
    if ':' in str(original):
        minutes, rest = divmod(seconds, 60.0)
        text = '%d:%06.3f' % (int(minutes), rest)
    else:
        text = '%.3f' % seconds
    return text.rstrip('0').rstrip('.') if '.' in text else text


def segment_rows(rows):
    """[(label, [row, ...]), ...] in order, segments started by a non-empty Video Cue (as on the Cue Book page)."""
    segments, label, current = [], 'Prologue', []
    for row in rows:
        video = (row.get(VIDEO) or '').strip().split('\n', 1)[0]
        if video and cs.CUT_MARK not in (row.get(cs.DIRECTOR) or ''):
            if current:
                segments.append((label, current))
            label, current = video, []
        current.append(row)
    if current:
        segments.append((label, current))
    return segments


def resolve_passage(name, segments):
    """Exactly one segment whose label or mapped key matches; never guesses."""
    mapping = cs._segment_map()
    hits = [label for label, _ in segments if label == name or mapping.get(label) == name]
    if len(hits) != 1:
        raise SystemExit('BREATH_SHIFT_STOPPED|reason=passage %r matched %d segments (labels: %s)'
                         % (name, len(hits), ', '.join(label for label, _ in segments)))
    return hits[0], mapping.get(hits[0], '')


def plan_shift(rows, surtitle_rows, passage, f_seconds, d_seconds):
    """Pure: which cue At values and surtitle In/Out values move. Returns (label, key, cue_moves, line_moves)."""
    if d_seconds <= 0:
        raise SystemExit('BREATH_SHIFT_STOPPED|reason=D must be positive (got %r)' % d_seconds)
    segments = segment_rows(rows)
    label, key = resolve_passage(passage, segments)
    cue_moves = []
    for row in dict(segments)[label]:
        at = (row.get(cs.AT) or '').strip()
        if at and cs.parse_cue_time(at) >= f_seconds - 1e-9:
            cue_moves.append({'key': row['Key'], 'field': cs.AT, 'before': at,
                              'after': fmt_like(at, cs.parse_cue_time(at) + d_seconds)})
    line_moves = []
    names = {label} | ({key} if key else set())
    for index, line in enumerate(surtitle_rows):
        if (line.get('Segment') or '').strip() not in names:
            continue
        for field in ('In', 'Out'):
            value = (line.get(field) or '').strip()
            if value and cs.parse_cue_time(value) >= f_seconds - 1e-9:
                line_moves.append({'row': index, 'line_key': line.get('Key', ''), 'field': field, 'before': value,
                                   'after': fmt_like(value, cs.parse_cue_time(value) + d_seconds)})
    return label, key, cue_moves, line_moves


def _read_surtitles():
    if not os.path.exists(cs.SURTITLES_EXPORT):
        return [], list(cs.SURTITLE_HEADERS)
    with io.open(cs.SURTITLES_EXPORT, encoding='utf-8-sig', newline='') as handle:
        import csv
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or cs.SURTITLE_HEADERS)


def _write_surtitles(lines, fields):
    import csv
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction='ignore', lineterminator='\r\n')
    writer.writeheader()
    for line in lines:
        writer.writerow({field: line.get(field, '') for field in fields})
    cs.atomic_write(cs.SURTITLES_EXPORT, buffer.getvalue())


def _apply(record, direction):
    """direction 'after' applies, 'before' reverts. Refuses any value that is not what the record expects."""
    want, put = ('before', 'after') if direction == 'after' else ('after', 'before')
    fields, rows = cs.load_csv(cs.WORKING)
    by_key = {row['Key']: row for row in rows}
    lines, line_fields = _read_surtitles()
    problems = []
    for move in record['cue_moves']:
        row = by_key.get(move['key'])
        if row is None or (row.get(move['field']) or '').strip() != move[want]:
            problems.append('cue %s %s is %r, expected %r' % (move['key'], move['field'],
                                                             row and row.get(move['field']), move[want]))
    for move in record['line_moves']:
        line = lines[move['row']] if move['row'] < len(lines) else None
        if line is None or (line.get(move['field']) or '').strip() != move[want] \
                or (line.get('Key', '') != move['line_key']):
            problems.append('surtitle row %d %s changed since' % (move['row'], move['field']))
    if problems:
        raise SystemExit('BREATH_SHIFT_STOPPED|reason=%s' % ' | '.join(problems[:8]))
    for move in record['cue_moves']:
        by_key[move['key']][move['field']] = move[put]
    for move in record['line_moves']:
        lines[move['row']][move['field']] = move[put]
    cs.save_csv(cs.WORKING, cs.with_cuebook_fields(fields), rows)
    if record['line_moves']:
        _write_surtitles(lines, line_fields)
    cs.render()
    changes_file = cs.tocuebook() if os.path.exists(cs.WEB_BASELINE) else None
    return changes_file


def shift(mode, passage, f_text, d_text, confirm=None):
    f_seconds, d_seconds = cs.parse_cue_time(f_text), float(d_text)
    _fields, rows = cs.load_csv(cs.WORKING)
    lines, _ = _read_surtitles()
    label, key, cue_moves, line_moves = plan_shift(rows, lines, passage, f_seconds, d_seconds)
    for move in cue_moves:
        print('  cue %s At %s -> %s' % (move['key'], move['before'], move['after']))
    for move in line_moves:
        print('  surtitle row %d %s %s -> %s' % (move['row'], move['field'], move['before'], move['after']))
    summary = 'passage=%s|key=%s|F=%g|D=%g|cues=%d|surtitle_fields=%d' % (label, key, f_seconds, d_seconds,
                                                                         len(cue_moves), len(line_moves))
    if mode == 'DRY':
        print('BREATH_SHIFT_DRY_OK|' + summary)
        return None
    if mode != 'APPLY' or confirm != 'APPLY_BREATH_SHIFT':
        raise SystemExit('BREATH_SHIFT_STOPPED|reason=APPLY needs --confirm APPLY_BREATH_SHIFT')
    run = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    os.makedirs(BREATHS, exist_ok=True)
    path = os.path.join(BREATHS, 'breath_%s.json' % run)
    record = {'run': run, 'passage': label, 'passage_key': key, 'F_s': f_seconds, 'D_s': d_seconds,
              'cue_moves': cue_moves, 'line_moves': line_moves, 'reverted': False}
    with io.open(path, 'w', encoding='utf-8') as handle:      # the record exists before anything changes
        json.dump(record, handle, ensure_ascii=False, indent=1)
    changes = _apply(record, 'after')
    print('BREATH_SHIFT_APPLY_OK|%s|record=%s|cuebook_changes=%s' % (summary, path, changes))
    return path


def revert(path, confirm=None):
    if confirm != 'REVERT_BREATH_SHIFT':
        raise SystemExit('BREATH_SHIFT_STOPPED|reason=REVERT needs --confirm REVERT_BREATH_SHIFT')
    with io.open(path, encoding='utf-8') as handle:
        record = json.load(handle)
    if record.get('reverted'):
        raise SystemExit('BREATH_SHIFT_STOPPED|reason=already reverted')
    changes = _apply(record, 'before')
    record['reverted'] = True
    with io.open(path, 'w', encoding='utf-8') as handle:
        json.dump(record, handle, ensure_ascii=False, indent=1)
    print('BREATH_SHIFT_REVERT_OK|record=%s|cues=%d|surtitle_fields=%d|cuebook_changes=%s'
          % (path, len(record['cue_moves']), len(record['line_moves']), changes))


def candidates():
    """Read-only: every 'pause possible' cue as a candidate breath point (Passage, time in it if known)."""
    _fields, rows = cs.load_csv(cs.WORKING)
    mapping = cs._segment_map()
    out = []
    for label, seg_rows in segment_rows(rows):
        for row in seg_rows:
            if (row.get(cs.PAUSE) or '').strip() == 'yes':
                at = (row.get(cs.AT) or '').strip()
                out.append({'key': row['Key'], 'segment': label, 'segment_key': mapping.get(label, ''),
                            'is_passage': label.lower().startswith('passage'),
                            'at': at, 'at_s': cs.parse_cue_time(at) if at else None,
                            'line': ' / '.join(v for v in (row.get('Speaker: Klara'), row.get('Speaker: Gary'),
                                                           row.get('Action')) if v)[:120]})
    with io.open(CANDIDATES, 'w', encoding='utf-8') as handle:
        json.dump({'generated': datetime.datetime.now().isoformat(), 'candidates': out}, handle,
                  ensure_ascii=False, indent=1)
    print('BREATH_CANDIDATES_OK|n=%d|passages=%d|file=%s'
          % (len(out), sum(1 for c in out if c['is_passage']), CANDIDATES))
    return out


if __name__ == '__main__':
    args = sys.argv[1:]
    confirm = None
    if '--confirm' in args:
        i = args.index('--confirm')
        confirm = args[i + 1] if i + 1 < len(args) else None
        args = args[:i] + args[i + 2:]
    if args[:1] == ['candidates']:
        candidates()
    elif args[:1] == ['shift'] and len(args) == 5:
        shift(args[1].upper(), args[2], args[3], args[4], confirm)
    elif args[:1] == ['revert'] and len(args) == 2:
        revert(args[1], confirm)
    else:
        print(__doc__)
        sys.exit(2)
