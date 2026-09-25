# Puss — engineering checklist

Systems, code, pipeline and Show data. The machine that runs the show, as
opposed to the show.

Companion lists: [creative](ShowCreativeTodo.md) · [rehearsal](ShowRehearsalTodo.md)
Reasoning behind each line: https://claude.ai/code/artifact/7d8d8c4f-885c-436b-8b7c-9f7ef709d29a

**G** Gary · **K** Klara · **C** Cameron · **X** external animator

| Date | What |
| --- | --- |
| **Now** | Windows workspace active at `E:\PussStage`; latest full suite **43/44**, same curtain-marker failure |
| **17 Sept** | Eight body-only captures packaged for Klara with matching source meshes; transfer/retarget by Klara is not yet confirmed |
| **15 Sept** | All 261 active Wing rows handedness-audited and repaired; Show/level read-back clean. Final Rob package ready, not confirmed sent |
| **14 Sept** | All six Passage → Scene handoffs and Scene-end holds passed in normal PIE; Shore playback reached through the Show. [Repair record](SceneTransitionRepair-20260914.md) |
| **28 Aug** | 19-segment spine, sequence-owned curtains, P2 opacity repair and Cue Desk transform tools verified |

## Decided 21 Aug

- **D.1** UE owns the clock → K/C mix, don't trigger. Musicians need a cue feed (D.2).
- **B.1** Both curtain attach modes in one rig.
- **G.1** Hardened PIE → operator HUD is in-game (G.2).
- **E.7** Cue sheet for v1, no DMX.
- **F.5** Dog owns the Void camera → Free Look, not Gaze.
- **I.5** Mountains brief and 152.341-second audio prepared for Rob; the 15 Sept package is ready, but external delivery is not confirmed.

Still open: **D.2** what the cue feed is · **A.5** camera owner on the other 18 cues.

---

## 22 Aug migration handoff (historical)

- [x] **T1** ✅ Music analysis re-run 21 Aug 15:34. All 6 rails + 4 scene stems now provider 0.3.0, 7 feature curves each, expressive sections present. `Scripts/analyze_show_music.py`. **Still to do: Cue Desk → Actions → Link / Reimport Music Analysis in Unreal.**
- [x] **T2** ✅ M.1 applied and **compile-verified** (build exit 0, new UTF-16 literals present in the linked dylib, Windows branch correctly compiled out). 0.6 turned out to be mostly already built — see below. Suite run deferred to the PC (M.5).
- [x] **T3** ✅ All 5 scripts de-hardcoded, syntax-checked.
- [x] **T4** ✅ Production spine now compiles to 19 segments: 7 SEQ blocks (opening, five interactions, closing), 6 Passages and 6 Scenes. Current proof: `Saved/CodexCurtainAuthoring/verify_curtain_staging.json`.
- [x] **T5** ✅ [Scene delivery contract](SceneDeliveryContract.md) and [Mountains brief](Brief_S5_Mountains.md) written. Brief is ready to send.
- [x] **T6** ✅ [Sound delivery list](SoundDeliveryList.md) drafted — **not sent**, yours to review and send.

---

## M. Move to PC

- [x] **M.1** ✅ Tries `py.exe` then `python.exe` on Windows, keeps `/usr/bin/env python3` on Unix, honours `INFINITYSTAGE_PYTHON`. Compile-verified.
- [x] **M.2** ✅ Done. Resolvers are per-script by design — Blender and Unreal embedded interpreters don't reliably put the script dir on `sys.path`.
- [x] **M.3** ✅ [Windows build procedure](WindowsBuildProcedure.md) — `dumpbin`/`llvm-nm`, plus the UTF-16 string check, because an anonymous-namespace symbol can inline away and show nothing.
- [ ] **M.4** (G) GO1 chain on PC — firewall rule for UDP 9876, 5 GHz adapter for ch 165.
- [x] **M.5** ✅ PC suite exercised and recorded. Latest complete run is **43/44** (14 Sept); the remaining `SavedFixturePIE` curtain-marker failure is tracked by J.1.
- [x] **M.6** ✅ Windows loopback route proven at `127.0.0.1:8000/mcp`, using guarded `ExecuteProjectPythonFile` scripts under `Saved/` with read-back and dirty-package checks.
- [ ] **M.7** (G) Move `DerivedAssets/` + shared `V2/` wing sources, update path conventions.
- [x] **M.8** ✅ Verified 18 Sept: `python` resolves to Python 3.14.7 and imports NumPy 2.5.2. `py.exe` remains unavailable, but the importer falls through to `python.exe`. A fresh Cue Desk analysis regeneration/reimport remains a separate task.

