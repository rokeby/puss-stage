# Klara hook-in plan v2: her dioramas inside our hangars (7 Oct, offline)

This is offline work only: nothing was run in Unreal or over MCP, nothing was copied into Content, and nothing was
committed.

| File | Role |
|---|---|
| `klara_hookin.py` | The tool |
| `klara_hookin_run.py` | Runner |
| `klara_hookin_args.json` | Arguments, mode DRY |
| `klara_hookin_request.json` | MCP request |
| `test_klara_hookin_offline.py` | Offline harness |

The harness passes 28 of 28 tests, and 12 of 12 seeded mutations are caught.

Proof tiers, marked per claim:
- **[decl]** — stated by a header, signature or source we can read.
- **[prec]** — follows an in-repo precedent (cited).
- **[meas]** — bytes, or a record, read back.
- **[inf]** — inferred; the reason is given.

## 1. Gary's decisions, encoded in `decided_by`

**7 Oct, his own answers:**
1. The shot starts "After the hangar lands" (`land_plus_strike`).
2. S1 narration: "Drop it for now". The tool **mutes** it (`set_is_active(False)`, never deleted). REVERT
   re-activates it.
3. S2: "Import, keep our S2". The S2 level is **streamed only**. `LS_DevScene_02` is untouched. It appears in
   `import_only`.
4. Lighting: "Hers; ours off in her scenes".

**7 Oct design note:** her dioramas sit inside the hangar. We see a wide shot as the light strikes on a dark hangar,
then go into her cinematics.

**Not Gary's, proposed by me:**
- `wide_hold_s` = 5 s;
- `anchor` = `center`;
- the lighting windows in section 4.

## 2. Mechanism, with evidence

**Placement: streaming sublevel + LevelTransform.**
- Use a non-instanced streaming sublevel whose `LevelTransform` is the landed dock frame composed with a fitted local
  offset. `LevelTransform` is "Transform applied to actors after loading", `BlueprintReadWrite` [decl
  `LevelStreaming.h:226-227`].
- Non-instanced streaming keeps her package name. Her bindings are full paths, e.g.
  `/Game/KK_S1_Animals/L_Animals.L_Animals:PersistentLevel.CineCameraActor_7` [meas: decoded soft-object-path table].
  So they should still resolve [inf]. This is **measured** at APPLY_STREAM through the live `CheckSceneCutBindings`
  verdicts (`CameraPilotLibrary.cpp:691,777`) [decl].
- LevelInstance is rejected: an instanced package is renamed (our code matches `"_LevelInstance_"`,
  `suppress_foreign_sky_stage1.py:10`) [meas]. Resolution would then need a per-player
  `SetSourceActorContext(StreamingWorld, ContainerID, SourceAssetPath)` (`LevelSequencePlayer.h:93`) [decl], which our
  single Master player does not supply [inf].

**Keys: a re-keyed COPY of her LS, translation-only. Her original is never edited.**
- **Sub-section transform origin.** It exists:
  - per-section `Translation[3]`/`Rotation[3]` with an `OriginOverrideMask` (`MovieSceneSubSection.h:278-285`) [decl];
  - composed by nesting depth (`MovieSceneTransformOriginSystem.h:13-35`) [decl].

  But the mask is a bare `UPROPERTY()` and `SetMask` is not a `UFUNCTION` (`:168-175, 278-279`) [decl]. So Python
  cannot turn it on [inf; DRY probes `origin_override_mask`]. It would be the better route if a small C++ setter were
  approved.
- **Actor-level `TransformOrigin`.** It lives on the actor's instance data (`DefaultLevelSequenceInstanceData.h:31-39`)
  [decl], so it would move the whole Master. Rejected.
- **The copy.**
  - It shifts every top-level, unattached `3DTransform` Location key and default by the same transform.
  - This is exact for cubic keys, because a constant offset leaves tangents unchanged [inf, standard Bezier algebra].
  - A test checks that a keyed point ends where the LevelTransform puts a static actor at the same point.
  - S1 and S4 docks have yaw 0 [meas: `hangar_s1_record.json` dock.yaw 0; `hangar_s4_plan.json` yaw 0]. Local yaw 0
    therefore gives a pure translation. Any non-zero world yaw refuses.
  - Channels are picked by order and their names verified (memory: names are suffixed, `Location.X_183`).

## 3. Fit: what was measured offline, and the result

- **Hangar interior** in dock-local coordinates: x in [500, 6500], y ±1000, floor top z = 0, lattice at 1200, height
  3000 [decl `hangar_build.py:211,229,435-440`; meas records]. With a 1 m margin this gives **58 × 18 m**.
- **Her sets**, as 2–98 % component pivots from her `.umap` files [meas; pivots understate mesh extent]:

| Level | Footprint | Ground | Top | Fits? |
|---|---|---|---|---|
| L_Animals (S1) | 18.6 × 10.2 m | 0 | 5.5 m | **Yes**, yaw 0. LevelTransform ≈ (32556, 122, 150) |
| L_KK_children (S4) | 22.6 × 13.3 m | 0 | 7 m | **Yes**, yaw 0 |
| Japanese_Alley (S2) | 33.9 × 25.6 m | ~7.9 m | 12.2 m above ground | **No** |

