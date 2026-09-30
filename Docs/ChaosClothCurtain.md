# Chaos Cloth curtain — pipeline and traps

> **26 Sep: the curtain FALLS, it does not fly** (Gary; `Docs/Conductor/BRIEF_TRANSITIONS_AND_SCALE_2026-09-26.md`).
> It is already down and lit; at the cue it drops to the floor and stays as a pile. It is the
> Kabuki *furi-otoshi*. **Chaos cannot un-pin at runtime**: the kinematic set
> (`KinematicVertices3D`) is baked when the simulation initialises, and changing MaxDistance later
> does not free those particles. So the falling asset `CA_<STEM>_Fall` pins **nothing**, and
> `BP_CurtainChaos` starts its ChaosClothComponent **suspended** (`bSuspendSimulation`,
> Sequencer-keyable), holding the hanging start pose. Un-suspending is the drop: it falls as a whole,
> the hem lands first, and it crumples up from the floor. The BP carries a hidden `FloorCatch` box (top
> at z = 0, WorldStatic, ignores Pawn/Camera/Visibility) because **the stage boards have no
> collision** (Rig & atmosphere: every structure ISM is NoCollision; the chariot slots are open).
> Unproven: whether Chaos environment collision counts a box in the cloth's *own* actor. If the
> pile drops through, FloorCatch must become a separate actor, which is a level write.
> Asymmetric release (one side first) would be pins as a stiff anim-drive spring whose stiffness
> goes to 0 at the cue. Not built.
> Scrub: tick **Simulate In Editor** (the cloth appears, hanging), then untick **Suspend
> Simulation** to drop it; `Hard Reset Simulation` and re-tick Suspend to hang it again.

Soft goods stream, 25 September 2026. The show curtain is now **Chaos Cloth simulated live
in the editor**, not a Blender bake. The bake route (`Scripts/build_curtain_cloth_bake.py`,
`DerivedAssets/CurtainCloth/CurtainCloth_Fly_V1.abc`) is kept for the one case it still wins:
a cue that needs the same silhouette every night.

