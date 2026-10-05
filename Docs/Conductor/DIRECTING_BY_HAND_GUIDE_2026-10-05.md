# Directing the Passages by hand: a guide for 5 Oct (no AI, no Python, no C++)

**For:** Gary, directing ambience in the Unreal editor himself.
**Written:** 4 Oct night, offline. The research read only code and docs. No Unreal, MCP or build was run.
**Updated 5 Oct afternoon:** see **§0, New on 5 Oct** first; it supersedes anything below that says "not built" for the strobe.

**State it originally described:** the build of 4 Oct night (cueing A1–A3 + A2e built, Choreos applied, bee swarm v3 built). **Held and NOT built:** the strobe (S1), the Cue List panel (B1), flash events (LD), the retime test (RT) and F1. Anything that depends on those is listed under "can't do by hand yet".

## How to read the tags

Every claim carries one tag:

- **[decl]**: read in source or config. The behaviour is what the code says; it was not run today.
- **[meas]**: measured in a recorded run (cited).
- **[inf]**: inferred, with the reason. Treat it as likely, not proven.
- **UNCLEAR**: not established. Collected at the end.

**Path shorthand** (all under `Plugins/InfinityStage/Source/`):

| Short | File |
|---|---|
| `CD` | `InfinityStageEditor/Private/SInfinityStageCueDesk.cpp` (the Cue Desk) |
| `EM` | `InfinityStageEditor/Private/InfinityStageEditorModule.cpp` (the write-back hooks) |
| `CP` / `PP` | `InfinityStageEditor/Private/InfinityStageCueProxy.cpp` / `InfinityStagePassageProxy.cpp` |
| `SB` | `InfinityStageEditor/Private/InfinityStageSequenceBuilderLibrary.cpp` (Rebuild Master) |
| `TY` | `InfinityStage/Public/InfinityStageTypes.h` (every Show field) |
| `PA` | `InfinityStage/Private/InfinityStagePassageActor.cpp` (materialize, Light Drama) |
| `SA` | `InfinityStage/Private/InfinityStageShowAsset.cpp` |
| `CO` | `InfinityStage/Private/InfinityStageCompiler.cpp` (timing maths) |
| `TC` | `InfinityStage/Private/InfinityStageTransportController.cpp` (PIE transport, GO) |

**Assets:**
- Show: `/Game/InfinityStage/Dev/DA_InfinityStage_V1Show`
- Level: `/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice`
- Master: `/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master`
- Choreos: `/Game/InfinityStage/Choreo/LS_Choreo_Passage_1` … `_6`

The Show and Master paths are the ones the gate test loads [decl `InfinityStageEditor/Private/InfinityStageEditorAutomationTests.cpp:1500-1505`]. The level path is from `Docs/CodexUnrealMCPRunbook.md`. The Choreo paths are from `Saved/CodexCueing/choreo_report_choreo-apply-3.json` [meas].

---

## 0. New on 5 Oct (read first)

| What | Where | Notes |
|---|---|---|
| **Lighting scores** on all six Passages | Show lamps labelled `Pnn SCORE Bnn <LOOK> <SLOT>` | Edit them like any Show lamp (§3.2). P02 rescored to your breakdown note: working stage rig bays 1–11, **failing** 12–19, mystic shrine 20–23 [meas: applied + tests 5 Oct] |
| **Direction notes** | `Docs/Conductor/LIGHTING_DIRECTION_NOTES.md` | Your P01/P02/car-light/tubes notes; add to it as you direct |
| **Iron rig** (girders, columns, piers, knees, deck at 20 m) | Structure actors → Details → Gridiron / Underpass (§3.5) | All six Passages. **TOP lamps hang just under the girders** now (≈1.28 m lower); P03 slashes 20 cm lower [meas] |
| **Office fluorescent tubes** | Structure 02 → Underpass → Tubes (§3.5) | P02 bays 12–19 only; 55 tubes, 13 rect lights, 15 % dead, hum flicker [meas] |
| **Car light** | "P02 Car Light (trial, Gary to tune)" (§3.5) | Too bright as placed; tune in Details while PIE runs, then copy values back after PIE |
| **Strobe** | "P04 Strobe (default, Gary to place)" (§3.5) | Built; move it where you want it |
| **Dark wet floor** | `MI_Floor_DarkWet` on the passage floor slabs | P02 untouched; 5.5 cm step at each hangar pit strip [meas] |
| **Stills after any change** | ask the AI: "stills of Pnn" | `passage_stills.py`, 5 frames along the Passage from the show camera |
| **PIE test list** | `Docs/Conductor/PIE_TEST_LIST_2026-10-05.md` | Today's checks, Passage by Passage |

**Known problem (5 Oct, being fixed):** the 9 "S3 Wave Split" wave flats show up **inside P01** (world x 3,665–5,335,
y −500…500). They belong to the Scene 3 beach (y ≈ 160,000). Don't move them by hand; the AI re-attaches them to
"S3 Hangar Root" with the recorded offsets after PIE.

**Tuning while PIE runs:** Details edits on level actors (car, strobe, tubes) in PIE are lost when PIE ends unless you
right-click → **Keep Simulation Changes**, or note the values and set them after PIE.

## 1. Cheat sheet (one page)

**Time units.** "Frames" in the Show are **ticks at 24,000 per second**: 24000 = 1 s and 48000 = 2 s [decl `SA:86-87`]. The Cue Desk "Timing" column prints this raw tick count with the label "fr" [decl `CD:954`].