## 0. Clear first

- [x] **0.1** ✅ Analysis regenerated at 0.3.0 (21 Aug). Reimport into the Show still pending — E.3 and the passage music work stay blocked until that lands.
- [x] **0.2** ✅ UE 5.8 editor closed → clean build → DLL marker/hot-reload check → focused tests → full suite. Latest result is 43/44; see J.1.
- [ ] **0.3** (G) P3: 1 triangle mismatch, 6 role mismatches. Re-verify, target-save.
- [x] **0.4** ✅ P5 read back 93 rows / 22 serialized meshes under `/Game/Scenes/Wings/Passage5_BirdToMountainV2`; that canonical in-use root is captured in the 15 Sept Rob package. The unused similarly named root remains covered by 0.5.
- [ ] **0.5** (G) Collapse `/Game/Wings` (191-asset shell) into `/Game/Scenes/Wings` (canonical, 148 Show refs).
- [x] **0.6** ✅ Rehearsal transport is visible, persisted and applied to live PIE. **Play Selected** cues a Scene/SEQ at its exact first frame and plays it to its boundary. Performance-mode external-clock locks remain deliberate; do not clear them merely to enable rehearsal.
- [ ] **0.7** (G) Scene-scoped preview — `GetSelectedPassage()` falls back to the previous Passage. Blocks scene music + surtitle timing.

## A. Show structure

- [x] **A.1** ✅ Seven SEQ cues authored (opening, five interactions, closing). `Sequence` now has distinct interstitial behaviour: sequence-owned curtain playback and automatic play on Next Segment.
- **Opening checkpoint, 14 Sept:** Passage 1 camera is established before the reveal; the foreground curtain is sized from its lens. Auto Play holds at Passage 1; viewport Space/Left/Right controls and camera retention after starting playback are implemented. [Evidence](OpeningPlaybackRepair-20260914.md).
- [ ] **A.2** (G) Colour + filter cue rows by tag.
- [x] **A.3** ✅ All thirteen non-wing cues use their sequence lengths (14 Sept), confirmed after saved-level reload. Master rebuilt; Scene 3 is no longer capped at 15 seconds.
- [ ] **A.4** (G) Per-cue "skip handoff match" flag for curtain cues.
- [ ] **A.6** (G) `Check All Scenes` once the spine is final, and after any route/lens change.
- **A.6 checkpoint, 14 Sept:** all six handoff cameras match; repeat after future route/lens edits. Automatic Passage → Scene playback is enabled on the production Show Root and verified in normal PIE.

## B. Curtain rig

- [ ] **B.2** (G) Curtain engineering base exists as `BP_InfinityStageSequenceCurtain`, using the fire-safety mesh with camera-relative placement. Remaining: world/camera mode authoring plus painted/diaphanous material treatment and final rendered framing.
- [x] **B.3** ✅ `LS_Interaction_Template` plus five production interactions authored with close / boy-cat window / covered changeover / open timing and separate Curtain, BoyCat, and Light/Shadow/Audio/VFX folders.
- [ ] **B.6** (G) Shadow Cat — clear the `SpeedMultiplier` empty-array and `HeightFixer Sphere` warnings, verify under stop/accelerate/reverse/seek.

## C. Surtitle system

