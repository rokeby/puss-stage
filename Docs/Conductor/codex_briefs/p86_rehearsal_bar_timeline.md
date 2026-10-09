# Job 86 — Rehearsal bar as a timeline: script stepping moves the playhead, bigger scrubber, markers, big Play, 8x FF
(Cueing stream; offline; HELD C++ patch; medium effort)

Read first: `_house_rules.md`; `Plugins/InfinityStage/Source/InfinityStage/{Public,Private}/InfinityStageRehearsalBar.*`,
`InfinityStageCueSheet.*`, `InfinityStageShowGameMode.*` (keys: `InfinityStageShowKeys`, `NextScriptLine`,
`PreviousScriptLine`, `BeginRightInput`/`HoldRightState`), `InfinityStageTransportController.h` (`FastForwardRate`,
`BeginFastForward`, `ScrubToMasterFrame`, `FInfinityHoldRightState`, `Segments[].StartFrame/EndFrame`),
`InfinityStageSurtitles.h` (lines with In/Out, existing next/prev scrub at :179), `InfinityStageDirectorHud.cpp`,
`InfinityStageTests/Private/InfinityStageRehearsalTests.cpp`; `Tools/CueSheet/cue_sync.py` (`render`: the `At`
column in `Content/InfinityStage/CueSheet/Puss_Master_cue_sheet.csv`; At format and its validation at ~:249).

Gary, 9 Oct ~21:45 (via Conductor 5), five asks:
1. "," / "." script stepping also moves the timeline: when the stepped-to row has an At time, scrub the playhead
   there (ScrubToMasterFrame, i.e. pauses, like surtitle stepping); untimed rows move the script pointer only (today's
   behaviour). FInfinityCueSheetRow has NO time today: parse the `At` column by header name (absent column = no time,
   no warning). At is relative to the row's segment start unless cue_sync says otherwise — READ cue_sync and the Cue
   Book At hint, cite the line, and mark the interpretation proven/inferred.
2. The bar SCRUBS by dragging the playhead (a slider exists, `InfinityStageRehearsalBar.cpp:412-418`, current segment
   only; keep its one-clock rule and the Scene 3 lock note).
3. Bigger bar and a bigger playhead/scrubber, "a bit like a sequencer view": a timeline strip for the current segment
   with ticks for script rows that have At times, surtitle lines (In..Out spans), and GO markers if cheap (say if you
   skip them). Readable at the existing HUD scale; no new fonts/assets.
4. A big PLAY/PAUSE button at the right-hand end of the strip (the existing small "> Play" at :352 can go or stay —
   one action path, Space unchanged).
5. Right key: fast-forward as now; after holding 5 s continuously it goes to 8x (FastForwardRate stays the 4x start;
   add a separate knob, e.g. `LongHoldFastForwardRate = 8`, `LongHoldSeconds = 5`). Release behaves exactly as today.
   Left hold unchanged.

## Rules
- Dedupe first: grep for any existing timeline strip, marker drawing, long-hold rate; report what you found (or
  "searched X, found nothing").
- C++ only as a HELD patch: `Scripts/patches/cueing_P86_rehearsal_bar_timeline.patch` against current master, made
  with explicit paths (never bare `git diff`). Do not build; do not touch other held patches. Unity build: helper names
  in anonymous namespaces must be unique. Tests module lacks InputCore (use the FName helpers).
- Do not touch the GO1, Go1Input or go1_pi_bridge. No Unreal editor runs. No Show/level writes.
- Tests per item (named `InfinityStage.Rehearsal.P86.*`): At parsing incl. absent column and bad values; step lands on
  the right frame / untimed step leaves the frame; drag maps fraction→frame (pure helper); marker layout from rows and
  surtitles (pure helper); 8x after 5 s and back on release (drive the hold state machine with fake time).
- Report: files, test names, what is proven vs inferred per claim (house tiers), and an estimated build-window length.
