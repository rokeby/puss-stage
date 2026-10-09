# cb3 — Surtitles in the Cue Book (shared model with the UE surtitles branch)

Read first: `_house_rules.md`; `Docs/Conductor/PLAN_CUEBOOK_EXPORT_STILLS_SURTITLES_2026-10-09.md` §3;
`git show surtitles:Docs/Surtitles.md` and `surtitles:Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageSurtitles.cpp`
(the parser: columns, segment keys, time forms, blank-Out and clear-row rules); `Tools/CueBook/README.md`,
`Tools/CueBook/apps_script/Code.gs`, `Tools/CueBook/site/index.html`, `Tools/CueBook/test/` (the mock runs the REAL
Code.gs in a browser).

Gary, 9 Oct: "The subtitles system, built into cue desk in UE5 and also into cueing web app."

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
save a line the parser would skip (Out <= In, bad time, ff >= 25), so nothing silently disappears in UE.

## Build (offline)

1. **Code.gs:** a `surtitles` tab (same safety as `cues`: text stored as literal text, append-only `log` entries with
   `field` prefixed `sub:`, op ids, field-level conflicts). `list` returns `surtitles` too; actions `saveLine`,
   `addLine` (keys `T` + base36). Old pages must keep working against the new script, and the new page against the
   OLD deployment (no `surtitles` in the reply → the view says "Surtitles need the updated script").
2. **Page:** a "Surtitles" toggle per segment showing its lines in time order (In, Out, Speaker, Text) with add /
   edit / cut, the same outbox / drafts / conflict UI as cues; a "Make surtitle" action on a cue's spoken line
   (copies the text, Speaker = that person, In blank for the author to fill); In/Out validated with the branch's
   time forms. Segment key written as `S<n>`/`P<n>`/`I<n>` using cb2's `segment_map.json` when present, else the
   segment's label.
3. **Export:** `cue_sync.py` gains `surtitles_csv(lines) -> text` writing the branch's columns exactly, and `export`
   writes `Content/InfinityStage/CueSheet/Puss_Surtitles.csv` (cb1's command). Byte-stable output for unchanged
   input.

## Harness

Browser mock (`Tools/CueBook/test/`): add/edit/conflict/offline-reload for lines (as was done for cues, see README
"Testing"); old-deployment control. Python: CSV export round-trips through a PORT of the branch parser's column and
time rules (cite the .cpp lines you ported), NEGATIVE controls for bad times and unknown segment keys, byte-stability.

## Do not

Change the surtitles branch or its C++ (owned by the "Surtitle system for show" session); report any format gap
instead. No editor/MCP. Code.gs changes need Gary's redeploy: say so in the report.
