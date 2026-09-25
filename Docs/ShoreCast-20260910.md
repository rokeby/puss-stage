# Shore cast — 10 September 2026

**Current delivery, 12 September evening (EDT):** all six MetaHumans are assembled, their full recorded takes are fitted and saved, and six draped copies are placed around the clam in the production level. `LS_Clams` now contains six separate body-animation bindings over its existing 797 frames at 30 fps. The chosen source sections play at 0.60 speed; the full animations remain intact. Four nearby mannequin originals are retained with their render components hidden; the separate distant mannequin group is unchanged.

The canopy defect is corrected: the sheet has a small crown attachment defined from actual cloth vertex positions, with the outer cloth free to fall around the shoulders. The deeply bowed Shore02 uses a separate gravity-aligned drape anchored to the moving head capsule's center, keeping its supported point above the skull instead of rotating out in front of the face. The other five use their crown/head socket. All six have private body collision assets with 3 cm extra head radius and 2.5 cm extra clavicle/upper-arm radius; the shoulder padding removed a visible sleeve intersection in the closer render. The full play-mode test passed at frame 795 with changing motion on every body and all six head attachments and cloth simulations intact (`Saved/CodexMocap/shore_clam_runtime_qc.json`). This establishes runtime motion and attachment; visual coverage is assessed separately in native rendered frames.

The saved production map was reloaded and all six body bindings, source animations, cloth assets and head attachments were read back successfully (`shore_clam_saved_delivery_audit.json`). The four retained original actors have serialized Hidden In Game flags and belong to `Shore_Retained_Mannys`. Editor-only layer visibility and Chaos cloth's **Simulate in Editor** are session state. After reopening the level, `Saved/CodexMocap/enable_clam_shore_preview.py` enables the cloth preview, hides that retained layer and pilots the review camera. Normal gameplay uses the saved actor flags and the cloth's BeginPlay setup.

Scene routing is already `DA_InfinityStage_V1Show` → `LS_DevScene_03` → `LS_Clams`. The Show's existing timing and camera cuts were preserved. `Shore Cast Review Camera` provides an additional view of the group without changing those cuts. The broader scene composition and lighting remain work under I.3; the character integration does not mark the entire Shore scene complete.

The dated entries below are session history. Earlier sign-in, assembly and placement blockers have been resolved unless explicitly retained in this current-delivery block.

**Final verification:** `shore_clam_runtime_qc.json` passed again after the shoulder-clearance change and saved-map reload, with 795 sampled frames and no attachment failures. The corresponding full editor review is `shore_clam_review_motion_qc.json` (run `1789259920`, nine rendered samples). `Saved/CodexMocap/Shore_Cloth_Corrected_Closeup.png` shows the corrected close drape. The original background CPU-throttle preference has been restored; the editor is left outside Play mode at review frame 300, with the group camera piloted. Original Show, source fabric, mannequin Blueprint and source sway sequence hashes remain unchanged; only the production map and `LS_Clams` changed among the seven backed-up originals.

**User-approved brief:** six pale, gaunt, pot-bellied adults: three men and three women. Five in their 50s and one woman around 25.

Gaunt faces and limbs with a rounded protruding abdomen; distinct faces and silhouettes rather than six identical bodies. Simple subdued clothing for the initial motion review.

| Character | Age | Height target | Source take |
| --- | ---: | ---: | --- |
| Shore01_M56 | 56 | 179 cm | shoreguy1 |
| Shore02_F52 | 52 | 166 cm | shoreguy12 |
| Shore03_M59 | 59 | 173 cm | shoreguy3 |
| Shore04_F55 | 55 | 160 cm | shoreguy4 |
| Shore05_M53 | 53 | 184 cm | shoreguy5 |
| Shore06_F25 | 25 | 169 cm | shoreguy6 |

Individual ages, heights and assignments are implementation starting points within the approved mix.

Planned asset root: `/Game/Metahuman/ShoreCast_20260910`.

Deliverables: six editable MetaHuman Characters, assembled Blueprints, six full-length animations fitted to the corresponding bodies, and a saved preview Level Sequence. Appearance and motion require rendered review, especially feet, hands and intersections around the abdomen.

**Additional user instruction, 11 September:** place the six characters near the existing clam, using the arrangement of the mannequin figures currently there. Put Chaos fabric over their heads in the same manner as the current Mannys. This is authorized scene integration, in addition to the separate review setup.

