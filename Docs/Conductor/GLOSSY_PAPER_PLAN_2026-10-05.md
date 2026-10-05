# Glossy, slightly wet paper on the wings: plan (offline, no writes)

By Wings & Textures, 5 Oct 2026. This answers Gary's request, relayed by Conductor 4: "a really convincing paper glossy billboard surface ... almost slightly wet". Every claim is tagged with how it is known.

## Where we are

- **[declaration-proven] Which master the wings use.** The V3 wings (all of P01–P06 since the 5 cm rebuild) render through `M_Wing_Billboard_Master` (via `MI_Billboard_Front/Flap`), not `M_Wing_PaintedSurface_Master`. The painted-surface master is used only by the old StageOpeningV2 pieces in P06 and the P01/P06 ceiling.
  Sources: `Saved/CodexFlatV3/slot_a_import.py:20-25`; the 4 Oct P06 probe, `Saved/CodexFlatV3/p06/p6_pom_all_dry.json`.
- **[declaration-proven] A gloss-capable copy already exists.** `M_Wing_Billboard_Master_v2` (with `MI_Billboard_Front_v2/Flap_v2`) was built on 3 Oct, and v1 was left untouched. It decides gloss per printed sheet:
  - `PGloss` is the share of sheets that are glossy;
  - `GlossRoughMin/Max` set the roughness of a glossy sheet;
  - `Specular` is 0.30;
  - a hard `RoughnessFloor` of 0.30 applies everywhere.

  Source: `Saved/CodexFlatV3/gloss/build_billboard_master_v2.py:34-91`.
- **[measured] The 3 Oct one-flat test on P04 Wing 004 R:**
  - at the default strength, nothing visible;
  - exaggerated (PGloss 1.0, roughness 0.30–0.32), a broad warm sheen across the whole sheet rather than paper-like glints.

  The comparison was confounded by exposure. It is parked (Gary, 3 Oct).
- **[inferred] Why v2 reads as sheen, not wet paper.**
  1. The 0.30 roughness floor stops highlights from getting small and sharp. Wet print needs roughly 0.05–0.15 in places.
  2. The board is perfectly flat. A flat plane gives one large, smooth highlight. Real paper cockles, and the ripple is what breaks the highlight into the streaks that read as "paper" and "wet".
  3. Gloss switches on per whole sheet, so it is all or nothing across a sheet.

## What makes it read as glossy, wet paper

1. **Sharp specular highlights from the lights that exist.**
   - [inferred] In a dark stage the only things a glossy wing can mirror are the practicals, the fence-post lamps, the beams and the bright cloud/sky areas.
   - The highlights from point and spot lights are computed directly (no Lumen tracing needed), so they cost almost nothing. These are the glints.
2. **Paper cockle.**
   - A low-frequency normal undulation (ripples of about 20–60 cm, very low amplitude), generated in the shader, so no new textures.
   - It turns one big highlight into rippling streaks that move as the camera walks. This, more than anything, is what reads as "wet". [inferred]
3. **Roughness driven by the art, not by the sheet.**
   - Varnished or ink-heavy areas glossy, paper and peel matte.
   - Plus a sparse "wet patch" mask: patches, not sheets. That was the lesson of 3 Oct.
4. **Wet darkening.** A slight drop in base-colour value and a gain in saturation where it is wet. Wet paper is darker and richer. [inferred]
5. **Fresnel.**
   - Reflectance rises at grazing angles, and the walkway views the wings obliquely, so the wings beside the camera will flash the most.
   - That works for us, but it needs a ceiling on it, or near wings mirror lights everywhere.

**Clear coat.** [declaration-proven, Conductor 4's memory] UE 5.8 Python exposes no ClearCoat inputs on the material output (`MP_CUSTOM_DATA0/1` missing). A true clear-coat layer would need an editor-UI edit or C++. Recommendation: skip clear coat. Points 1–4 on the default-lit model get most of the effect. Add clear coat later, by hand in the editor, only if Gary wants a lacquer layer on top of matte ink.

## Cost

- **[declaration-proven, UE behaviour; not measured here]** Direct-light highlights (point 1) are essentially free.
- **[inferred]** The expensive part is Lumen reflections: tracing the scene into the wing.
  - Lumen traces reflections for surfaces below its roughness threshold (UE default 0.4, `r.Lumen.Reflections.MaxRoughnessToTrace`). Our wings are many large planes, so dropping their roughness under 0.4 broadly could add real GPU time.
  - The plan keeps most of each wing at 0.4 or above and confines low roughness to sparse patches, so few pixels trace.
- **[measured, required]** The test must record GPU frame time before and after, alongside the stills.

## Is "slightly wet" achievable?

- **[inferred] Mostly yes, as moving glints and ripple streaks** from the lights:
  - darker, richer colour in the wet patches;
  - sharp, small highlights that slide across ripples as you walk.
- **[inferred] Not as a mirror of the room.** A true wet look reflects the surroundings, which needs cheap, broad Lumen reflections; in a dark stage there is little to reflect anyway.
- **[inferred] It depends on light placement, and Gary is right that it's hard.** A wing with no light at a mirror angle to the camera shows nothing. It will read best on wings near practicals, fence lamps and beams. Conductor 4's lighting decides where the gloss is seen.

## One-MI test proposal (needs Gary's yes)

1. **Build a NEW `M_Wing_Billboard_Master_v3`.**
   - A new asset; v1 and v2 are untouched, and no nodes are deleted on any existing asset.
   - It adds:
     - the shader cockle normal;
     - art-driven roughness plus a sparse wet-patch mask;
     - wet darkening;
     - a Fresnel ceiling;
     - a lower roughness floor, but only inside the patches.
   - Every parameter and connection is read back.
2. **Reparent one flat's Front MI to it.**
   - Proposed: a P04 bay-3/4 wing, where the fence lamps and beams are.
   - Originals go to JSON plus a `.uasset` backup first, and a revert script restores the parent.
   - Reuse the 3 Oct gloss test harness: `Saved/CodexFlatV3/gloss/gloss_test_apply.py` / `gloss_test_revert.py`.
3. **Evidence:**
   - PIE stills before and after, at the same frame, in the same session, both with the same exposure handling;
   - a 3–4 s PIE clip of the walk past, because glints only read in motion;
   - GPU frame time before and after.
4. **Gary judges.** Roll out to all V3 MIs only after his yes; all of them repoint in one guarded batch.

**[declaration-proven] Not yet done.** No editor work, no asset written. This file is the only output.
