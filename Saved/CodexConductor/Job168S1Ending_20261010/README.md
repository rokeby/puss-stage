# Job 168 — S1 animals fade, lights out, and shorter ending

Offline-authored only. Nothing in this bundle has run in Unreal. The only
save-eligible content assets are the PussStage-owned S1 wrapper, Show, and
managed Master. Klara's copied sequence is read-only and `L_Animals` is never
saved.

## Reviewed timing (S1 local, 25 fps)

- animal additive-scale fallback fade: `[3525,3600]` (exactly 3.0 s), then
  wrapper-owned `bHidden=false` (`True` means visible);
- Job 29 rig-light fade reused at `[3800,3838]` (1.52 s);
- Exit Handoff Camera: `[3875,3900]`;
- exclusive new S1 end: `3900`.

`preview_timing.svg` is an analytical timing card, not rendered proof.

## Why the fallback is used

The offline S1 snapshot contains no animal binding or visibility track in our
wrapper. Pig, Raccoon, and Deer each have late additive transform sections in
`LS_Animals_1_S1Hangar`; their exit keys end around her frames 3500–3513, which
map to S1 frames about 3417–3428. A persistent wrapper-owned MID is unavailable,
and no common material scalar is proven to drive opacity. Stage A therefore
uses Gary's permitted scale/visibility fallback while leaving Klara's motion
evaluating underneath it.

## Ordered DRY / APPLY

For every call, edit `job168_args.json` with the named `stage`, matching `mode`,
and `confirm: "<MODE> JOB168"`; then send
`job168_request.json` through the guarded project-Python route.
Use one run id for a stage's reviewed DRY→APPLY pair; use a fresh run id for a
later retry or REVERT.

1. `ANIMALS` DRY, inspect the author/material audit, then APPLY.
2. `LIGHTS_OUT` DRY, require every Job 29 target and `[3800,3838]`, then APPLY.
3. `SHRINK` DRY. Its exhaustive JSON is the authority for every direct S1
   section, key, marker, audio, event, camera cut, and subsection at/past 3900.
   Inspect it, then APPLY. The proven shrink implementation rebuilds the
   managed Master, moves downstream absolute Passage keys, and saves only S1,
   Show, and Master when dirty.
4. `VALIDATE` DRY. Require `JOB168_VALIDATE_OK`: three animal tracks, lights
   record at 3838, the exit handoff `[3875,3900]`, all three hangar holds ending
   at 3900, Show/Master match, Klara hash unchanged, and zero dirty packages.

The final editor runner should additionally run
`InfinityStage.Editor.SavedMasterMatchesShow` and the sequence binding resolver.

## REVERT (reverse order only)

1. `SHRINK` REVERT.
2. `LIGHTS_OUT` REVERT.
3. `ANIMALS` REVERT.

Each mutating stage takes a `Backups/Pre...` snapshot and writes a transaction
record before mutation. Never use Save All. A refusal after an in-memory write
and before a success marker means Don't-Save restart, then inspect the record.

## PIE stills plan (later, not this offline job)

- 3500: animals visibly mid-fade;
- 3600: animals fully absent without a one-frame pop;
- 3700: absence holds and no material/scale residue appears;
- 3800: first frame of lights-out;
- 3900: capture frame 3899 as the final valid S1 frame and verify the next cue
  takes camera ownership at the exclusive boundary.