| I want to… | Where | It persists to | Then press | Gotcha |
|---|---|---|---|---|
| Change a wing's **spacing** (distance to the next pair) | Cue Desk → select wing row → Details → Layout → **Gap To Next Cm** | Show | Nothing for the level (it rematerializes itself). **Rebuild Managed Master** before PIE | Moves every later wing and its lamps. Keep the Passage's **total** distance the same, or the next hangar won't dock (§3.1) |
| Change a wing's **timing** (beat to the next pair) | Same → Timing → **Interval To Next** | Show | **Rebuild Managed Master** | **Changes Passage length. NOT retime-safe** (§3.1) |
| Change Passage **lead-in / tail** | Cue Desk → click the **Passage heading** → Passage/Music panel → Lead In / Tail Frames, Lead In / Tail Distance Cm | Show | Rebuild Master | Changes Passage length. Lengthening only the **tail** is the least risky (§3.1) |
| Change a wing's **opening width / side offset** | Cue Desk Details → Wing Pair Layout → **Rest Opening Width**, **Opening Centre Offset** | Show | (auto rematerialize) | — |
| Drag a wing with a gizmo | Cue Desk → Actions → **Edit Selected Wing in Level Viewport** → Whole Pair / Left / Right / Top → drag → **Finish Viewport Edit** | Show | — | Selecting another cue also **commits** the edit; use **Cancel Viewport Edit** to back out |
| Change **wing movement** | Cue Desk Details → Mechanism, or Actions → **Wing Movement** presets | Show | — | Explicit Origin Frame is an **absolute** time; avoid it |
| Swap **wing art** | Cue Desk Details → Panels → Left/Right/Top → **Mesh** / Material Overrides | Show | — | Only swap to existing, approved meshes. New art goes through the V2/V3 pipeline |
| **Move / aim** a stage lamp | Viewport: select the lamp actor (under its Passage in the Outliner) → gizmo | Show (auto write-back) | Save Show + level | Re-select the cue in the Cue Desk before editing it there again (stale copy, §3.2) |
| Lamp **colour / intensity / cone / shadows** | Select the lamp actor → Details → Light component | Show (auto write-back) | Save Show + level | Keyed settings are withheld while their sequence is open |
| Lamp **Light Drama** (strike on approach, slow move) | Cue Desk Details → Stage Content → Attachments → [n] → Lighting → Drama | Show | — | Visible **only in PIE**. Station-anchored lamps only |
| Copy one pair's lamps to others | Cue Desk → select template pair → Actions → **Replicate First Pair's Lighting** → scope | Show | Save Show + level | **Replaces ALL lamps** on the targets, including scored lamps |
| **Add** a lamp | Actions → **Add Missing Stage Lights to Selection** (only pairs with no lamp on that side), or Details → Attachments **+** | Show | Materialize Selected Passage | **+** leaves the lamp without an ID (§3.2) |
| **Delete** a lamp | Select the lamp actor → Delete | **Show (it is removed from the Show!)** | — | Not "hide". Untick its Enabled box in the Cue Desk instead |
| **Key** a lamp / light / prop over time | Open the Passage's **Choreo** → drag the actor into Sequencer → add a track → key | Choreo sequence asset | Save the Choreo | Strike lamps: drama wins in PIE. Key at least 1 frame after a GO |
| **Cue point** (GO) | In a Choreo or Scene sequence: press **M**, rename to `GO 12 Warmers out` | That sequence asset | Save it | Upper-case GO plus a number. Choreos default to PASS; Scenes to HOLD |
| **Haze** (global) | Outliner → the celestial rig's Exponential Height Fog → Details → density / volumetric | Level | Save level | Fog **colour** is overwritten by the sky rig every frame; density is not |
| **Haze** (local pockets) | Place Actors → **Local Fog Volume** into the level | Level | Save level | Doesn't follow wing re-spacing |
| Rig / gridiron / floor after re-spacing | Select the Passage's Structure actor → Details → **Materialize Structure** | Level | Save level | Not automatic |
| Hangar rise timing | Select the Arrival actor → Details → **Read Hangar Timing** → edit → **Apply Hangar Timing** | That Scene's rise sequence | Save that sequence | — |
| **Music** in/out, fades | Cue Desk → Passage heading → Passage/Music panel → Defining Music (Source In/Out, Fade In/Out) and Music (Mode, Rail Offset) | Show | **Rebuild Master** | Hand-keyed volume on the Master's music section is **wiped** by every rebuild |
| Passage **camera** speed, height, lens | Cue Desk music workspace → Camera curve → channel → key at playhead / Curve Actions | **Master** sequence | Save the Master | Pins past a shortened end are deleted |
| **Scene length** | Cue Desk → Scene row → Details (Duration / Use Sequence Length), or the Scene sequence's playback range | Show / Scene sequence | Rebuild Master → **Scene Camera Handoff → Match Selected Scene** → run the two tests | The one retime that is safe |
| Preview drama, GO holds, strobe, hangars sinking | **PIE** | — | — | The editor scrub shows wings and camera only |

**The three save targets.** Save only what you touched: **Show**, **level** and **the sequence you keyed**. Never **Save All** (§5.1).

---

## 2. The model in five sentences

1. **The Show asset** owns the cue list: every wing pair, its spacing, timing, mechanism and art, and every **stage lamp, prop and effect attached to a pair** (`Attachments`, [decl `TY:725-727`]).
2. **The level** holds the *materialized copy* of the Show: wing instances and one actor per attachment, rebuilt from the Show by **Materialize**. It also holds the things the Show doesn't know about: fog, the sky rig, Structure (rig, floor) actors, hangars and any light you place yourself.
   - The level never re-materializes on its own when it loads [inf: no `PostLoad`/`OnConstruction` materialize in `PA`; the game world refuses to clear content, `PA:617-623`]. So after a Show edit, the level must be saved too, or PIE and the next session show the old copy.
3. **The Master sequence** owns **time and the Passage camera**.
   - **Rebuild Managed Master** (Cue Desk → Actions) re-lays Passage, Scene, music and Choreo sections from the Show. It leaves your own Master tracks alone [decl tooltip `CD:3921-3922`].
4. **Choreo and Scene sequences** hold everything you key over time.
   - A Choreo is nested over its Passage, with 0:00 at the Passage start. It moves with the Passage when the Show is retimed [decl `TY:972-976`, `SB:367-483`].
5. **Write-back.** Moving or editing a materialized **attachment actor** in the editor writes back into the Show [decl `EM:227-298`, `EM:307-404`]. The actor is a live window onto the Show record; it is not a separate thing.

**When is Rebuild Master needed?**
- **Automatic** after: add / duplicate / delete / move cue rows, Rename Passage, Refit from Music and Wing Sequence imports [decl `CD:6617-6645`, `CD:4335-4343`, `CD:6007-6016`, `CD:6578-6588`].
- **NOT automatic** after any edit in the Cue Desk **Details** or **Passage/Music** panel: timing, spacing, music, Scene length [decl: the proxy change handler `CD:1522-1540` only refreshes the list and rematerializes; `CP:50-78` and `PP:76-117` never call the builder].
- **Rule:** after any timing, music or Scene-length edit, press **Actions → Rebuild Managed Master Sequence** before PIE.

---

## 3. Parameter by parameter

### 3.1 Wings

**Getting there.**
- **Window → Infinity Stage Cue Desk** [decl `EM:553-565`]. You can also type the console command `InfinityStage.OpenCueDesk` [decl `EM:145-151`].
- Pick the Show in the asset box at the top. Alternatively use **View → Use Current Level Show** [decl `CD:2941`].
- **View → Nested Passage View** groups the wings under Passage headings [decl `CD:2920`].
- Selecting a wing row puts its full record in the middle **Details** pane [decl `CD:1500-1508`].
- Right-clicking the list opens the same **Actions** menu [decl `CD:2890-2893`].

**(a) Spacing: `GapToNextCm`** [decl `TY:712-713`]
- **By hand: yes.**
  - Details → Layout → Gap To Next Cm.
  - Multi-select several rows to set them all at once. The panel says "shared edits apply to all" [decl `CD:6920`].
- **Persists:** to the Show. The edited Passage re-materializes automatically [decl `CD:1522-1540` → `CD:1573-1633`].
- **What moves:** every later wing in the Passage slides along the route.
  - Lamps and props follow, because their offsets are stored relative to their pair [decl `EM:216-224` comment; `PA:1648-1650`].
  - Spacing changes distance, not time: the pass beat comes from Interval To Next [decl `CO:262-287`]. So the camera simply walks faster or slower over that stretch.
- **Risk 1: hangar docking.**
  - The Passage's **total distance** is the sum of the gaps plus the lead-in and tail distances [decl `CO:262-292`].
  - The next Scene's hangar is a **level** actor that does **not** follow a re-fit [decl, cited in `Docs/Conductor/P06_DOCKING_CLEARANCE_2026-10-04.md:7`].
  - If you lengthen one gap, shorten another by the same amount. The status rail at the bottom of the Cue Desk shows "Route …m" [decl `CD:6748`]: note it before and after.
- **Risk 2: other things that go stale.**
  - The rig, gridiron and floor go stale: **Materialize Structure** (§3.5) [decl `InfinityStage/Public/InfinityStageStructureActor.h:504-524`].
  - Scene handoff views at that Passage's ends may go stale: **Actions → Scene Camera Handoff → Check All Scenes (read-only)**, then **Match Selected Scene** [decl `CD:2778-2793`].

