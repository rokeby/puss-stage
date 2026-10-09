# cb3 — Surtitles in the Cue Book (shared model with the UE surtitles branch)

Read first: `_house_rules.md`; `Docs/Conductor/PLAN_CUEBOOK_EXPORT_STILLS_SURTITLES_2026-10-09.md` §3;
`git show surtitles:Docs/Surtitles.md` and `surtitles:Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageSurtitles.cpp`
(the parser: columns, segment keys, time forms, blank-Out and clear-row rules); `Tools/CueBook/README.md`,
`Tools/CueBook/apps_script/Code.gs`, `Tools/CueBook/site/index.html`, `Tools/CueBook/test/` (the mock runs the REAL
Code.gs in a browser).

Gary, 9 Oct: "The subtitles system, built into cue desk in UE5 and also into cueing web app."

## Scope: keep it light (Gary, 9 Oct)

"The subtitle's primary role is for the section with the mountains to speak, and perhaps we can bring it in
elsewhere … if it involves any heavy effort, please don't pursue incredibly detailed subtitle control … the
surtitle is more like a time-coded subtitle on the upper end of the display than … an opera surtitle, which has a
queuing person running it all the time."
So: a plain per-segment list of time-coded lines (mostly S5) with add / edit / cut, and the export. **Not** wanted:
a "make surtitle" action on every script line, per-line styling, operator cueing, or anything beyond the fields
below. If a feature costs more than a small amount of code, leave it out and list it in the report.

## The model (do not invent another)

The surtitles branch's sheet: `Segment, In, Out, Speaker, Text, Notes`; Segment = `S<n>`/`P<n>`/`I<n>` or a cue label;
In/Out relative to the segment start; blank Out = until the next line or segment end; a row with time and no Text
clears. The Cue Book stores exactly these fields per line, plus `key`, `ord`, `version`, `cut`, `updatedBy`,
`updatedAt` like cues.

**Confirmed by the owner (Surtitle session, 9 Oct; declaration-proven from the branch's InfinityStageSurtitles.cpp,
not built or run yet):** header = first row with a cell "Segment" (case-insensitive), rows above ignored; columns by
name, any order; required In + Text; aliases In/Start, Out/End, Text/Surtitle/Line; Notes ignored. RFC-4180 via
`FInfinityCueSheet::ParseCsv`: quote any cell with commas, quotes or newlines (a quoted newline is an on-screen line
break). UTF-8 (BOM handled). Times: seconds, m:ss.s, h:mm:ss.s, hh:mm:ss:ff (ff < 25 @25 fps), no negatives.
`S<n>`/`P<n>`/`I<n>` count Scene / **WingPair** / Sequence transport segments in show order (same as `use_video`).
Skipped with INFINITY_SURTITLES_WARNING: Out <= In, unparseable In, missing segment, text with no In. Reloads ~1 s
after the file's timestamp changes, and on F5 (an export during PIE lands live). **Single writer:** the Cue Book
export is THE writer of `Puss_Surtitles.csv`; the master Sheet tab must not also export it. The page must refuse to
save a line the parser would skip, so nothing silently disappears in UE: Out <= In, a bad time, ff >= 25, **text with
no In**, and **a line with no segment** (the Cue Book always writes the segment on every exported row, so the
parser's "carry down" never applies). **But an In time with EMPTY Text is a valid "clear row"** (it ends the line
before it): the page must allow saving it, show it as "clear screen", and export it.

**Two editors, one file (Gary, 9 Oct):** "The surtitles should be editable in the cue book, but also editable in
Unreal because it's in Unreal that we'll understand the real time codes and be able to see them and move between
them." So the CSV has two writers: the Cue Book export and (later, Surtitle session C++) the Cue Desk. Make the export
a **three-way merge**, never a blind overwrite:
- every exported row carries a stable `Key` column (`T…`; confirm with the Surtitle session that its parser ignores an
  unknown column; it finds columns by name, so it should [inf]);
- each export also writes `Docs/CueSheet/surtitles_base.csv` (exactly what was exported);
- before exporting, if `Puss_Surtitles.csv` on disk differs from the base, diff it against the base by `Key` (rows
  without a Key = new rows added in Unreal): those are Unreal-side edits. Turn them into a Cue Book changes file (the
  same `kind: "changes"` route as `cue_sync tocuebook`, so the page previews and applies them with field-level
  conflicts), write NOTHING to the CSV, and stop with `CUE_SYNC_SURTITLES_UNREAL_EDITS|n=..|file=..`. After Gary
  applies that file, the next export includes them.
- Owner's amendments (Surtitle session, 9 Oct; parser cites `InfinityStageSurtitles.cpp:100, 196-200, 212-243` on
  branch `surtitles` [decl], not compiled): (1) **atomic writes**: write `Puss_Surtitles.csv.tmp` then rename over
  the real file (the runtime re-reads within ~1 s of a timestamp change); (2) write `Key` as an **empty cell, never
  missing**, so every row has the same column count; (3) never name a new column `Line`, `Start` or `End` (parser
  aliases for Text/In/Out); `Key` is safe. The Unreal writer will round-trip the raw table and edit only its cells.
- Harness: an Unreal-side time nudge comes back as a change, never lost; a row edited on both sides is a conflict;
  NEGATIVE control: an export over an un-imported Unreal edit must refuse.

## Build (offline)

1. **Code.gs:** a `surtitles` tab (same safety as `cues`: text stored as literal text, append-only `log` entries with
   `field` prefixed `sub:`, op ids, field-level conflicts). `list` returns `surtitles` too; actions `saveLine`,
   `addLine` (keys `T` + base36). Old pages must keep working against the new script, and the new page against the
   OLD deployment (no `surtitles` in the reply → the view says "Surtitles need the updated script").
2. **Page:** a "Surtitles" toggle per segment showing its lines in time order (In, Out, Speaker, Text) with add /
   edit / cut, the same outbox / drafts / conflict UI as cues (no per-script-line "make surtitle" action: out of
   scope, see above); In/Out validated with the branch's
   time forms. Segment key written as `S<n>`/`P<n>`/`I<n>` using cb2's `segment_map.json` when present, else the
   segment's label.
3. **Export:** `cue_sync.py` gains `surtitles_csv(lines) -> text` writing the branch's columns exactly, and `export`
   writes `Content/InfinityStage/CueSheet/Puss_Surtitles.csv` (cb1's command). Byte-stable output for unchanged
   input.

4. **Cue `at` / `go` fields (left over from cb1, 0e658a6).** `cue_sync` now carries `at` (segment-relative time) and
   `go` (`"<number> [HOLD|PASS]"`) per cue (`WEB_FIELDS`, `parse_cue_time`, `parse_go` in `Tools/CueSheet/cue_sync.py`),
   but `Code.gs` `FIELDS` does not list them, so the server silently drops them, and the page has no inputs. Add both
   to `Code.gs` `FIELDS` and the page editor (two small inputs: "At (time in segment)" and "GO"), validated like
   `parse_cue_time` / `parse_go`; show them on the cue card when set. Same one Gary redeploy as the surtitles tab.

## Harness

Browser mock (`Tools/CueBook/test/`): add/edit/conflict/offline-reload for lines (as was done for cues, see README
"Testing"); old-deployment control. Python: CSV export round-trips through a PORT of the branch parser's column and
time rules (cite the .cpp lines you ported), NEGATIVE controls for bad times and unknown segment keys, byte-stability.

## Do not

Change the surtitles branch or its C++ (owned by the "Surtitle system for show" session); report any format gap
instead. No editor/MCP. Code.gs changes need Gary's redeploy: say so in the report.
