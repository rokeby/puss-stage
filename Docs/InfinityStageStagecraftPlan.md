# Infinity Stage stagecraft development plan

Drafted 2026-08-17. Covers dog/timeline camera ownership, cue-anchored stage
content, wing lighting, environmental animation triggers and wing mechanism SFX.

## The one insight that unifies most of this

Props, lights, animation triggers and mechanism sounds all fail the same way:
they are placed against **world position or absolute time**, and a music change
that alters wing spacing or Passage duration silently destroys the arrangement.

So they should all be anchored to a **stable cue identity plus a relative
offset**, and be re-placed by the same materialization pass that already builds
the wings. One mechanism, four features. This is the spine of the plan.

`FInfinityWingPairCue` already carries a stable `CueGuid` and the Passage Actor
already rebuilds geometry from cue data on **Materialize Passage**. Nothing new
is needed conceptually — attachments ride the existing path.

## Phase 1 — Go1 camera ownership moves into the Show

**Assessment.** `Docs/Go1TelemetryProgress.md` records a working chain and one
hard constraint: **one socket, one owner** (UDP 9876). The component currently
lives on the Passage 1 camera actor and holds every setting. Duplicating it onto
every Passage and Scene camera cannot work — the second binder receives nothing.
The report's own open item 5 already prescribes the fix.

**Decision.** One receiver on a persistent actor; cameras become consumers;
ownership becomes authored Show data rather than a per-actor component setting.

1. Move the `Go1 Remote Receiver` to `AInfinityStageShowRoot` — one per level,
   already owns the Master player and transport, already the natural singleton.
2. Add `EInfinityCameraOwner { Timeline, Dog, DogGazeOnly }` to Passage settings
   and to the Scene cue. Authored per Passage/Scene, so the score records who
   drives the camera at each moment.
3. Camera rigs read ownership at evaluation time and ask the Show Root for stick
   values. A missing or stale receiver falls back to Timeline — the show must
   never stall because the dog is asleep.
4. Cue Desk gains a **Camera Owner** control on the selected Passage/Scene, plus
   a live global override (Force Timeline / Follow Show) for performance.
5. Cue Desk owns receiver enable, which also resolves the editor-vs-PIE socket
   clash the report lists as a known limitation: one toggle, one owner.

**Test.** Ownership switches at a Passage boundary; stale telemetry falls back
within one frame; no socket contention with the receiver enabled in editor and
PIE entered; ownership survives Master rebuild.

## Phase 2 — PIE starts at the selected cue

Today PIE always starts at frame zero and the position has to be found again.

`UInfinityStageTransportController` already has `ScrubToMasterFrame` and
`JumpToSegment`, and `InitializeTransport` already claims the segment camera at
its current frame. So this is a start-frame handoff, not new machinery: the Cue
Desk records its playhead, the Show Root consumes it on Begin Play.

Guard: only honour it when the Cue Desk Show matches the level's Show, and offer
**View > PIE Starts At Playhead** so always-from-the-top remains available for a
real run-through.

## Phase 3 — Cue-anchored stage content

`FInfinityCueAttachment` on the Wing Pair cue: attachment kind, soft actor/class
reference, transform relative to the pair's station, and a flag for whether it
rides the moving panel or stays at the station.

Materialization places attachments alongside the panels. Because the anchor is
the cue GUID and the offset is relative, re-fitting wing count or changing music
moves the attachment with its wing instead of orphaning it.

**Editing must be direct.** Artists place props by dragging in the viewport, not
by typing offsets — so reuse the proven `AInfinityStageWingEditProxy` pattern:
grab in the level, finish, and the resulting relative transform is written back
to the cue.

## Phase 4 — Wing lighting

Attachments with a light kind, plus a generator: **Add Stage Spots to Selection**
creates top-left and top-right spots per selected pair at a default relative
transform. Then move any individual light in the viewport and its *relative*
offset is what persists, so later spacing changes carry it along.

Whole-Passage edits (intensity, colour, cone) belong on Passage settings with a
per-cue override flag, matching how mechanism settings already work.

## Phase 5 — Environmental animation triggers

**Decision: do not make every environmental animation a subsequence.** Scenes
earn that structure; a mouse running past does not, and hundreds of subsequences
would bloat the Master and slow every rebuild.

Instead: an attachment kind that fires at a cue-relative distance or frame —
"when the camera passes within N cm of this pair, trigger X". Because the
trigger is anchored to the cue and expressed as camera distance, it stays
correct through retiming, and reverse/scrub can re-evaluate it deterministically
like Camera Gust already does.

Expose the trigger's progress as a Master channel only where an artist needs to
key it; keep the default lightweight.

## Phase 6 — Wing mechanism SFX

A **Wing Mechanism Sound Set**: an array of Sound assets plus selection policy
(round-robin, random with a stable per-cue seed, or by mechanism speed).
Deterministic seeding matters — the same wing must make the same sound on every
replay, or reverse and scrub will fight it.

Timing is derived, never authored twice: the existing mechanism data already
says when a pair moves, how far and how fast. Sound placement recomputes from
`CycleRateHz`, `InwardTravelCm`, phase and the Wing channels, so retiming the
music re-times the squeaks automatically.

Global on/off and per-Passage gain in Cue Desk; opt-out per cue.

## Sequencing and risk

Phases 1 and 2 are contained and well-specified — do them first and verify in a
live editor. Phase 3 is the foundation for 4, 5 and 6, so its data model deserves
review before the three consumers are built on top of it.

Highest risk: Phase 3's attachment materialization touching the same path as wing
placement. It needs the 3,000-wing scale test kept green, and attachments must
never block a materialize — a broken attachment reference should warn and skip,
exactly as a route that is too short now warns rather than silently failing.

## Deliberately deferred

Wing texture and material development for lighting realism. Blocked on Phase 4
anyway: judging materials before the lighting exists means judging them twice.
