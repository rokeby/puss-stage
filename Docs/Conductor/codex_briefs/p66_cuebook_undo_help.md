# P66 — Cue Book: Undo + plain-language help for At / GO (Cueing stream; offline, medium effort)

Read first: `_house_rules.md`; `Tools/CueBook/README.md`; `Tools/CueBook/site/index.html` (outbox, drafts, conflicts,
moves, cut); `Tools/CueBook/apps_script/Code.gs` (save / add / move / cut, op ids, base checks, `log`);
`Tools/CueBook/test/` (browser mock runs the REAL Code.gs; extend `--browser-harness`). Dedupe done: no undo exists.

Gary, 9 Oct: (1) undo for cue changes, "a button will do", plus Ctrl/Cmd+Z where it doesn't clash with typing;
(2) the At and GO fields confuse a new user: tooltips / help / clearer placeholders, plain language, real semantics.

## 1. Undo (page only if possible; Code.gs only if truly needed — a redeploy costs Gary a step)

- An "Undo" button in the header (and Ctrl/Cmd+Z when focus is NOT in an input/textarea/select/contenteditable)
  undoes THIS viewer's most recent change: a field save, a move, an add (→ mark the added cue as cut, never delete),
  a cut/restore (→ the opposite), a surtitle line save/add/cut. Keep a per-viewer undo stack in localStorage (try/catch),
  recording for each change exactly what the existing save path needs to reverse it (patch + base = the values the
  change wrote). Several steps of undo; the button shows what it will undo ("Undo: Light on R0042").
- An undo is just another normal change through the existing queue: new op id, `base` = the values the change wrote,
  so if someone else changed that field since, the server returns the usual conflict and the page shows both versions
  (never a silent overwrite). Works offline (queued like any edit). Logged in `log` like any edit (who = the viewer).
- An undo of an undo is a redo only if trivial; otherwise leave it out.

## 2. Help text for At / GO (use the real semantics; cite where you got them)

- **At** = time from the START of this cue's segment (Passage / Scene / Interaction), not show (Master) time; it
  follows the segment if the show is retimed. Formats: `74.5`, `1:14.5`, `0:01:14.5`, `00:01:14:12` (last field =
  frames at 25 fps). Optional: most cues have no fixed time (the show runs by its order and the music). Needed for a GO.
  Sources: `Tools/CueSheet/cue_sync.py` `parse_cue_time`; `Docs/Conductor/PLAN_CUEBOOK_EXPORT_STILLS_SURTITLES_2026-10-09.md`.
- **GO** = a cue number Klara presses GO on, plus optional mode: `HOLD` = the show stops there until GO is pressed;
  `PASS` = it doesn't stop (just marks the point); `BREATH` = notes an authored breath (documentation only, the show
  never stops for it). Examples `20 HOLD`, `21 PASS`, `22 BREATH`. Sources: `InfinityStageTransportController.cpp`
  `ParseMarkerLabel`; `Tools/CueBook/unreal/go_markers_sync.py` (BREATH skipped); `Docs/Conductor/P47_BREATH_NOTES.md`.
- **Pause possible** = an ambience moment where a breath could go.
- Show this as a one-line hint under each field (always visible, small), a `title` tooltip, `aria-describedby`, and a
  "?" toggle with the longer explanation; placeholders become real examples. Plain language; no "segment-relative".

## Harness

Browser harness: undo of a field save restores the old value with a `log` entry; undo of a move/add/cut; undo when
someone changed the field since → conflict shown, nothing overwritten (negative control); offline undo survives reload;
Ctrl+Z inside a textarea does NOT trigger page undo (negative control); hints present for At/GO/pause (aria-describedby
resolves). 375 px: no horizontal scroll with hints open. Keep every existing test passing (export, selftest, stills,
breath, browser harness). If git cannot commit (index.lock), leave the files and list them.
