# Director & transitions — brief

For a session to be opened as **"Puss · Director"**, from the conductor, 2026-09-25.
Read `README.md`, then `Docs/Conductor/CONTAINER_WORLD_PLAN_2026-09-25.md`.

## What Gary asked for

> "review and improve the overall director system of passing from mechanism
> (e.g. curtain opening) to passage to scene to passage using sequences and
> camera handovers, it's still pretty clunky and buggy"

He rated this above the effects work he asked for in the same breath. It is the
spine of the show: 19 segments — 6 Passages, 6 Scenes, 7 SEQ blocks — and every
seam between them is a handover the audience sees.

## What I found in a read of the code

`UInfinityStageTransportController` (662 lines) plus
`MovieSceneInfinityPassageTrack.cpp`. These are **conductor findings from
reading, not from running** — confirm each before fixing.

### 1. Every handover is a hard cut. This is almost certainly "clunky."

All three camera claims call `PlayerController->SetViewTarget(Actor)`.
`SetViewTargetWithBlend` appears **nowhere in the plugin** — verified by grep
across the whole `Source/` tree. So mechanism → passage, passage → scene and
scene → passage all pop instantly, on the frame.

Call sites: `InfinityStageTransportController.cpp:494`, `:597`,
`MovieSceneInfinityPassageTrack.cpp:135`.

A theatre handover is a dissolve, a match, or a cut *chosen* to be a cut. Right
now the system cannot express any of those, because it has one behaviour. This
is the first thing to fix and probably the largest single gain.

### 2. `ClaimSegmentCamera` can silently do nothing.

It takes a segment by reference, then searches `Segments` by GUID to recover the
index the caller already had. If that search misses, `SegmentIndex` is
`INDEX_NONE`; `Segments.IsValidIndex(INDEX_NONE - 1)` is false; the function
returns having claimed no camera and logged nothing. The previous segment's
camera stays live and the show carries on looking almost right.

Pass the index in. Make a failed claim loud.

### 3. Chained `bRetainPreviousCamera` breaks.

The retain path claims `Segments[SegmentIndex - 1]` at its `EndFrame`. If that
previous segment *also* retains, nothing recurses — you claim the camera of a
segment that was itself borrowing one. Two consecutive retaining segments give a
wrong view, not an error.

### 4. A fallback silently substitutes for authored timing.

`ResolveCoveredHandoffOffset` prefers an `InfinityStage.HiddenChangeover` marked
frame in the Scene sequence, and falls back to
`CurtainEntryTransitionFrames + CurtainHoldFrames` when the sequence fails to
`LoadSynchronous` or has no marker. Both are legitimate. The problem is that a
**soft reference that fails to load** is indistinguishable from **a sequence
with no marker**, so the handoff silently happens at a different frame depending
on load state — which would present exactly as intermittent, unreproducible
timing. Log which path was taken, every time.

### 5. Two copies of "scan forward for the next WingPair".

The `OpeningReveal` path and the covered-handoff path each walk `Segments`
looking for the next `WingPair`, and neither handles not finding one — they fall
out of the loop and return, silently. Factor it out; make the miss explicit.

### 6. The tick is a patch over a missing event.

The constructor comment is honest about it: the camera claim used to happen only
on init, scrub and jump, so playing across a boundary never handed over, and a
`TG_PostUpdateWork` tick was added to watch for the crossing. It works, but
handover timing is now tied to frame rate rather than to sequence evaluation —
so it will drift under load and behave differently in PIE and in a build. The
sequence knows when it crosses a boundary; the boundary should be an event.

### 7. `TActorIterator` per handover.

The WingPair claim iterates every actor in the world to find the matching
`AInfinityStageCameraRig` — at the transition, the worst moment, in a world
that is about to gain a gridiron and a floor. Cache the rig per Passage.

## Order I would work in

1. **Blended handovers** (#1) — biggest visible gain, and it turns "cut" into a
   choice. Per-segment blend time and function, authored on the cue.
2. **Make failures loud** (#2, #4, #5) — before changing behaviour, make the
   system say when it did nothing. Half of "buggy" is probably silent no-ops.
3. **Chained retain** (#3).
4. **Boundary as event** (#6) and rig caching (#7).

## Ownership and boundaries

- **`InfinityStageTransportController.*` and `MovieSceneInfinityPassageTrack.cpp`
  are yours.** No other stream is in them.
- **Look & camera** owns `SInfinityStageCueDesk.cpp`, the camera-pilot files and
  camera write-back into the Master sequence. Coordinate through the conductor;
  do not both edit the handover.
- The **Master Level Sequence owns time and camera**; the **Show asset owns cue
  content and attachments**. Do not write camera poses into the Show — Look &
  camera established this and it corrected me.
- Builds are batched and go through the conductor. The editor must be closed,
  including any other project's — Live Coding blocks globally.
- `Backups/Pre<Thing>-YYYYMMDD-HHMM` before mutating the Show, the level or the
  Master sequence. Git covers source; it does not cover those.

## Proof

Suite baseline is moving to **49/50** with Rig & atmosphere's four new tests;
`SavedFixturePIE` is the long-standing lone failure. Never call it green.
Transport logic is testable without a render — add tests for the chained retain,
the silent-claim miss, and both handoff-resolution paths.
