# P10 — stage front, S6 Void, ending (8 October 2026)

**Evidence key.** **[declaration-proven]** means readable source/config; **[binary-proven]** means saved UE package bytes; **[measured]** means an existing run record, read-back, or this offline repository census; **[inferred]** is a design conclusion still needing Gary or rendered proof. This pass was offline and authored no Unreal content, as required by the brief (`Docs/Conductor/codex_briefs/p10_stage_front_void_ending.md:1-3`). **[measured]**

## 1. Opening stage front / proscenium (job 1.2)

### What actually exists

- The memory at `c467046` was true on 28 September: the stage-front C++ was then unbuilt (`Docs/RigAndAtmosphere_Handover_2026-09-28.md:114-124`). It is not current: the later handover records portals enabled at all six mouths with full stage fronts, except S03's frame-only case (`Docs/InfinityStageSessionHandover.md:111-120`; `Docs/RigAndAtmosphere_Handover_2026-09-28.md:317-320`). **[measured]**
- The built substrate is functional scenery, not Gary's ornamental front: a 19 m clear opening, 10.5 m high, made from two fitted posts and a header, with forestage, fascia, house floor, trough and lines (`Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageStructureActor.h:262-305,329-367`; `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageStructureActor.cpp:1584-1606,1662-1768`). **[declaration-proven]**
- `PortalMesh` and `PortalMaterial` now let the frame stay timber while the passage rig becomes iron, but one mesh/material is fitted repeatedly to every structural member; these slots cannot by themselves express distinct painted Left/Right/Top ornaments (`Plugins/InfinityStage/Source/InfinityStage/Public/InfinityStageStructureActor.h:369-382`; `Plugins/InfinityStage/Source/InfinityStage/Private/InfinityStageStructureActor.cpp:1584-1596`). **[declaration-proven]**
- The existing black-velvet top border masks the curtain's comb; it is 19.8 m wide and presently still awaiting Gary's explicit keep/revert verdict (`Docs/RigAndAtmosphere_Handover_2026-09-28.md:804-817`). **[measured]**
- Gary's later direction supersedes the plain-frame look: the Opening portal must become “a proper baroque stage front (using wings)” (`Docs/Conductor/MORNING_SUMMARY_2026-10-04.md:194-198`). **[measured]**

### Reusable art and plans

- P01 already has a warm fairy-tale vocabulary of Baroque foliage and classical architecture (`Docs/FlatV3PassageCards_2026-09-30.md:37-46`), and current Flat V3 records name a rococo pair, `P01_L_1_roccoco_L` / `P01_R__1_roccoco_R`, plus classical pillar flats (`Saved/CodexFlatV3/swapkit/run_sk.json:41-230`). **[measured]**
- The historical audit records 14 stage-opening meshes, shared relief/edge materials and verified 10 cm depth under `/Game/Scenes/Wings/StageOpeningV2/` (`Docs/PussProjectTaskTracker.md:301-307`); a later read-only listing still contains `SM_SaltFormation_01_L_v2` there (`Saved/CodexFlatV3/probe_p05_labels_out.json:684`). The other 13 assets' present state and all current visual suitability are **UNCLEAR** because this pass did not open UE or render them. **[measured + inferred]**
- The existing geometry/collider contract and verification route are `Docs/StageFrontSpec_2026-09-28.md`, `Docs/StageFrontColliders_2026-09-28.json`, `portal_enable_apply.py`, and `verify_stage_front_readonly.py` (`Docs/StageFrontSpec_2026-09-28.md:28-38,52-82`; `Docs/RigAndAtmosphere_Handover_2026-09-28.md:127-132`). **[declaration-proven]**
- Fuser specs exist for one-piece arch rings and red-velvet/gold swag valances (`Saved/CodexConductor/fuser_specs/baroque_devices_2026-10-05.py:14-42`), but searches of tracked files, `DerivedAssets/FlatV3`, and the absent `FuserQueue` found prompts only, not generated job-44/45 outputs. **[measured]**