**Why the route changed:** four bake cycles were rejected ("gelatinous", "waxy", "drawn-on
creases", "pretty poor"). Each was a blind guess plus a 10–15 min bake, because nobody could
touch a parameter while watching the cloth. Chaos puts the solver in the editor.

## WHAT THE SHARED CACHE ASSUMES ABOUT ITS SITE (read this before building any floor, portal or mouth)

`GC_CurtainDrop_Opening` holds final13 as of 30 Sep 16:22. It is ONE cache played at SIX sites: the Opening at P01, and
Interactions 1–5 at the mouths of P02–P06.

**It is world-true for P01.** The bake simulated against P01's stage front, and each placement just moves and turns that
result to a mouth: the root sits at the route start, yawed to the route's start tangent, at the Passage actor's z. So
every mouth must reproduce P01's stage front, measured from its own route start. What the cloth depends on is listed
below, then what goes wrong at a site that lacks each part.

Coordinates below are UE cm with x downstage-negative/upstage-positive from the curtain line, y across, z up. Sources:
the bake record `DropBake/final13_opening_a06_w188.json` (measured) and `Docs/StageFrontColliders_2026-09-28.json`.

**Stage version.** final13 simulated against commit c467046 ("v3", LF SHA-256 fc3a88…). It ran 09:32–14:37 on 30 Sep,
before v4 added the border at 14:52; the border sits above everything the cloth reaches. From 30 Sep every bake and
every ray test records the stage file's LF-normalised SHA-256, which equals git's blob hash.

| What the cloth relies on | Where (P01, cm) | What the cloth does there (final13, measured) |
|---|---|---|
| Curtain line and posts | posts x −20..+20, inner faces y ±950 (19.0 m opening) | Hangs 18.8 m wide (y −940..+940), 10 cm inside each post. |
| Header underside | z 1050 (x −20..+20) | Heading at z 1020 (drop 10.0 m + lift 0.2 m). The pleats span x −41..+39. |
| Upstage border (v4) | x +45..+50, z 1020..1100 | **DECIDED, 30 Sep: KEEP at 10.2 m.** This is Gary's choice, "Keep at 10.2 m", made in the conductor session and relayed here by Puss · Conductor (v2); I did not hear it directly. So the stage stays v4, and final13's top_masked and stage_clear verdicts stand against it. Masks the top edge's gaps. **NOT a collider in final13's bake** (its log: 18 boxes = v3; v4's 19th is the border). The "6 cm clear" is a comparison of two records, not an observation or a constraint: the hang reaches x +39.1 at frame 479, and the top never exceeds z 1019.98 (0.2 mm under the border's bottom). **The clearance is on the border's side, designed against THIS cache.** Touching the HANG needs BOTH a face at or below x +39.1 (more than 5.9 cm downstage) AND a bottom below z 1019.98; either one alone clears it (records compared, geometry inferred). Moving UPSTAGE keeps the masking with the same bottom, since sightlines over the top keep rising (inferred), provided the top rises too: sightlines under the header reach about 10.69 m at x +50. Raising the bottom at x +45 re-opens the comb (10.35 m: 157 rays, measured). **The FALL, measured 30 Sep (`stage_clearance_cache.py`, every vertex, all 331 frames):** no cloth enters the border, header or posts in any frame. Inside the border's footprint (x +45..+50, full width), the highest the cloth ever reaches is **z 812.5 cm, at frame 501**, as the falling cloth swings upstage 0.7 s after the release. So at its current x, the bottom could come down to about 8.1 m before even the fall touched it; that far down is a look question. Corrected 30 Sep: an earlier line said "lower OR move downstage". |
| Stage floor | z 0 (x −150..+250), then "ground beyond" z 0 to x 5400 | The hem hangs at z 20. The pile lies on z 0, up to 99 cm high, reaching x +467 upstage. |
| The lip (trough) | x −150..−115, z 0..25 | The pile spills over it. |
| The fascia | x −155..−150, z −120..0 | The spill hangs down it to **z −71**. |
| House floor | z −125..−120, downstage of x −155 | Not reached (the spill stops at z −71). |
| Lip lamp housings (16) | x −145..+325, y −841..+758, z −11..+43 | The pile's footprint (x −190..+467) covers them, so it presumably drapes over them (inferred: the footprints overlap; not seen). |
| Mouth side returns | y ±1300..±1305, x −150..+250 | The pile spreads to y −1072..+1091 (wider than the opening), inside the returns. |

**What goes wrong at a site that lacks a part** (inferred from the numbers above; not rendered at any such site yet):
- **No floor at z 0** (a void, as P03 has had since the landscapes were deleted on 30 Sep): the pile is drawn where it was
  baked, so it floats in the air over nothing. The fall looks the same until it lands.
- **A floor at another height**: the pile's lower layers sink into a higher floor, or float above a lower one, by the
  difference. The hem's 20 cm clearance changes the same way.
- **No lip or fascia (a flat floor)**: the spill that hangs down P01's fascia to z −71 at x about −150 to −190 either
  sinks into a floor that carries on downstage, or floats if the floor stops at the curtain line. **One shared cache
  cannot fit a lip-less mouth.** Gary's sheet B0c: (a) a P01-like stage front at every mouth, or (b) per-site bakes.
- **A lip at another x**: the spill folds over the wrong line and hangs in the air or through the lip.
- **A narrower or wider opening**: coverage is 10 cm a side at 19.0 m. All six portals are 19.0 m (Rig, 30 Sep). Wider
  leaks at the sides; narrower pushes the cloth through the posts.
- **A lower header or no border**: the comb of notches returns over the top. The ray test `mask_raycast_stalls.py`
  measures any stage file.
- **No lamp housings where P01 has them**: the pile shows the drape over objects that are not there. Small dents; the
  first to notice would be a close camera.

**P03 MEASURED (30 Sep 17:10, `probe_mouth_surfaces.py`, read-only, instance by instance over the pile footprint).**
- Structure 03 (ground on since 12:25) BUILDS P01's stage front at P03's mouth. From the curtain line:
  - forestage x −150..0, top 0 (89 instances);
  - portal pieces (3; lip trough to 25);
  - ground from 0 to +906, top 0 (139);
  - stage front with fascia and house floor, top −120..0 (250; P01 has 192);
  - understage at −255.
- The lamp-housing fixtures differ: 2 in the footprint at P03 against 5 at P01, so there would be small phantom dents.
- **But the oak plane "Passage 03 - Floor" (top z −5.0, 1 cm thick) runs from 84 m downstage to 451 m upstage.**
  Downstage of the lip, EVERY sample's top surface is that plane at −5, so it buries the fascia below −5 and the house
  floor at −120.
- At P01 the equivalent "Passage 01 - Opening Floor" STARTS at x −150, the lip, and leaves them exposed.
- So at P03 the lip EXISTS (B0c is not "no lip" here). The pile's spill down the fascia (to z −71) is cut off where it
  enters the oak plane at −5: it clips, it does not float.
- **Trimming the oak plane to start at the lip (x ≥ −150 from P03's route start), as at P01, makes P03's mouth match P01's
  stage front, and the shared cache fits.** That is Rig's geometry.
- Measured separately: the oak plane under the ground is invisible there (the ground's top 0 is above −5).

**AFTER RIG'S TRIMS (30 Sep 17:42; probe v2, every mouth in its own route frame, read-only, map clean before and after):**
- House-side top (x −200..−155), which the spill needs below −72:
  - P01 −120, P04 −120 (reference);
  - **P03, P05, P06 −119** (the new oak house floors): clear;
  - **P02 −5: fails, RETAINED** by Gary ("Leave P02 for now").
- Lip 0..25 and forestage 0 at every mouth.
- Two site differences inside the footprint:
  - P03 has 2 Structure fixtures at x 68–156, top 87 cm, where P01 has none. The pile passes through them (inferred).
  - P04's ground shows the understage (−255) at 18 of about 855 samples, the open chariot slots, which the pile bridges.
- **I2 rendered at P03** (17:44): hold frozen (200→399 0.008), no pop at the release (399→400 0.049, 400→402 0.086),
  down by 450. At 499 the pile lies on the forestage with the spill hanging down the stage front to the oak house floor,
  as at the Opening: not floating, not cut off.
  - Two dark lumps in the pile are probably those fixtures (inferred).
  - Picture: `RenderCheck/interaction2_final13_contact.png`.

**To make a new site fit the shared cache**: reproduce the table relative to that mouth's route start. Otherwise, bake
that site against its own stage (`COLLIDER_ORIGIN_CM`, as P04's backcloth was) and give it its own cache.

## 30 Sep (16:20): final13 PLACED at the Opening and all five transitions

- **Approval, recorded as it happened**: Gary, relayed by the Conductor at 16:20, "OK place the cloths". The placement
  was INSTRUCTED BEFORE he viewed the pile. The video was resent for review.
  - The acceptance tool now labels this a "RECORDED OVERRIDE", not "by eye".
  - If the pile is wrong, revert from the backups and re-bake.
- **Import**: `GC_CurtainDrop_Opening` now plays final13; one asset feeds all six sites.
  - Measured read-back: frames 450–780, `release_in_cache_s` 1.0, axis check clean, MI PatternWidthM 37.629 (18.8 m track).
  - It passed the stage-hash check (v4, border in).
  - Backup `PreBakeImport-GC_CurtainDrop_Opening-20260930-162139`.
  - `MI_CurtainVelvet_DeepRed_Drop` is also the parent of Rig's border material. The pattern-width change reaches it:
    invisible on black (inferred), noted to Rig.
- **Transitions**: fit at `hold_at="release"`, lead 4.0 s: each holds bake sample 479 until 16.0 s, then falls.
  - Five sequences saved; backup `PreTransitionDrapes-20260930-162304`.
  - `verify_transition_fit`: ok, all eleven checks true at I1–I5.
- **Opening**: `opening_hold_at_release` applied. HOLD 0–49 is a one-tick window at 23200 ticks (sample 479), FALL
  49–299 from the same point (ends 10.97 s < 11.0 s), PILE 299–375.
  - Read back equal to the plan. Backup `PreOpeningHoldAtRelease-20260930-162328`.
- **Rendered check** (`rendered_check_drape.py`, measured): Sequencer posed twice per frame (the GeometryCache rule), two
  captures each, from the stalls seats, no exposure override.
  - Opening: the two captures agree to a mean 0.02–0.23 of 255. The hold is frozen (20→48→49: 0.04–0.05), the release
    starts with no pop (49→50: 0.10, 50→52: 0.49), and the pile has settled at 350.
  - The top edge's gaps between pleat crests show the BLACK border, with no bright slots.
  - Interaction 1 (P02, rotated): hold 200→399→400 at 0.09–0.12 (capture noise in a dark scene), release 400→402 at 0.28.
    At frame 450 the curtain is down with the jungle revealed.
  - Pictures: `Saved/CodexSoftGoods/RenderCheck/opening_final13_contact.png`, `interaction1_final13_contact.png`.
- **P03 (Interaction 2's mouth)**: final13 is placed there (read-back: P03's route start, within 1 cm and 0.01°), but
  its PILE is unchecked.
  - Deliberately DEFERRED (the Conductor, 30 Sep). Gary approved "remove all landscapes and replace them with the floors"
    (`Docs/Conductor/RUNTHROUGH_NOTES_2026-09-30.md` §5), so the Wet Ground the pile would be judged against is going
    away. A PASS today would outlive its floor.
  - Order: the P03 floor first, then the rendered check at I2's pile frame.
  - Measured: the shared cache's pile spills over P01's lip to about −71 cm (pile AABB z −0.713 m). On a flat P03 floor
    with no lip, that spill hangs in the air whatever the check says. So P03 needs either a P01-like stage front or its
    own cache; a single shared cache cannot fit both.
  - The END-of-P03 curtain (the P04 pattern) waits on Rig's P03 hangar and site. Nothing is to be baked before Gary
    judges final13's pile.
- **Side effect**: capturing (spawning and destroying the transient capture actor) left the MAP dirty with no intended
  change. It must NOT be saved. Quit the editor without saving.

## 30 Sep (14:00): THE CURTAIN TOP DOES NOT MASK (a comb of notches), the adaptive release, and a fourth gate

Each claim below is marked with its evidence: **measured** (a test was run and read back), **declaration-proven** (read
from a file, header or config) or **inferred** (reasoned from numbers, not run).

**The finding.** The pieces:
- The bake hangs the heading at 10.20 m (drop 10.0 + lift 0.2; bake script l.72/181/188, declaration-proven).
- The pleats reach 41 cm upstage of the curtain line (final9 frame 479, measured).
- Rig's header is x −20..+20 cm with its underside at 10.50 m (portal_drape_alignment.json).

So wherever a pleat's top sits behind the header's back face, a sightline from the stalls can clear the drape top and
still pass under the header. This was inferred first by hand, then measured.

`Scripts/mask_raycast_stalls.py` is an offline ray test on the baked cloth plus Rig's colliders. It casts one ray per
two pixels from the stalls eye and counts the rays through the portal opening that reach 2.5 m upstage unmasked, split
into side, top, bottom and interior. Measured results:
- final9 (the final13 recipe): a **21-notch comb** over the top, 4,132 samples, pixel rows 138–196. The bottom is masked
  (the floor catches the rays under the hem).
- The **live** Opening cache, final2 at its held frame 120: the same comb, plus side wedges and a lifted hem, because
  that frame is the mid-sway one.

What the comb shows depends on what is behind it. Measured by overlaying the notch mask on Look & camera's no-drape seat
captures (02:04 editor state, not show-evaluated), as luminance mean / p99 on 0–255:
- **Opening: 28 / 146. Bright:** the lit gilded relief shows as a row of bright slots.
- P02: 6.6 / 118, a green lantern glow behind the centre notches.
- P03–P05: p99 10–15, invisible HERE.
- P06: p99 22.

**The fix, measured on final9's hang raised by an offset:**
- Raised 0.5 m (heading 10.7 m): the top is masked, except the 17.77 m corner, which the 18.8 m track closes.
- Raised 0.4 m (heading 10.6 m): a sliver remains.
- Moving the heading downstage cannot work while it stays at 10.2 m (inferred).
- A 10.5 m drop is 0.5 m more cloth, so the fall changes. That is **Gary's** decision; the pictures went to him.

**The adaptive release** (`RELEASE_AUTO=min:max:limit_mm:window`, a6f151a). The hang **surges**, so it is not a smooth
settle. final9's per-frame series shows 2.0–2.9 mm/frame for 10–20 frames between quiet spells of 0.4–0.6, with peaks
decaying only about 0.2 mm per 100 frames. final11 passed with a 3.29 mm surge at f340. So a fixed release is a lottery
on whether a surge lands in the 30-frame window.
- The bake now watches its own motion. At the first quiet window after `min`, it **moves the release keys** there. The
  export window, the at-rest window, the clip and the frame count all follow.
- **Moving keys mid-bake is safe, measured.** On a coarse strip, keys moved from 60 to 46 at frame 40 gave a result
  bit-identical, over all 90 frames, to keying at 46 from the start. That is also the first evidence of run-to-run
  determinism: two processes, 2 threads, identical output.
- **Trap:** Blender 4.4 keeps the object's and the shape keys' curves in ONE slotted action, and the legacy `.fcurves`
  lists only the first slot. Walk `action.layers[].strips[].channelbags[].fcurves`.
- Replayed on the old series with `min` 360: final9 would have released at 393 and final11 at 457. Dense final10 never
  finds a quiet window, so the dense recipe is out.
- Launcher: `DropBake/run_final16_auto.ps1 -DropM 10.0|10.5`, final13's recipe plus the adaptive release.

**The fourth machine gate** (8f554a3): **TOP MASKED** is required for full-width Opening-type drapes. It runs the ray
test on the bake's frozen sample and re-uses a result only for identical .abc bytes. Consequences:
- final9 now also fails top_masked.
- final13 and final14 hang at 10.2 m, so they **fail it by construction**. They ship only if Gary accepts the comb, as a
  recorded override.

## 30 Sep (13:00): final9 and final10 judged; a prediction for final13/14 registered BEFORE they land

final9 and final10 are 17.77 m test pieces, so both fail coverage (0.615 m to each post). The deliverable pair is
final13/final14 at 18.8 m. Both used the same recipe: pleated_switch at amount 0.6, hem guide 0.7, release at frame 480.

| bake | at-rest window max (mean), mm/frame | under 2 mm from | hang | verdict |
|---|---|---|---|---|
| final9 (standard) | **2.02** (1.39) | 13.0 s | bulge/flare 1.00, folds kept | FAIL (still by 0.02, coverage) |
| final10 (dense) | **6.93** (5.59) | never | bulge 1.00, folds kept 1.0/0.97 | FAIL (still, coverage) |
| final11 (P04, for reference) | 1.59 (1.25) | 10.7 s | | PASS |

The dense cloth hangs perfectly but never settles. It moves at 14–16 mm/frame through the whole pre-release run.

**Registered at 12:56, sent to the Conductor, before either landed:**
- final13 (standard, 18.8 m): at-rest max 1.8–2.4 mm. A coin toss at the limit.
- final14 (dense, 18.8 m): fails stillness at about 6–8 mm.
- Both pass coverage and hang.
- **Wrong if** final14 is under 2 mm, or final13 is over 3.
- A near-miss goes to the Conductor as the frozen frame plus the number. The Conductor decides and it is recorded as an override. The threshold does not move.
- If both fail, the lever is a longer settle: release at about 600 instead of 480, with the cache start following. That costs about 1.5 h of bake.
  (Corrected the same day: a whole 900-frame bake is 5–6 h. The 1.5 h was only the added cost.)

**RESULT, final13 (landed 14:37), measured:**
- still **PASS at 0.9 mm/frame** (mean 0.73; under 2 mm from 0.2 s). **The prediction was wrong on the low side.** The
  18.8 m, 23-fold hang is far quieter than final9's 17.77 m, 21-fold one. (The "wrong if" clause, above 3, was not hit,
  but the 1.8–2.4 range missed.)
- hang PASS; coverage PASS (0.101 m per side).
- **top_masked FAIL**: 4,105 rays, the comb.
- The pile needs Gary's eye.

final13 is a complete candidate in every respect but the comb. final14 had not landed at the time of writing.

**RESULT, final14 (dense; landed 14:49, judged 17:28), measured:** still **FAIL at 8.95 mm/frame** (mean 6.49; never under
2 mm). **The prediction ("fails at about 6–8") was right in direction and missed its range high by about 1 mm.** Hang,
coverage (0.10 m per side), top_masked (against v4, with the border) and stage_clear all pass. The dense recipe stays
out: it never finds a quiet window.

**The comb has a fix that needs no bake (measured on final13, frame 479):**
- An UPSTAGE border at x +45..+50 cm, bottom 10.20 m, lets **0 rays** through. Rig's proposed 1020–1100 also gives 0, and
  so does a top at 1090.
- Bottom at 10.35: 157 rays leak.
- A header lowered to 10.20: 324 leak.
- A downstage border must come down to 9.65 m, hiding the top 55 cm of the curtain.
- Contact: the cloth's highest exported point is 10.1998 m, at R−1, and it only falls afterwards. The hang reaches 0.391 m
  upstage, 6 cm short of the border.
- Rig is costing six black slabs. The file every bake simulates against changes when the border enters it, so bakes and
  ray tests now record `colliders_sha256`, and the gate re-casts when the stage bytes change.
- The import refuses a top_masked PASS judged against a stage that has since changed.

**The in-level Opening cache is final2_stage_v2. Provenance measured end to end, 30 Sep 15:10:**
- The saved `GC_CurtainDrop_Opening.uasset` carries its own import record: RelativeFilename
  `DerivedAssets/CurtainCloth/Baked/CurtainDrop_Opening_final2.abc`, `FileMD5 687572618c16e10bbbe2545cc36a4d38`.
- That equals the MD5 of the .abc on disk.
- The .abc is byte-identical (SHA-256) to `DropBake/final2_stage_v2.abc`, the only final2 bake with a cache (the other
  final2 ids have JSON only).
- The cache spans frames 120–450, as that bake's export window does.
- The Opening sequence (`probe_opening_cache_provenance.py`, read-only) holds the first sample (frame 120) for 1 s, then
  plays from 120: about 1 s of pre-release swing before the release at 150.
- All five transitions use the same asset.
- Python does not expose the import MD5 (`AssetImportInfo.source_files` is not a property), but the saved file carries
  it. Grep the .uasset for `"FileMD5"`.

**Gary described both of its faults from PIE, unprompted, before seeing any measurement:** "doesn't have a setting where it
holds still, and it's already kind of mid motion bunched towards the centre". "Doesn't hold still" is the frame-120
mid-sway hold. "Bunched towards the centre" is the measured side wedges (43k ray samples, the edges drawn in). That is the
third time on 30 Sep his eye matched a measured criterion, after the pile verdict and the straight-versus-flare hang. It
is the best evidence that the acceptance gates measure what a director sees.

**final15 (the guided traveller, landed 14:52): FAIL, and PARKED; it was the last traveller bake until Gary gives it a
site.**
- still 17.81 mm/frame at the start (under 2 mm only from 13.0 s).
- end 6.5 mm/frame, even with ×10 air damping.
- hang passes (flare 1.00, bulge 1.02).
- The stacks open to only 11.96 m clear against a 14.17 m design (about 3.6–4.0 m per side instead of 1.8).

## 30 Sep (night): three overnight bakes, the traveller, and what is blocked

Gary, via the Conductor: "The main thing I need to get right is the first part of the bake - a still acceptable
curtain that can be extended in its stillness for as long as I need". So EVERY bake now has the following:
- an 18 s settle after the gather;
- a 1 s still window before anything moves;
- `still_window_max_mm`, the largest single-vertex move per frame in that window. The target is under about 2 mm per
  frame, and a bake that fails it is not placed.

The bake's first sample is then looped for as long as a cue needs, with a one-tick HOLD window.

| id | what | changes from final2 |
|---|---|---|
| `final3_settled` | the Opening drape re-baked to settle | release at 570 not 150; export, clip and show start at 540; `SETTLE_PROBE=480` |
| `final4_dense_pleats` | ~40% more pleats, the same weight and fall | as final3 plus `CURTAIN_FOLD_WAVELENGTH=0.607` (0.85 / 1.4); `FULLNESS` stays 2.0, so the fabric per metre is unchanged |
| `final5_traveller` | the side-opening traveller (Gary: "doesn't fall, but like a normal curtain, opens slowly to the sides") | `Scripts/bake_curtain_traveller.py` |

**The traveller** is `Scripts/bake_curtain_traveller.py`. It imports `bake_curtain_drop.py`, so the fabric, solver,
colliders, renders and export are the drop's, not a copy.
- **Two halves** in one cloth object, as two islands, so self-collision handles the centre. The halves overlap by
  0.4 m on tracks 15 cm apart, with the left half downstage.
- **A ripplefold heading.** Carriers sit at the pleat nodes, and the heading between them bows as a stadium. Closed,
  that is a smooth S-wave. Stacked, it is a comb of U-loops one carrier pitch (7 cm) wide, so the stack never pinches
  the fabric tighter than the self-collision distance.
- **The opening.** The lead carrier moves offstage with a cosine ease over 12 s. The carriers bunch behind it as a
  compression front.
- **The heading is pinned KINEMATICALLY** (weight 1.0) and never released. Its path is animated by one shape key
  every 2 frames, cross-faded linearly. The weights are checked to sum to 1 at every whole and half frame (build
  refuses otherwise).
- **The flat sheets are laid out from each leading edge outward**, so the gather never crosses the halves.
- **Measured as well:** end stillness (`end_still_max_mm`, the last 60 frames, so the OPEN stacks can be held too);
  the clear opening; stack width and depth; hem clearance; worst extents against Rig's posts.
- **Renders** include the Opening's stalls camera, emulated at 15 mm on Super 35.
- **Assumed size, a look question left to Gary:** a 17.77 m track, as the drape. The stacks are 1.8 m per side at the
  heading, leaving a 14.2 m clear opening. They sit INSIDE the posts (±9.5 m), so they frame the stage. The hem is
  5 cm off the floor.

Smoke test (`traveller_smoke`, 27 cm quads, short settle): the mechanism works (closed, then two halves, then stacks)
and the key-weight error was 3e-8. At that resolution the lower fabric spread the stacks to about 3.2 m wide and
±1.1 m deep, and nothing had time to settle. So the smoke's numbers are not the result.

**The fit is APPLIED and VERIFIED (30 Sep, 01:43, on Gary's go-ahead).** All five Interactions (the shadow-puppet
Interactions ARE these five) have the drape at their mouth. Each cuts to its mouth's tagged stalls camera, with HOLD
0–375 on a one-tick window, FALL 375–500, and the fire-safety rig keyed off. The marker is
`PUSS_SOFTGOODS_FIT_VERIFY|ok=True`.
- The read-back caught a real fault in the first apply: **`set_actor_location` on a spawnable TEMPLATE does not
  persist**. All five were saved at (0,0,0), which would have been the Opening's stage front. The fit now writes the
  root component's relative transform.
- The backups are `Backups/PreTransitionDrapes-20260930-014009` and the one from the re-apply.
- The five drapes still play the OLD cache. One re-import into `GC_CurtainDrop_Opening` upgrades them and the Opening
  together, provided the new window is 330 frames with the release 1 s in.

**The hang was wrong, and it has been fixed at the method level (30 Sep, 02:00–02:30).** Gary asked for a "dignified
and stable still set of nicely sculptural pleats", with ripplefold photos, and "structured hanging profile, the good
fall we already got". A coarse 29 s hang showed a FLAT-rest cloth on the pinned heading flares, and merges its pleats
into soft swags within 1.5 m of the heading, so `final3_settled` / `final4_dense_pleats` are NOT to be placed. They
finish as full-width controls. A hem guide (`HEM_GUIDE_WEIGHT`) stops the flare but not the merging.

**`REST=pleated_switch` fixes it.** The mesh is pleated, so the hang is true columns. From the release, a Flat key
plus `use_dynamic_mesh` ramps the rest shape to flat over 0.5 s, so the pile keeps no pleat memory.
- Coarse proof, identical hang: `pswitch_coarse_hangfront.png` shows 21 folds at every height, depth kept 99–100%,
  flare 1.00.
- `pswitch_coarse_34.png` is a loose heap; `pleated_coarse_34.png`, with a plain pleated rest, is regimented rows.

The acceptance test is `Scripts/report_overnight_bakes.py`. A bake is placed only if all three pass:
- stillness under 2 mm/frame;
- the hang: flare at most 1.15, fold count kept at least 0.75 and depth kept at least 0.5 at 75/50/25% height;
- the pile within 25% of final2 (or, at P04, the site).

In flight: `final6_columns`, `final7_columns_dense` (0.607 m pleats) and `final8_backcloth_p04`. The backcloth is
10 m wide with a 12 m drop at x 10450; 12 m spilled off the passage floor at ±9.67 m. Alongside them runs an 8-run
full-resolution strip sweep (`sw_*`), the evidence.

## 30 Sep (12:10): the spawnable drapes are NOT late. Frame-count test in PIE, pre-registered

The hypothesis was that the transition drapes, as spawnables that decode their first frame asynchronously, would draw a
few frames late, so the Passage shows first (Gary: "misloaded wings followed by cloth"). Tested at real time
(Saved/CodexSoftGoods/drape_first_frame_test.py; Scripts/analyse_drape_first_frame.py): the show plays across the
boundary into Interaction 1, with dense and sparse screenshot runs. **The drape is DRAWN at tick 0 in both runs**
(curtain-red 86-88% of the frame centre against a 90% reference; tick 0 ran at 38-44 ms, not a stalled frame). The
hypothesis is dead, so fix (a) (level actors at each mouth) is NOT needed for the reveal. It remains an option only
for making "fall the curtain" a Master-time event.
**Observed, and handed to Look & camera (not a cloth fault):** at TICK 1 the view is, for one frame, a different camera
(an empty dark box with a grid floor, no drape). The transport's handover is logged one frame after the boundary
(`INFINITY_HANDOVER … source=SceneCameraCut`, frame 7732091 against a start of 7731265). Frames are in
Saved/CodexSoftGoods/DrapeFirstFrame/.

## RULE (30 Sep): a coarse bake can only FAIL something, never PASS it

27 cm quads (CURTAIN_QUADS_PER_BOLT=5) are for catching broken mechanisms quickly, not for clearing a recipe. Today
they misled in BOTH directions:
- They exaggerated fold merging, because they can't resolve a 0.85 m pleat.
- They falsely CLEARED the traveller's 0.4 m track gap: 0.06 mm/frame coarse, 24 mm/frame at full resolution
  (final12), with the halves still crossing by 1.79 m.
A fast green is the most seductive result there is. Accept a recipe only at full resolution. Strips (full resolution,
narrower) are valid for comparing recipes against each other, and for per-area pile properties, not for shape or
width.

**The traveller is parked.** final15_traveller_guide (hem guide in the hold, released as it opens) is the last bake
until Gary gives it a site. A site sets its lens, its seam distance and its masking, so a fourth bake before that would
be guessing at a target. Whatever final15 shows, its OPEN stacks will read as DAMPED, not settled; a pass does not mean
the stacks are solved.

## 30 Sep (13:00): the "standing curtain" at P04 was a stale frame after a jump, not the cache

Rig's bench showed a full-height curtain standing over the backcloth's pile after the fall, while the component's bounds
already reported the pile. It was NOT the cache: the .abc holds one object, a pile at the end. It was not temporal AA
either (0.00% difference with it off). **Geometry Cache frames decode asynchronously.** A jump requests an undecoded
frame, the proxy keeps drawing its last one, and only the next request after the decode shows it. Continuous playback
is unaffected.
- **For any capture of a GC:** pose, tick, RE-POSE the same time, then capture. Repeated captures without re-posing stay
  stale.
- **OPEN, a real show behaviour:** after a transport JUMP (a rehearsal scrub, reverse navigation, or the Arrival's first
  evaluation after one), a cloth may show a stale frame for a frame or two. Check it with PIE at real time: jump into
  and across each cloth's window, and screenshot the first frames.

## 30 Sep (10:30): THE P04 BACKCLOTH IS PLACED (final11), and the recipe that got it there

**Recipe, for every falling cloth from now on:** `REST=pleated_switch`, `REST_SWITCH_AMOUNT=0.6`, `HEM_GUIDE_WEIGHT=0.7`,
bending 5, final2's fabric.
- The hang holds pleated columns from heading to hem, and the hem guide holds it still (0.41 mm/frame on strips).
- At release the rest shape goes 60% of the way to flat and the guide lets go, so the pile keeps no rows and is not
  thrown flat.
- 0.6 was a GUESS that held, not a derived choice (Docs/Conductor/PREREG_SWITCH_AMOUNT_2026-09-30.md: the amount sweep
  came back U-shaped and inconclusive).
- Pile numbers from 6 m strips transfer per area (layers, fold size) but not in shape (height, depth).

**final11_backcloth_p04_a06:**
- 10 m track, 12 m drop, cloth line x 10450 at P04.
- Still 1.59 mm/frame (a thin pass; the hold wanders 1.4–3.7), hang perfect (12 folds everywhere).
- Site: 3.05 m short of the hinge, 1.25 m inside the boards, resting on the floor. Settles 5.4 s into its 10 s fall.
- Placed by import_passing_bake.py as "P04 Backcloth (baked)" (GC_CurtainBackcloth_P04; manual_tick, running, no
  looping). Axis exact, map saved clean.
- Rig's G2/section script drives it: BackclothLeadS 3.0 s (the whole cloth is under the 1.80 m lens 2.20 s after
  release), release-in-cache 1.0 s.

**Coverage:**
- The straight columns hang at EXACTLY track width, so 17.77 m leaves 0.615 m to each post: Gary's light leak.
- All six portals are 19.0 m and coaxial with the drape, so 18.8 m tracks (final13/14, due about 15:30) serve the
  Opening and every transition.
- The fit's mouth yaw at distance 0 is load-bearing at that width, because P02 curves.

## 28 Sep (night): the goal is WEIGHT and a WIDE pile, and the Blender drop bake

Gary reset the goal: "heavy, rough cloth... a wider pile than on top of itself... not a pile of virtual
silk falling into a thin slice of space". The mechanism is free, and he approved baking the fall in Blender.
The tool is `Scripts/bake_curtain_drop.py` (headless Blender 4.4, the SAME pattern code, all settings as env
vars). It measures the settled pile in metres: depth, width, height, footprint, LAYERS and FOLD SIZE.
Renders go on phone cards via `Scripts/drop_bake_card.py`, clips via `Scripts/drop_bake_clip.sh`, and
tables via `Scripts/drop_bake_summary.py`. Outputs are in `Saved/CodexSoftGoods/DropBake/`.

What the scouts found (27 cm quads; pictures checked before any number was trusted):
- **Compression.** Cloth that out-stiffs gravity is cardboard. The pleated sheet STOOD 10 m TALL ON ITS
  HEM with no pins. Blender stiffness is not normalised by mass, so it needs a heavy per-vertex mass
  (`VERTEX_MASS_SCOUT`, area-scaled) and low compression. Too stiff and it tips over whole as a "PLANK";
  too soft and it crinkles into a low silky "MAT". Both were shown to Gary.
- **Rest shape (Gary's catch).** A curtain MODELLED pleated has pleats as its rest shape, and they survive the
  fall. Blender's `rest_shape_key` has NO effect in 4.4. The working route is `REST=gather`: model it
  FLAT and gather the pinned heading onto the track with an animated shape key. It then hangs in soft swags,
  and after the fall the fold size rises from 0.42 m to 0.72 m (the pleat pitch is gone). The pile is FLATTER,
  because flat fabric wants to lie flat.
- **Thickness.** Self-collision 1 → 3 cm doubles the pile height (0.14 → 0.30 m) and rounds the folds
  (0.69 → 0.94 m). With a flat rest shape, thickness is what holds a pile up.
- **Creasing (Gary's catch).** 27 cm quads with zero thickness fold to knife edges. At 0.7–0.9 m folds,
  9 cm quads give ~8 quads per fold. Measured cost at 2.0×: 15 cm 15.7k verts ~1 s/frame; 9.1 cm 42.9k
  ~2–5 s/frame (~30 min a run); 7.6 cm 61.8k ~5–9 s/frame (~1 h).
- **Arithmetic ceiling.** ~12 m² of fabric per metre of track heaps to ~0.5 m, not more.
- **Chaos side, not yet tested.** PBD stretch is symmetric, with no compression knob, and BucklingRatio = 0
  (set 27 Sep) disables buckle-softening. The Chaos rest shape is already flat (2D rest lengths, FlatnessRatio 1).

Blender traps, each of which produced a plausible-looking wrong result:
- An animated Vertex Weight Mix does not release pins. Use weight 0.99 with pin stiffness keyed to 0.
- ANY data change to the cloth after the sim (adding a modifier, or creating its material at render time)
  frees the in-memory cache, so the "final" render shows the unsimulated or hanging pose. Build everything
  first, and render the final frame BEFORE stepping the timeline back.
- A/B results identical to every digit mean a disconnected knob, not a result.

## 29 Sep (night): held patch E, light-replication draw order (not a curtain item; recorded here as its author's log)

`ReplicateLightAttachmentsWithVariation` passed six random draws as FVector/FRotator ARGUMENTS, so the compiler chose
their order. `Scripts/check_light_variation_order.py` reproduces UE 5.8 offline: the seed is
uint32(CityHash64(FGuid)) ^ Seed, then the FRandomStream LCG, with FRandRange in double. Run on a read-only dump of all
261 Wing Pairs / 2676 lights:
- **Result:** P02's corridor (21 Wing Pairs, 126 lights, jittered copies of P02 Wing 001, Cue Desk "with variation",
  seed 0) reproduces exactly under RIGHT-TO-LEFT order (MSVC): translation 7e-12 cm, rotation 7e-16, intensity at float
  rounding. Left-to-right reproduces none, and the other rotator order fails at 4e-2. Patch E pins that order, keeping
  FVector::FReal.
- **SCOPE OF THE PROOF:** it proves P02's corridor. A passage varied under a DIFFERENT binary would show as "no match",
  not as a contradiction. No other passage matched in either order, so nothing else in the saved Show depends on the
  draw order. If a future dump shows a new variation match, re-run the checker before trusting the pinned order for it.
- **Same bug class, flagged to Rig (their file, InfinityStageStructureActor.cpp):** lines 747 and 1047
  (`FRandRange * FRandRange`) and line 1216 (`(FRand() < 0.5 ? 180 : 0) + FRandRange(...)`).

## 29 Sep (night): transition curtain, RE-SIZED after Gary's reframe (plan only, nothing built)

Gary: "since the interaction is a shadow interaction my idea was for it to happen on the curtain and to drop it and
enter the next passage"; "The interaction will be more like 60s and maybe longer, so the fall should happen after it".
So the curtain is not a device inside the Interaction; THE INTERACTION HAPPENS ON IT. It hangs for the whole segment,
the boy-and-cat shadow play runs on it, and only at the end does it fall and reveal the Passage.
- **Length is his and will keep changing.** Interactions go from 20 s to about 60 s or more; he lengthens the sequences
  himself. Every cue has bUseSequenceLength, so the segment follows each sequence's PLAYBACK RANGE. Hardcode nothing:
  - the drape's sections derive from that range: HOLD [0, end − lead), FALL [end − lead, end);
  - lead = about 1 s of hang, plus the fall and landing (about 4–5 s). It is a parameter, not a baked number.
- **A long hang costs nothing.** HOLD loops the cache's FIRST FRAME (the end-offset trick used in the Opening). A 60 s or
  5-minute hang needs no longer bake and no extra disk. The existing 11 s GC_CurtainDrop_Opening covers the release and
  fall.
- **Standing step after he changes an Interaction's length:**
  1. `fit_transition_drapes.py`: idempotent; re-places each drape's HOLD/FALL from the current playback range.
  2. The guarded Master rebuild, which moves everything after it (5 × 40 s = +200 s if all go to 60 s). Growing the
     Interactions is his content; the mechanism is offered, not the decision.
  - A test should assert "each transition drape's FALL ends at its sequence's end", so a stale fit fails loudly.
- **Placement:** the drape at Passage N+1's route start (its mouth). Portals are approved at ALL mouths (Gary), so ONE
  bake serves all five once Rig enables them. The camera cut runs from the Interaction's START to its end, to Look &
  camera's stalls camera for that mouth. The pile goes under the cut to the Passage rig.
- **The fire-safety rig** is made inactive (or removed), and the SavedFixturePIE Interaction block (retained Scene camera,
  active fire-safety mesh, the 0.61 keying) is rewritten in the same build.
- **Reopened by the reframe (not now):** a minute or more of shadow play makes the curtain's FRONT-LIT READ matter more than
  its fall. The heavy velvet was tuned for the fall. Whether a pale, matte show cloth should carry the scene is now a real
  question, and it goes to Gary with pictures.

## 29 Sep (evening): restart protocol, the stutter after a clean editor

- **Instrument fix first.** The Slate post-tick delta is CLAMPED at 125 ms (1/8 s), so every max_ms before 19:10Z read
  125.0 and spike magnitude was censored. `editor_frames.py` now times frames with a wall clock (perf_counter) and reports
  the clamped Slate delta beside it. The recorder unregisters cleanly: each of 12 recordings logged exactly one summary.
- **Results** (editor pid 45468, new binaries, PIE off, 450 frames each; wall clock):

  | Step | Mean | p95 | Frames over 40 ms | Max |
  | --- | --- | --- | --- | --- |
  | (1) Virgin | 21.5 ms | 34.2 ms | 13 | 217 ms |
  | (3) After Look & camera's read-only probe | 20.3 ms | 32.6 ms | 8 | 101 ms |
  | (5) After Rig's writes (6 refits, a save, captures) | 22.2 ms | 36.1 ms | 16 | 195 ms |
  | Afternoon's dirty editor, for comparison | 23.7 ms | 49.6 ms | 33 | (censored) |

  In the afternoon the spikes came on a steady beat about 1 s apart.
- **Reading:**
  - A milder periodic stutter (clusters every ~1–2.5 s) is INHERENT to a fresh editor.
  - One round of read-only or writing scripts did not rebuild the afternoon's heavier state.
  - That extra weight was either cumulative (hours of use) or removed by today's code. One restart cannot separate the
    two, so neither is claimed.
- **Traces:** `Saved/Profiling/Stutter_DirtyEditor_20260929.utrace` and `Stutter_CleanEditor_20260929.utrace`.
- **Still missing:** `stat unit` (Game, Draw, GPU) during a spike.

## 29 Sep (late): Opening fall fixed; Scene 1 full length; the stutter measured

- **Opening fall fixed.** The drape template's GeometryCacheComponent had `running = False`, which I set to stop
  auto-play, and that froze the GeometryCache track on frame 0. The bench (`opening_fall_bench.py`) showed identical
  frames. With running on, frame 150 is fallen and frame 350 is the bake's pile. Saved on Gary's "yes fix" (backup
  `PreOpeningRunningFix-20260929-142225`) and re-proven from disk. Gary in PIE: "curtain fell ... and it looks ok".
  Traps: memory `ue58-geometrycache-sequencer-traps`.
- **Scene 1 plays its full 210.8 s.** Every cue already had bUseSequenceLength = true. The cut came from LS_DevScene_01's
  PLAYBACK RANGE (0–15 s) against its LS_Animals_1 shot section (to 210.8 s). `scene1_extend_rebuild.py` sets the playback end
  from the shot SECTION end, rebuilds, and verifies 13/13 at 0.000 s. Show total 993.4 s (16:33). Scene 3 is untouched: its
  LS_Clams section is placed for 60.58 s of a 119.93 s shot, which looks like Gary's trim, so it is his call. The lasting fix
  is in the compiler: ResolveSceneDuration = max(playback end, latest nested shot SECTION end). Section, not child: a
  trimmed section is a decision. Queued for a build.
- **Cloth gate, measured** (`cloth_gate_measure.py`, PIE copies only). Suspending the six Shore drapes removes their
  end-tick (4–10 ms ×6 down to <1 ms). A/B mean frame: 30.2 → 24.3 ms; frames over 40 ms: 45 → 13. SUSPEND is the
  switch. `cloth_gate_apply.py` (level default suspended, plus an infinite RESTORE STATE track in LS_DevScene_03) is ready
  and needs Gary's yes. Python trap: `suspend_simulation` is the bool property and shadows the UFUNCTION.
- **The ~1 s stutter is periodic, and the show does not set its rhythm.**
  - Measured in all three states: PIE with the transport paused, PIE with toggles, and the editor with PIE off.
  - Things that change the SIZE of the spikes but never the RHYTHM: flicker light functions off (−1.5 ms mean, Gary's flicker
    decision priced), dynamic shadows off (−4.5 ms), VSM cache off (worse), MaxLightsPerPixel 32 (no effect), and
    instanced meshes hidden (−4.7 ms).
  - The hitch owner is the scene render on the game thread. In the editor it shows `UpdatePrimitive` and
    `FScene_EndFrame`, which look like render-state churn.
  - Ruled out: other editors, scene captures, BP lights (all 2450 lights are native), and effect sources (0 instances).
  - Gary says it is a regression. The leading bet is accumulated editor state, a leaked callback or similar. The test is
    a clean-editor recording at the next build.
  - Trace of the dirty state: `Saved/Profiling/Stutter_DirtyEditor_20260929.utrace`.

## 29 Sep (14:00): THE OPENING IS PLACED (Gary: "yes opening", typed in this session)

- `curtain_place_opening_and_transitions.py` with `DO_TRANSITIONS = False` (backup
  `Backups/PreCurtainPlacement-20260929-135157`):
  - level CineCamera "Opening — Stalls Camera": (−1400, 0, 150), +14°, 15 mm, HFOV 76.8°, focus off;
  - `LS_Opening_Curtain_Baked`: the Fire Safety rig is removed; "Opening Drape (baked)" GeometryCacheActor spawnable
    with HOLD 0–25 / FALL 25–300 / PILE 300–375 (tick 24000, 960 per frame, loop offsets 263040); Camera Cut 0–375.
  - It saved only that sequence and the level; dirty after [].
- `repoint_opening_rebuild.py` (backup `Backups/PreOpeningRepoint-20260929-135221`): cue 0 now points at the baked
  sequence, RebuildManagedMaster ran, and it saved only the Show and the Master. 13/13 sections matched before
  (0.000 s: the 12:56 rebuild held) and after, and the Master's first section plays LS_Opening_Curtain_Baked.
- **Tier: read-back, NOT rendered.** Nobody has seen the fall in Unreal yet. Watch:
  - frames 0–25 should show the hang;
  - the PIE view should cut to the stalls camera, then to P01 at 15 s;
  - the pile goes at 15 s, under the cut.
- **Known red until patch A is built:** SavedFixturePIE "Opening reveal establishes Passage 1 camera before lifting".
- **Revert:** point cue 0 back to `LS_Opening_Curtain` and rebuild the Master. The camera actor and the new sequence
  can stay, since nothing else references them.
- **Transitions: not touched.** Gary's redesign (via the conductor, 29 Sep afternoon): there is no curtain on scene entry. On exit the box
  rotates back, and a show cloth at the passage mouth carries the shadow play, then drops. The scrim/calico/velvet
  panels are in `Saved/CodexSoftGoods/ShowCloth/` (`Scripts/render_show_cloth_compare.py`), parked on Gary's
  "don't get distracted from end to end".

## 29 Sep (afternoon): the curtain at the front and at the transitions — IMPORTED; placement written, NOT RUN

Gary (via the conductor): "place the opening curtain where it's supposed to be (at the front and also in between
transitions)... functioning end to end".

**Why it wasn't "at the front":** every sequence curtain is `BP_InfinityStageSequenceCurtain`, a CAMERA-FOLLOWING rig
with the flat fire-safety mesh. In the Opening it sits 100 cm from the lens at 0.1 scale ("too close, focus off").
The Opening has no camera cut, so the transport shows Passage 1's camera, which starts at X = 0, ON the curtain line
(`InfinityStageTransportController.cpp`: "Establish the next Passage's frozen opening view behind the closed
curtain", with an authored Camera Cut taking priority).

**DONE (content only, `Saved/CodexSoftGoods/curtain_baked_import.py`):** under `/Game/Scenes/Curtain/Baked/`:
`GC_CurtainDrop_Opening` (final2_stage_v2, Blender frames 120–450, 11.0 s, motion vectors computed),
`SM_CurtainDrape_Hanging` (frame 121) and `SM_CurtainDrape_Pile` (frame 450), and `MI_CurtainVelvet_DeepRed_Drop`
(PatternWidthM 35.529, DropM 10, SeamWidthM 1.37). `M_CurtainVelvet` now has Used with Geometry Cache (backup
`Backups/PreCurtainBakedImport-*`). Source: `DerivedAssets/CurtainCloth/Baked/CurtainDrop_Opening_final2.abc`.
- **Axis check passed exactly.** Conversion is Custom, scale (100, −100, 100), rotation (90, 0, 90). The cache is
  world-true (curtain line at X = 0), so the actor transform is identity. Hanging frame: X −103.7…+69.0,
  Y ±888.5. Pile: X −468.6…+508.4, Y −1084.6…+1167.6. Both are the bake's own numbers to 0.1 cm.
- **Trap: UE numbers Alembic frames ABSOLUTELY.** The file holds Blender frames 120–450, so sampling "330" gave
  Blender frame 330, not the 330th frame. The first run's check caught it; nothing was saved from that run.
- **Trap: `mcp_request.py` times out after 30 s by default,** while the import keeps running in the editor. Pass
  `--timeout 900`, and do not re-send (a re-sent call queues and re-runs the script).

**WRITTEN, NOT RUN (the classifier blocks level/sequence writes without Gary's direct yes in this session):**
1. `Saved/CodexSoftGoods/curtain_place_opening_and_transitions.py`. It backs up the level and seven sequences first.
   - It creates a level CineCamera "Opening — Stalls Camera": (−1400, 0, 150), pitch +14, 15 mm on 23.76 × 13.365,
     focus off. This is Gary's 28 Sep stalls view, and it's a level actor because the transport locates a
     sub-sequence cut in the world.
   - It duplicates the Opening to `LS_Opening_Curtain_Baked`, which:
     - drops the fire-safety rig;
     - adds a spawnable "Opening Drape (baked)" GeometryCacheActor with three sections: HOLD 0–25 (first frame looped),
       FALL 25–300 (release lands on frame 50, as the old lift did) and PILE 300–375 (last frame looped);
     - adds a Camera Cut 0–375 to the stalls camera.
   - It swaps the mesh of the six transition rigs (Interactions 1–5 and Closing) from SM_FireSafetyCurtain_01 to
     SM_CurtainDrape_Hanging. The frame is the same 17.8 × 10 m, so the rig keys, distances and tests hold.
2. `Saved/CodexSoftGoods/repoint_opening_rebuild.py`: it repoints cue 0 to the new sequence, runs the guarded
   RebuildManagedMaster and requires the Master's first section to play LS_Opening_Curtain_Baked. The revert is to
   point cue 0 back and rebuild.
- **REAL vs STAND-IN:** the Opening gets the real baked fall. The six transitions get the velvet drape flying in and
  out on the old camera-following rig: a stand-in, with no fall.
- **Known consequences:**
  - The pile vanishes at 15 s. That's the cut to Passage 1's camera, so the pop is hidden.
  - `SavedFixturePIE`'s "Opening reveal establishes Passage 1 camera before lifting" will FAIL by design once the
    Opening authors a camera cut. The test needs updating to accept an authored cut.
- **Not covered:** the passage-end curtains (run-through note: the dusky end of the tunnel). They need a drape at
  each passage end that falls at the Scene's start, which means edits inside the Scene sequences.

## 29 Sep: Master rebuilt; two durable lessons

- **Master rebuilt** (`Scripts/rebuild_managed_master_guarded.py`, Gary's go after saving Scene 3). Before, every
  section from Scene 3 on was 520.098 s off (Scene 3: Show 272.455–337.997 vs Master 272.455–858.095). After, all
  13 sequence sections match their Show segments to 0.000 s. Only the Master was dirtied and saved. Backup:
  `Backups/PreMasterRebuild-20260929-125656`. Proven by read-back; `SavedFixturePIE`'s Closing assertion is
  predicted to pass but has NOT been run (it starts PIE while Gary works). Scene 3 now reads 65.5 s, not the "2 min"
  mentioned, so Gary should check it.
- **STANDING STEP: after changing any Scene's playback range, rebuild the Master.** The 14 Sep repair doc already
  said so and it was not followed, which cost the back half of the show. A note alone has failed once, so the fix is a
  TEST asserting every managed Master section equals its sub-sequence's own playback range, naming the cue
  (to write next; source-only; needs a build window).
- **Scene-scoped cost is a class of problem.** Two things measured today cost the WHOLE show for one place: the
  Chaos curtain preview (removed, `Backups/PreRemovePreview-20260929-123440`) and the six Shore drapes on the
  Scene 3 MetaHumans (13.4 ms of a 23.6 ms PIE frame, a stall in `FChaosClothComponentEndTickFunction`, every
  frame). The plan is to switch them off outside Scene 3 (keyable `bSuspendSimulation`/`bEnableSimulation`, the switch
  to be picked by `stat dumpframe` in PIE), driven by Scene 3's sequence with Restore State. The entry settle is Gary's
  look call.

## 29 Sep (night): plan for curtains at the transitions (Gary's morning brief), nothing built

Gary: "implementing the curtain in many of those transition areas ready for later different more tattered and
otherwise dramatic curtains to replace them in their fall to transition between scenes".
- **The slot exists.** `Saved/CodexCurtainAuthoring/author_sequence_curtains.py` gave all 7 sequence blocks
  (Opening, Interactions 1–5, Closing) a spawned `BP_InfinityStageSequenceCurtain` (an AInfinityStageCurtainRig) and
  a CurtainProgress track, and the Show holds each block's cover/handoff timing. A baked curtain belongs INSIDE
  that slot: a rig subclass with a GeometryCacheComponent plus a GeometryCache track. That keeps the transport's
  covered handoff and the tests' "exactly one curtain rig". Traps: the rig force-shows SM_FireSafetyCurtain_01
  when active, and it disables actor collision.
- **A fall only REVEALS.** The Opening covers from frame 0 and reveals 50–150 (the bake). Interactions COVER 0–50 then
  REVEAL 325–375. The Closing only COVERS 0–100. So Interactions need a fly-in before the drop (a small addition to
  the bake: keyed heading motion), and the Closing a fly-in without a drop. Fly-in vs appear vs cut is Gary's call.
- **One bake per distinct site geometry.** The bake is only as right as its colliders, and the stage front is defined
  for Passage 01 only. Identical sites can share one asset (instanced); different ones need their own bake
  (~2.5–3.5 h unattended each).
- **Cost:** imported caches are STREAMABLE (UGeometryCacheTrackStreamable: per-sample info resident, chunks
  streamed), so RAM follows what plays; disk is one asset each.
- **Swapping:** a Sequencer GeometryCache section stores its own asset reference, so swap by RE-IMPORTING OVER THE
  SAME ASSET PATH (no sequence edits) or with a one-field section edit. Start with one shared placeholder per
  block type; give a transition its own named asset when its tattered curtain arrives.
- **CONFIRMED 29 Sep (read-only, `Saved/CodexSoftGoods/segments_vs_master.py`): the Master is STALE from Scene 3
  on.** BuildSegments on a transient transport matches the Master exactly up to Scene 3's start (272.455 s). Scene 3
  is 160.375 s in the Show and 585.640 s in the Master, so every later segment is 425.265 s off (Closing: Show
  877.429 vs Master 1302.694). SavedFixturePIE scrubs to the Show's Closing + 4 s = 881.4 s, which falls between
  Interaction 3 and Scene 4 in the Master, so it finds 0 rigs. In PIE the transport lands 425 s off for every segment
  after Scene 3. Fix: RebuildManagedMaster (the library call, never the PussStageBootstrap.RebuildCurrentMaster
  test), with the Show and Master backed up and Gary's yes. The original hypothesis follows:
  SavedFixturePIE's failing "Closing sequence evaluates exactly one curtain rig" (1 expected, 0 found): segments are built from the SHOW; the Master (saved 21 Sep) lays Scene 3 at 585.64 s
  against a 160.375 s sequence, so every segment after Scene 3 may sit ~425 s earlier in the Show than in the
  Master, and the Closing scrub (+4 s) then lands outside the Master's Closing section. That fits it being the only
  curtain assertion that fails (Interaction 1, before Scene 3, passes). Check read-only: Segments[18].StartFrame
  vs the Master's Closing section start (frame 32567 = 1302.69 s).

## 29 Sep: Opening repoint preflight (read-only), and an anomaly in the Master (NOT curtain work)

`Saved/CodexSoftGoods/preflight_opening_repoint.py` (read-only; dirty set empty before and after; run after Wing
materiality's saves) compared every Show cue that has a sequence against the Master
(`LS_InfinityStage_V1Master`: 25 fps, 24000 tick, 0–32942 = 1317.7 s, 13 subsequence sections).
- **The Opening is consistent.** Cue 0 "Opening — Curtain" → `LS_Opening_Curtain`, sequence_owns_curtain true,
  15.0 s at 25 fps; Master section frames 0–375 = 15.0 s. The curtain holds closed 0–50 and flies out 50–150
  (CurtainProgress 1 → 0), so a replacement curtain must release at frame 50.
- **ANOMALY, cue 97 "Scene 3 — External Sound" → `LS_DevScene_03`:** its Master section is **585.64 s**
  (frames 6811–21452), against a sequence of **160.375 s**, 3.65 times as long. It is also the **only 24 fps**
  sequence in the show; every other one is 25. The other 11 sequence cues match their sections exactly. It is
  NOT known whether this is a deliberate hold/loop laid by the builder or a stale Master. It sits in the
  passage→scene→passage path Gary calls "clunky and buggy", but it has NOT been shown to cause that. It is carried
  into the transitions work (conductor). Consequence here: a full `RebuildManagedMaster` would re-lay it, so the
  Opening repoint is a NARROW edit: cue 0 in the Show plus only the Master's Opening section (0–375), retargeted to
  a 15.0 s / 25 fps sequence, which is what a rebuild would produce for cue 0. Do NOT use the
  `PussStageBootstrap.RebuildCurrentMaster` automation test: it rebuilds AND SAVES the Show and the Master.

## 28–29 Sep: the landing bounce (fixed) and the final bake

Gary on the true-speed take: "it does read as heavy... the bounce is off". Measured before theorising:
per-frame silhouette, then per-frame centre of mass (`Scripts/drop_bake_bounce.py`). The hem touches at
+0.2 s with no effect. The pile collapses at ~+1.7 s and THEN swells: COM +0.106 m, top +0.72 m. It happens at
9.1 cm only; the 27 cm scout rose 1.6 cm.
- **Cause: solver under-stepping.** QUALITY 10 → 20 with COLLISION_QUALITY 4 → 8 removes it (COM rise +0.001 m).
  COM crossings match the old fall to the frame down to 2 m, and the final pile is unchanged. Finer edges need
  more steps. Cost: ~2x solve.
- **Refuted:** self-collision/edge ratio (the swell is the same at 3 and 1.5 cm); impulse clamps (1.0 never engages,
  0.1 barely moves it).
- **Trades, not fixes:** bending damping 5 or 2 from release kills the swell but slows the whole fall into a sink.
- **Dead end, do not retry:** keying bending damping up at the collapse. The descent stayed bit-identical, then the
  cloth BLEW UP (top 6.2 m).
- The self-collision ratio check is a WARNING only. The approved take uses 3 cm on 9.1 cm edges.

**Final bake** `final1_q15_quality20`: the approved settings with only the solver fixed, and a real-time clip plus
Alembic (frames 120–330, simulated mesh only, 110 MB; take 1 was 5.5 GB because the export evaluated the
render-only subdivision + solidify). There is no bounce. After the heap forms (+1.6 s) it SLUMPS outward for ~4 s
to ~0.5 m high. Staging (full extents over every frame, UE cm, UE X = 100 × Blender y upstage, UE Y = 100 ×
Blender x): downstage −379 (lip at −150), upstage +435 (Wing 001 at 250), portal |Y| 1354 settled and ±1188
mid-fall (limit ±920), header 1000 (passes). All were still growing at +6 s. The drop has NO upstage bias:
Gary accepted a forward fall; the Chaos asset's upstage air was not carried over. An upstage throw
(THROW_M) moves the pile upstage, but the hem kicks downstage as the top goes over.

## 27 Sep: why the free fall was a "viennetta", and the guided fall

Gary rejected the first fall: "It should be a big crumpled heavy fabric sprawled on the floor, not a very
narrowly squished viennetta." Four off-stage benches (`Scripts/curtain_fall_bench.py`: transient
curtains at y >= 60000, runtime overrides through the ChaosClothAssetInteractor, one capture per few
ticks, full cleanup) found:

- **A free-released sheet cannot sprawl.** Released uniformly, a symmetric vertical sheet falls straight
  down and piles in its own footprint. Stiffer solver (8 iterations, 4 substeps), 2 cm/side
  self-collision, bending 0.3–0.5, no buckle-softening, a 4° lean, low friction and a real 2.5 m/s gust
  all still end as a strip. With the stiffer settings the pile first has volume, then **deflates** to a
  strip over ~200 ticks.
- **Guiding the heading works.** Keep the heading pinned (`CA_<STEM>`, fly mode) and carry the cloth
  component down (gravity-timed, s²) and forward over ~1.4 s, like a batten falling forward. The top edge
  folds over the body and the cloth lands crumpled and spread 2–3 m deep. **Forward distance is the dial**
  (0 m: narrow; 3 m, 6 m: progressively sprawled). Bench config: `Scripts/curtain_fall_bench_guided.json`;
  clip: `Saved/CodexSoftGoods/curtain_guided_fall_plain_vs_ragged.gif`. In the show this is a transform
  track on the cloth component; in the editor, drag the component down with Simulate In Editor on.
- **Heavy-fabric loft** (bench5, guided 4.5 m, plain): bending 0.8, no buckle-softening (BucklingRatio 0),
  3 cm/side self-collision at stiffness 1.0 turns the fine crinkle into broad heavy folds. Grip (0.9 cloth,
  0.8 floor) holds them, and damping plus 3 self-collision substeps adds crumple. A **faster drop (0.9 s)**
  billows on the way down and lands as the most crumpled, overlapping heap: the best match so far for
  "big crumpled heavy fabric sprawled". Clip: `Saved/CodexSoftGoods/curtain_guided_fall_loft.gif`.
- **WindVelocity is in m/s**, not cm/s ("a gust is above 8 m/s"). 250 means a hurricane.
- **Environment collision is gathered from the cloth's bounds, which are the reference pose.** A cloth lifted
  off the floor (even with bounds scale 2) fell straight through FloorCatch. The placed curtains land only
  because the hem touches z = 0. Unresolved.
- **The editor currently ticks at ~2.5 s idle** (background throttling plus intermittent 3 s HTTP stalls to
  generate_204), so cloth cost can't be measured until the editor runs in the foreground. The physics is
  still valid (Chaos clamps dt), just slow-motion.
- Setting a cloth component's transform through `set_editor_property` re-registers it, and its interactor
  never comes up. Use `set_relative_location/rotation(..., teleport)`.

## 28 Sep: THE PIN WAS WRONG ALL ALONG. Chaos re-sorts sim vertices

**Every guided fall before 28 Sep was from a mis-pinned curtain.** The heading selection used static-mesh
vertex indices (verified on the imported mesh), but **Chaos does not use the static mesh's vertex order
for its sim vertices**. Observed on running sims (in-situ settle tests plus an off-stage pin-order test):
Chaos orders sim vertices **column by column across the 2D pattern (low u first), bottom-to-top within
each column**. So the mesh's "top row" indices 0–146 pinned the bottom-up runs of the first two columns:
the curtain hung from its LEFT EDGE. Renumbering the source mesh (first-appearance order) changed nothing,
because Chaos re-sorts regardless. For the plain 147×67 grid the true heading is `c·67 + 66`; that holds
the whole top edge level (pin-order test, silhouettes). The indices always read back correctly on the
imported mesh, so this is invisible until a sim runs. Treat ANY index-based cloth selection or weight map
as suspect.

The sprawl, loft, breeze and gust bench findings were all measured on this mis-pinned cloth. They point
the right way but are not trustworthy numbers until re-run on a correctly pinned curtain.

**Fixed (28 Sep), and the fix cannot ship wrong silently.** The pattern cutter reproduces Chaos's sort
(2D pattern UV: u asc, then v asc) and writes `heading_sim_indices`, which the build pins; the mesh-order
`heading_vertex_indices` are still verified on import. Every pinned build must PASS the automated check:
`Scripts/curtain_pin_check.py` hangs each pinned curtain off-stage under its own lamp (the bench site is
unlit) for 120 ticks, and `Scripts/curtain_pin_check_score.py` requires ≥95% of the top edge within 8 px
and ≥95% of the width retained. Result: plain PASS and ragged PASS (100% held); a negative control (the
old left-edge hang) scores 26.6% and fails. Next: a position-based pin (UV-mask TextureToAttribute, then
vertex colour) as the durable replacement, validated by the same check. No position-based cloth selection
node has been found in 5.8.

## 28 Sep: the Chaos Opening (in a duplicate sequence)

Gary: the curtain doesn't follow the camera. It stands fully in front of every wing (x ≈ 0, just
upstream of station 1) and falls UPSTAGE. `Scripts/build_opening_chaos_sequence.py` made
`/Game/InfinityStage/Interactions/LS_Opening_Curtain_Chaos`, a duplicate; **the original
`LS_Opening_Curtain` is untouched** and Show cue 0 still plays it. The copy spawns:

- "Chaos Curtain" = `BP_CurtainChaosCloth` (a plain Actor with the pinned PLAIN cloth). Its actor
  transform track parks it at (0, 0, 0), yaw 90, then from frame 50 to 72 (≈0.9 s) carries it 1.8 m
  upstage and 995 cm down (s^1.5 / s² keys): the guided fall.
- "Curtain Floor" = `BP_CurtainFloorCatch` (a hidden WorldStatic box, top at z = 0, ignoring
  Pawn/Camera/Visibility/CatFloor).

Why not a subclass of `AInfinityStageCurtainRig` (the old Fire Safety rig): its constructor calls
`SetActorEnableCollision(false)` (a bare UPROPERTY Blueprint cannot flip, so a floor box inside it
is dead), it force-shows `SM_FireSafetyCurtain_01` whenever active, and the Interaction-1 automation
test counts exactly one rig. With `bSequenceOwnsCurtain` nothing outside the sequence reads
`CurtainProgress`.

The 1.8 m throw (not 4.5 m) keeps the ±888 cm pile in front of station 1's wings (x = 250, ±750).
Still open: persistence (a default spawnable pops the pile at 15 s), the camera pose and lens,
removing the x = 5400 preview (a level write), and repointing cue 0 (a Show write). All are Gary's.

**Breeze** (bench6): under 1 m/s, a breeze makes no measurable difference to the hanging 0.8 kg/m²
velvet. Mean frame-to-frame change: still 1.50, 0.3 m/s 1.48, 0.6 m/s 1.47, 0.6 m/s with drag 0.15
1.17. Not baked. Options: none, a 1–2 m/s gust timed at release, or a lighter-feeling fabric.

**Air at the release** (28 Sep, Gary's choice): the plain pinned asset carries a constant 1.5 m/s
wind UPSTAGE, in the cloth's COMPONENT space (upstage = local −Y for a yaw-90 curtain), drag 0.08
(`AIR_BY_STEM` in `build_curtain_chaos_asset.py`). Benched (bench8): inert while hanging (motion
1.41 vs 1.46 still), and it adds a subtle upstage billow once the cloth falls, so it is functionally
"air at the release" with no timing machinery. A scene Wind Directional Source (strength 1, speed 5)
did NOT measurably reach the cloth, so a Sequencer-keyed wind actor cannot deliver a gust. A literally
timed gust would need a small C++ component (a keyable float feeding the interactor's WindVelocity).
Not built.

## 28 Sep (late): the Opening fall goes THROUGH the floor, and Gary was right

The conductor captured `LS_Opening_Curtain_Chaos` by stepping the playhead one frame per tick. The
curtain slid down and vanished, and Gary said "it seems to fall through the ground". I predicted a
Sequencer teleport-with-reset. **That prediction was falsified.** `Scripts/curtain_teleport_drop_test.py`
reproduces the Opening arrangement off-stage: `BP_CurtainChaosCloth` with the correctly pinned plain cloth
stands over a SEPARATE `BP_CurtainFloorCatch`, and the cloth ACTOR is carried 995 cm down and 180 cm
upstage (s² / s^1.5) over 32 ticks. Variant A used `teleport=False` and variant B `teleport=True`. **They
are indistinguishable.** Both descend taut and rigid, with the hanging folds unchanged. The lower curtain
goes BELOW the floor instead of bunching on it, and only a small crumple near the heading stays above
z = 0. Frames are in `Saved/CodexSoftGoods/Frames/teleport_drop/`.

- **`UChaosClothComponent` ignores the actor/component `ETeleportType`.** It teleports only on its own
  `bTeleport`/`bReset` (Interp, so Sequencer-keyable), on `ForceNextUpdateTeleport[AndReset]`, or when
  one frame's move exceeds `TeleportDistanceThreshold`. That threshold is 300 cm on both BPs, and the
  rotation threshold is 0, which is off. The drop moves at most ~62 cm per tick, so it never auto-teleports.
- **A separate floor-catch actor did NOT catch the correctly pinned cloth.** It is unknown whether the
  in-actor `FloorCatch` (`BP_CurtainChaos`) does, because that has only been seen on the mis-pinned
  cloth. So **the guided fall has never been seen working on a correctly pinned curtain.**
- The conductor's per-tick scrub capture is not shown to be the cause. Whether scrubbing resets the
  cloth is a separate, unmeasured question.
- The rigid descent is not explained. Two suspects, neither measured: the default `LinearVelocityScale`
  0.75 (a quarter of the reference-frame motion is carried rigidly), and a drop that is slow in sim
  time (the idle editor ticks at ~2.5 s and Chaos clamps dt). If the drop is slow, the heading's
  acceleration stays under g and the cloth simply hangs taut from it all the way down.

(The "next steps" first written here are superseded by the section below.)

## 28 Sep (evening): moving the component CARRIES the cloth, so a guided fall cannot work

Five benches, all off-stage and transient, measured with SIDE ORTHOGRAPHIC show-only captures
of the cloth alone in base colour, so the z-range below ground and the upstage spread are read in
pixels, not by eye. Measure scripts: `Scripts/curtain_floor_bench_measure.py`,
`Scripts/curtain_carriage_measure.py`. Bench scripts: `Scripts/curtain_{floor_control,floor_timing,vscale,carriage}_bench.py`.

- **Floor control (six variants).** Every floor variant ends 75–80% below z = 0, against 98% with no
  floor. That includes a 400 cm-thick box and CCD on (read back as present), so it is **not
  tunnelling**. (The in-actor variant with `BP_CurtainChaos` never simulated, so it is void.)
- **Floor timing.** A floor RISING into a static curtain leaves a bulge at the slab's current
  height (z≈420), and so does a floor SPAWNED after the sim starts. **Environment colliders are live and
  late ones are gathered.** The thin 50 cm slab still passes through: my reading is that cloth caught
  inside is pushed out through the nearer face.
- **Velocity scale.** A transient in-memory copy of the plain cloth, WITHOUT the node, matches the
  saved asset exactly through the drop, so the technique is faithful. With `LinearVelocityScale` 1.0
  (read back as (1,1,1) from the running interactor), the result is **unchanged**: 0.42 s into the
  drop, the heading has come down 217 cm, free fall would be 86 cm, and the hem has come down 215 cm.
- **Carriage probe (the decisive one).** Heading jerked 300 cm UP in 0.25 s: the hem rose −1 → 299 in the
  same 0.25 s. Cloth cannot be pushed up. Sideways jerk: the hem arrives 300 cm across on the same
  tick, with no lag or swing, and identically at velocity scale 0.75 and 1.0. The free particles still
  drift ~11 cm in the baked 1.5 m/s air afterwards, so they ARE simulating.

**Conclusion.** Under Simulate In Editor, moving a ChaosClothComponent (by actor or by component)
moves the whole simulation frame, and the free cloth rides along with none of that motion felt as
inertia. That explains the taut descent, the hem welded to the heading, and the floor failure (the
floor slides up through a carried sheet). **A guided fall by moving the component cannot work.**
Untested: whether PIE or a packaged game differ. Rehearsal in the editor would not, either way.

**Candidate fix, which is Gary's decision:** move a BONE, not the component. Build a Root + Heading
skeleton (Blender, skeletal import through `FChaosClothAssetSkeletalMeshImportNode_v2`), with the
heading skinned to Heading, and parent the cloth under a SkeletalMeshComponent playing a short drop
animation. `bUseAttachedParentAsPoseComponent` is a plain component property, so no runtime hook is
needed. The component and reference frame stay put, as with any character's cape. **Unverified:** that
bone motion is felt as inertia. The current assets have ONE bone (Root), which is also the reference
bone, so no no-content test exists. The pin must be re-derived for the skeletal import (the pin check
covers that).

**Other facts from these benches:**
- The editor's tick delta is CLAMPED at 0.125 s. Any frame slower than that runs the sim in slow
  motion, so bench "seconds" are delta seconds, not wall seconds.
- Cloth cost, wall-clock with no captures: frame 333 ms with 3 curtains spawned, 340 ms with 3
  simulating, i.e. ~+7 ms for three (median of 19 each; p90 546 ms). The cloth is cheap; the frame
  was not.
- The environment collision config's `UseCCD` is present in the asset; `LinearVelocityScale` is not
  (there is no VelocityScale node).

**TRAP, which crashed the editor (28 Sep 17:09):** `SetSkinnedAssetAndUpdate` on a REGISTERED
Poseable or SkeletalMesh component with a Chaos cloth asset asserts
(`AssetSkeletalMeshObj || AssetSkeletonObj`, BoneContainer.cpp:163). The cloth asset has no Skeleton.
The same call on an unregistered `new_object` component passes, which is misleading. Never give a
cloth asset to a pose component; a pose parent needs a real SkeletalMesh with a Skeleton.

## Read this first: the rest-shape trap

**Chaos takes the cloth's rest shape from the 3D mesh by default.** Two settings:

| Node | Setting | Default | Must be |
| --- | --- | --- | --- |
| `SimulationStretchConfig` | `bStretchUse3dRestLengths` | `True` | **`False`**: rest lengths from the flat 2D pattern (UV0 × UVScale) |
| `SimulationBendingConfig` | `RestAngleType` | `Use3DRestAngles` | **`FlatnessRatio`**, `FlatnessRatio` = 1: flat at rest |

The mesh's 3D positions are the pleated *start pose*. With the defaults, those pleats become
the rest state and the solver holds them forever. That is the "creases drawn on in repeated
patterns" defect Gary rejected twice in the Blender route, in a different engine. **Shape the
start pose; let the solver make every crease.** The same rule applies to the pattern cutter:
raggedness is boundary topology made from non-repeating noise. Sine sums repeated about 11× across
the 35 m pattern and were thrown out.

## Files

| What | Where |
| --- | --- |
| Pattern cutter (Blender 4.4, headless) | `Scripts/build_curtain_chaos_pattern.py` → `DerivedAssets/CurtainCloth/Chaos/SM_<STEM>.fbx` + `<STEM>.json` + `<STEM>_pattern.png` |
| Weave maps | `Scripts/build_curtain_weave_maps.py` → `DerivedAssets/CurtainCloth/Chaos/Textures/` |
| Unreal build (textures, velvet material, mesh, Dataflow, cloth asset) | `Scripts/build_curtain_chaos_asset.py` |
| Place a scrubbable instance in the level (**needs the conductor's level slot**) | `Scripts/place_curtain_chaos_preview.py` |
| Unreal content | `/Game/Scenes/Curtain/Chaos/` |

`<STEM>` is `CurtainChaos_Ragged_Q15` (15 cm quads, ~15k vertices: interactive) or
`CurtainChaos_Ragged_Q09` (9 cm, ~41k: the bake resolution, for once the values are settled).

Unreal scripts run through the guarded MCP route: copy into `Saved/CodexSoftGoods/`, then
`python Saved/CodexMocap/mcp_request.py tools/call --params-file <request>.json`
(`ExecuteProjectPythonFile`, relativeSavedPath `CodexSoftGoods/<script>.py`). Each script
checks it is in the expected world, refuses to start if any package is dirty, saves only what
it made, and ends on an explicit `PUSS_SOFTGOODS_*_SUCCESS` marker.

## Rebuild

```bash
"/c/Program Files/Blender Foundation/Blender 4.4/blender.exe" -b --factory-startup --python Scripts/build_curtain_chaos_pattern.py
python Scripts/build_curtain_weave_maps.py
```

Then run `build_curtain_chaos_asset.py` in the editor. It re-imports the mesh and textures,
rebuilds the material in place, and deletes and recreates `DF_`/`CA_` (they are derived data).
Pattern knobs are environment variables: `CURTAIN_QUADS_PER_BOLT` (9 → 15 cm, 15 → 9 cm),
`CURTAIN_SEED`, `CURTAIN_FULLNESS`, `CURTAIN_RAGGED=0`. For the Unreal side, set `CURTAIN_STEM`.

## Pattern

- Flat pattern **fullness 2.0**: 35.5 m of fabric for a 17.77 m track, 10 m drop. UV0 is that
  pattern normalised 0–1. Chaos `StaticMeshImport` uses UVChannel 0 with UVScale =
  (pattern width, drop) in cm, so the 2D rest lengths are the real fabric's.
- Start pose: the fabric gathered onto the track in pleats. The gather is by arc length, so it
  starts unstretched, and pleat depth varies per pleat, never per vertex.
- Columns are sized so a **seam** falls on a grid line every **1.37 m** of flat fabric (one bolt).
  The material draws the seams from UV0.
- Rags: an aperiodic torn hem, 3–5 tongues torn well up, frayed sides, 4–7 tears ripped up from
  the hem (split edges, opened 4 mm so they cannot re-weld) and 5–8 holes. Cut edges are
  relaxed off the grid. Anything not connected to the heading is removed.
- **Heading** = the top row, tied to the batten. Its vertex indices go into the sidecar JSON;
  the build checks after import that every one of them is on the top edge.

## Physics: what carried over from the bakes

Relationships, not numbers. Blender's per-vertex mass and stiffness units do not translate.

| Relationship | Chaos |
| --- | --- |
| Will not stretch | `Stretch` PBD, stiffness 1.0, **area constraint off** (it resists compression → plate); tethers stiffness 1, scale 1 |
| Folds for free (Blender tension 200 / compression 3) | `Bending` PBD stiffness 0.05, **buckling stiffness 0.005** after buckling ratio 0.5 |
| Heavy, not jelly | Density **0.8 kg/m²** (heavy velour, about 25 oz/yd²). The Blender "7 kg/m²" was a solver artefact, not a fabric weight |
| No flutter | Damping 0.05, drag/lift 0.03 |
| Folds keep their structure | Self-collision on, friction 0.8 |
| Heading on the batten | `Selection` "Heading" (SimVertices3D indices) → `MaxDistance.InKinematic`; MaxDistance 10000 cm for everything else |

Tune in the graph (`DF_CurtainChaos_Ragged_Q15`) with the cloth running. Numbers that settle
go back into `PHYSICS` in `build_curtain_chaos_asset.py` so a rebuild keeps them.

## Velvet

`M_CurtainVelvet` / `MI_CurtainVelvet_DeepRed`: **Cloth** shading model, two-sided, with sheen
from Fuzz Color. The base is darkened face-on and lifts toward grazing (Fresnel), which is the
nap turning away, the cue that reads as weight under raking beams. Flat deep-red base
(Gary, 25 Sep), weave from `FireSafetyCurtain_01_WeaveDetail_v1` at 12 cm tiles and ~20%,
seams darkened along a 2.4 cm line. **Nothing is painted into the colour**: TextileV5 is a picture of a
whole curtain with crumples painted in and must not be used on simulated cloth.

## Engine traps (UE 5.8), each hit once

1. **MaxDistance defaults to 0 when no weight map is painted**, which freezes the whole cloth.
   Set Low/High high and pin with `InKinematic` instead.
2. **`DataflowBlueprintLibrary.EvaluateDataflow` returns False for cloth assets even on
   success.** Epic's `DF_StaticMeshClothTemplate` and `DF_EmptyClothAssetTemplate` return False
   too. Don't gate on it. The evidence of a build is `LogSkeletalMesh: Built Skeletal Mesh
   CA_…` plus the cloth asset's material slots, which the evaluation fills.
3. **`MaterialEditingLibrary.DeleteAllMaterialExpressions` deletes only about half per call**
   (15 → 7 → 3). Loop until `GetNumMaterialExpressions` is 0, or orphans pile up on every rebuild.
4. **The Cloth model's "Cloth" input (CustomData0) is not reachable from Python.** Go through
   `MakeMaterialAttributes`: its `ClearCoat` pin *is* CustomData0.
5. **Saving a cloth asset sets the Clothing usage flag** and re-dirties the material instance
   unless the base material already has `used_with_clothing`.
6. **Dataflow authoring is fully scriptable**: `DataflowEditorBlueprintLibrary.add_dataflow_node`
   / `set_dataflow_node_property` (ImportText strings, e.g. `(bIsAnimatable=True,Low=1,High=1)`)
   / `connect_dataflow_nodes` (pins `Collection`; terminal input `CollectionLods[0]`). Node type
   names are the struct names, e.g. `FChaosClothAssetStaticMeshImportNode_v2`. The cloth asset
   links to its graph through `dataflow_instance.dataflow_asset` / `dataflow_terminal`, a
   deprecated-warning property path that still works.
8. **A configured game trace channel is named by its display name in Python.** `ECC_GameTraceChannel1`
   = "CatFloor" is `unreal.CollisionChannel.ECC_CAT_FLOOR`; there is no `ECC_GAME_TRACE_CHANNEL1`.
   Also, `set_collision_response_to_all_channels(BLOCK)` writes all 32 slots, including channels
   not yet defined, and an explicit per-component response beats the channel's default. So FloorCatch
   ignores CatFloor explicitly (the cat must not stand on the cloth's hidden safety net).
9. **`suspend_simulation` is a bool PROPERTY in Python**: it shadows the SuspendSimulation function, so
   calling it raises "'bool' object is not callable". Set it with `set_editor_property`.
   `resume_simulation()` is a real method.
10. **To put a curtain back to rest, switch Simulate In Editor off FIRST, then suspend.** The other order
    undoes the suspend and leaves the curtain live-simulating in the editor (hit twice on 27 Sep, once by
    the conductor and once by this stream; both caught on read-back). `simulate_in_editor` refuses
    `set_editor_property` on templates: use `set_simulate_in_editor()`.
7. `ChaosClothComponent.bSimulateInEditor` is transient and per instance ("Simulate In Editor" in
   Details): switching it on never dirties the level. `bEnableSimulation` and `bSuspendSimulation`
   are Sequencer-keyable.

## State and proof (25 Sep)

- Built: the CA/DF/mesh/material/textures under `/Game/Scenes/Curtain/Chaos`. **Tier: saved
  read-back.** 7/7 assets load, the cloth is linked to its graph and carries the velvet MI, 0 dirty
  (`Saved/CodexSoftGoods/verify_chaos_curtain.json`).
- Placed (26 Sep, 01:57, approved by Gary): `BP_CurtainChaos` and one instance, "CurtainChaos
  Preview", in `L_InfinityStage_V1VerticalSlice` at (5400, 0, 0), yaw 90 (P01's world, currently
  dark: judge the velvet after Rig's back-thrown lamps). Simulate In Editor is off; switching it
  on is Gary's call. Read-back: one actor, the right asset, dirty 0/0. Backup
  `Backups/PreCurtainChaosPreview-20260926-0156`. This save also absorbed the conductor's
  capture-tool map flag (`absorbed_capture_map_flag`). The conductor's HOLD reached this stream
  only after the save.
- The actor's bounds extend about 128 cm deeper and lower than the geometry. Probably cloth bounds
  padding; not confirmed.
- **Disproven (28 Sep):** Chaos does NOT keep the static-mesh vertex order; see "THE PIN WAS WRONG ALL ALONG".
- **Not yet seen:** any rendered frame. The look, the weight and the frame rate are unverified.
- Not started: the sequencer swap (conductor's call), velvet/sack/hanging-cloth variants,
  peeling wing-edge strips, dust sheets.
- **Festoon retired** (26 Sep, 20:01, Gary's go): the "CurtainCloth Preview" actor at x = 4400 and
  `GC_CurtainCloth_Festoon_V1` are gone. Before deleting, the asset registry, a byte search of all 30
  LevelSequences and the in-memory bindings all confirmed the level was the only referencer.
  Backup `Backups/PreFestoonRemoval-20260926-2001` (the .umap + the cache, hash-verified). The fly
  bake `.abc` on disk stays as a record.
- **Plain variant**: `CA_CurtainChaos_Plain_Q15_Fall` (fullness 1.25, no rags) and
  `BP_CurtainChaos_Plain_Q15`, unplaced, for Gary to compare with the ragged one. This is the one that
  matches "heavy, thick… nothing too fancy, a core fabric rather than drapery".
