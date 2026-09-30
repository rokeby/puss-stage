# Next build window — what is in it, and in what order

The build gate is **machine-wide**: any open UE editor in any project blocks any
build. The editor is currently held by the landscape block, so this waits.

Gary set the review cadence on 30 Sep: **the adversarial Codex review runs once
per build window**, not ad hoc.

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

| **Passage keys travel with their section** (`MoveSection(Δ)` before `SetRange` in the rebuild) | Look & camera | To be held as a patch. **~5 lines, and its TEST is the point:** `MoveSection` carrying its keys is **inferred** from a doc comment and Sequencer's drag behaviour — the engine `.cpp` is not shipped. The test (*a two-key channel keeps its section-relative frames across a rebuild that moves the section*) converts that inference into a measurement at every future build. **Without it, lengthening a Scene leaves every later Passage's camera score Δ early**, and `SavedMasterMatchesShow` stays green because it checks section placement only. |

## Expected suite delta

- Cat fix: **0 new tests**; `ShadowFiguresOnlyWhileRigIsLive` gains three
  assertions (the cat has a mesh, the body is not drawn in a game world, it still
  casts its shadow while live).
- Celestial patch: no test change expected.

So **90/0/90 remains the target**, with three more assertions inside one test.