**Performance direction:** “They should sway with the cloths staying over their heads similar to how people eat ortalan birds, except they are gently swaying in their shame.” Interpret this as small, slow weight shifts and restrained rocking beneath Ortolan-style head drapes, with withdrawn posture and slight individual timing differences. Use the recorded shore performances as the source. Preserve the full solved takes and fitted exports; make any scene-specific timing, segment selection or motion adjustment in derived scene assets.

The fabric must keep covering each head throughout the sway. Retain or adapt the crown support/attachment that holds the drape in place, with the loose cloth moving softly around the shoulders and body. Validate the complete used motion in the clam scene for slipping, sudden cloth motion and conspicuous penetration.

Existing files found on disk: `/Game/Scenes/LS_Clams`, `/Game/Scenes/BP_OrtalanSheet`, `/Game/Scenes/CA__OrtolanSheets`, `/Game/Scenes/SM_OrtalanSheet`, and `/Game/Scenes/LS_OrtalanSheetSway`. Their current actor transforms, sequence bindings, attachments and collision sources still require live inspection. The old task tracker's statement that no cloth prototype exists is historical and must not override the current assets or this request.

Back up the affected level and scene assets before changes. Keep the existing fabric design and arrangement, adapt its attachment/skinning/collision to the six bodies, and verify the drapes while the shore animations play. Preserve recoverable mannequin originals during the replacement. Scene integration is pending; no placement or cloth adaptation has been performed yet.

**Current setup (11 September, 13:19 UTC):** PussStage restarted successfully with MetaHuman Creator enabled. MCP verified Editor PID 39312, the production map, the Creator subsystem, all eight saved mocap outputs and zero dirty packages. Creator Core Data is installed (29 preset assets, 38 hair items, default clothing and texture synthesis models).

The original content watcher incorrectly required `metahuman_content` in the installed manifest. UE5.8.2 left `InstallTags` empty despite completing the download overnight, so this check prevented the automatic restart. On 11 September the completed Launcher UI state and installed files were verified, the gate was corrected to use the completed manifest plus actual content, and the authorized restart was released. The corrected watcher collected the Creator and clam inventories successfully.

**Character progress (11 September, 13:29 UTC):** all six editable draft Character assets are saved under `/Game/Metahuman/ShoreCast_20260910/Characters/MHC_<id>`. Starting presets are Walter, Lani, Aoi, Grace, Lorenzo and Celeste respectively. Global lean/low-muscle settings were applied first, then limb and chest measurements constrained while increasing waist/high-hip measurements; pale skin settings retain the individual preset skin textures. The first character was reviewed in Creator with a visibly rounded abdomen and lean limbs. Full visual review of the other five, final age impression, assembly and motion remain pending.

The first joints-only rig request (`rig_shore_pilot.py`) opened Epic's browser authentication flow. No persistent Epic credentials were available for automatic login. The user has been asked to complete this sign-in; Computer Use must not automate authentication dialogs. Rig status is in `Saved/CodexMocap/shore_pilot_rig_status.json`. A returned request alone does not prove a completed rig: check the resulting asset and build readiness.

**12 September update:** Epic authentication succeeded at 21:25 UTC and the pilot's joints-only rig completed. Its 2K texture sources were downloaded and the Character asset saved at 21:48 UTC; `can_build_meta_human` then passed. Optimized/Medium assembly ran out of video memory at 21:50 UTC while another Unreal project was also open. No assembled output folder was saved. All six draft assets and renderer configuration were backed up under `Backups/PreShoreAssembly-20260912-174654` before this work.

The user closed the other Unreal instance and requested a retry with the same settings. With both Editors closed the GPU reported about 14.5 GiB free. A restricted-shell restart (PID 30488) paused at Zen cache initialization before loading the map. Automatic approval review rejected forcibly closing that startup; the user then explicitly approved closing only PID 30488 and retrying. That process was ended and PussStage relaunched outside the restricted shell as PID 41060. Graphics and assembly quality settings remain unchanged. The pilot rig and downloaded textures are saved on disk; post-restart read-back is pending.

