# cb2 — Cue Book stills harvester (Cueing stream, low priority)

Read first: `_house_rules.md`, `Docs/Conductor/PLAN_CUEBOOK_EXPORT_STILLS_SURTITLES_2026-10-09.md` §2,
`Saved/CodexConductor/scene_stills.py` (whole header; segment resolution :100-120 and :640-660; markers),
`scene_stills_run.py`, `Tools/CueBook/site/index.html` (the `STILLS` table and `renderHero`).

Gary, 9 Oct: "Make a still of each Passage, Scene, Transition etc for the Cue app's visual ref. … grab a visual for
each actual cue where available."

## Build (offline)

1. **`Tools/CueBook/segment_map.json`** + loader: Cue Book segment name → Show segment key. Rules: `Passage <n>` →
   `P0<n>`, `Scene <n>…` / `S<n> …` → `S<n>`, the n-th `Transition` → `I<n>` (order proven in
   `SCENE_EXIT_SHADOW_CURTAIN_PLAN_2026-10-07.md`:54), `Curtain opening…` → `Opening`, `Ending` → closing segment,
   explicit overrides in the JSON win. Unmapped names are reported, never guessed.
2. **`Saved/CodexCueing/cuebook_stills_driver.py`** (run later by Conductor 5 inside a PIE it started; you do NOT run
   it): reuses `scene_stills.py`'s capture route and gates by import, never by copy-paste; one still per mapped
   segment at `fraction` (args; default 0.5, Transitions 0.3), plus one per cue with an `at` time (from the latest
   `Docs/CueSheet/pulls/cuebook_*.json`), capped by `max_cue_stills` (args, default 60). Same safety as
   scene_stills (refuses without PIE, census before == after, never saves/ends PIE). Markers
   `CUEBOOK_STILLS_OK|run=..|segments=..|cues=..|dir=..`.
3. **`Tools/CueBook/publish_stills.py`** (offline): run dir → 1280-px JPEG (quality 82) into
   `Tools/CueBook/site/stills/<KEY>.jpg` and `stills/cue/<CUEKEY>.jpg`, plus `site/stills.json`
   `{segments: {KEY: {file, unreal_id, master_frame, captured}}, cues: {R0042: {...}}}`. Never deletes an existing
   still; replaced files are moved to `Backups/PreCueBookStills-<run>/`.
4. **Page change (small, coordinate with cb3 if both run):** `index.html` loads `stills.json` (fallback: today's
   table), maps segments via the same names as `segment_map.json` (ship it as `site/segment_map.json`), and shows a
   cue's own still as a thumbnail in the cue card when present.

## Harness

Mapping table incl. the current 19 segment names in `Docs/CueSheet/working.csv` (expect every one mapped or
explicitly reported); NEGATIVE: an unknown name is reported, not mapped; publish on a fake run dir (sizes, manifest
read-back, no deletes, backup made on replace); driver plan building on a fake transport (segment spans, fractions,
cue `at` → master frame, cap).

## Do not

Run Unreal, MCP, PIE; touch scene_stills.py itself (Conductor's tool; propose changes as a diff in your report).
