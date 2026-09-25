# Overnight run — 25/26 September

Written by **Puss · Conductor**. Six streams are live: Rig & atmosphere, Wing
materiality, Soft goods, Look & camera, Effects sources, Director.
This says what the run is for, how the exclusive resources are shared, what each
stream must produce as evidence, and what waits for Gary in the morning.

## The goal of this run

**By morning, the corridor should read as the inside of a Baroque stage machine
rather than wings passing on a travellator.** Concretely, three things that do
not exist yet:

1. A **timber gridiron** overhead that is real geometry from a real pass, not a
   grey preview — with the existing 136 shaft-casting fixtures visibly hung on it.
2. A **floor that is machinery** — wooden boards with chariot grooves at the wing
   stations, cloth laid over and worn through at the frays, the cat's centre line
   clear. The Landscape gone.
3. **Wings with material depth** — parallax rather than bump offset, oil and
   varnish rather than flat print, per-instance variation so 48 pairs in a row
   are not one finish.

Plus **one hero curtain in Chaos Cloth** that Gary can scrub in the editor —
heavy and ragged, every crease earned by the solver.

Everything else — walls beyond the wings, effects sources, the closed ring, the
Scene transitions — is explicitly **not** this run.

## Phases, and why they are phased

The streams parallelise because they own disjoint files. They collide on three
things only: the **build**, the **editor**, and the **Show/level**. So:

### Phase A — parallel, no build, no level mutation (now → build window)

| Stream | Work | Evidence it must produce |
| --- | --- | --- |
| Rig & atmosphere | Write the C++ `MaterializeStructure` pass. Do **not** build. | Compiles cleanly in review; new files only; plan for ground grooves |
| Wing materiality | Survey, then the unification decision, then material work on its own packages | The unification proposal, to me, before executing |
| Soft goods | Blender pattern-cutter → one hero Chaos cloth, hung and tunable | The asset exists and scrubs; no level or sequence edits |
| Look & camera | H.9 camera piloting with write-back, new editor files | Compiles in review; keys the Master's Passage camera channels, verified through the rig's evaluation, never writes the Show |
| Effects sources | Own new files first, then the conductor's shared enum pass | Files compile in review before the shared change is made |
| Director | Confirm or refute the seven transition findings, then fix | Transport tests, not screenshots |

Blender runs in its own process, so Soft goods never blocks anyone.

### Build window — exclusive, run by me

When Rig & atmosphere says its C++ is ready, **and not before**, I:

1. Require **zero dirty packages** from a read-back. The editor is never closed
   over unsaved work.
2. Tell all streams the editor is going down.
3. Close Puss. **MHFat's editor must also be closed** — Live Coding blocks builds
   globally, not per project. That one needs Gary or the MHFat conductor.
4. Build, prove the new code by its UTF-16 string in the DLL, check for
   hot-reload leftovers, run the full suite.
5. Reopen, confirm the world and zero dirty, release the streams.

**One window, batched.** Gary's standing preference is one restart cycle over
several, so any other stream with C++ ready gets folded in — currently Rig &
atmosphere's structure actor and Look & camera's piloting tool. Soft goods and
Wing materiality need no build at all: Chaos Cloth's plugins are already enabled
and material work is asset-only.

### Phase B — level and Show mutation, one stream at a time

The editor slot is granted by me, singly. Read-only scripts need no slot. Order:
Rig & atmosphere first (structure changes the world everything else sits in),
then anything else that needs it.

## Acceptance criteria — machine-checkable, because I cannot see

Gary is asleep; nothing can be accepted on how it looks. Each task lands only
when it passes a check that reads the **result**, not a return code. Today's
robocopy reported failure while having copied 62.8 GB successfully, and the
opposite failure mode — a wrapper exiting 0 over a command that did nothing —
happened earlier in the same session. So:

- **C++**: build exit 0, the new UTF-16 literal present in the DLL, zero
  `-####.dll` hot-reload leftovers, suite **45/46** with only `SavedFixturePIE`
  failing. Any other failure = stop and revert, do not proceed.
- **Structure pass**: instance counts per Passage, derived from station counts
  (48/23/21/21/93/55 pairs), read back from the live actors after materialize.
- **Materials**: assets compile; the affected wings read back with the expected
  master; zero dirty outside the material packages.
- **Cloth**: the Chaos asset opens, simulates without exploding, and its mass and
  tension/compression asymmetry are the settled values. Heaviness and raggedness
  are Gary's eye, not mine.
- **Always**: zero dirty packages at rest, and a `Backups/Pre<Thing>-…` snapshot
  named in the report for anything that mutated the Show, the level **or the
  Master sequence** — a camera key saves the Master, not the Show.

**Editor screenshots are broken project-wide.** Captures return stale or black
frames: a top-down from 60 m and an eye-level shot differ by <1.3/255 mean. The
level viewport does not render while another window is in front. Until Gary
fronts it, no stream may claim rendered acceptance, and "unverified" must be said
out loud rather than implied.

## What I will not do unattended

- **Accept anything visually.** No render substitutes for Gary's eye, and editor
  captures have been unreliable when the editor is backgrounded. Movie Render
  Queue may give reliable stills; it is unproven here and I will treat any
  success as a bonus, not a gate.
- **Touch the route.** It stays straight with auto-fit on until the ground
  generator exists to follow a curve.
- **Add attachment kinds**, swap the Sequencer curtain, or let two streams write
  the same file. Those are mine and they wait.
- **Delete anything of Gary's.** The Landscape gets replaced only after its
  removal is reversible from a named snapshot.

## Morning report

Left at `Docs/Conductor/MORNING_2026-09-26.md`, and it will say plainly:

- What landed, at which tier of proof — built / read-back / **not yet seen**.
- What did not land and why.
- Anything a stream escalated, with my decision.
- The suite count. It will not be called green while `SavedFixturePIE` fails.
- What needs Gary's eye first, in order, with where to stand to see it.

## Rollback

- **Source**: git, four commits, clean tree. `git diff` shows exactly what each
  stream changed.
- **Show and level**: `Backups/PreContainerWorld-20260925-181332` plus a snapshot
  per mutation.
- **Everything, including the 46 GB of Content**:
  `D:\PussStageBackups\FullSnapshot-20260925-1853`, verified, Show and level
  byte-identical to live at the time it was taken.

## Standing state to return to

The editor at rest: open on **8010**, Puss world, **zero dirty**, route straight,
auto-fit on. No stream inherits another's half-finished mutation.
