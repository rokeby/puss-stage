# P54 — Printable cue lists / PDF (Cueing stream; offline, medium effort)

Read first: `_house_rules.md`; `Tools/CueBook/README.md`; `Tools/CueBook/site/index.html` (P48's "Running order" view
is the base); `Tools/CueSheet/cue_sync.py` (`render`, segments, `WEB_FIELDS`); `Tools/CueBook/test/` (browser mock +
`--browser-harness`, extend it).

Gary, 9 Oct: "a formatted output that we can print on paper that doesn't take up too much space for the stage manager
and everyone really to look at. export as pdf (full, klara's, gary's lighting etc)".

## Build

1. **Page print view** (Cue Book, GitHub Pages: the browser's print dialog works there, so "Save as PDF" is the PDF):
   a "Print…" button opens a small panel: preset = Full / Stage manager / Klara / Gary / Cameron / Lighting / Sound,
   optional segment range (from–to), then "Print". Presets choose which fields show per cue:
   Full = everything; Stage manager = cue number, segment, light, sound tech, sound cue, video cue, action, GO,
   PAUSE POSSIBLE, notes (lines shortened to ~60 chars); Klara/Gary/Cameron = that person's lines in full plus the
   one-line context of the cue before (who speaks), segment headings, and their own GO/action notes; Lighting = light
   + video cue + GO; Sound = sound tech + sound cue + GO + pause points. Cues with nothing for the preset are hidden
   (Stage manager and Full hide nothing). Cut cues hidden unless "include cut".
   `@media print`: A4 portrait, ~9–10 pt, two columns for line-light presets where it reads well, segment headings
   never orphaned (`break-after: avoid`), cue blocks never split (`break-inside: avoid`), black on white regardless of
   the dark theme, no header buttons/rail/bars, a footer line "Puss cue list · <preset> · printed <date> · page n".
   The screen preview of the print view must also work at 375 px.
2. **Offline print from the project:** `python Tools/CueSheet/cue_sync.py print <preset> [--from SEG --to SEG]` writes
   `Docs/CueSheet/print/PussCueList_<preset>_<date>.html` from `working.csv` using the SAME preset definitions (one
   shared JSON `Tools/CueBook/site/print_presets.json`, loaded by the page and by cue_sync). Open in a browser → Save as
   PDF. No new Python dependencies.

## Harness

Python: each preset's field selection and hiding rules on a small fixture (positive) and a preset that would show a
field it must not (negative); HTML is well-formed and byte-stable for the same input. Browser harness: print view
renders each preset, counts of visible cues match the Python rules for the seed, cut cues hidden by default, old
deployment still works. Report counts.

## Do not

Touch Code.gs (no server change needed), the Unreal side, or any test you don't extend. If git cannot commit
(index.lock), leave the files and list them.