### Shortest build path

Keep the proven structural portal and cloth colliders untouched; add an Opening-only ornamental skin attached to Structure 01: the existing rococo L/R flats as side tormentors, with the existing velvet border as the temporary top. Build a dedicated arch/valance only after Gary approves that still. This avoids C++, a clean build, and a new cloth bake; a later authoring tool would still need record/backup, DRY/APPLY/REVERT, targeted level save, read-back and stills. **[inferred]**

Gary must choose: (1) rococo foliage/classical stone versus red-and-gold theatre velvet; (2) paired side flats plus valance versus a complete arch ring; (3) one flat plane versus two receding layers; (4) symmetric grandeur versus visibly handmade asymmetry; (5) keep the 19 × 10.5 m opening or lower/narrow it; (6) Opening only or a motif repeated at other mouths; and (7) keep the velvet comb-mask as part of the design. **[inferred; creative decisions]**

## 2. S6 — the Void (job 3.12, needed Sunday)

### Inventory and present state

- The offline plan's “nothing was run” header is stale (`Saved/CodexConductor/KlaraIngest/S6_VOID_PLAN.md:1-13`). The later record says run `KLARAVOIDS6-20261007-013108` applied, backed up, replaced the short `/Game/Scenes/LS_Void` shot with `/Game/InfinityStage/KlaraHookin/LS_Void_S6`, and made S6 219.56 s (`Saved/CodexConductor/KlaraIngest/klara_void_s6_record.json:175-223,652-653,1601-1608`). **[measured]**
- Authority assets are `/Game/InfinityStage/Dev/Sequences/LS_DevScene_06`, source `/Game/Void_content/LS_Void`, source level `/Game/L_KK_Void`, and applied spawnable copy `/Game/InfinityStage/KlaraHookin/LS_Void_S6` (`Saved/CodexConductor/KlaraIngest/klara_void_s6_args.json:6-20`). **[declaration-proven + measured by record]**
- The copy contains five static cameras, Klara's keyed `/Game/FX/NS_BeeSwarm`, and `/Game/MetaHumans/MHC_Elder_Female/BP_MHC_Elder_Female`; her body uses `AS_MHP_Void_woman`, with a face Control Rig (`Saved/CodexConductor/KlaraIngest/klara_void_s6_args.json:141-258`). **[binary-proven]**
- Current staging hides the hangar and our sky/fog, turns her directional and sky off, keeps her black-water floor and two 3/8 cd spots, and grows a glimmer from 1.00 to 6.16 s before handing to her swarm (`Saved/CodexConductor/KlaraIngest/klara_void_s6_args.json:31-51,329-402`; `Saved/CodexConductor/KlaraIngest/klara_void_s6_record.json:419-447,1352-1385`). **[measured]**
- The bee asset has no `User.` controls; timing the spawn window is the available density lever. The separate C++ swarm cannot render because its expected Niagara asset is absent (`Docs/Conductor/EFFECTS_PLAN_2026-10-07.md:42-55,143-155`). **[binary-proven + measured]**

### Draft beat outline

1. **0:00-0:04.16 — absolute black, then one distant glimmer.** Preserve the exact P06-dark seam; no floor or woman yet. **[inferred from measured seam/timeline: `Saved/CodexConductor/KlaraIngest/klara_void_s6_record.json:1352-1379`]**
2. **0:04-0:54.96 — bees establish depth.** Keep the first cameras sparse; reveal only fragments of the old lady at the track's 0:50.8 swell (scene 0:54.96). **[inferred from measured marker: `Saved/CodexConductor/KlaraIngest/klara_void_s6_record.json:468-485`]**
3. **0:54.96-2:00.12 — approach/recognition.** Let swarm motion lead the gaze; the woman becomes the still centre, never explanatory. **[inferred]**
4. **2:00.12-2:40.00 — trough to climax.** Reduce bee field at the trough, then let it crowd or orbit at the 2:35.85 climax; avoid general fill light. **[inferred from measured markers: `Saved/CodexConductor/KlaraIngest/klara_void_s6_record.json:487-503`]**
5. **2:40.00-3:39.56 — release into black.** After the track's 2:53.78 drop (scene 2:57.92), extinguish woman/floor, thin the bees, then hold true black before the Ending arrives. **[inferred from measured marker/end: `Saved/CodexConductor/KlaraIngest/klara_void_s6_record.json:505-512,652-653`]**

