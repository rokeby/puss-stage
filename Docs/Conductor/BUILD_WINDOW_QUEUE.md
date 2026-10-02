> **2 Oct ~02:20 (Conductor 4): HELD `Scripts/patches/2026-10-02_SS_scene_shot_step.patch`** (Codex draft, reviewed,
> `git apply --check` clean on 52ac17b, UNBUILT). Gary's rulings: in a Scene, tap RIGHT/LEFT step root camera-cut
> starts (LEFT restarts the shot within 12 display frames' grace, else previous); past the ends they fall through to
> today's cue Advance/Previous; play state kept; hold RIGHT unchanged; vamp release stays first. Also adds IsActive to
> FindSceneCameraCut (the planned "retired ClamCam1 hole" 2-line fix). Tests: ShotStepNextAndPrevious,
> ShotStepEngagesVampAtStart, ShotStepOutsideSceneUnchanged (names UTF-8; run each alone first, then the suite).
> **LANDED SAVE: Gary 2 Oct ~02:15, his words: "proceed ... including letting the hangars be available fully up in
> editor mode so I can arrange the lighting and scenes".** So the save goes ahead although the PIE gate found S2 (and
> possibly S4/S5/S6) not rising: HL sinks every hangar at BeginPlay regardless (all six INFINITY_HANGAR_INITIAL_POSE
> lines, 2 Oct 05:38:52 UTC), so PIE is unchanged by the save (inferred). Those rises still need their Scenes lengthened.

> **1 Oct ~22:40: WINDOW RUN, BUILT 467d2c8 (FFV + HL), suite 106/0/106** — HoldRightFastForwards,
> VampLoopsUntilRelease, Arrival.GameWorldStartsAtFirstHangarKeys passed; markers UTF-8 test names + UTF-16
> runtime literals with +/- controls (first attempt 222729 rolled back on a UTF-16 test-name search — wrong
> encoding, see memory puss-dll-marker-encoding). Warning lines 36 (baseline ~29; not failures). NOTHING HELD.
> **Still to do (Gary present):** PIE: every hangar starts sunk and rises as before (level still saved sunk);
> then raise all + save the level LANDED; PIE again; retire/invert the landed-preview save-check.

> **1 Oct ~21:15 (Conductor 3): TWO HELD PATCHES, checked to apply on HEAD TOGETHER (--ignore-whitespace):**
> 1. **FFV** `Scripts/patches/2026-10-01_FFV_fast_forward_and_vamp.patch` (supersedes FF): hold RIGHT = 4x
>    fast-forward (tap unchanged, interlock kept, Master audio muted at 4x); `InfinityStage.VampStart/VampEnd`
>    marker pairs loop until RIGHT (Scene 3 song vamp, Docs/Scene3BeatSheet_2026-10-01.md). Tests
>    `InfinityStage.Transport.HoldRightFastForwards`, `...VampLoopsUntilRelease`. Codex draft, unbuilt.
> 2. **HL** `Scripts/patches/2026-10-01_HL_hangars_landed_in_editor.patch`: AInfinityStageArrival sets each
>    hangar's root/roof/lattice to their rise FIRST keys at BeginPlay in GAME worlds only; editor untouched.
>    Test `InfinityStageHangarInitialPoseTests`. Six Arrivals S1-S6 exist (binary-proven, level strings).
>    **ORDER AFTER THE BUILD (do not skip):** suite green -> PIE check that every hangar starts SUNK with the
>    level still saved sunk -> ONLY THEN raise all (s3_landed_preview UP all) and save the level LANDED ->
>    PIE again: every hangar must still start sunk and rise as before -> retire/invert the save-check
>    (it refuses saves while up, which becomes the desired state).
>    BeginPlay ordering vs ShowRoot is INFERRED safe (initial transport evaluation re-asserts the root).

# Next build window — what is in it, and in what order