The live clam inventory found eight `BP_OrtalanSheet` actors, a Manny skeletal component and a separate ChaosCloth component with approximately 1.64 relative scale. Neither the inspected Manny mesh nor cloth asset has an assigned Physics Asset. `LS_Clams` and `LS_OrtalanSheetSway` currently use 30 fps; preserve existing scene timebases when integrating. Clam and actor locations, component values and current sequence tracks are recorded in `Saved/CodexMocap/clam_setup_inventory.json`. No scene assets have been changed.

Creator also reports two renderer settings absent from the project: `r.GPUSkin.Support16BitBoneIndex` and `r.GPUSkin.UnlimitedBoneInfluences`. The installed UE5.8 header marks 16-bit support as universal/deprecated, but retains the setting for compatibility. Review and apply the required skinning configuration with a scoped config backup before final deformation validation; no configuration change has yet been made for these warnings.

Live Link Hub's temporary close-confirmation setting was restored byte-for-byte from `Backups/PreCloseLiveLinkHub-20260911-002359/DefaultEngine.ini`; its original read-only attribute was restored. The Launcher's original minimize-to-tray preference was also restored.

**12 September, 22:36 UTC recovery update:** PID 41060 successfully reloaded the pilot's saved rig and textures, but the second Optimized/Medium assembly exhausted system commit at 22:01 UTC (about 79.5 GiB committed; a 64 KiB allocation failed because the paging file was too small). The Editor exited after the fatal error. No assembled output was saved. This second failure was system RAM/pagefile exhaustion, distinct from the first video-memory failure.

The next launch opened the empty `/Engine/Maps/Entry` world to reduce assembly memory use, retaining the existing graphics and assembly settings. That startup, PID 58276, stalled before MCP became available. The splash displayed “Waiting for textures,” but a read-only, non-suspending thread inspection identified `UncontrolledChangelists::LoadState` blocked in `GetFileAttributesW` on the old Google Drive path ending `Content/InfinityStage/Dev/Sequences/LS_DevScene_03.uasset`. Zen's readiness endpoint returned HTTP 200.

`Saved/SourceControl/UncontrolledChangelists.json` still contained 27 pre-migration `G:/.../UE5.8/PussStage/` paths. Its exact 19,077-byte original was backed up to `Backups/PreChangelistPathRepair-20260912-183542/UncontrolledChangelists.json`; those references were remapped to `E:/PussStage/` and duplicates removed, leaving 150 entries. The saved JSON was read back successfully. No asset files were deleted or changed. Evidence: `Saved/CodexMocap/changelist_path_repair.json` and `startup_filename_58276.txt`.

Normal `CloseMainWindow` returned false for PID 58276. The user explicitly approved closing it, and the guarded restart verified its creation time and exact command line before ending only that process. The new PussStage Editor is PID 16800, launched 22:39:27 UTC with the empty Entry map and unchanged graphics/assembly quality settings.

That launch exposed a second set of obsolete project-root paths in `Saved/Config/WindowsEditor/EditorPerProjectUserSettings.ini`: ten remembered folders and one Simplygon intermediate folder. The original 344,233-byte config was backed up to `Backups/PreRememberedFolderRepair-20260912-184220`, and all eleven references were remapped to the local project. The thread stack verified a read-only `FEditorDirectories::LoadLastDirectories` lookup of the old G-drive Content folder. Windows I/O cancellation released each of the ten stale folder checks; no thread or process was terminated during this step. At 22:43:29 UTC the Editor started serving MCP. `SHORE_RETRY_PREFLIGHT_SUCCESS` verified PID 16800, the Entry map, the saved pilot rig/textures and no existing assembled outputs. Pilot Optimized/Medium assembly was scheduled at 22:43:59 UTC.

**12 September, 23:01 UTC assembly result:** all six characters are assembled at Optimized/Medium quality. Native assembly creates unsaved packages; the helper now explicitly saves only the new `Assembled` tree and verifies each output file before recording completion. All six body packages passed independent reload checks, their Blueprint asset types were verified, and each body has its own generated Physics Asset. Character-specific asset counts are 92, 69, 96, 69, 95 and 73, plus shared Common assets. The final audit is `Saved/CodexMocap/shore_assembly_saved_audit.json`; asset paths are in `shore_cast_assets.json`.

The first in-session Blueprint reload reported a facial ARKit Control Rig skeleton-binding error. Body-only reload verification passed, and the first four bodies were subsequently read back in a fresh Editor. Blueprint instantiation, facial appearance and rendered motion remain review steps; the saved-body audit is not rendered proof.

