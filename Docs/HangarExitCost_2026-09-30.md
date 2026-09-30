# Hangar exit: what docking costs (Rig & atmosphere, 30 Sep)

Picture: `Saved/CodexStructure/Captures/HangarExit_DockingCost.png` (regenerate with
`Saved/CodexStructure/hangar_exit_cost_sheet.py`; offline, no editor).

## The number

**Docking every Passage behind the previous hangar's far wall is a chain move plus a
new rise, and in the full version a relight too.**

- **Every Passage after P01 moves and turns.** P02 moves 879 m; P03–P06 move 1.8–5.1 km.
  P02 turns −22.9° and P03–P06 all turn −66.5°, because P02's route bends 66.5°
  (start yaw +22.9°, end −43.6°).
  - It is a chain: each dock sits on the end of the previous moved Passage.
- **A turned Passage is a relit Passage.** The sun is one world-fixed azimuth for the whole
  show (`InfinityStageCelestialRig.cpp:383`, `SunAzimuthDegrees` 225°). Every turned set would
  see the sun, and the dusk horizon glow, from a different side.
- **With the rise as built, nothing can stand within 48 m of a far wall** (Scene 5: 100 m).
  The box swings up out of its pit with the roof standing upright on the far wall.
  - The roof tip crosses ground level 114 m from the camera stop, then climbs to 90 m before
    it folds over the box.
  - The next proscenium, gridiron and boards would stand inside that sweep.
  - Figures from the builder's own swing formula and its reach (`hangar_build.py:209-218`,
    reach 109.8 m; Scene 5 251.7 m).

**Cheapest version that is still a place: dock only where the headings already agree.**
- S3→P04, S4→P05 and S5→P06 are pure translations into P03's lane: 821 m, 1,642 m and 2,601 m.
  Nothing turns and nothing is relit.
- S1→P02 and S2→P03 stay cloth match cuts. Those two links carry the bend.

## What a docked exit needs, even in the cheap version

1. **A new roof beat** for every hangar with a Passage behind it (S3, S4, S5 in the cheap
   version).
   - For example, two roof leaves hinged on the side-wall tops. They sweep sideways, not
     forward.
   - The box alone, walls up without the upright roof, then reaches 7 m past its far wall
     (Scene 5: 8 m).
   - This is a builder change plus the existing per-hangar chain (un-nest, Arrival revert,
     hangar revert, build, Arrival, nest). **It changes the rise's climax, so it is Gary's
     call.**
2. **A far-wall opening.** A portal-sized panel (19 × 10.5 m) cut from the far wall, falling
   outward as a drawbridge.
   - It spans the ~10 m pit gap the new rise still needs and lands on the next forestage; the
     cat walks out over it. That sets the far wall to portal gap at about 11 m, and the stalls
     seat (14 m before the portal) stays inside the hangar.
   - A flying iron (the panel flies up, no sweep) would need a separate cover over the gap.
     The drawbridge is its own floor.
3. **The moves themselves, per moved Passage:**
   - **Rides along free:**
     - Show content: attachments and lights are anchor-relative (`InfinityStageTypes.h:459`
       `RelativeTransform`);
     - Master timing: passages are distance-driven and no route length changes;
     - the Entry Handoff Camera, which regenerates from the compiled Passage (a rematch).
   - **Must be moved by hand:**
     - the Structure actor (a separate actor at the route start);
     - hand-placed level actors (props, lanterns, stalls cameras, floors, cloth actors,
       volumes);
     - the Passage's own hangar and Arrival, rebuilt at the new dock.
   - **Must be re-keyed:** any sequence transform track on a moved actor that holds world-space
     keys. `LS_S4_HangarFold` is the known one; Scene sequences are unknown.
   - **NOT COUNTED YET.** The number of level actors and world-space keys per lane needs a
     read-only probe in an editor slot. That count is what turns this into hours.
4. **New adjacency:**
   - P04–P06 would stand on or near P03's oak floor, which runs to x 452 m.
   - Before a hangar rises, the next proscenium is visible about 76 m ahead down the lane.
     That is either a destination or a spoiler, which is Gary's call.
   - More passage lights in view at once, so a perf check.

## The trick, for comparison

The cloth match cut: per exit, one drape, one stalls camera in the hangar, and one cut.
- Every portal is 19 × 10.5 m, so one bake serves all five exits.
- Nothing moves and the rise stays as it is.
- The real work is matching the light on the cloth across the cut: the hangar interior
  against the next Passage's mouth.

## Gary's calls

1. Place or trick, per exit. The cheap mix is three places and two tricks.
2. The new roof beat, if any exit is a place.
3. For the bent links, relight or trick.
4. Whether the next stage should be visible down the lane before the hangar rises.

If the mix is chosen, the engineering order is:
1. Builder change: roof leaves plus the drawbridge panel, with swept checks.
2. One test hangar, then Gary looks.
3. The three translations, after the lane inventory.