> **1 Oct: EDITOR (import, no build) requested by Flat V3 ("Puss - Wings and
> Textures").** Pilot pair import under `/Game/Scenes/Wings/FlatV3/Pilot/`, new
> names only, plus later the S3 backdrop MI and wave rows. Not ready until the
> FBX passes clean re-import. Status: `Docs/FlatV3Status.md`.
>
> **1 Oct ~11:20: WINDOW RUN.** Built and committed `35094de`: C v2 and S v2. Suite
> **102/0/102**. **U (82e36b7) was reverted:** its own test `KindsUseCachedPivotsAndAxes`
> failed ("Topple Top instance exists" is null). It's back with Rig. **Nothing else is held.**
> A second try (8559f2c) failed at :1444, the mirrored θ=0 comparison. **U is now 8046114**, held: the test
> compares matrices, since a mirrored FTransform round-trips via FMatrix with a different decomposition
> (Rig). Run `InfinityStage.Mechanism.KindsUseCachedPivotsAndAxes` FIRST, then the suite.
>
> **30 Sep ~19:45: WINDOW RUN.** Built and committed `cc1331e`: K, L v2, MR (replaces
> M and R), N v2, O v2, P v2, Q v2, T. Suite **99/0/99**. **Still held for the NEXT
> window:** C (didn't compile: `TNumericLimits<float>::QuietNaN` is absent in 5.8) and S
> (Codex P1: resettle after the camera reclaim). The table below is history, except for
> those two.

The build gate is **machine-wide**: any open UE editor in any project blocks any
build. The editor is currently held by the landscape block, so this waits.

Gary set the review cadence on 30 Sep: **the adversarial Codex review runs once
per build window**, not ad hoc.

## BUILD IT IN TWO STAGES — the tests' redness is INFERRED, not measured

**Nothing in this queue has compiled.** "Every test is red without its patch" is
read from the code — the clamp, the `SetRange`-only rebuild — and it is
**inferred**. Each new test lives in its own new file, separate from its fix, so
proving it costs one extra compile:

1. **Build with ONLY the three new test files** (`InfinityStagePassageKeyCarryTests.cpp`,
   `InfinityStageHandoffGapTests.cpp`). Run `PassageKeysFollowSection`,
   `RetainedExitLeavesNoGap` and `ExitHoldSurvivesLengthening`. **Expect red.**
2. **Apply the fix hunks, rebuild, run again. Expect green.**

**The exact commands are in `Scripts/patches/2026-09-30_KL_STAGING.md`, and no
split patches are needed:** `git apply --include=` takes only the two test files
for stage 1, `--exclude=` takes only the two fixes for stage 2. Both stages are
verified to pass `git apply --check` on HEAD and to select exactly their two
files. C touches neither, so it rides in either stage.

**That note also pre-registers WHICH ASSERTIONS should be red in stage 1** — K's
"key N stays at the same section-relative frame", L's "cuts cover the whole
Scene" and "Exit starts where the designed shot ends", and the hold test's "still
a 24000-frame hold at the new end". **The other assertions in each test should
PASS.** That is what closes the last gap: a fixture fault would show up as the
*wrong* assertions failing, which a bare red/green could not distinguish.

**The reading table:** K still red after stage 2, on the same assertions →
`MoveSection` does not carry keys, and the fix becomes a per-channel offset. **Any
stage-1 red elsewhere, or a stage-1 GREEN, means fix the test before trusting
anything.**

**This is not optional for K.** K's test is the **measurement of an inference
nobody here can read** — that `MoveSection` carries its keys, taken from a doc
comment because the engine `.cpp` is not shipped. **If K's test is red after
applying K, that result is uninterpretable without stage 1**: it means either
"the engine does not behave as documented" or "the test is broken", and those
have completely different consequences. Stage 1 separates them.

**And it guards the exact fault class that cost the morning of 30 Sep.** All six
`SavedFixturePIE` failures that day were **fixture** faults — a test red for the
wrong reason looks identical to a test red for the right one. A stage-1 red
proves the test *runs and sees something*; a stage-2 green proves the fix is what
changed it.

**LINE ENDINGS (Rig, 30 Sep ~18:30, measured):** patch Q is CRLF and its target file's working copy is LF, so a plain `git apply --check` FAILS; with `--ignore-whitespace` it applies cleanly. **Before the window, run `git apply --check` on EVERY held patch (cat body, C, K, L, M, N, O, P, Q, R) together, in the same mode used to apply.** A check done in a different mode proves nothing. See the `puss-held-cpp-edits-as-patches` memory.

## Order

1. **Close the editor** (`Saved/CodexConductor/quit_editor_clean.py` — it refuses
   if anything is dirty, which is why it is the route).
2. **Run the adversarial review** on the accumulated diff:
   `Scripts/codex.sh --review-today`, or the prompt in `Docs/CodexPrompts.md`.
   Its last run found a live P0. Read it **before** building, so anything it
   finds can go in the same window.
3. **Apply the held patches**, each from its patch file with the working copy at
   HEAD.
4. **Build**, and verify each change by its own **UTF-16 marker in the DLL**,
   never by exit code.
5. **Run the suite**, narrow filter only: `Automation RunTests InfinityStage`.
   **Never broaden to `PussStage`** — that matches an automation test which
   rebuilds and SAVES the Show asset and the Master.
6. Anything other than **90/0/90** is a revert, not a debugging session.

## In the queue

| Change | Owner | State |
| --- | --- | --- |
| **Cat body never drawn in a game world** (`0f2d276`) | Look & camera | Committed, **unbuilt**. Source has the categorical guard in `ShouldDrawShadowCatBody()`; a binary check confirms the installed DLL predates it. Fixes the cat Gary saw in front of the camera at two transitions. |
| **Celestial writes only on change** (`Scripts/patches/2026-09-30_C_celestial_write_only_on_change.patch`) | Rig | Held as a patch, tree at HEAD, applies cleanly. Skips a sun/moon rotation, intensity, colour, fog or stars write when the value is already there. **Cannot change a value — a mismatch falls through to the setter — so it can only remove writes.** |

| **Passage keys travel with their section** — patch **K**, `Scripts/patches/2026-09-30_K_passage_keys_follow_section.patch` | Look & camera | **Held, tree at HEAD, `git apply --check` passes, no file contention with C or the cat build.** **~5 lines, and its TEST is the point:** `MoveSection` carrying its keys is **inferred** from a doc comment and Sequencer's drag behaviour — the engine `.cpp` is not shipped. The test (*a two-key channel keeps its section-relative frames across a rebuild that moves the section*) converts that inference into a measurement at every future build. **Without it, lengthening a Scene leaves every later Passage's camera score Δ early**, and `SavedMasterMatchesShow` stays green because it checks section placement only. |

| **A retained exit leaves no gap** — patch **L**, `Scripts/patches/2026-09-30_L_retained_exit_leaves_no_gap.patch` | Look & camera | **Held, tree at HEAD.** The handoff builder starts a retained exit at `max(sceneEnd − hold, lastInteriorEnd)`, so whenever the last interior shot ends before the hold it **opens a gap** — 48 frames at Scene 3, against the 23 it was being run to fix. Scoped to the **retained** path only; the normal Passage exit is unchanged, with a comment saying its stretch is a look decision. Carries one stated refinement: the Exit now copies the cut that **ends last** (the transport's own overlap rule) rather than the one that starts latest, since only the camera **on screen at the seam** makes the join seamless. Identical for every current Scene. |

| **The gait bob's roll is centred on a running mean** — patch **M**, `Scripts/patches/2026-09-30_M_gait_roll_running_mean.patch` (8dfd463) | Look & camera | **Held, not applied, not compiled; tree at HEAD.** **Gary's ruling, 30 Sep: *“no need to permanently tilt and the camera is at an ok height as it is”*.** Roll stops deriving from the lift's ABSOLUTE value and derives from its deviation from an exponential running mean (`ShadowCatCameraBobRollMeanSeconds = 1.0`, editable). **Height is untouched — the whole lift stays.** Re-primes on the first sample, a backwards step, or a gap over 0.5 s, so a jump or a resumed Passage never kicks the roll; a zero step leaves the mean alone, so several evaluations in one frame agree. **Also corrects the code comment claiming the lift “is zero-centred… needs no running average”** — that comment was the root of the fault and would have misled the next reader. |

| **Look resets at every cut** — patch **O**, `Scripts/patches/2026-09-30_O_look_resets_at_every_cut.patch` | Look & camera | **Gary, 30 Sep ~17:45: "reset at every cut for now"**. `bResetLookAtCut` (default on), which includes the Passage → Scene entry cut. Test `InfinityStage.Go1.LookResetsAtEveryCut`. Held, applied whole in stage 2. |
| **Binding-resolution check** — patch **N**, `Scripts/patches/2026-09-30_N_scene_cut_bindings_resolve.patch` | Look & camera | `CheckSceneCutBindings` / `CheckSequenceCutBindings`, root and nested, failing closed. The import gate for Klara's sequences (Python's `get_bound_objects` crashes the editor). Conductor approved as tooling. Test `InfinityStage.Editor.SceneCutBindingsResolve`. Held, applied whole in stage 2. |

| **The Arrival drives the lights and exposure before the cut** — patch **P**, `Scripts/patches/2026-09-30_P_arrival_predrive.patch` (857ace1; `--ignore-whitespace`) | Rig | **Gary, 30 Sep ~17:58: "Re-key, and dim from the curtain too".** Today the Arrival evaluates only the root rotation and the backcloth before Scene 0 (`InfinityStageArrival.cpp:246–275`). P also evaluates the light and exposure tracks, so they begin at the cloth release (−3.874). The ramps need re-keying after the build. Held, with a test. |

| **A/B switch for the per-frame wing render reset** — patch **Q** (file name pending) | Rig | `InfinityStagePassageActor.cpp:1461` `MarkRenderStateDirty` behind a console variable, so it can be A/B'd live. A suspect for Gary's blur, which is "only while moving", in P02 and other passages (30 Sep ~18:05). |
| **The bob fades in with walking speed** — patch **R**, `Scripts/patches/2026-09-30_R_bob_walk_weight.patch` (held; applies with C K L M N O; stage 2 whole) | Look & camera | A walk-weighted bob. Needed for the walk-in trial (Gary: "Trial one transition first", Interaction 1 → P02, "Slow zoom 15→35 during the walk"), and it's the same change the settle needs. The trial's keys go in after this is built. |

**C, K, L and M apply together on HEAD — the queue is file-disjoint**, and the
new tests are new files, so nothing contends.

**M IS APPLIED WHOLE IN STAGE 2, not split like K and L.** Its test
`InfinityStage.ShadowCat.GaitRollCentredOnRunningMean` calls the new function, so
without the fix it fails to **COMPILE** rather than going red — there is no stage-1
reading to take. The test is a pure function with no world: a constant biased lift
holds no roll; a −15 ± 8 cm gait rolls both ways and averages about zero; the
**old rule's input — the lift itself — is one-sided**, and that assertion is what
discriminates the fix from the fault; re-prime on gap and on reverse; the zero step
is stable.

### Patch K's test is the point of patch K

**`InfinityStage.Editor.PassageKeysFollowSection`** (a new file, so no merge
contention). It builds Passage → Scene → Passage, keys a **two-key**
SpeedMultiplier and a WingPhaseBias on the later Passage and a height key on the
earlier one, lengthens the Scene by 1 s, rebuilds, then asserts: the later
section moved by exactly the added length; **every key kept its section-relative
frame and value**; the earlier Passage's key did not move; and an unchanged
rebuild moves nothing again.

**A RED HERE IS A FINDING, NOT A FAILURE.** `MoveSection` carrying its keys is
**inferred** — from a doc comment and from Sequencer's drag behaviour — because
the engine `.cpp` is not shipped. **If the test is red at the build, the
inference is wrong** and the fix becomes a manual per-channel offset. That is
worth knowing at a build window rather than after a Scene length change.

**No effect on the show at its first rebuild:** every section already sits at its
compiled start, so nothing moves until a Scene's length actually changes.

### Patch L also fixes a clamp that silently eats the designed hold

**Declaration-proven** (`MovieSceneSection.h:391-393`): `SetStartFrame` is
clamped to the current **end**, and `SetEndFrame` to the current **start**. The
builder set the Exit start before the end — so **after any lengthening the new
start lands past the old end, clamps to it, and the Exit runs from the OLD end to
the new one instead of holding for its designed second.**

**It has already happened.** Scene 1's repair produced an Exit at `[375, 5270]` —
full coverage, zero camera delta, and **a 195-second Exit where a 1-second hold
was intended.** Invisible today, because a retained Exit copies the Entry camera
so the view never changes. **The coverage gate passes it, because coverage IS
whole.**

L now sets each range in **one `SetRange` call**, removing the intermediate state
entirely. **That fixes both paths.** Setting only the retained path would have
masked the clamp where L touches and left it live on the normal exit — the fault
surviving in the branch nobody looks at.

**Second test, `InfinityStage.Editor.ExitHoldSurvivesLengthening`:** match a
retained Scene, lengthen it, rematch, and assert the Exit is **still the designed
hold** rather than running from the old end. **Red on today's code.** Coverage is
whole in both cases, so this is the only assertion that can see the fault.

### Patch L's test discriminates

**`InfinityStage.Editor.RetainedExitLeavesNoGap`** — a fixture whose designed
shot ends at 120000 of 240000 with the hold starting at 216000. It asserts full
coverage, a retained Exit running from 120000 to the end, the designed shot left
as authored, and the same again after a second match (idempotent).

**The pre-fix code gives Exit [216000, 240000], so the test is RED without L.**
That is the property that matters: a test which would have passed before the fix
proves nothing about the fix.

## Expected suite delta

- Cat fix: **0 new tests**; `ShadowFiguresOnlyWhileRigIsLive` gains three
  assertions (the cat has a mesh, the body is not drawn in a game world, it still
  casts its shadow while live).
- Celestial patch: no test change expected.

So **90/0/90 remains the target**, with three more assertions inside one test.
