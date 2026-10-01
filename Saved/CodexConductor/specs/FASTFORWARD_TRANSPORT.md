# Hold RIGHT to fast-forward (Conductor 3, 1 Oct) — Gary: "a version of transport using right
# button that holds down to fastforward through the movement, rather than skips to next part,
# since it means I can see transitions."

Owner: none (InfinityStageTransportController is unowned). Deliverable: a HELD PATCH for the next
build window, plus an automation test, in your worktree. Read the controller (.h/.cpp), its key
bindings and the performance interlock first (memory: Right/Left/Space ARE bound; result=4 =
interlock refused). Read Docs/Conductor/RUNTHROUGH_NOTES_2026-09-30.md around line 52.
Behaviour:
- TAP Right (released < HoldThresholdSeconds, default 0.30, editable): unchanged — today's advance.
- HOLD Right: from the threshold on, play forward at FastForwardRate (default 4.0, editable;
  consider ramping 1→rate over 0.5 s) THROUGH passages, cuts and scenes as continuous playback,
  never skipping; release returns to 1.0 and leaves the transport PLAYING if it was, else held
  where it is. Must respect the performance interlock exactly as advance does.
- Must not change Left/Space. Must not alter authored timing. Audio: state what happens (mute or
  pitch) and choose the least surprising; say which.
- Test: new file, InfinityStage.Transport.HoldRightFastForwards — pure/fixture logic: tap → old
  advance path; hold → rate applied after threshold; release → rate 1.0; interlock refusal honoured.
- Patch file: Scripts/patches/2026-10-01_FF_hold_right_fast_forward.patch (git diff of the
  worktree vs HEAD), plus a short note of every inference (engine .cpp not shipped).
Do NOT build. Do NOT touch the editor. Final message: the diff summary, the test, every
inference tagged.