- [ ] **C.1** (G) `BP_Surtitle` — `UPROPERTY(Interp) FText`, keyed by native `UMovieSceneTextTrack`. No plugin code.
- [ ] **C.2** (G) `WBP_SurtitleBar` — one shared style, safe-area margins for the real screen.
- [ ] **C.3** (G) Bind inside each Scene sequence, **never** on the managed Master.
- [ ] **C.4** (G) `Actions → Export Surtitle Script` (timecoded, for proofing).
- [ ] **C.5** (G) Operator blackout toggle, transient.

## D. Audio plumbing

- [ ] **D.1** (G) Spec the show PC → sound desk audio routing: channel count, interface, latency. Required now UE owns the clock.

## E. Lighting systems

- [ ] **E.1** (G) Freeze the celestial rig at a fixed hour, don't delete it.
- [x] **E.2** ✅ Stage lights via typed, cue-anchored attachments: native Spot/Rect/Point fixtures, persistent parameters, and first-selected-pair replication across an ordered Wing selection. Scoped replication (Selection / Whole Passage / Entire Show) added; on 21 Sep 2026 Whole Passage was fixed to follow the template pair's own Passage and rematerialize only the affected Passages.
- [ ] **E.3** (G) Music-driven light channels on the Passage section, mirroring the Wing Movement channels. Needs the 0.1 reimport.
- [ ] **E.7** (G) Build the cue-sheet export action.

## F. Dog integration

- [ ] **F.3** (G) Link-state indicator — last packet age, in Cue Desk and HUD.
- [ ] **F.6** (G) Full telemetry pass on the PC.
- [ ] **F.7** (G) `GameMode Override` → `InfinityStageShowGameMode`.

## G. Operator surface

- [ ] **G.1** (G) Harden PIE: autosave off, source-control prompts off.
- [ ] **G.2** (G) `WBP_OperatorHUD` — cue, time to boundary, next surtitle, dog link, camera owner, transport mode.
- [x] **G.3** ✅ Rehearsal toggle plus **Play Selected** provides exact first-frame entry and bounded Scene/SEQ playback. Production Next Segment auto-plays Scene/SEQ cues; entering a Passage still holds. Normal Passage playback now continues through its following Scene before holding.
- [ ] **G.4** (G) Verify `PIE Starts At Playhead`; watch for `SHOW MISMATCH`.

## H. Wing pipeline

- [ ] **H.1** (G) Generate wing families for P4 and P6. V2 profile; `replace_existing=True`, not `import_assets()`.
- [x] **H.8** ✅ Superseded by the 15 Sept all-Passage audit: all 261 rows read back with zero remaining Left/Right flips after 221 redundant flips were cleared and two P2 side assignments repaired. Saved Show/level read-back was clean; rendered venue framing remains open.
- [ ] **H.9** (G) Camera piloting with write-back. Do before the aesthetic passes, or framing is typed rather than looked at.
- [x] **H.10** ✅ Passage 1 orphaned managed ISMs fixed in materialization cleanup; all six Passages verify with zero orphan components.
- [x] **H.11** ✅ Passage 2 opacity masks repaired: 60/60 material instances use their own wing texture, zero Bamboo masks, 23 pairs rematerialized.
- [x] **H.12** ✅ Fire-safety curtain generated and clean-reimported with the V2 profile: 10 cm thickness, Front/Back/Edge slots, Base/alpha + height + DirectX normal maps. Imported relief material now uses its own opacity mask and 4K TextileV5 Base Color.

## I. Show data

- [ ] **I.7** (G) Replace all six `LS_DevScene_0N` placeholders as authored scenes land.

## J. Test coverage

- [ ] **J.1** (G) Return the suite to green. Latest PC run (14 Sept): **43/44**; `SavedFixturePIE` still fails the fully-lowered hidden-changeover assertion. Passage-to-Scene and camera-boundary regressions pass. The 3,000-wing compile test passes.
- [ ] **J.2** (G) New coverage: surtitles vs Master rebuild, ownership at all 18 boundaries, telemetry fallback. Curtain retained-camera/sequence coverage now exists, but the full-suite marker regression above remains.