Gary must answer: what does the old lady do and mean; when is her face readable; which existing camera cuts survive; whether the black-water floor may ever read; swarm quantity/near-camera aggression; whether bees have sound; whether the 219.56 s duration stands; and how many seconds of terminal black precede the Ending. **[inferred; creative decisions]**

## 3. Ending (job 3.13)

### Reusable cast and existing destination

- S1 supplies Pig, Red Deer calf and Raccoon meshes in `/Game/KK_S1_Animals/L_Animals`, with eating, idle and run clips (`Docs/Conductor/S1_ANIMALS_SNAP_INVESTIGATION_2026-10-08.md:29-39,83-97`; `Saved/CodexConductor/KlaraIngest/census_report.json:453-493`). **[binary-proven]**
- S4 supplies `/Game/L_K_Children/Pigeon_Project/Pigeon/SK_Pigeon_01` plus two idles and a landing animation (`Saved/CodexConductor/KlaraIngest/census_report.json:14195-14196,14621-14623`); its live scene/copy are `/Game/InfinityStage/Dev/Sequences/LS_DevScene_04` and `/Game/InfinityStage/KlaraHookin/LS_Children_S4Hangar` (`Saved/CodexConductor/KlaraIngest/klara_reveal_s4v5_args.json:69-75,102-108`). **[measured]**
- S6 supplies the bee swarm, so bees can cross the black and disappear as the warm stage arrives (`Saved/CodexConductor/KlaraIngest/klara_void_s6_args.json:44-51`). **[declaration-proven; reuse is inferred]**
- The current 19-cue spine already ends S6 → Closing, and the existing Closing sequence is `/Game/InfinityStage/Interactions/LS_Closing_Curtain`; its scaffold and curtain-close track exist, but sweeping-up figures do not (`Docs/ShowBuildTodo.md:38,67`; `Saved/CodexConductor/S1Snap/LS_Master_sem.json:1440-1457`; `Docs/ShowCreativeTodo.md:41-50`). **[measured + binary-proven]**

### Staging options and estimates

1. **Recommended: bedtime tableau inside the existing Closing — 8-12 hours.** Black holds; the new ornamental proscenium appears in low amber worklight; pig, deer, raccoon and pigeon are already settled; workers remain implied; lamps go out upstage-to-downstage; the house curtain closes. No twentieth cue. **[inferred estimate; excludes rendered approval]**
2. **Gentle living stage inside Closing — 16-24 hours.** Same bookend, but the pigeon lands, animals wander/settle on short loop-safe clips, bees hand off into warm dust, and the camera makes one slow homeward move. Extra time is animation trimming, placement/collision and seam testing. **[inferred estimate; excludes asset repair]**
3. **A literal new Scene before Closing — 24-40 hours.** Add a twentieth cue and new Scene sequence/set/cameras, then retain Closing as the final shutdown. This best separates “lovely stage” from “closed up,” but expands the proven 19-cue spine and requires Show/Master rebuild plus full boundary regression. **[inferred from the measured 19-cue contract]**

Gary must choose the option, duration and music/silence; which animals recur; asleep versus playful; visible old lady/crew versus an apparently self-closing theatre; final camera ownership; blackout order; and the last image—curtain, sleeping animals, or one remaining ghost light. **[inferred; creative decisions]**
