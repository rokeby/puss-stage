# Scene exit → shadow play ON the curtain → drop (plan, 7 Oct, offline)

**Status: read-only investigation + plan. Nothing was run in Unreal (Gary in PIE).** Trigger: Gary ~17:55 UTC on
S4's exit, "excellent, with amendments", and "aim for this for all the scenes with shadow interaction"
(`CONDUCTOR5_LOG_2026-10-07.md:40-46`).

Tiers per claim: **[decl]** read in a file/header/record; **[meas]** an intervention + read-back (dated), incl. a
log line or byte search run here; **[inf]** inferred, reason given. Frames are 25 fps unless said.

## 0. Headline findings
1. **Gary's card removal is SAVED.** He removed the **"Sleight Hangar Shadow Card"** spawnable from
   `LS_Interaction_04_GetsAName`. The **mouth** card is still there. Gary saved it with the level at **17:05:10 UTC**,
   using an editor save prompt (`PussStage.log:9431-9441`, "InternalPromptForCheckoutAndSave … total 38.1 sec"
   `:9442`) **[meas: log]**.
   - A byte search of the saved .uasset finds the names "Sleight Mouth Shadow Card", both "Shadow Play Spot" names and
     "Sleight Hangar Drape", but **no "Sleight Hangar Shadow Card"**. `LS_Interaction_05` has both cards
     **[meas: grep -a, 7 Oct]**.
   - The 16:47 autosave already lacks the hangar card (`Saved/Autosaves/.../LS_Interaction_04_GetsAName_Auto1.uasset`)
     **[meas]**. So the removal came before 16:47.
   - The **level was saved in the same prompt** (`:9434-9435`). What, if anything, he changed in the level is
     **UNCLEAR**. The memory note "level saves persist evaluated state" applies.
2. **Consequence for our tools.** The I4 records are now stale: `curtain_sleight_record_I4.json`
   `created_binding_guids` includes the hangar card **[decl]**.
   - REVERT on either tool refuses when the live snapshot ≠ `snapshot_after` (`curtain_sleight.py:1117, 1135`;
     `shadow_play_spot.py:585`) **[decl]**.
   - V2G (7 Oct, 11 drape templates incl. both I4 drapes, `velvet_v2g_apply.py:1-30`) may already have drifted the
     snapshot too **[inf: depends on whether the snapshot covers template overrides]**.
   - **So nothing on I4 can be "reverted and re-applied" through the old records.** That path is restore-from-backup only
     (`Backups/PreShadowPlaySpot-I4-SPS-20261006-015508`, `Backups/PreCurtainSleight-I4-CST-20261005-111737`), and it
     would undo V2G and Gary's edit. Plan §4 uses an **in-place re-time tool** instead.
