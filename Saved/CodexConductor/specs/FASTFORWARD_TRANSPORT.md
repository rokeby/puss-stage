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

## Revision 2 — add the Scene 3 VAMP to the same patch (after the fast-forward draft)
Read Saved/CodexRuns/live_hold_investigation.log (its design, file:line) and the "SONG VAMP" entry in
Docs/Scene3BeatSheet_2026-10-01.md. Implement marker pairs `InfinityStage.VampStart` / `InfinityStage.VampEnd`
collected in BuildSegments like HiddenChangeover (child→Show ticks, + segment start). Playing forward at 1×,
reaching VampEnd jumps back to VampStart seamlessly (same frame cadence, no hitch, no camera re-claim) until
the operator presses RIGHT; RIGHT inside a vamp = "release": play on through VampEnd at 1× (don't skip a
segment). Scrubs/jumps never arm a vamp; rewinding re-arms. A vamp outranks hold-RIGHT fast-forward (which
Scene 3 refuses anyway: DeclaredUnpausable). It must not call PauseTransport (the interlock stays intact).
State what audio does at the loop seam (Scene 3 has no Master music; the singer is live). Test (new file):
InfinityStage.Transport.VampLoopsUntilRelease — fixture with a vamp pair: loops N times, RIGHT releases,
scrub doesn't arm, rewind re-arms. Same patch file, same rules, every inference tagged.
