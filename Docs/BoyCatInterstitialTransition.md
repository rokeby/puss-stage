# Boy–cat interstitial transition contract

**Status:** approved performance behavior, engineered for implementation on
27 August 2026. This document is normative for the five post-Scene boy–cat
interstitials. It describes required behavior; it does **not** claim that the
current C++ or production Show asset already implements or verifies it.

## Decision

Each interstitial lowers the curtain over the final shot of the Scene that has
just ended. The boy–cat shadow interaction plays behind the closed curtain. A
hidden handoff then primes and selects the **next Passage**, while the curtain
is still fully closed. The curtain lifts onto that new Passage held at its
opening pose.

The completed reveal is a performance hold. The Passage must not move
automatically. A separate operator **GO**, which can be taken from the performed
“and Puss walked on” beat, starts the Passage and its authored ease into motion.
The line is a human cueing opportunity, not a time-coded automatic trigger.

In short:

`previous Scene final shot → close → interaction → covered handoff → reveal next Passage static → READY hold → manual GO → next Passage moves`

## Cue spine

There are five interstitials and no sixth interstitial after the Void:

| Cue | Position | Boy–cat action | Reveal / manual GO destination |
| --- | --- | --- | --- |
| I1 — Washing the boy | S1 Animals → P2 | Rejection/whimper; Puss washes the boy clean; response | P2 opening pose |
| I2 — Turnips | S2 Shrine → P3 | Turnips received/eaten; food runs out; father remembered/cursed; whimper; response | P3 opening pose |
| I3 — Forgets his name | S3 Shore → P4 | Song of Forgetting; father then own name forgotten; gagging/nasal whimper; response | P4 opening pose |
| I4 — Gets a name | S4 Children → P5 | Puss presents the stolen page/name “Cagliuso”; recognition; whimper; response | P5 opening pose |
| I5 — Becomes King | S5 Mountains → P6 | Crown/declaration; boy becomes King; trace/sound of the crushed village; whimper; response | P6 opening pose |

The main Scene establishes or acquires the resource; the interstitial applies
it to the Boy and shows the consequence. Script editorial may move an
individual story beat, but it must not change the transition machine without a
new explicit decision.

## Performance states

| State | Curtain | Camera | Next Passage evaluation | Advance |
| --- | --- | --- | --- | --- |
| 1. Incoming final shot | Open | Previous Scene final designed shot | Not selected | Scene reaches boundary and pauses |
| 2. Closing | 0 → 1 | Previous Scene final shot retained | Not selected | Operator GO runs the interstitial |
| 3. Interaction | Fully closed | Previous Scene camera retained | Not selected | Shadow play, surtitles and audio run |
| 4. Covered handoff guard | Fully closed | Switch to next Passage camera | Prime exactly at next Passage start frame | Automatic inside interstitial |
| 5. Reveal | 1 → 0 | Next Passage camera | Held at opening pose / local frame 0 | Automatic inside interstitial |
| 6. `READY — GO Pn` | Fully open | Next Passage camera | Master paused exactly at Passage start | Indefinite performance hold |
| 7. Passage running | Open / curtain inactive | Next Passage camera | Passage time advances from frame 0 | Separate operator GO |

Curtain progress is `0 = open`, `1 = closed`.

“Held at opening pose” means that camera/route travel and all Master-time-driven
mechanisms are evaluated at the Passage start frame and do not advance. An
intentionally ambient idle animation may continue only if that is an authored
creative choice; it must not move the Passage or the travel camera.

## Exact frame contract

For an interstitial segment with start frame `S`:

- `C` = `CurtainEntryTransitionFrames`, the closing duration.
- `H` = `CurtainHoldFrames`, the total fully-closed duration.
- `G` = `CoveredHandoffGuardFrames`, the final fully-closed portion after the
  camera switch and before the lift.
- `O` = `CurtainExitTransitionFrames`, the lift duration.
- `R = S + C + H`, the first lift frame.
- `K = R - G`, the covered camera-handoff frame.
- `E = R + O`, the interstitial end and exact next-Passage start frame.

Required intervals:

| Master interval | Curtain | Effective camera | Passage evaluation |
| --- | --- | --- | --- |
| `[S, S+C)` | Closing | Previous Scene | No next-Passage advance |
| `[S+C, K)` | Closed interaction | Previous Scene | No next-Passage advance |
| `[K, R)` | Closed guard | Next Passage | Evaluate and hold at next Passage `StartFrame` |
| `[R, E)` | Lifting | Next Passage | Continue holding at next Passage `StartFrame` |
| `E` until GO | Open | Next Passage | Master paused at `E`, which is Passage local frame 0 |
| After GO | Open | Next Passage | Master advances normally from `E` |