After four characters, a safe callback-boundary pause and normal MCP-requested editor exit released accumulated assembly memory. The restart opened PID 51248 at 22:54:40 UTC, passed the repaired startup paths without intervention, and built the final two. No additional force-close was used. Original graphics, virtual-texture and assembly quality settings remain unchanged.

Seven original clam scene files were backed up and hash-verified in `Backups/PreShoreClamIntegration-20260912-190124` (10,041,633 bytes).

**12 September, 23:06 UTC animation result:** all six fitted full takes passed saved reload verification with 342 animated bone tracks, their original sample counts and changing sampled body poses. The direct Performance export produced only a static root because its required `SourceSkeletalMesh` is protected from Python in this build. That preliminary `AS_Shore01_M56_shoreguy1` asset is not used. The working route is `IKRetargetBatchOperation.run_batch_retarget`, using each saved performer-proportioned `SK_<take>_Body_Full` mesh, its verified raw Animation Sequence, the assembled target body, and `/MetaHumanCharacter/Animation/Retargeting/RTG_MH_IKRig`. The final six names end in `_Full`; `shore_cast_fitted_animations.json` is authoritative.

The separate `Review/L_ShoreCast_Review` map and `Review/LS_ShoreCast_AllSix` sequence are saved. A native Unreal screenshot at review frame 250 shows all six bodies in their recorded poses. Use named `Rotator(pitch=..., yaw=..., roll=...)` arguments in this UE Python build; positional construction produced a rolled camera and was corrected. Individual appearance, motion continuity and foot-contact review are ongoing.

A scoped pilot Blueprint copy, `SceneCharacters/BP_Shore01_M56_Draped`, has a Chaos Cloth component using the original Ortolan sheet. Its `ConfigureShoreDrape` function attaches the component to Body's `head` socket and supplies the pilot's actual Physics Asset to `AddCollisionSource`. Construction and BeginPlay both call this function. Setting only the component template's socket did not survive Blueprint instantiation, so the explicit construction attachment is required. The one-character test map is `Review/L_ShoreDrape_Pilot`; rendered drape fit and full-motion coverage remain under review.

Computer Use remains off at the user's request. Production clam placement and cloth validation remain incomplete; none of the backed-up production scene assets have been changed yet.

**12 September, cloth correction:** the user explicitly requires that the cloth cannot fall off as the body moves. All six `SceneCharacters/BP_<id>_Draped` copies now have construction/BeginPlay head-socket attachment and per-character collision. The original cloth and assembled character assets remain intact. A numbered vertex selection produced an unacceptable canopy shape; the user identified the same problem in the live viewport. That approach is superseded and must not be restored.

The working `Cloth/CA_ShoreHeadDrape` defines its crown attachment spatially on the actual simulation vertices: distance from the cloth origin, zero Max Distance inside 3 cm, a smooth transition out to 14 cm, and freely hanging fabric beyond. Its separate material is two-sided subdued linen. The numbered pin selection is empty and the original painted Max Distance map is bypassed. Each `Cloth/PHYS_<id>_Drape` is a copy of that character's body Physics Asset with only the head capsule radius increased by 3 cm. The draped character variants hide their covered grooms. The latest pilot render shows the canopy removed and the scalp covered; full-motion, multi-character coverage remains under review.

`Review/L_ShoreDrape_AllSix` and `Review/LS_ShoreDrape_Gentle` contain all six draped copies with selected sections of their own full fitted takes at 0.60 playback speed, over the clam scene's existing 797 frames at 30 fps. Selection is recorded in `Saved/CodexMocap/shore_gentle_motion_selection.json`; it is an initial motion-energy selection and still needs visual review, especially the low posture in Shore02's take. Source animations are preserved. The full review callback records sampled attachments and native rendered frames in `shore_draped_motion_qc.json`.

`EditorPerformanceSettings.bThrottleCPUWhenNotForeground` is temporarily false in this session so cloth advances during background MCP testing. Its original value was true and must be restored when testing finishes; see `Saved/CodexMocap/shore_simulation_temporary_settings.json`. This change was not saved to config. Production clam integration is still pending.

[Restart status](MetaHumanCreatorRestart-20260910.md) · [Mocap status](MocapBatch-20260910.md)