- **Japanese_Alley detail.** It overhangs **3.8 m per side** and its top is above the 12 m lattice. S2 is import-only,
  so this is reported as a warning. Gary or Klara must choose which part goes in; scaling is not proposed.
- **Live check.** The tool re-measures live bounds once the levels are streamed. It checks each dock against the
  world-fixed `S<n> Hangar Apron` (`hangar_build.py:432-441`) [decl], because the dock records are from 30 Sep
  [meas, stale].
- **One level, one placement.** S4's 5 SpotLight bindings into L_Animals [meas] resolve to S1-hangar lights. Those
  are hidden during S4, so S4 loses them. A second copy of L_Animals would need rebinding, which is not mechanical.
  This is a decision.

## 4. Timeline and lighting, encoded in each `LS_DevScene_0N`

```
[0, land)    dark hangar; her level hidden
[land, cut)  Level Visibility track shows her level; OUR strike lights reveal the diorama (wide shot on our root
             cuts); HER sun/sky/fog/atmosphere/cloud/PPV hidden (Visibility tracks, RESTORE_STATE)
[cut, end)   her re-keyed cinematic; her environment visible; OUR rig's sun/moon/sky light/height fog hidden
cut = land + StrikeAfterLandSeconds + wide_hold_s;  end = cut + her length  (S1 = 255 + 5265 = 5520 f at the
measured land 104 + 26 strike frames: harness numbers, live values come from DRY)
```

Every window is a section in the Scene's own sequence: the Master stays the authority, and scrubbing out of a window
restores state [inf: RESTORE_STATE semantics].

**OUR lighting** is the rig's four bound actors (`CelestialRig.h:42-52`) [decl]. Hiding them is not fought:
- the rig never ticks (`CelestialRig.cpp:49`) [decl];
- `ApplyCyclePhase` writes only intensity, colour and rotation, never their visibility (`:362-528`) [decl];
- it runs only from Passage sections (`MovieSceneInfinityPassageTrack.cpp:228-236`) [decl].

The Visibility track's property must read `bHiddenInGame`; APPLY gates on that [inf until run].

**HER lighting is silenced by the rig today.** `bSuppressForeignEnvironmentLighting` defaults to true
(`CelestialRig.h:95-107`). It hides every foreign directional light, sky light, atmosphere, fog and cloud (component
visibility plus hidden-in-game, `cpp:254-298`):
- at BeginPlay (`:91-110`);
- on every level add (`:352-359`);
- every 2 s during phase applies (`:320-340, 362-386`) [decl].

A Visibility track only toggles hidden-in-game [inf], so it cannot undo this.

**Narrow fix (a C++ patch, held for the Rig & atmosphere owner; not written into the source).** Add
`TArray<TSoftObjectPtr<UWorld>> ForeignLightingExemptLevels`. In `SuppressIfForeign`, return false when
`UWorld::RemovePIEPrefix(Actor->GetLevel()->GetOutermost()->GetName())` names an exempt level. Test with one exempt and
one non-exempt level. Until it is built, DRY refuses `RIG_SUPPRESSES_HER_LIGHTING` (or set `lighting.hers_on` false).

**Risks of her environment inside our hangar** [inf]:
- A directional light, sky light and height fog are **world-global**. While visible they also light the passages and
  other hangars, but only during [cut, end), when we are in her cinematic.
- Our hangar **roof and walls occlude her sun and sky**, so her set will be darker than she authored it. Proposal:
  hide the S<n> roof and lattice during [cut, end). This is Look & camera / Gary's call and is not implemented.
- Her cameras may sit outside our 20 m-wide box and see walls. This is **UNMEASURED**: read the re-keyed camera keys
  against the box (`inside_box_local`) after APPLY_SEQ.
- An unbound PPV of hers may fight the hangar's pinned exposure.

## 5. Steps

0. Klara's copy lands, then take a `Backups/` snapshot. Run DRY: every API row must be ok, the dock checks must pass,
   and there must be no refusals.
1. **APPLY_STREAM.** Adds all 3 levels with their LevelTransforms, initially loaded and hidden. Saves only the map.
   Records the cut-binding verdicts.
2. **APPLY_SEQ** (S1, S4). Duplicates and re-keys her LS. Retargets the shot section to the copy, with
   `get_parent_sequence_frame` read-back (`MovieSceneSectionExtensions.h:255`) [decl]. Mutes the narration, adds the
   visibility and lighting tracks, and saves only the Scene sequences and the copies.
3. **Relength** with `extend_scene_playback.py`, using the printed `new_end_s` (it rematches handoffs, gates coverage
   and rebuilds the Master).
4. **Verify.** Run `SavedMasterMatchesShow`, live `check_scene_cut_bindings` per cue, and a PIE play-through (wide
   shot, then cut).

   Note that the `SceneCutBindingsResolve` test uses its own preview world (`InfinityStageCutBindingTests.cpp:31`)
   [decl], so it does not check our data.
5. **REVERT.** `REVERT_SEQ`, then extend back, then `REVERT_STREAM`.