**(b) Timing: `IntervalToNext`** [decl `TY:709-710`]
- **By hand: yes.** Details → Timing → Interval To Next, in ticks.
- **Persists:** to the Show. Press **Rebuild Master**.
- **Gary's rule (5 Oct): SHIFT, never stretch.** Keys belong to the boundary they sit near and move with it [Gary's words, `Docs/Conductor/MORNING_SUMMARY_2026-10-04.md:177-180`]. **The code does not do this yet.** Changing any interval changes the Passage length, and then:
  - Later Scenes and Passages shift correctly [decl `SB:300-309`; audit row 7].
  - Inside the changed Passage, **camera and wing-channel keys keep their old Passage-relative times** while the wings after the edit move. The score drifts off the wings [decl `SB:300-309`; `Docs/Conductor/RETIME_ROBUSTNESS_AUDIT_2026-10-04.md` row 4].
  - **Camera pins past a shortened end are silently deleted** at the next rebuild [decl `SB:286-291`].
  - **Choreo keys** stay at their Passage-relative times. A longer Passage plays silence past the Choreo's end; the log says `INFINITY_CHOREO_SHORT` [decl `SB:472`].
  - **Music** always starts at the Passage start. A longer Passage plays more of the song, and the fades re-fit to the new ends [decl `SB:539-542`, `SB:78-95`].
  - Scene handoff cameras are not rematched [decl audit row 12].
- **Least-bad by-hand route** if you must change a Passage's length:
  1. Change the **tail** (`TailFrames`, Passage/Music panel) rather than an interval in the middle, and **lengthen rather than shorten**. Nothing inside the Passage moves relative to its start, and nothing gets deleted [inf from `SB:286-309`].
  2. If a middle interval must change, shift the downstream keys yourself:
     - Open the Master (**Curve Actions → Open Master in Sequencer**, `CD:3555`). Select the Passage section's camera/wing-channel keys after the changed wing and drag them by the same Δ.
     - Do the same in that Passage's Choreo.
     - This is the manual form of "shift". It is easy to miss a channel [inf].
  3. Rebuild Master → Check / Match Scene handoffs → run the two tests (§5.4).
- **Recommended for tomorrow:** treat Passage length as **frozen** unless it really matters. The conductor's handover says the same: "Avoid Passage length changes until Gary decides stretch vs keep" [decl `Docs/Conductor/CONDUCTOR_START_PROMPT.md`, 20b50d4]. Gary has since decided "shift"; the code to do it is not built.

**(c) Lead-in / tail** (`LeadInFrames`, `TailFrames`, `LeadInDistanceCm`, `TailDistanceCm`) [decl `TY:957-967`]
- **By hand: yes.** Click the **Passage heading row**; the right-hand **Passage / Music** panel shows the Passage settings [decl `CD:4880-4890`, `PP` header].
- The same retime cautions apply.
- A non-zero lead-in or tail **distance** needs non-zero **frames**, or the compile errors [decl `CO:294-301`].

**(d) Side offsets, opening width, pose**
- **Rest Opening Width (Pivot-to-Pivot)** and **Opening Centre Offset** are at the top of the wing's Details [decl `InfinityStageEditor/Public/InfinityStageCueProxy.h:17-29`, `CP:21-35`].
- **Per panel:** Panels → Left / Right / Top → Local Transform [decl `TY:602`].
- **Per occurrence:** Layout → Occurrence Offset [decl `TY:716`].
- **Gizmo route:** **Actions → Edit Selected Wing in Level Viewport → Edit Whole Pair / Left / Right / Top Panel** [decl `CD:1977-1991`].
  - A transient "EDIT …" proxy appears and is selected. Drag it.
  - **Finish Viewport Edit** writes it to the Show and rematerializes [decl `InfinityStage/Private/InfinityStageWingEditProxy.cpp:117-166`].
  - Selecting another cue also **finishes, not cancels** [decl `CD:1895`, `CD:1950-1963`].
  - **Cancel Viewport Edit** restores the originals [decl `InfinityStageWingEditProxy.cpp:168-187`].
- **Copy one panel's transform to every use of that mesh:** **Actions → Relative Transform** [decl `CD:2434-2452`].

**(e) Wing movement (mechanism)**
- **Per row:** Details → Mechanism. Fields: Kind, Playback Mode, Cycle Rate, Phase Offset, Inward Travel, Max Angle, the three curves, Camera Gust [decl `TY:625-686`].
- **Presets for the selection or a whole Passage:** **Actions → Wing Movement**. Options: Gentle Wave Along Passage, Gentle Wave Toward Camera, Breathe Together, Phased Breathe (2/3/4), Camera Gust / Fan Reveal, Hold Static. Scope: Selected Wing Pairs or Whole Current Passage [decl `CD:2678-2764`].
- **Passage-wide phase pattern** (Passage/Music panel): **Live Phase Pattern From Cue Order** [decl `TY:983-994`].
- **Live scaling over time:** the camera-curve rail has **Wing Travel Scale**, **Wing Cycle Rate Scale** and **Wing Phase Bias** channels. These are keys on the **Master** [decl `CD:190-192`].
- **Avoid** Phase Origin = Explicit with **Explicit Origin Frame**. It is an absolute Master time and goes wrong on any retime [decl `TY:642-645`; audit row 16a].
- Wing motions are **not** keyable in a Choreo yet (Gary Q3: later) [decl `PLAN_DIRECTING_AND_CUEING_2026-10-04.md:46,135`].

**(f) Wing art swap**
- Details → Panels → Left / Right / Top → **Mesh**, **Material Overrides**, Flip Image Horizontally, Cast Shadow, Visible In Main Pass [decl `TY:595-621`].
- **Actions → Image Orientation** offers per-occurrence flips and "apply to every use of this mesh" [decl `CD:2387-2422`].
- **Persists:** to the Show, with an auto rematerialize.
- **Risk.** Generating **new** wing art is not a by-hand job. New Left/Right pairs must be authored in final handedness, to the V2 / Flat V3 profile (AGENTS.md; `Docs/WingGenerationConventions.md`, `Docs/FlatV3Spec_2026-09-30.md`). Swapping to an **existing, already-imported** mesh is fine.

**(g) Hiding, adding and removing wings: three traps**
- **Do NOT untick a wing's Enabled box in the middle of a Passage.**
  - A disabled row **splits the Passage in two** [decl `CO:198-203`, `CO:240-246`; `SA:133-179`].
  - The second half gets a **new Passage identity with default settings**: no music, no Choreo, no camera curves, and no Passage actor in the level to materialize it [inf from `SA:150-171`].
  - **To hide one wing instead:** set its panels' **Visible In Main Pass** and **Cast Shadow** off, or swap the mesh [decl `TY:615-618`].
- **Add Cue / Duplicate / Delete / Move Up/Down** on wing rows (Add Cue menu; Actions) auto-rebuild the Master [decl `CD:6617-6645`]. They also **change the Passage length** (see b).
- **Wing Sequence Files → Import and Insert / Advanced: Replace** give rows **fresh identities** [decl tooltip `CD:3884`]. That breaks every Choreo lamp binding and every saved tool record keyed to those cues [inf: bindings key on the cue GUID, `PA:967-970`]. **Apply Saved Arrangement** keeps identities [decl tooltip `CD:3964-3966`].
- **Export Whole Current Passage…** is a cheap personal backup of a wing arrangement (`.infinitywings.json`; no music or sky) [decl `CD:3954-3956`, `CD:6401`].

### 3.2 Stage lamps attached to wings ("Show lamps")

These are actors labelled like `P01 Wing 001 Spot L` / `House L`. In the **Outliner** they sit under their Passage actor [decl `PA:958-961`, `PA:1006`].

