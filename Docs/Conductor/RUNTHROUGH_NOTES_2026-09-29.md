# Run-through notes — 29 September 2026

Gary, playing from the top in rehearsal mode. His observations, grouped. Nothing
here is diagnosed unless it says so.

## Before play — the opening frame

- **The Opening sequence shot doesn't exist as intended.** No curtain falls like
  a drape in front of the first wings. There are just the first wings, and a
  curtain asset.
- **The curtain he can see is the `CurtainChaos Preview`** (Soft goods' preview
  actor, x=5400) sitting behind the third/fourth/fifth wing, near the back of
  the stage — not covering the front where it should be.
- **What works:** the proscenium from outside looks good. **The floor has "a
  great shiny, waxy kind of wooden floor texture"** — this is the walnut slab
  the conductor flagged overnight as a mistake to remove. HE LIKES IT. The
  problem is its HEIGHT (top at +49.5, half a metre above stage level), not its
  existence. The warm-light / blue-exterior contrast is good.
- **NO SENSE OF RIGGING.** Nothing shows where the wings slide in and out or up
  and down from. He wants **pistons, rigging, struts** — some visible mechanism.
- **NO OUTER ARMATURE.** No supporting scaffolding around the whole thing.
- Net: "a wide, dusky, empty space rather than inside a big machine."

## On play

- **The opening curtain that plays is the OLD FIRE SAFETY CURTAIN asset.** Too
  close to camera, focus slightly off. It does do the job of opening, but **he
  wants the drape (the new baked curtain) as the opening curtain.**
- Snaps into cat view. **Two shadows of the cat's ears**, bottom left and right,
  moving slightly — the movement is nice, but he'd rather it weren't two.
- **THE MOUSE LOOK FIGHTS THE CENTRAL VIEW.** Mouse look works (and the dog
  equivalent), but it is in conflict with the sequence camera.

## Performance — priority

- **Every ~1 second the frame rate drops from ~40 to ~12.** Regular, rhythmic,
  "very noticeable". Persists during the walk.
- NOT contention: a periodic beat is a timer, not load. (MHFat's PIE was running
  at 35–40% GPU during this; a yield flag was set at 15:51Z to get a clean
  baseline.)
- Checked and ruled out: no `SetTimer`/tick-interval work anywhere in the
  InfinityStage plugin, and no `SceneCapture` actors in the level.
- Still to try: `stat unitgraph` + `stat game` / `stat gpu` during a spike, or
  an Insights trace. Needs to be caught in the act.

## The walk through P01

- **He walks straight through the chaos cloth curtain.** "Just no clip through."
  No reveal, no drama. (The baked curtain is an animation, not a collider.)
  The curtain with the big holes in it looks nice.
- **At the end of the tunnel he sees the dusky outside light.** He does not want
  to see that: the passage should **open into the scene**, so **another curtain
  is needed at the passage end**.
- The tunnel may also need to be **longer** — it shouldn't feel like you are
  already facing the end of it from the middle of the stage. Wings could **come
  in more, or travel further**.
- The camera angle plus the wings' movement means he keeps seeing the outside
  dusky space, so there is still no sense of enclosing infrastructure.

## WHAT WORKS — and a direction, not a detail

- **A blinking spotlight with a shadow in it, near the end of P01, is "really
  effective".** He wants many more.
- **The idea that follows: characterful shadows as a feature of every passage.**
  Interior **shadow puppets**, flat like the wings, so characters and ideas are
  *intimated* rather than modelled and rendered as full assets.
- **Lights that come from the side into the centre of the passage are good.**
- This is cheap relative to building assets, and it is in the material language
  the show already has.

## Visual quality

- **Moving wings blur.** Paused (space), they look sharp and nice; moving, they
  smudge, and the whole scene reads much lower resolution — especially against
  the floor, which stays sharp and shiny. Likely motion blur or temporal
  upscaling; both are settings.