Constraints:

- `C >= 0`, `H > 0`, `O > 0`.
- `0 < G <= H`.
- Default `G`: 0.10 seconds in Master ticks, with a minimum of two display
  frames. It is a safety guard, not a perceptible dramatic hold.
- The interstitial duration must equal `C + H + O`; there is no finite
  post-reveal duration. The indefinite post-reveal hold comes from transport
  pausing at `E`.
- `E` must equal the following Passage segment’s `StartFrame` exactly.
- At `K`, the curtain is exactly closed before the view target changes.
- At every frame in `[R, E)`, the active camera is the next Passage camera and
  its evaluated time is its own `StartFrame`.

Recommended starting values are 2.0 seconds closing, an interaction-length
closed hold, a 0.10 second covered handoff guard inside that hold, and 2.0
seconds lifting. Final timing is authored per interaction after audio is locked.

## Operator semantics

The normal performance path uses two distinct GO operations:

1. At the previous Scene boundary, **GO INTERACTION** runs the complete
   interstitial through its closing, interaction, handoff and reveal.
2. The transport stops at the next Passage start and reports
   **`READY — GO Pn`**. **GO PASSAGE**, taken manually at the desired performed
   beat, starts its authored ease into travel.

There is no automatic timeout in the READY state. Waiting five frames, five
seconds or five minutes must produce the same image and the same subsequent
first movement frame.

`Play Through Boundaries` must not defeat this contract. A
`PostSceneInterstitial` end is a protected manual-stop boundary; play-through
may cross ordinary boundaries but must stop at the next protected boundary.

The Passage ease belongs to the Passage’s authored movement channels. The
operator GO starts normal timeline evaluation; transport must not add a second
speed ramp or camera blend.

## Show-data contract

- Author I1–I5 as `Scene` cues. `Sequence` currently has no distinct runtime
  behavior and must not be used as a second spelling for an interaction.
- Set `CurtainMode = PostSceneInterstitial`.
- Set `bUseSequenceLength = true` after each interaction sequence has a locked
  playback range.
- A post-Scene interstitial must be followed immediately by a `WingPair`
  Passage segment. The compiler must reject any other adjacency.
- The mode itself implies “incoming camera until covered, then outgoing Passage
  camera.” This behavior must not depend on an author remembering a second
  boolean flag.
- `bRetainPreviousCamera` is provisional and too broad: it currently retains
  the previous camera for the whole segment. Preserve it for asset migration,
  but replace its runtime meaning for `PostSceneInterstitial` with the phased
  contract in this document. Prefer a later rename to
  `bRetainIncomingCameraUntilCovered` if the field remains author-facing.
- Add `CoveredHandoffGuardFrames` to the interstitial data, stored in Master
  tick frames and displayed in seconds/display frames in the Cue Desk.
- `LS_Interaction_Template` owns shadow play, surtitles and audio, but no Camera
  Cut track. Effective camera selection belongs to the transport phase resolver.
- The interaction visual must finish before `K`. Audio may tail under the lift
  only when deliberately authored.

## Runtime implementation map

### 1. Compile the transition metadata

The compiled/transport segment needs the curtain mode and timings, plus a
derived `bRequiresManualGoAtEnd` for `PostSceneInterstitial`. During compile or
transport initialization:

- resolve the previous segment and next segment indices;
- prove the next segment is a ready Passage;
- compute `K`, `R` and `E` from the authoritative Master tick resolution;
- validate duration, adjacency and guard constraints;
- expose an actionable validation error rather than silently falling back to
  the previous camera.

### 2. Resolve effective camera by frame

Replace whole-segment camera retention with a pure resolver such as:

`ResolveEffectiveCameraSegmentIndex(InterstitialIndex, MasterFrame)`

For `PostSceneInterstitial`, it returns the previous segment before `K` and the
next Passage at or after `K`. Other cue modes retain their existing ownership
rules.

`UInfinityStageTransportController::TickComponent` currently returns early when
the segment index has not changed. It must also detect a change in the resolved
effective-camera segment inside an interstitial. Cache the last claimed camera
identity only to avoid redundant work; frame plus Show data remains the source
of truth.

Jumps, initialization, scrubs and reverse playback must call the same resolver.
Do not implement `K` as a one-shot event, because events are not reliable under
direct seek or reverse.