**(a) Move and aim**
- **By hand: yes.** Select the lamp in the viewport or Outliner and use the gizmo.
- **Persists:** the offset relative to its pair is written to the Show. The log says `INFINITY_STAGE_ATTACHMENT_MOVED` [decl `EM:227-298`]. This works for **every** attachment kind, not just lights [decl: no Kind filter in `EM:227-286`].
- **Exception:** if an open sequence keys that lamp's transform, the move is **not** written. The log says `INFINITY_CAPTURE_SKIPPED_SEQUENCER` [decl `EM:252-267`].

**(b) Colour, intensity, temperature, cone, radius, shadows, IES, light function**
- **By hand: yes.** Select the lamp → Details → its Light component.
- **Persists:** every non-interactive Details change on a **Light** attachment is captured into the Show (`INFINITY_STAGE_ATTACHMENT_LIGHT_UPDATED`) [decl `EM:307-404`].
- **Keyed settings are withheld.** If an **open** Sequencer keys some of the lamp's settings, those stay at their authored Show value and the rest is written (`INFINITY_CAPTURE_WITHHELD`) [decl `EM:356-389`; [meas] M4 on P01 House L: keyed Intensity withheld, hand-edited Colour written, `MORNING_SUMMARY_2026-10-04.md:147`].
  - So, to change a keyed lamp's **base** value: close the sequence first, or edit it in Cue Desk Details (c).
- Light Drama is not on the actor's Details. It is Show-only (c).

**(c) The Show record itself**
- Cue Desk → wing row → Details → **Stage Content → Attachments → [n]**: Label, Kind, Enabled, Actor Class, Mesh, Anchor, Relative Transform, **Lighting** (all light fields + **Drama**) and Effect [decl `TY:427-477`].
- **Persists:** to the Show, with an auto rematerialize.

**(d) Light Drama** (distance-driven strike and slow move) [decl `InfinityStage/Public/InfinityStageLightDrama.h:38-104`]
- **Strike group:** Strike On Approach, Strike Distance, Strike Ramp, Ignition Stutter, Unstruck Intensity Scale, After Pass (Hold/…), After Pass Distance, Decay Distance.
- **Slow Move group:** Slow Move, Pan / Tilt Amplitude, Period, Phase From Identity, Phase.
- **By hand: yes**, at (c) → Lighting → Drama.
- **Limits:**
  - It runs **in game worlds only**, so you see it **only in PIE**. The editor deliberately shows authored values [decl `PA:1620-1623`].
  - It applies only to **Station-anchored** lamps [decl `PA:1641-1643`].
  - It writes the lamp's intensity, visibility and (slow move) rotation **after Sequencer every frame** [decl `InfinityStage/Private/InfinityStageLightDrama.cpp:121-133`; tick group `InfinityStage/Private/InfinityStageCameraRig.cpp:99`]. So **keying intensity or aim on a drama lamp in a Choreo does nothing in PIE inside its Passage** [inf from tick order; `PLAN_DIRECTING_AND_CUEING:45`].
  - Slow move phases off absolute Master seconds, so a retime shifts its phase [decl audit row 16b].

**(e) Replicating a lamp setup** ("spacing of different kinds of lighting")
- **Steps:** tune one pair → select it → **Actions → Replicate First Pair's Lighting** → choose a scope [decl `CD:3784-3824`]:
  - **Across Selection — Exact / With Variation:** the template is the **earliest** selected pair; the targets are the other selected pairs. Ctrl-click every 2nd or 3rd pair to get a rhythm.
  - **Whole Passage:** every other pair in the **template's own** Passage.
  - **Entire Show:** every pair in the Show.
- **Persists:** to the Show as one undo step, and the affected Passages rematerialize [decl `CD:2284-2294`].
- **RISK: it replaces ALL Light attachments on every target** [decl `SA:617-620`]. This includes lamps placed by the lighting scores: P05's applied score, the P04 tune-4 lamps and the P06 black mode [meas, those applies are recorded in `MORNING_SUMMARY_2026-10-04.md`]. Use **Selection** scope inside scored Passages.
- **You cannot replicate one kind of lamp only.** It copies all of the template's lights [decl `SA:617-640`].
- The copies **reuse the targets' existing lamp IDs by position** [decl `SA:624-627`]. Choreo keys on a target's "lamp #2" therefore drive the new lamp #2 [inf].

**(f) Adding a lamp**
- **Actions → Add Missing Stage Lights to Selection** adds a spot on the Left and/or Right **only if that side has no light** [decl `CD:2128-2143`]. It mints proper IDs [decl `CD:2152`].
- **Details → Attachments → +** works, but the new row gets **no ID**. Only replication and the Add-Spots action mint one [decl `SA:91-123` mints cue, occurrence, passage and rail IDs, never attachment IDs; `TY:431-432` is read-only].
  - One un-ID'd lamp per pair probably behaves [inf: lookups are per cue + ID, `PA:1820-1848`].
  - **Two** on the same pair collide: moving one writes the other [inf].
  - **Never use the array's "Duplicate" on an attachment**: it copies the ID [inf].
- **Never Ctrl+D / Alt-drag a lamp actor.** The copy carries the same identity tag [decl `PA:967-970`, `PA:1829-1844`]. Moving the copy rewrites the original's offset; deleting the copy **deletes the original from the Show** [inf from `EM:414-476`].

