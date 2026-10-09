# P48 — Cue Book: move cues + a compact running order (Cueing stream; offline)

Read first: `_house_rules.md`; `Tools/CueBook/README.md` (safety model and testing); `Tools/CueBook/apps_script/Code.gs`;
`Tools/CueBook/site/index.html`; `Tools/CueBook/test/` (the browser mock runs the REAL Code.gs; `--browser-harness`
gives an automated runner, extend it); `Tools/CueSheet/cue_sync.py` (`web_merge` uses `ord`; `cuebook_changes`).

Context: first rehearsal Tue 13 Oct. Klara and Cameron edit on phones and laptops. The page cannot reorder cues yet,
and reading the whole show in order means clicking through 19 segments.

## Build

1. **Move a cue up / down** (one step, and "move to after cue …" by key). Server action `move` in Code.gs: changes only
   that cue's `ord` (midpoint between its new neighbours; renumber nothing else), same lock / op id / base check as
   saves (base = the cue's current `ord` and its neighbours' keys, so a concurrent move becomes a conflict, not a
   shuffle), logged in `log` as field `_move` with before/after neighbours. A move that crosses a segment boundary is
   allowed but the page says which segment it lands in. Cut cues move like any other.
   Page: two small buttons on each cue's meta row (↑ ↓, keyboard-reachable, `IsFocusable` habits irrelevant here) and
   the same outbox/offline behaviour as saves.
   `cue_sync`: `web_merge` must carry page-side reordering into `working.csv` (today it inserts new cues by `after`,
   but never moves existing rows). Rule: if a cue's page order changed relative to the baseline and the working copy's
   order around it did not, move the row; if both changed, keep the working order and report it as a conflict.
   Harness positive/negative controls.
2. **Running order view:** a toggle in the header, "Running order", showing every segment and cue on one scrolling
   page, compact: segment headings, cue number/key, who speaks (first ~60 chars), department chips abbreviated,
   PAUSE POSSIBLE and GO marks. Read-only; tap a cue to jump to it in the normal view. Must work at 375 px width.
   Remembers the toggle per viewer (localStorage, wrapped in try/catch like the rest).
3. Keep every existing behaviour and test: old-deployment fallback (no `move` action on the old script → buttons
   hidden), surtitles, at/go/pause gating.

## Harness

Extend `Tools/CueSheet/test_cuebook_export.py` (reorder merge: page-only move applied; both-sides move = conflict;
NEGATIVE control: a cue edited but not moved keeps its row). Extend the browser harness: move up/down reaches the
sheet with `_move` audit; a concurrent move from another client conflicts; offline move survives reload; old
deployment hides the buttons; running order lists every cue of the seed once (count check). Report counts.

## Do not

Change the surtitle CSV format or the Unreal side. Code.gs changes need Gary's redeploy: say so. If git cannot commit
(sandbox index.lock), leave the files and list them; the Cueing stream reviews and commits.