3. **Where the ~20 s tail comes from: UNCLEAR, narrowed to Klara's own LS.**
   - S4's nested slot plays her **whole** playback range: `her_range [0, 4920)` @30 fps = 164 s → Scene `[405, 4500)`
     (`klara_reveal_record_S4.json` plan.slot) **[decl]**. The range comes from `copy.get_playback_start/end()`, not
     from her last key (`klara_reveal.py@HEAD:1743-1745`) **[decl]**.
   - Our outro starts 13 frames (0.5 s) after the slot: hold `[4500, 4513)`, blink `[4513, 4612]` **[decl: record
     timeline]**. So a 20 s "nothing, then lights go off" sits **inside her last ~20 s** **[inf: Gary's order of events]**.
   - Her audio sections run to her frame 4920. Whether the sounds themselves are shorter, and where her last camera,
     animation and light key falls, was **not readable offline** (no key parser in the repo; `names_S4.txt` is a name
     table only).
   - Other parts ruled out as "the tail": the 60 s exit-block hold (reverted 5 Oct, `e8a7405`; the records are archived
     `.reverted-*`) **[decl]**. The S4 hangar hold only holds the pose, `[775, 4890)` (`s4_hangar_hold_record.json`)
     **[decl]**. S4's length is 195.6 s: Master S4 starts at tick 28482625 (`PussStage.log:8491`) and I4 at 33177026
     (`:9356`), Δ = 195.6 s **[meas: log]**.
4. **What renders the "shadows" today: nothing.**
   - Each Interaction has two plain lit 480×270 cubes ("Shadow Card", `/Engine/BasicShapes/BasicShapeMaterial`,
     `curtain_sleight.py:15, 95-99, 513-523`) **[decl]**. They sit 1 cm in front of each drape. The shadow-play spot
     (7483 cd, cast_shadows) lights them (`shadow_play_spot_record_I4.json`) **[decl]**.
   - No puppet, flipbook or light function exists. A byte search found 0 MediaTexture/Flipbook assets
     (`SCENE_EXIT_BLOCK_PLAN_2026-10-04.md` §2) **[meas, 4 Oct]**.
   - **Removing the cards loses nothing but a grey rectangle.**

## 1. Map: segment order and what exists per boundary

Order: … S1 → **I1** → P02 … S2 → **I2** → P03 … S3 → **I3** → P04 … S4 → **I4** → P05 … S5 → **I5** → P06 … S6 → Closing
(`CURTAIN_SLEIGHT_TRANSITION_PLAN_2026-10-05.md:19`) **[decl]**. Shadow interaction = **I1–I5**. S6 is "done
differently" (Gary, `MORNING_SUMMARY_2026-10-04.md` b66636a) **[decl]**. S3 is in scope ("done this way").

**The Interactions** (all sleights applied 5 Oct; records `curtain_sleight_record_I<n>.json`) **[decl]**:

| | run | len (f) | GO | spot | cards | fold placeholder lights |
|---|---|---|---|---|---|---|
| I1 | CST-…-003926 | 2183 | GO 10 @1675 | **none** (refused SLEIGHT_DRIFTED, e03a0d2) | both | S1 Ghost 60→0 |
| I2 | CST-…-111701 | 2226 | GO 20 @1675 | applied | both | S2 Ghost |
| I3 | CST-…-111719 | 2238 | GO 30 @1675 | applied | both | 50 lights (daylight, lattice glows, ghost) |
| I4 | CST-…-111737 | 1837 | GO 40 @1675 | applied | **mouth only (Gary)** | S4 Ghost |
| I5 | CST-…-111752 | 1837 | GO 50 @1675 | applied | both | S5 Ghost |

**Beat order inside every Interaction today** (identical frames I1–I5, `frames` in each record; I4 markers read
6 Oct, `interaction_curtain_probe_ICURT-20261006-223039.json` I4.markers) **[decl/meas]**:

```
0     CST wide: cut 1 "S<N> Sleight Hangar Camera" (I4: same pose as S4's Exit Handoff, 10668,240000,180)
0-250 S<N> Ghost Light ON at 60 cd (keys [0,60],[250,60],[1000,0])   <- a light pops on at the I-start [inf]
75    CST curtain in: hangar drape spawns high, FLIES IN 75->175 (z 1970 -> hung)
75    twin lantern 0 -> 117 cd over 75->175 (same window as the fly-in)  <- light on back wall BEFORE curtain is hung
75-275 camera push-in to the matched framing (lit)
150   spot spawned at 0 cd; 175-187 spot SNAPS up (fade_up_s 0.5) to 7483 cd   <- not "slowly"
175   CST play start (placeholder cards), 60 s
250-1000 fold placeholder: hangar lights linear to 0 (DURING the play)
1250  CST sleight: cut 2 -> "I<N> Sleight Mouth Camera" (matched pose to the mouth drape)
1300  hangar strike (drape/card/lantern/spot off, unseen)
1675  GO <n> curtain (HOLD); spot fades 1675-1700; drape FALL; PILE (I2/I3); walk-in from 1700
```

- Legacy markers are still present in I4: `InfinityStage.BoyCatStart` 75, `HiddenChangeover` 375,
  `CurtainRiseStart` 400 and `CurtainFullyOpen` 500. A "Curtain Rig - Fire Safety Curtain" binding is also present
  (probe I4) **[meas 6 Oct]**. Their effect under explicit cuts is inert (`InfinityStageTransportController.cpp:1612-1618`,
  per the sleight plan) **[decl, not re-read]**.

**The Scene tails today:**

| | Scene end content | lights off | dark move |
|---|---|---|---|
| S1 | Klara slot `[594, 5769)` | outro blink `[5782, 5986]` | glide out `[6001, 6151]`, exit cut → 6176 (247.04 s) |
| S4 | Klara slot `[405, 4500)` | outro blink `[4513, 4612]` (her 5–8 lights, gaps 0.3–0.6 s) | glide out `[4627, 4865]` 9.5 s, exit cut → 4890 |
| S2, S3, S5 | ours / Klara S2 hookin | **none in the Scene**; only I-fold 10–40 s, during the play | none |

Sources: `klara_reveal_record_S1.json` / `_S4.json` plan.timeline; outro config `klara_reveal_args.json` outro
(hold 0.5, blink_gap [0.3, 0.6], env_fade 2.0, glide 4.0, exit 25 f); `plan_timeline` `klara_reveal.py@HEAD:891-953`
**[decl]**. That S2, S3 and S5 have no Scene-side blackout is **[inf]**: no reveal record exists for them, and the
fold keys are the only lights-off found.

**Where the curtain is during the shadow scene.**
- Hangar side, 0–1300: the spawnable "Sleight Hangar Drape", world-keyed, at x 16768 (root-local 5600 = door face − 400).
  GC `GC_CurtainDrop_Opening` HOLD section `[75, 1300)` (probe I4) **[decl/meas 6 Oct]**.
- Mouth side, from 1250: "Transition Drape (baked)".
- **S4's hangar was resized today with depth kept at 6000** (`hangar_resize_s4_args.json` not_gary), so the drape plane
  is still inside **[decl]**. The probe predates the resize, so re-probe before writing **[inf]**.

**Can shadows land on the drape?** Likely yes.
- The drape material is the velvet family: **Cloth shading model, two-sided, opaque** (`ChaosClothCurtain.md:1044`)
  **[decl]**. Today it is the V2G override, parented to v2_DeepRed (`velvet_v2g_apply.py`) **[decl]**.
- The opaque Cloth model receives shadows and light functions like Default Lit **[inf: no engine .cpp, memory
  ue58-engine-source-limits]**. The translucency UNKNOWN in `ScrimFeasibility_2026-09-29.md:16` applies only to a
  translucent scrim, not to this drape.
- **Two in-repo mechanisms fit:**
  - **(i) Light function on the spot.** This is the spec's plan (`ShadowPuppetCaptureSpec.md:99-108`). Lights here take
    `SetLightFunctionMaterial` (`InfinityStagePassageActor.cpp:491-494`) **[decl]**.
  - **(ii) Shadow-only puppet meshes between the spot and the drape.** This is the Puss shadow-cat method: the mesh is
    drawn only into shadows, `CatMesh->SetRenderInMainPass(bDrawBody)` (`InfinityStageCameraRig.cpp:275`) **[decl]**.
- Neither needs a card.

## 2. Target sequence (common to I1–I5)

```
 Scene ... content end (TRIMMED) | (b) STEPPED BLACKOUT N steps | (c) DARK MOVE: camera to matched framing, |
                                                                   curtain already hung, rig settles, ghost=0 |
 Interaction: (e) lantern+spot SLOW fade-up ON the curtain | (f) shadow play on the drape (no card) ... SLEIGHT cut
 (invisible, mid-play) ... | (g) dim to the GO level | GO HOLD | (h) drape FALL (already the mouth drape) | pile | walk-in
```

| step | what | owner/tool | status |
|---|---|---|---|
| (a) trim | Klara Scenes: end the nested slot at her **content end**, not her playback end. Ours: n/a | `klara_reveal.py`: new arg `slot_end_her_frame` (or `her_tail_trim_s`) feeding `E` in `plan_timeline`; then `extend_scene_playback` shorten; then `s4_hangar_hold.py` re-fit | **needs extension + a read-only probe first** |
| (b) stepped blackout | N discrete intensity steps across ALL lit lights in frame (hers + our rig glows + ghost), last step = 0 | Klara Scenes: extend `outro` with `blackout_steps`, `step_gap_s` (today 1 step per light, `blink_gap_s`). S2/S3/S5: new **Scene-tail** keys (or the I's first seconds) | **extension / new** |
| (c) dark move | camera to the matched sleight framing **in the dark**; drape hung before any light | S1/S4: the existing glide-out (keep). In I: move fly-in + push to the dark interval (`fly_in_start_s`, `push_start_s` params exist, `curtain_sleight.py:118-122`) | **params exist, re-time tool needed (§4)** |
| (d) curtain present | "Sleight Hangar Drape" spawned **hung** from I frame 0 (no visible fly) | same | re-time |
| (e) slow fade-up | twin lantern + spot, **after** the drape is hung, over `fade_up_s` (Gary's call, e.g. 4–6 s) | `shadow_play_spot` `fade_up_s` exists (`:109`); lantern ramp is welded to the fly window (`[75,0],[175,117]`): needs a `lantern_fade_*` param | **param + extension** |
| (f) shadows on curtain | remove **both** cards (I1–I5); placeholder until puppets: light function or shadow-only mesh | new; light-function asset does not exist | **new (look call)** |
| (g) dim | spot/lantern dim to a GO level before the GO (today the spot fades 1 s *from* GO, `fade_out [1675,1700]`) | `shadow_play_spot` `fade_out_s`; add `dim_to` + `dim_s` | extension |
| (h) swap→fall→reveal | unchanged: sleight at 1250, GO, FALL, PILE, walk-in | existing | keep |

The ghost light pop at I frame 0 (60 cd keyed at 0 after S1/S4's `ours_off` until the Scene end) is folded into (b):
keys go to 0 at the end of the blackout and stay there **[inf: pop not yet seen in a capture]**.

## 3. What gets measured first (read-only, after Gary's PIE; no writes)
1. **Dirty and saved census** (`census_print_request.json`), plus a binding list of LS_Interaction_04 against the record.
   This confirms the card is gone and nothing else changed.
2. **Klara tail probe** (new, read-only, `load_asset` only, never evaluates). For her S4/S1 copies it reads the max key
   time over every channel, the end of each anim/GC/audio section, and `SoundWave.duration` for her 3 audio sections.
   That gives `content_end_her`, and tail = 164 s − content end. Pre-registered: if every last key is ≥ 160 s, the
   tail is **not** in her LS. Then look at `interaction` frames 0–175 instead (the I4 wide/fly, which Gary may read as
   "nothing").
3. **Interaction curtain probe re-run** (`interaction_curtain_probe.py`, exists, read-only) after the S4 resize.

## 4. Tools, DRY/APPLY order (per transition; I4 first, S4→I4 is Gary's reference)

New tool **`shadow_curtain_retime.py`** (Conductor; modelled on `curtain_sleight.py`/`shadow_play_spot.py` guards):
in-place re-key of **named** bindings in LS_Interaction_0N.
- Drape spawn at 0 and hung pose from 0.
- Camera at the matched framing from 0, or a dark push.
- Lantern and spot ramps after `hung + dark_hold_s`.
- Both cards' spawn tracks false, or the bindings removed.
- Ghost/fold lights to 0 before the first fade-up.
- `dim` keys before the GO.
- Marker moves (`CST …`); the cut ranges and the sleight frame are unchanged.

Its own backup (`Backups/PreShadowCurtainRetime-I<n>-<run>`), record and DRY snapshot. It **never** goes through
the old sleight/spot records (finding 2), but cross-checks that the matched-pose invariants still hold (reuse
`check_sleight` match rules via the `load_sleight_lib` pattern, `shadow_play_spot.py:56-70`).

Order (each its own approval; S4/I4 shown):
1. Census + probes (§3). **Gary closes PIE first; never end his PIE.**
2. **Trim (a), S4 only:**
   - `klara_reveal` DRY with `slot_end_her_frame`. **Coordinate with the S4-entry agent:** v5 `strike_preroll` is being
     added to the same tool. Wait for that commit; the trim is a REVERT+APPLY of klara_reveal S4 on the committed tool.
   - Then `extend_scene_playback` (shorten) DRY → APPLY → `SavedMasterMatchesShow`.
   - Then `s4_hangar_hold.py` DRY → APPLY: the range `[775, 4890)` must become `[775, new_end)`.
   - Then `SceneCutBindingsResolve`.
3. **Stepped blackout (b), S4:** the outro extension in the same klara_reveal APPLY as step 2 (one REVERT+APPLY, not
   two).
4. **`shadow_curtain_retime` I4:** DRY → APPLY (Interaction length changes only if the dark lead grows; then rebuild
   the Master in-tool, as curtain_sleight does, `curtain_sleight.py:24-27`).
   - Then `SceneCutBindingsResolve` → `SavedMasterMatchesShow`, singly.
   - Then **SavedFixturePIE** (`InfinityStageEditorAutomationTests.cpp:755-759`) as the regression control.
   - All six earlier SavedFixturePIE reds were fixture faults: name the assertion (memory).
5. **Look** (pre-registered PIE stills, conductor PIE only when Gary is out):
   - Frames: blackout steps; dark move; hung curtain with 0 light; fade-up mid/end; play; sleight ±5 f; GO; drop; P05
     frame 0.
   - −control: today's I5 (fly-in visible with the lantern). +control: two frames on one side of the sleight.
6. **Roll to I1, I2, I3, I5** with the same params.
   - I1 has no spot (needs `shadow_play_spot` APPLY first; its SLEIGHT_DRIFTED must be resolved).
   - S2/S3/S5 need a Scene-tail blackout writer (`scene_tail_blackout.py`, new, for Scenes without a Klara outro), or
     the blackout at the I-start in the dark (simpler; recommended for S2/S3/S5).
7. Commit tools, records and the doc (explicit paths only; never `-a`, never stash).

**Tests per step:**
- Offline harnesses with −/+ controls:
  - drape hung before the first nonzero light (must FAIL with today's I4 keys);
  - blackout step count = N, monotonic, last = 0;
  - no light > 0 between the blackout end and the fade-up;
  - cards absent or unspawned;
  - the sleight match is unchanged (5 cm offset → FAIL).
- Live:
  - read-back of every key;
  - marker `SHADOW_CURTAIN_RETIME_APPLY_OK|run=<id>` only after the read-back and save (memory: assert, don't print);
  - the census dirty set == {Interaction seq, (Master), level only if written}.

## 5. Risks
- **Keys are absolute** (`puss-passage-keys-absolute`). Shortening S4 moves every later Passage section. Patch K is
  built (test name `PassageKeysFollowSection` in the DLL, 2 Oct, per `SCENE_EXIT_BLOCK_PLAN` §3) **[decl, not
  re-checked]**. The `extend_scene_playback` KEY GATE may still refuse (`extend_scene_playback.py:27` ff.) **[decl]**.
- **Scene relength vs the hangar** (`hangar-rise-bounded-by-scene-length`). The hold must be re-fit after any S4 length
  change, or the hangar sinks to REST and the sky shows.
- **GeometryCache end-frame REST and stale-after-jump** (memory). Hanging the drape at frame 0 means its GC HOLD
  section must start at 0 on the hold sample. A jump into the dark interval needs re-settle (paused only).
  - Gate: a GC section start ≤ the first lit frame. Capture *after* a re-pose.
- **The camera moves in the dark but the lens and exposure must match at the fade-up.** S4's hangar PPV EV100 0.5 vs
  the show −3 (sleight plan G10) **[decl]**.
- **Gary's saved level (17:05)** may carry evaluated poses (memory: level saves persist evaluated state). Run the census
  before any write. The S4 "ROOT_NOT_LANDED" guards will catch a moved root.
- **The klara_reveal concurrency:** never edit or depend on its uncommitted v5. The trim parameter lands after that
  agent's commit.
- **Light function / shadow mesh under scrub:** light functions are material-driven (scrub-safe if frame-keyed,
  `ShadowPuppetCaptureSpec.md:101-104`) **[decl]**. Shadow-only meshes need keyed transforms. Both are unmeasured.
- **Trimming Klara's content** shortens her authored sequence, which by Gary's rule sets the Scene length
  (`klara-sequences-set-scene-length`). Trim only her idle tail. Her audio may be cut mid-sound, so a fade is needed
  (gate: no audio section ends with nonzero volume unfaded).

## 6. Look calls for Gary (recommendation first)
1. **Blackout steps:** *4 steps*: her practicals, then her keys, then our rig glows/ghost, then the last light. Spacing
   *0.8 s*, a hard step (no fade) per step. Alternatives: 3 or 6 steps; equal or accelerating gaps.
2. **Dark interval** before the light (camera and rig move unseen): *2 s* after the last step for S4 (the glide-out
   already gives 9.5 s); *3 s* for the Scenes without an outro.
3. **Spot fade-up:** *5 s* ease-in, starting *1 s* after the curtain is hung and still. The lantern and spot rise
   together (today 0.5 s snap / 4 s).
4. **Which curtain:** *keep the same red V2G drape* ("Sleight Hangar Drape", the twin of the mouth drape). It is
   required for an invisible sleight. Alternative: a different cloth would make the swap visible.
5. **Framing when the light comes up:** *already at the matched close framing* (the push happens in the dark), or the
   hangar wide on the hung curtain, then a lit push.
6. **Placeholder shadows until the puppets are shot:** *none* (bare lit curtain), a light-function test silhouette, or
   shadow-only cut-out meshes.
7. **Dim before the drop:** *to 30 % over 2 s* before the GO, then the drop. Alternative: today's fade from the GO.
8. **Remove the mouth card too** (I4) and both cards in I1–I3, I5? *Yes*. It follows from "shadows on the curtain".
9. **S4 tail:** trim to Klara's last action (pending the probe). Tell Klara?

## 7. Searched and found nothing in
- **An offline parser for Klara LS key times:** `KlaraIngest/*.py`, `census_report.json` (`sequence_facts` = name
  tables only). So the tail cannot be proved offline.
- **Any light-function, flipbook or MediaTexture asset for puppets:** per the 4 Oct byte search. Not re-run.
- **Any existing stepped-blackout parameter:** `klara_reveal_args.json` outro has only `blink_gap_s` (one blink per
  light); `curtain_sleight.py` DEFAULTS has only a linear fold `fold_start_s`/`fold_end_s`.
- **A Scene-side lights-off for S2/S3/S5:** none found. There are no reveal records for S2/S3/S5 in
  `Saved/CodexConductor/KlaraIngest/`.
- **What Gary changed in the level at 17:05:** the log shows only the save, no actor-delete lines in
  `PussStage.log:9380-9445` (filtered read).
- **An I1 shadow_play_spot record:** absent (`shadow_play_spot_record_I1.json` does not exist).
- **Whether velvet V2G is in the sleight snapshot:** not checked. That is why the in-place tool is recommended.