### 3. Prime the outgoing Passage

On first resolving to the outgoing Passage, and on any direct seek into
`[K, E)`, locate its `AInfinityStageCameraRig` by Passage GUID and call
`EvaluateAtMasterFrame(NextSegment.StartFrame)` before claiming its view target.
That existing method evaluates the camera and Passage mechanisms at a legal
frame without advancing the Master playhead.

Continue presenting that same opening pose throughout `[K, E)`. Do not pass the
interstitial’s current Master frame into the outgoing Passage, because it lies
before the Passage’s compiled range.

### 4. Stop at the ready boundary

`PlayForwardToBoundary` already targets the selected segment end. At `E`, the
half-open segment lookup must select the next Passage and the player must be
paused exactly on its start frame. The next GO uses the existing forward command
to begin that Passage.

Change `PlayForwardThroughBoundaries` to target the nearest upcoming segment
whose compiled `bRequiresManualGoAtEnd` is true, instead of always targeting the
end of the Show.

If the next Passage becomes not-ready at runtime, pause at `K` with the curtain
closed, retain a safe covered image, and report `NEXT PASSAGE NOT READY`. Do not
lift onto an unprimed or missing camera.

### 5. Operator feedback

The Cue Desk and performance HUD must distinguish:

- `INTERACTION RUNNING`;
- `HANDOFF COVERED` (diagnostic/rehearsal display is sufficient);
- `REVEALING Pn`;
- `READY — GO Pn`;
- `Pn RUNNING`.

At READY, the next-cue label is the Passage that will move, not the completed
interstitial. GO remains the ordinary performance forward command; no special
interaction-only button is required.

## Scrub, reverse and recovery

- Direct seek to any frame must reconstruct curtain progress, effective camera
  and primed Passage pose from that frame alone.
- Reverse from the next Passage into `[R, E)` shows the next Passage while the
  curtain closes in reverse.
- Crossing `K` in reverse changes back to the previous Scene camera only while
  the curtain is fully closed.
- Jumping to the interstitial start shows the previous Scene final shot with the
  curtain open.
- Jumping to `E` shows the new Passage at frame 0, curtain open, transport
  paused and READY.
- Restart-from-last-curtain should land either at `S` for the full interaction
  or at `E` for a clean Passage GO; the HUD must name which restart target was
  selected.

## Acceptance tests

Add a focused native automation fixture with
`Scene → PostSceneInterstitial → Passage` and assert:

1. At `S`, curtain progress is 0 and the previous Scene camera owns the view.
2. At `S+C`, curtain progress is 1 and the previous Scene camera is retained.
3. At `K-1`, the previous Scene camera still owns the view.
4. At `K`, curtain progress is exactly 1, the next Passage camera owns the view,
   and its camera/mechanisms have been evaluated at the Passage start frame.
5. At `R-1`, the curtain remains exactly closed on the next Passage camera.
6. Halfway through `[R, E)`, curtain progress is 0.5, the next Passage camera
   owns the view, and Passage evaluation is still its start frame.
7. At `E`, curtain progress is 0/inactive, selected segment is the next Passage,
   the Master is paused, and current frame equals its `StartFrame`.
8. Wall-clock waiting at `E` does not change the Master frame, camera transform,
   route distance or time-driven mechanisms.
9. Manual GO at `E` advances from Passage local frame 0 and uses the Passage’s
   authored ease without a transport-added blend.
10. `Play Through Boundaries` still stops at `E`.
11. Direct seek into every phase produces the same state as sequential play.
12. Reverse crossing switches cameras only during full cover.
13. Missing/non-Passage adjacency fails validation; runtime not-ready pauses at
    `K` and does not reveal.
14. The production Show compiles I1–I5 as five `Scene` interstitials in the
    19-cue spine, and a narrow save/readback proves their timing and adjacency.

The current provisional test that expects “curtain lifts before the next
Passage” is incomplete. Its lift assertion must also prove that the **next**
Passage camera owns the view and is held at its opening evaluation.

## Implementation completion gate

This contract is complete only when all of the following are true:

- clean editor-closed C++ build;
- focused transition fixture green;
- full InfinityStage automation suite green, with any unrelated failure named;
- production Show updated through a timestamped backup and narrow save;
- post-save readback proves all five cue types, timings, modes and adjacency;
- PIE rehearsal demonstrates the separate reveal and Passage GO;
- reverse, seek, hold and not-ready recovery are exercised on the show machine.

