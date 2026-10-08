"""Writes a Cue Book file (the same format as the page's own backups) from Docs/CueSheet/working.csv.

  python Tools/CueBook/seed_from_working.py <out.json>
Load it once into the EMPTY shared list from the page (Backup > Choose a backup file). The Apps Script refuses a
seed into a non-empty list, so this can never overwrite work.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'CueSheet'))
import cue_sync  # noqa: E402

_, rows = cue_sync.load_csv(cue_sync.WORKING)
cues = [cue_sync.web_doc(r, (i + 1) * 10) for i, r in enumerate(rows)]
with open(sys.argv[1], 'w', encoding='utf-8') as f:
    json.dump({'app': 'puss-cue-book', 'saved': None, 'source': 'Docs/CueSheet/working.csv', 'cues': cues}, f,
              ensure_ascii=False, indent=1)
print('CUEBOOK_SEED_FILE_OK cues=%d out=%s' % (len(cues), sys.argv[1]))
