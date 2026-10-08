# Surtitles

Gary, 8 Oct 2026: "text at centre top of screen, visible serifed font, timecoded",
"should integrate as part of cue system". The first use is the S5 mountains, who
talk to each other in rumbles that get surtitled.

This **replaces** the old plan in `ShowBuildTodo.md` §C: C.1 to C.3 (a `BP_Surtitle`
actor keyed with a Text track inside each Scene sequence) and the matching line in
`SceneDeliveryContract.md`. Scene artists no longer bind anything. They send
**timings**, and the timings go in the sheet.

## How it works

- **Where the text lives:** the surtitle sheet,
  `Content/InfinityStage/CueSheet/Puss_Surtitles.csv`. Make it a "Surtitles" tab in
  `Puss_Master_cue_sheet` and export it as CSV to that path. Nothing is written to the
  Show or the level.
- **Columns** (found by name, any order): `Segment, In, Out, Speaker, Text, Notes`.
  - **Segment:** `S<n>` (the n-th Scene), `P<n>` (the n-th Passage), `I<n>` (the n-th
    Interaction), or a Show cue label. These are counted the same way as the Cue
    Director's `use_video = S<n>`. A blank cell carries the segment down from the row above.
  - **In / Out:** time from the **start of that segment**, so a line moves when its
    segment is retimed or reordered. Write it as `74.5`, `1:14.5`, `0:01:14.5`, or
    `00:01:14:12` (the last field is frames, at 25 fps).
  - **Blank Out:** the line stays up until the next line in that segment starts, or
    until the segment ends.
  - **A clear row:** a row with a time and no Text clears the screen at that time.
  - **Line breaks:** a quoted multi-line cell keeps them.
- **Display:** the line sits at the top centre of the frame, in a serif font, on a
  black bar, with a short fade at each end. It is a viewport overlay in PIE and in the
  show. It draws over the Scene video fallbacks, which follow the same Master playhead.
  It is **not** rendered into MRQ output.
- **What's on screen depends only on the Master playhead,** so seek, reverse, hold and
  fast-forward all agree.
- **Reloading:** the sheet is re-read automatically within about 1 s of being saved.
  F5 (which also reloads the cue sheet) and `InfinityStage.Surtitles.Reload` do the
  same thing by hand.

## Operator and rehearsal controls

| Control | Effect |
| --- | --- |
| **T** (show viewport) | Blackout on/off (`InfinityStage.Surtitles` 1/0) |
| `InfinityStage.Surtitles.Size` | Text size in px of a 1920×1080 frame (default 54) |
| `InfinityStage.Surtitles.Top` | Gap above the bar, px of 1080p (default 40); safe area for the real screen |
| `InfinityStage.Surtitles.BarOpacity` | 0 to 1 (default 0.85) |
| `InfinityStage.Surtitles.Fade` | Seconds (default 0.3; 0 for hard cuts) |
| `InfinityStage.Surtitles.Speakers` | 1 shows the Speaker column, small, above the line |
| `InfinityStage.Surtitles.Font` | A TTF/OTF path |
| `InfinityStage.Surtitles.Path` | Another sheet, e.g. `Saved/Surtitles/surtitle_test_sheet.csv` |
| `InfinityStage.Surtitles.Dump` | Logs every line at its absolute Master time, for proofing |

**Font:** the default is `Content/InfinityStage/Surtitles/Fonts/Surtitle.ttf` (or
`.otf`). Until that file exists, Windows Georgia is used. Gary wants EB Garamond for
now and may choose another font later. To change it, drop the file in under that name;
no rebuild is needed. These are loose files, so a packaged build would have to stage
them. That last point is inferred: the show runs from the editor, and staging is
unverified.

## Log markers

- `INFINITY_SURTITLES_LOADED ok= lines= warnings= path=`
- `INFINITY_SURTITLES_WARNING`: one per row that was skipped or corrected
- `INFINITY_SURTITLES_STYLE font= size= top= bar= speakers=`
- `INFINITY_SURTITLE row= seg= in= out= hold= master=`: one per line, from Dump.
  `PAST_SEGMENT_END` marks a line that starts after its segment has ended.
- `INFINITY_SURTITLE_UNRESOLVED`: the segment key matches nothing
- `INFINITY_SURTITLES_ON` / `INFINITY_SURTITLES_BLACKOUT`

## Code

- `Plugins/InfinityStage/Source/InfinityStage/{Public,Private}/InfinityStageSurtitles.*`
  holds the sheet parser, the pure evaluator, and a `UTickableWorldSubsystem` that
  draws a Slate overlay at ZOrder 10 (over the video fallback at 5, under the
  rehearsal bar at 20).
- `InfinityStageShowGameMode.*` binds T, and F5 also reloads the sheet.
- The tests are `InfinityStage.Surtitles.*` in `InfinityStageSurtitleTests.cpp`.