**(g) Deleting a lamp actor deletes it from the Show**
- Deleting a materialized **Light** attachment actor removes that lamp from the Show (`INFINITY_STAGE_ATTACHMENT_LIGHT_DELETED`) [decl `EM:407-476`].
- To switch a lamp off, untick **Enabled** on its attachment row in the Cue Desk (it then isn't spawned [decl `PA:905-908`]), or set Intensity 0.
- Deleting a **prop / effect** actor does **not** remove it from the Show; it comes back on the next materialize [decl `EM:459`, Light-only].

**(h) Stale-copy trap in the Cue Desk** [inf from code, not measured]
- The Details pane works on a **copy** of the selected cue, taken when you select it [decl `CD:1500-1507`, `CP:39-48`].
- Any edit there writes the **whole copy** back [decl `CP:72-73`].
- The Cue Desk does not listen for Show changes made elsewhere [decl: no modify/undo hook in `CD`; `RefreshFromAsset` `CD:4193-4280` does not rebuild the proxies].
- So if you move or Details-edit a lamp in the **viewport** while its wing is selected in the Cue Desk, and **then** edit any field of that wing in the Cue Desk, the viewport change can be **reverted**.
- **Habit:** after viewport work, click another row and back before touching that wing in the Cue Desk.

### 3.3 Practicals, props and effects (non-light attachments)

- **Move / aim:** the gizmo writes back, as for lamps [decl `EM:227-298`].
- **Other settings** (mesh, effect type, haze density, fire, flicker…): edit them in the **Cue Desk → Attachments → [n]** only. Details edits on a prop or effect **actor** are **not captured** and are lost at the next materialize [decl `EM:343`: capture is Light-only].
- **Effect attachments** (Haze / Smoke / Steam / Fire / Wing Burn / Motes, with a Local Fog Volume "Medium") [decl `InfinityStage/Public/InfinityStageEffectTypes.h:46-190`].
  - Effect **flicker / pump** runs on world time. It will **not** replay identically when you scrub or re-run [decl audit row 16g, `InfinityStage/Private/InfinityStageEffectSource.cpp:691-726`].
- **Moving a prop over time:** key its transform in the Choreo (§3.4). I found **no per-frame plugin code that repositions non-drama attachments** [decl: only the drama loop `PA:1620-1660` writes attachment actors during evaluation]. So a key should hold [inf].

### 3.4 Lighting timing in Master time (Choreos, GO cues)

**What exists [meas/decl]:**
- Six Choreos, `LS_Choreo_Passage_1…6`. 0:00 = Passage start; bar and section markers come from the song [meas `choreo_report_choreo-apply-3.json`; `CUEING_MORNING_CHECKLIST_2026-10-05.md:1-8`].
- They are nested by the Master rebuild [decl `SB:367-483`].
- The Master opens with them since build 5 [meas `MORNING_SUMMARY:139-145`, 132/0 headless suite].

**Workflow:**
1. Cue Desk → **Curve Actions → Open Master in Sequencer** [decl `CD:3555`], then **double-click the Passage's Choreo section** to focus it.
   - Alternative: open `LS_Choreo_Passage_N` directly from the Content Browser. It then evaluates on its own, without the song [inf].
2. **Level lights, spot actors, Niagara, sounds:** drag them from the Outliner into Sequencer and key them. This is native Sequencer.
3. **Show lamps (and props):** drag the lamp actor into Sequencer.
   - The intended binding is **"Stage Attachment (by tag)"**, which survives rematerialize [decl `InfinityStage/Public/InfinityStageAttachmentBinding.h:12-27`; tests `…Binding.ResolvesByTagAcrossRespawn`, `…SurvivesRealMaterialize`, `…CreatedOnlyForAttachments` in `InfinityStageTests/Private/InfinityStageAttachmentBindingTests.cpp:38,75,130`].
   - **Check the binding type:** right-click the track's binding. If it is a plain possessable, use **Change binding type → Stage Attachment (by tag)** [decl fallback, `Scripts/patches/cueing_A_REVIEW.md:62`]. That drag-in picks the tag binding automatically is **UNCLEAR** (§8).
   - Then **+Track → the light component → Intensity / Light Color**, and key.
4. **Restore State.** Right-click each section → Properties → **When Finished → Restore State**, so the lamp returns to its Show value after the section. The tools do not set this [decl: no completion-mode code in `SB` or `Saved/CodexCueing/choreo_tool.py`]. The default is UNCLEAR.
5. **GO cues:** at the playhead press **M** for a marker and rename it `GO <number> <label>`, optionally with `HOLD` or `PASS`. Example: `GO 14 HOLD Warmers out`.
   - It must be **upper-case GO plus a number**, or the marker is ignored [decl `TC:601-648`].
   - Defaults: Choreos **PASS** (the music never waits); Scenes and other sequences **HOLD** [decl `CUEING_MORNING_CHECKLIST:10-13`].
   - Rules [decl `CUEING_MORNING_CHECKLIST:31-35`]:
     - put a cue's first key at least one frame **after** its GO;
     - no HOLD inside a Vamp (`InfinityStage.VampStart/VampEnd`, `TC:29-30`);
     - a GO on a Scene's very first frame doesn't stop a jump into it;
     - **never add a Camera Cut track to a Choreo**: the rebuild refuses to nest it (`INFINITY_CHOREO_REFUSED_CAMERA_CUTS`, `SB:393`).
6. **Save the Choreo asset** (Content Browser → right-click → Save). Opening the Master dirties the map (§5.1).

**Worked example: house warmers OFF in the Opening.** They are P01 Wing 001 Show lamps [decl `MORNING_SUMMARY:80`].
1. Open `LS_Opening_Curtain_Baked` (`/Game/InfinityStage/Interactions/`) in Sequencer.
2. Drag both warmer lamps in (tag binding), add **Intensity**, key **0** across the Opening, and set the section to **Restore State**.
3. Save the Opening. Check in PIE that they are off through the Opening and back on after.
- That a tag-bound key inside a **nested** sequence evaluates in PIE is **not yet measured** (§8). Make this your first test.

**Scenes, the Opening and Interactions** are ordinary sequences. Level lights are keyed there today [meas: hangar rise `Intensity` keys, audit §1]. Show lamps work through the tag binding, as above.

**Other cautions:**
- **Don't key on the Master root.** Master artist tracks are absolute and do not move on retime [decl audit row 14].
- **Sequencer audio stops during a GO hold** [inf, `PLAN_DIRECTING_AND_CUEING:56`]. A loop that must keep running through a hold belongs on a level Ambient Sound actor that the sequence switches on.

### 3.5 Level things

| Thing | How | Persists | Notes |
|---|---|---|---|
| **Global haze** | Outliner → the Exponential Height Fog bound to the Celestial rig (tag `InfinityStage.CelestialFog`) → Details: Fog Density, Height Falloff, Volumetric Fog (scattering, extinction, distance) | Level | The rig rewrites the fog's **inscattering colours** every apply [decl `InfinityStage/Private/InfinityStageCelestialRig.cpp:468-481`]; density and volumetric settings are not touched [decl, same lines]. **A second height fog you add is silenced** by "Suppress Foreign Environment Lighting" [decl `InfinityStage/Public/InfinityStageCelestialRig.h:92-107`]. Measured values: density 0.022, falloff 0.12, start 680 cm, g 0.55 [meas, `LOOK_DEPTH_PLAN_2026-10-05.md:115-116`]. Keying density in a Choreo should work [inf]. **300 m view ceiling** for volumetric fog [decl `SCENE_DOCKING_AUDIT_2026-09-29.md:56`]. Shafts need **back-light** (g = 0.55) [meas, memory `puss-lighting-authoring-lessons`] |
| **Local haze pockets** | Place Actors → **Local Fog Volume**; scale it; set density in Details | Level | Not on the silenced list [decl `CelestialRig.h:92-100` comment]. Each costs volumetric-fog work [inf, `LOOK_DEPTH_PLAN:131`]. The Show-attached alternative is a **Haze effect** attachment (§3.3) |
| **Rig / gridiron / floor** (Structure actors) | Select the Passage's Structure actor → Details → **Materialize Structure** after re-spacing or moving lamps | Level | Not automatic [decl `StructureActor.h:504-524`]. It goes stale when wings are re-spaced **or a light moves** [decl `:520-522`]. On failure it keeps the old build [decl `:504-505`] |
| **Hangar rise / roof / lattice / strike timing** | Select the Scene's Arrival actor → Details → **Read Hangar Timing** → edit → **Apply Hangar Timing** | That rise sequence (one undo step; Apply never saves) [decl `InfinityStage/Public/InfinityStageArrival.h:140-156`] | Fields: Roof Close Start/End, Lattice Start/End, Strike After Land, Dim Instead Of Strike, Dim Seconds [decl `Arrival.h:15-53`]. Hangars show **landed** in the editor and sink at BeginPlay in PIE [meas `BUILD_WINDOW_QUEUE.md`, HL] |
| **Strobe** | **Built** (2497c96). Place Actors → *Infinity Stage Strobe Light*, or move "P04 Strobe (default, Gary to place)". Details: Period, Flash, Decay, Ghost Seconds, Ghost Volume (a bounded PPV) | Level | 1 s, point light, ghost ≈ 1/3 s (Gary 5 Oct) [meas: placed + read back 5 Oct] |
| **Car light (sweep light)** | **Built** (a52051c). Place Actors → *Infinity Stage Sweep Light*. Details: Start/End Offset (local path), Curved Path + Arc Control Offset, Aim At Target + Aim Target Local, Travel / Repeat Every / Repeat Jitter / Start Delay Seconds, Fade In/Out, Peak Intensity, Temperature, Attenuation Radius, cones, Light Function Material | Level | Must cast shadows to break through the gaps. Trial: "P02 Car Light (trial, Gary to tune)" — **too bright as placed (9000 cd)**, try ~2500 [meas: stills 5 Oct]. Freezes on pause / follows scrub like the strobe [inf: same clock] |
| **Underpass rig + office tubes** | Select the Passage's Structure actor → Details → **Underpass**: Enabled, Columns / Knees / Deck / Catwalk, Column Every; **Tubes**: Tubes, From/To Station (a stretch), rows, Drop, Dead Fraction, Tube Seed; Tube Lights, Light Every / Max, Intensity (lumens), Temperature, Color, Light Function (e.g. `MI_LF_Flicker_Hum`). Then **Materialize Structure** | Level | On in all six Passages (rig); tubes only P02 stations 11–18 [meas 5 Oct]. Tubes are "occasional, dingy office" (Gary) — switch per stretch, not show-wide |
| **Post-process** | A Post Process Volume in the level, or the camera's post settings | Level | Keyable in a Choreo as a level actor [inf]. Capture exposure ≠ show exposure (memory `puss-capture-exposure-convention`) |
| **Your own level lights** | Place Actors → Spot/Point/Rect light | Level | Absolute world position: they **don't** follow wing re-spacing. Keep them few; VSM overflow shows up as coloured rectangles [meas, memory `puss-lighting-authoring-lessons`] |
| **Time of day in the editor** | Cue Desk → View → **Editor Lighting** (Manual Editing Light / Follow Master / presets) [decl `CD:3105-3165`] | Rig actor (level) | Editor convenience only |

### 3.6 Music

- **Where:** Cue Desk → click a **Passage heading** → right panel **Passage / Music** [decl `CD:1215`, `CD:3998`].
  - **Defining Music** (the rail): Sound, Source In / Out, Fade In / Out, Analysis Map [decl `TY:734-765`].
  - **Music** (the binding): Mode, Primary / Secondary rail, Rail Offset [decl `TY:768-783`].
  - Scenes carry their own Music binding in their Details [decl `TY:817`].
- **Persists:** to the Show [decl `PP:84-116`]. **Press Rebuild Master** afterwards: the Master's music sections are re-laid only by the rebuild [decl `SB:497-600`].
- **How it plays:**
  - The music section always **starts at the Passage start**.
  - **Rail Offset skips *into* the song.** It does not delay it [decl `SB:539-540`].
  - So "silence first, then music" inside a Passage is **not possible** by hand [decl; `MORNING_SUMMARY:50`: "needs a builder change"].
- **Volume:**
  - **Hand-keyed volume on the managed music section is wiped** by every rebuild [decl `SB:78-95`: `Volume->Reset()` then fades only].
  - Use Fade In / Fade Out. A mid-song dip cannot be done by hand; see the can't-do list.
- **Previewing:** Cue Desk **View** offers **Audible Music Scrub**, **Snap Scrub to Music Markers** and **Show Music Timeline Workspace** [decl `CD:2962`, `CD:3069`, `CD:3087`].
- **Extra sound** (spatial sound, stems, one-shots) goes on the **Choreo's own audio tracks**, separate from the song (Gary Q2) [decl `PLAN_DIRECTING_AND_CUEING:134`].
- **Avoid "Refit Selected Passage from Music".** It changes the wing count, and therefore the Passage length [decl tooltip `CD:3759-3764`].

### 3.7 Camera

- **Passages.** The camera is the cat on a track, in Dog Gaze. **Gaze overwrites rotation** in performance [memory `puss-camera-handover-facts`; Gary 5 Oct, "no camera moves in passage music bit"].
- **What you can tune:** in the Cue Desk music workspace, **Camera curve** → choose a channel [decl `CD:180-192`]:
  - Speed / Time Warp, Longitudinal, Lateral, Height, Look Ahead, Focal Length, Focus Distance;
  - Pitch / Yaw / Roll are overridden by gaze [inf];
  - the wing channels.
  - Use the **key at playhead** controls and **Curve Actions**: Add Speed Envelope, Remove Key at Playhead, Reset Active Curve, Pin Selected Wing as Timing Anchor, Pin Playhead as Music Anchor, Pilot Camera from Viewport, Open Master in Sequencer [decl `CD:3471-3556`, `CD:3574-3585`].
- **Persists:** to the **Master** sequence [decl memory `puss-two-authorities`, and `CD:4457` "Set Passage Camera Key"]. Save the Master.
- **Scenes** are all **Timeline**-owned [meas `MORNING_SUMMARY:108`]. Edit their cameras in the Scene sequence (Actions → **Open Scene Sequence** [decl `CD:3828`]).
  - After moving a Scene camera near its start or end, or after a Passage endpoint changes: **Actions → Scene Camera Handoff → Check All Scenes (read-only)**, then **Match Selected Scene**. This dirties the Scene sequences; save them [decl `CD:2778-2793`; `InfinityStageEditor/Private/InfinityStagePassageActorDetails.cpp:83`].
- **Don't put cameras or camera cuts in Choreos** (§3.4).

### 3.8 Scene lengths: the safe retime

1. Cue Desk → Scene row → Details. Either change **Duration Frames**, or tick **Use Sequence Length** and change the Scene sequence's playback end in Sequencer [decl `TY:803-807`].
   - The compiler warns if nested shots run past the playback end [decl `CO:229-236`].
2. **Rebuild Managed Master.** Later Passages move rigidly with their camera keys (patch K) and Choreos [decl audit rows 3, 4, 7, 9].
3. **Scene Camera Handoff → Match Selected Scene**. A range change needs a rematch [memory `puss-two-authorities`: the S1 30 Sep incident].
4. Run both gate tests (§5.4).
- The AI tool `extend_scene_playback.py` does the same with an extra key-carry check [decl `735a2fa`]. By hand, you are that check: scrub one later Passage and confirm the camera still meets its wings.
- Scene 3 (the cellist) is **unpausable** [decl `CUEING_MORNING_CHECKLIST:9`].

---

## 4. Previewing

| You want to see… | Editor (Cue Desk scrub / Sequencer) | PIE |
|---|---|---|
| Wings, mechanisms, Passage camera | ✅ Cue Desk **Scrub View: Camera / Overview**, **Play Selected**, **Follow Music Scrub** [decl `CD:3178-3189`, `CD:4075`, `CD:2952`] | ✅ |
| Choreo / Scene keys on level lights and tag-bound lamps | ✅ in Sequencer | ✅ (nested tag binding in PIE: UNCLEAR) |
| **Light Drama** strike / slow move | ❌ authored values only [decl `PA:1620-1623`] | ✅ |
| **GO holds / vamps** | ❌ | ✅ [decl `TC`] |
| Hangars sinking and rising | ❌ (landed in the editor) | ✅ |
| Effect flicker | free-running | free-running (world time) |
| Dog gaze | ❌ | ✅ with the dog or **Force Dog** |

**PIE controls** [decl `InfinityStage/Private/InfinityStageShowGameMode.cpp:44-47`; `CUEING_MORNING_CHECKLIST:15-25`]:

| Key | Does |
|---|---|
| **→ tap** | Next cue / segment. GO at a hold. Releases a vamp. In a Scene, steps to the next camera cut (SS built 301c8ae) |
| **→ hold** | 4× fast-forward, audio muted. Releasing into a hold stays held |
| **←** | Previous |
| **Space** | Play / pause, and GO at a hold |

**Cue Desk View menu settings for PIE:**
- **PIE Starts At Playhead** [decl `CD:2988`].
- **Play Through Boundaries** [decl `CD:3032`].
- **Rehearsal Transport (ignore external sound locks)**: lets you pause Scene 3 in rehearsal [decl `CD:3054`].
- **Live Camera Owner → Follow Show / Force Timeline / Force Dog / Force Dog (Gaze Only)** [decl `CD:5458-5475`].
  - Force Dog does not apply inside Sequence cues (the Opening, Interactions, Closing) [decl tooltip `CD:5470`].
  - **Re-select it after every PIE restart** [meas `MORNING_SUMMARY:108`].
- **Stop PIE yourself** with the toolbar Stop or Esc.

---

## 5. Safe working practice without AI

### 5.1 Saving: never Save All
- **The three things you save:**
  - the **Show** (Content Browser → `DA_InfinityStage_V1Show` → right-click → Save);
  - the **level** (File → **Save Current Level**);
  - **the sequence(s) you keyed** (Choreo / Scene / Opening / Master, each via right-click → Save).
- **File → Choose Files to Save…** lists every dirty package with tick boxes. Untick everything you didn't mean to change [inf: standard UE dialog, not checked in 5.8].
- **Expect surprise dirt:**
  - **Opening, scrubbing or playing the Master dirties the map** [meas, memory `ue58-sequencer-read-traps`].
  - A level save **persists evaluated state** (rig poses, wing instances) even when it looks net-nil [meas, memory `puss-camera-handover-facts`: a net-nil save shrank the file ~200 KB]. Before saving the level, close Sequencer, or park the playhead outside your keyed sections [inf].
- **Every write-back log line ends "save it intentionally".** The plugin never saves for you [decl `EM:295`, `EM:400`, `EM:473`].

### 5.2 Back up before the session (5 minutes)
1. Make a folder `E:\PussStage\Backups\PreGaryHand-20261005-HHMM` (the `Pre<Thing>-YYYYMMDD-HHMM` convention, AGENTS.md).
2. In Explorer, copy into it:
   - `Content\InfinityStage\Dev\DA_InfinityStage_V1Show.uasset` (~15 MB);
   - `Content\InfinityStage\Dev\Maps\L_InfinityStage_V1VerticalSlice.umap` (~18 MB);
   - `Content\InfinityStage\Dev\Sequences\` (the Master and Dev Scenes, ~7 MB);
   - `Content\InfinityStage\Choreo\` (~84 KB);
   - any Scene, Opening or Interaction sequence you plan to key (e.g. `Content\InfinityStage\Interactions\LS_Opening_Curtain_Baked.uasset`).
   - Sizes [meas, `du` today]. The level is a single `.umap`; this project's map has no external-actor folder [meas: `Content\__ExternalActors__` holds only EnvironmentPacks, KK_S1_Animals, Levels].
   - The tools copy these while the editor is open [meas: e.g. `Backups/PreSceneExitBlock-S6-20261004-214958` holds the Show + map + Scene].
3. Optional: a full snapshot to `D:\PussStageBackups` (e.g. `FullSnapshot-20260925-1853`) [meas, folder exists].
4. **Restore:**
   1. Close the editor and choose **Don't Save**.
   2. Copy the files back over `Content`.
   3. Reopen.
   - Never copy over files while the editor is open [inf: the editor holds the loaded copy and will overwrite it].
   - Never use in-editor reload on the open level (§5.5).

### 5.3 Undo, and its limits
- **Ctrl+Z works** for:
  - Cue Desk Details edits: the proxy is transactional and calls `Modify` [decl `CP:72`, `CD:1500-1501`];
  - Replicate (one transaction) [decl `CD:2284`];
  - viewport lamp moves, where the Show write happens inside the move transaction [inf].
- **After any undo:** the Passage may not re-materialize, especially if the selection changed. Run **Actions → Materialize Selected Passage** and look [inf from `CP:80-85`].
- **Treat as NOT undoable:** Rebuild Master (no transaction found in `CD:6028-6040`; UNCLEAR), and anything spanning several materializes. Restore from your backup instead.
- **If something is badly wrong:** stop, don't save, and restart the editor with **Don't Save**. This has been the standard recovery all week [meas, several in `MORNING_SUMMARY`].

### 5.4 The two gate tests, by hand
- **Where:** Tools → **Session Frontend** → **Automation** tab (in UE 5.x also **Tools → Test Automation**) [inf: standard UE UI].
- **How:** filter, tick **one** test, Start. Run each **alone** (house rule; memory `puss-verification-tiers`).
  - **`InfinityStage.Editor.SavedMasterMatchesShow`**: every Scene/Sequence section on the Master sits where the Show puts it, within 0.05 s [decl `InfinityStageEditor/Private/InfinityStageEditorAutomationTests.cpp:1491-1580`].
    - **Red** = you changed timing and didn't Rebuild Master (its message says so, `:85`).
    - It does **not** check Passage sections, music, Choreo or keys [decl audit §3].
    - It loads by path, so it reads the **in-memory** Show and Master, including unsaved edits [inf: `LoadObject` returns the loaded object].
  - **`InfinityStage.Editor.SceneCutBindingsResolve`**: Scene camera cuts resolve [decl `InfinityStageEditor/Private/InfinityStageCutBindingTests.cpp:26`].
    - **Red** = a Scene camera binding is broken. Don't save; restore that Scene sequence from backup.
- **Green** means "laid out consistently". It says nothing about "looks right".

### 5.5 Things that crash or corrupt: avoid them

| Do not | Why |
|---|---|
| **Reload the open level** (Asset Actions → Reload on the map, or reverting it in-editor) | Fatal "World Memory Leaks" [meas, memory `puss-mcp-python-crashes-the-editor` #3, via Python; by hand inferred same]. Restart with Don't Save instead |
| Give a **Chaos Cloth asset** to a Poseable / Skeletal Mesh component | Editor assert [meas, same memory #1, via Python] |
| Delete nodes in a **material you didn't create** | Rooted-node assert [meas via Python, #2]. In the UI: UNCLEAR. Add and rewire instead |
| **Reimport a mesh in place** | Cannot be undone in-editor [meas, memory `ue58-reimport-revert-by-reload-fails`] |
| Add a **Camera Cut track** to a Choreo | The rebuild refuses to nest it [decl `SB:393`] |
| **Save All** | Saves stray dirt (map dirtied by the Master, temp packages) |
| Disable a mid-Passage wing; Ctrl+D a lamp; delete a lamp actor to "hide" it | §3.1(g), §3.2(f–g) |
| Opening the Master with Choreos (crashed on 4 Oct) | **Fixed** in build 5 (A2e) [meas `MORNING_SUMMARY:139-145`] |
| Asset Actions → **Reload** on a *sequence* (not the map) | OK: the checklist uses it to drop a test marker [decl `CUEING_MORNING_CHECKLIST:29`] |

- **Opening sequence:** the curtain is a GeometryCache. A scrub can show a stale frame; re-pose in a later step [memory `ue58-geometrycache-sequencer-traps`].

### 5.6 Ending the day so the AI can resume cleanly
1. **Save only what you meant to.** Then close the editor; when it asks about the rest, choose **Don't Save**.
   - The AI tools take a **dirty-package census** and refuse to run if anything is dirty [meas: `census_before` in `choreo_report_choreo-apply-3.json`].
2. **Write five lines** in `Docs/Conductor/` or a chat message:
   - which Passages, lamps and sequences you changed;
   - whether you changed any **interval / tail / lead-in** (the AI must then re-check camera keys and pins);
   - whether you replicated lighting in a scored Passage.
   - The scores and light audits compare against saved baselines, and your edits will look like drift. The tools stop on drift by design [decl `MORNING_SUMMARY:34`].
3. Keep your backup folder until the AI has verified.

---

## 6. What you can't do by hand yet, and the least-bad workaround

| Can't do (by hand, today) | Least-bad workaround tomorrow | Minimal tool that unlocks it |
|---|---|---|
| **Change a Passage's length** with keys **shifting, not stretching**, and pins moving with the end | Freeze Passage lengths. If you must: lengthen the **tail** only, or shift downstream keys by hand (§3.1b) | C++: rebuild "keep + shift" key/pin policy + auto handoff rematch (RT test held, f52bf87) |
| ~~Strobe~~ **now built** (see §3.5) | — | — |
| (old row) Strobe with a ~1/3 s ghost | Key a level Point Light in the Choreo with step keys (on 1 frame, off) and a fast linear tail. Key a Post Process Volume's Blend Weight for the ghost. Deterministic, because Choreo keys run on the Master clock [inf] | Build held patch **S1** (`SPEC_STROBE_2026-10-05.md`) |
| **Operator cue list** (GO / Back / Jump / standby) | The GO markers already hold in PIE (→ / Space). Keep a paper list | **B1** Cue List panel (spec only, `SPEC_CUE_LIST_PANEL_B1_2026-10-05.md`) |
| **Mid-song music dip** / volume automation | Use the rail's Fade In / Out only | Builder: keep artist volume keys (or a separate gain track) |
| **Silence before the song** inside a Passage | None by hand | Builder change: a start delay for the music section [decl `SB:539-540`] |
| Key intensity / aim on a **Light Drama** lamp | Turn drama off on that lamp, or key a non-drama twin | Patch: multiply drama by the keyed value (`PLAN_DIRECTING_AND_CUEING:45`) |
| **Replicate only one kind of lamp**, or replicate without wiping scored lamps | Across Selection on just the pairs you want | Replicate option "by label/kind, add-don't-replace" |
| **Add a second lamp** to a pair with a guaranteed unique ID | Add Missing Stage Lights (empty sides only); one "+" per pair at most | Cue Desk "Add Light Attachment" that mints a GUID (or EnsureStableIds minting attachment IDs) |
| **Hide** one mid-Passage wing without splitting the Passage | Panels → Visible In Main Pass / Cast Shadow off | A "Hidden" flag distinct from Enabled |
| **Key wing motions** over time | Mechanism presets plus the Master wing channels (Travel / Rate / Phase) | Phase 2 Choreo wing tracks (Gary Q3) |
| **Looks crossfade** (many lamps at once) | Key each lamp | T2 Looks tool (proposal, `PLAN_DIRECTING_AND_CUEING:149-153`) |
| **Deterministic flicker** on effects | Accept the free-running flicker, or key a lamp instead | Patch: effect flicker on the Master clock (`EffectSource.cpp:691-726`) |
| **Deep-bay flash events** / far blinkers | Key lamps in the Choreo | Build held **LD** draft |
| Edit an effect or prop's settings on the **actor** | Edit it in Cue Desk → Attachments | Extend the capture hook beyond Lights (`EM:343`) |
| Re-check the cue list for lint (duplicate GO numbers, audio across holds) | Read the markers by eye | AI `cue_list_tool.py` (read-only, exists) |

---

## 7. A suggested order for tomorrow

1. Take the backup (§5.2). Open the editor and the Cue Desk.
2. **First test (5 min).** In `LS_Choreo_Passage_1`:
   1. drag a P01 lamp in;
   2. confirm the binding type is **Stage Attachment (by tag)**;
   3. key one Intensity flash;
   4. set the section to Restore State;
   5. PIE from P01 (**PIE Starts At Playhead**) and watch it flash.
   - If it doesn't flash, key level lights only today and note it for the AI.
3. Direct Passage by Passage:
   - **space** (gaps, keeping the total);
   - **pose and movement**;
   - **lamps** (viewport plus Details, replicate with Selection scope);
   - **drama** (check in PIE);
   - **timing in the Choreo**;
   - **haze**.
   - Save the Show, the level and that Choreo after each Passage.
4. If you touched any Scene length: Rebuild Master → Match handoffs → the two tests.
5. End clean (§5.6).

---

## 8. UNCLEAR (what was searched, and what would settle it)

| Item | Searched | Settles it |
|---|---|---|
| Does dragging a Show lamp into Sequencer create the **tag binding** automatically, or a possessable? | `AttachmentBinding.h` declares it (`SupportsBindingCreationFromObject`); the review lists it as intended; M4 used a **possessable** made by Python (`Saved/CodexCueing/m4_capture_probe.py:72`). No drag-in measurement found | First drag-in tomorrow: right-click the binding and read its type |
| Does a tag-bound key inside a **nested** Choreo / Opening evaluate in **PIE**? | Tests cover the nested *data walk* (`…SequenceBindsTagFindsNested`, `AttachmentBindingTests.cpp:159`), not PIE evaluation. The plan's UNCLEAR table lists it | The §7 step 2 test |
| Default **completion mode** (Restore vs Keep State) of new sections | No completion-mode code in the plugin or the Choreo tool | Set it explicitly per section |
| Does the song play while a Choreo is focused from the Master? | Plan lists it as unchecked | First open |
| Is a Cue Desk-induced **revert of viewport lamp edits** (stale proxy) real? | Inferred from `CP:72-73` plus no refresh hook in `CD`. Not measured | Move a lamp, then edit the same wing's Gap in the Cue Desk, and watch the lamp |
| Are **Show writes from the capture hook undoable** with Ctrl+Z? | The hooks call `Modify` without their own transaction (`EM:288`, `EM:392`) | Move a lamp, Ctrl+Z, Materialize, compare |
| Is **Rebuild Master** undoable? | No transaction seen in `CD:6028-6040` | Treat as not undoable |
| Does a single "+"-added lamp with an empty ID behave? Do two collide? | Code paths `PA:1820-1848`, `SA:91-123` | Add one, move it, check the log names the right attachment |
| Does saving the level with Sequencer open bake keyed values into level lights? | Memory says level saves persist *evaluated* state (rig, wings); lights not tested | Close Sequencer before saving |
| Does the **Source Out** field clip the music section? | The builder sets only start offset and range (`SB:539-541`); no Out use seen there | Listen at the Passage end |
| The UE 5.8 menu names "Choose Files to Save…", "Session Frontend / Test Automation" | Standard UE; not checked in this install | Look in the File / Tools menus |
| Does deleting material nodes **by hand in the UI** crash on pre-existing assets? | Only the Python path was measured | Don't do it |

## Sources read for this guide

- **Code:** `CD`, `EM`, `CP`, `PP`, `SB`, `TY`, `PA`, `SA`, `CO`, `TC`, `InfinityStageLightDrama.h/.cpp`, `InfinityStageAttachmentBinding.h`, `InfinityStageCelestialRig.h/.cpp`, `InfinityStageStructureActor.h`, `InfinityStageArrival.h`, `InfinityStageWingEditProxy.cpp`, `InfinityStageShowGameMode.cpp`, `InfinityStagePassageActorDetails.cpp`, `InfinityStageCameraRig.cpp`, and the gate tests.
- **Docs:** `PLAN_DIRECTING_AND_CUEING_2026-10-04.md`, `CUEING_MORNING_CHECKLIST_2026-10-05.md`, `Scripts/patches/cueing_A_REVIEW.md`, `RETIME_ROBUSTNESS_AUDIT_2026-10-04.md`, `MORNING_SUMMARY_2026-10-04.md`, `SPEC_STROBE_2026-10-05.md`, `LOOK_DEPTH_PLAN_2026-10-05.md`, `P06_DOCKING_CLEARANCE_2026-10-04.md`, `BUILD_WINDOW_QUEUE.md`.
- **Project memory notes** as named inline.
