# Next build window — what is in it, and in what order

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
