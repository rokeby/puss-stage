# Proposal: props hanging on physical strings (cable physics)

From "Puss - Wings and Textures", for the conductor, 1 Oct 2026. Gary's idea,
and his ask: "bringing in some cable physics would be nice, it would need a bit
of veracity, as just swaying on moving wings is hard to make look real." Nothing
is built.

## The image

A bird (later perhaps other small cutouts) hangs from a cloud on a string, as if
it had just been dropped. When the cloud or wing moves, the bird lags, swings and
settles with real inertia. On a cue, a bird DROPS: it falls, snaps taut on its
string, bounces and settles. First use: P05 (clouds; the bird-to-mountain line).

## Why physics and not keyed sway

Gary: a keyed or material sway on MOVING wings looks false. The swing has to
answer the support's acceleration, and only a simulation does that convincingly.

## Proposed mechanism (to be designed by Rig, who owns the PassageActor mechanism path)

- **The anchor follows the wing:** a kinematic anchor component driven each frame
  from its panel's live transform (the same per-frame batch Rig designed for
  poles: instance = offset x live panel transform). Without that, a hung prop is
  left behind when the panel moves (`InfinityStagePassageActor.cpp:881`, per
  Rig's 29 Sep note). For rig-hung clouds that don't move, the anchor is static.
- **The string:** UE's Cable component (Verlet rope; *inferred* available as an
  engine plugin, not listed in `PussStage.uproject` — check it is enabled) for the
  look, and the actual hang from a Chaos physics constraint (a distance or rope
  limit) between the anchor and the bird body, so the bird has mass and swings
  as a pendulum.
- **The bird:** a small Flat V3 cutout (art from a Fuser job, built by this
  pipeline as a slim flat with a `Hang` socket at its string point), simulated as
  a light rigid body with damping tuned for "paper-and-wood".
- **The drop:** on a cue, release a hold constraint, or start the body above with
  the rope slack, so it falls and snaps taut. Key only the release time, not the
  motion.
- **Rules:**
  - query-only collision, with `CatFloor` explicitly Ignore (the CatFloor trap in
    the container-world plan);
  - a handful of instances, not hundreds;
  - check repeatability on scrub and replay (physics state on jumps; reset
    rules like TSR's history reset on jumps).

## Owners

- Rig: anchor, constraint, cue release (C++, with the build gate).
- This pipeline: bird art and meshes (`Hang` socket).
- Wing materiality: materials.
- Gary: which passages and cues.

## Cost

One design note plus C++ in one build window (Rig), a Fuser job and a small flat
build (this pipeline), and look-tuning in PIE with Gary.
