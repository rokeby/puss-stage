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
  - The box swings up out of its pit with the roof standing upright on the far wall.
  - **MEASURED on the live rise, 30 Sep 13:02** (`rise_sweep_measure_readonly.py`). It posed
    the saved rise every 0.5 s and read the world corners of every hangar mesh in the dock
    frame:

    | | far wall | roof crosses ground level | past the far wall | box alone |
    |---|---|---|---|---|
    | Scene 1 | 65.5 m | 113.7 m, at 5.0 s | **+48.2 m** | +7.0 m |
    | Scene 5 | 155.5 m | 255.5 m, at 9.5 s | **+100.0 m** | +8.1 m |

    The model predicted 113.6 m, +48, +7 and +100, +8, so the live rise matches it.
  - After the run the root pitch read back at −90 and the editor was 0+0 dirty.
  - Limit: 0.5 s sampling can under-read a peak slightly. The model agrees with the samples to
    0.1–0.2 m.

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
   - **COUNTED, 30 Sep 13:04** (`lane_inventory_readonly.py`, run 130421, read-only, dirty
     unchanged). The table is *measured*; the notes after it mark what is inferred.

     | lane | the move | camera rig | placed by hand (of which handoff cams, which regenerate) | hangar actors + Arrival (rebuilt) | world-space re-keys outside the hangar |
     |---|---|---|---|---|---|
     | P02 | 2 | 1 | 14 (2) | 117 + 1 | 0 |
     | P03 | 2 | 1 | 68 (2) | 112 + 1 | **5 bindings**: Scene 3's clams (`LS_Clams` ×4, one with 12 keys; `LS_DevScene_03` ClamCam1) |
     | P04 | 2 | 1 | 6 (2) | 117 + 1 | 0 |
     | P05 | 2 | 1 | 11 (2) | 895 + 1 | 0 |
     | P06 | 2 | 1 | 13 (2) | 115 + 1 | 0 |

     - **Cheap mix (P04–P06):** 6 move actors, 3 camera rigs, 24 hand-placed actors (plus 6
       handoff cameras that regenerate), 1,127 hangar actors rebuilt with 3 Arrivals, and
       **zero** world-space re-keys outside the hangars.
       - Each hangar root holds a world Location default in its rise, so a hangar moved rather
         than rebuilt costs one re-key.
       - The hand-placed pieces are lanterns, stalls cameras, floors, pit liners, the P04
         backcloth and the Ortolan sheet. None has attached children.
     - **Full chain (P02–P06)** adds P02, and P03's 68, which include Scene 3's cast and props.
       It also adds the 5 Scene 3 re-keys and the turns.
     - Not ridden or re-keyed: 4 dev establishing cameras sit on lane boundaries (unconsumed per
       the docking audit).
     - Env-pack demo sequences (LSM `S_Sequencer_*`, `LS_Sunset`) have world keys in these lanes
       but are referenced only by other maps or nothing (*measured*: asset referencers). Not a
       cost.
     - `LS_OrtalanSheetSway`'s 8 bindings are skeletal-mesh components under `BP_OrtalanSheet*`
       actor bindings, which is relative. No actor with those labels exists in the level
       (*measured*), so it binds nothing here.
     - `LS_S4_HangarFold` still exists. The scan found no unparented world-space binding in it
       (its actors are attached since v2). Whether anything still plays it was not checked.
     - **Camera rigs:** one per lane. How each follows its Passage when moved is **not
       assumed**; that needs a code read or a test.

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
1. Builder change: roof leaves plus the drawbridge panel, with swept checks.
2. One test hangar, then Gary looks.
3. The three translations (camera rig behaviour checked first).
