# Hangar exit: what docking costs (Rig & atmosphere, 30 Sep)

Picture: `Saved/CodexStructure/Captures/HangarExit_DockingCost.png` (regenerate with
`Saved/CodexStructure/hangar_exit_cost_sheet.py`; offline, no editor).

**Tiers, marked on every claim (AGENTS.md, 30 Sep):**
- **declaration-proven:** read in source, a header or config.
- **measured:** read back from Unreal by a probe, with its date.
- **computed:** exact arithmetic on measured inputs. It goes stale if the inputs moved since they were read.
- **inferred:** not verified; the reason is given.

## The number

**Docking every Passage behind the previous hangar's far wall is a chain move plus a
new rise, and in the full version a relight too.**

- **Every Passage after P01 moves and turns.** P02 moves 879 m; P03–P06 move 1.8–5.1 km
  *(computed)*. P02 turns −22.9° and P03–P06 all turn −66.5°.
  - The turns come from P02's route bending 66.5°: start yaw +22.91° (Look & camera's mouth
    survey, *measured* 30 Sep 01:21), end yaw −43.57° (the S2 hangar record's dock, copied from
    the Entry Handoff Camera at build, *measured* 30 Sep 12:31).
  - It is a chain: each dock sits on the end of the previous moved Passage.
- **A turned Passage is a relit Passage.**
  - The sun is one world-fixed azimuth for the whole show: `InfinityStageCelestialRig.cpp:383`
    sets `FRotator(SunPitch, SunAzimuthDegrees, 0)` *(declaration-proven)*.
  - No other azimuth exists: I searched for "Azimuth" across the plugin's `Public/*.h` and the
    rig's `.cpp` and found only that property.
  - That a 66.5° turn visibly relights a set is *inferred*; it has not been rendered.
- **With the rise as built, nothing can stand within 48 m of a far wall** (Scene 5: 100 m).
  - The box swings up out of its pit with the roof standing upright on the far wall. The roof
    tip crosses ground level 114 m from the camera stop, then climbs to 90 m before folding over.
  - These figures are *computed* from the builder's own swing formula and reach
    (`hangar_build.py:209-218`, reach 109.8 m; Scene 5 251.7 m). That model generated the rise
    keys.
  - The sweep has **not been measured** in the editor against the live rise, so "the live rise
    matches its model" is *inferred*, though strongly: the keys came from it.

**Cheapest version that is still a place: dock only where the headings already agree.**
- S3→P04, S4→P05 and S5→P06 are pure translations into P03's lane: 821 m, 1,642 m and 2,601 m
  *(computed)*.
- All four headings involved are 0° (P04–P06 start yaw *measured* by the mouth survey; S3–S5
  dock yaw in the hangar records).
- S1→P02 and S2→P03 stay cloth match cuts. Those two links carry the bend.

## What a docked exit needs, even in the cheap version

1. **A new roof beat** for every hangar with a Passage behind it (S3, S4, S5 in the cheap
   version).
   - For example, two roof leaves hinged on the side-wall tops, sweeping sideways.
   - The box alone, walls up without the upright roof, then reaches 7 m past its far wall
     (Scene 5: 8 m) *(computed, same model)*.
   - It is a builder change plus the existing per-hangar chain (un-nest, Arrival revert, hangar
     revert, build, Arrival, nest).
   - **It changes the rise's climax, so it is Gary's call.** The conductor adds that the roof
     beat reads at most 3.7% of the frame from the stop on a 25° look-up, and is never in frame
     on a level look. That was measured this morning (conductor's report); I have not re-read it.
2. **A far-wall opening.**
   - All six portal openings are 19 × 10.5 m (±950 × 1050 cm, `mouth_survey.json`, *measured*
     30 Sep 09:34).
   - A panel that size, cut from the far wall and falling outward as a drawbridge, spans the
     ~10 m pit gap the new rise still needs and lands on the next forestage. The cat walks out
     over it. That sets the far-wall-to-portal gap at about 11 m, and the stalls seat (14 m
     before the portal) stays inside the hangar *(computed)*.
   - A flying iron would need a separate cover over the gap.
3. **The moves themselves, per moved Passage:**
   - **Rides along free:**
     - Show content: attachments store an anchor-relative `RelativeTransform`
       (`InfinityStageTypes.h:459`, *declaration-proven*). That a materialize after moving the
       Passage actor carries them is *inferred*, not exercised.
     - Master timing: *inferred* from distance-driven Passages (docking audit, 29 Sep). No route
       length changes, but no rebuild has confirmed it.
     - the Entry Handoff Camera, which regenerates from the compiled Passage (docking audit's
       reading of `SceneHandoffBuilder.cpp:224-226`; not re-read by me).
   - **Must be moved or rebuilt by hand:** the Structure actor, hand-placed level actors, the
     Passage's own hangar and Arrival.
   - **Must be re-keyed:** sequence transform tracks on moved, unparented actors with
     world-space keys. `LS_S4_HangarFold` is the known one (docking audit).
   - **NOT COUNTED.** `Saved/CodexStructure/lane_inventory_readonly.py` (written, not run; it
     needs an editor slot) counts, per lane:
     - root actors to move, with their attached children;
     - Infinity Stage actors whose following is not assumed;
     - hangars and Arrivals;
     - every sequence binding holding world-space Location keys or defaults.
     It marks where a binding's lane is only *inferred* from key positions.
4. **New adjacency** *(inferred, not rendered)*:
   - P04–P06 would stand on or near P03's oak floor, which runs to x 452 m.
   - The next proscenium would be visible about 76 m ahead down the lane before a hangar rises.
   - More passage lights in view at once.

## The trick, for comparison

The cloth match cut: per exit, one drape, one stalls camera in the hangar, and one cut.
- One bake serves all five exits, because the portal openings are identical *(measured, above)*.
- Nothing moves and the rise stays as it is.
- The real work is matching the light on the cloth across the cut *(inferred; not tried)*.

## Gary's calls

1. Place or trick, per exit. The cheap mix is three places and two tricks.
2. The new roof beat, if any exit is a place.
3. For the bent links, relight or trick.
4. Whether the next stage should be visible down the lane before the hangar rises.

If the mix is chosen, the engineering order is:
1. Run the lane inventory.
2. Builder change: roof leaves plus the drawbridge panel, with swept checks.
3. One test hangar, then Gary looks.
4. The three translations.
