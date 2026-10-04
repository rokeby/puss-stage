# Light & sound cueing audit (4 Oct, offline)

Gary asked: *"Soon I will need granular hand tuning of moment-to-moment lighting and sound cues. Is that
possible now?"* No Unreal, MCP or build was used. Tags: **[decl]** = read in source or header,
**[meas]** = file read or byte-grep on disk today, **[inf]** = reasoning that has not been checked.
Paths: `IS/` = `Plugins/InfinityStage/Source/InfinityStage/`, `ISE/` = `…/InfinityStageEditor/`.

## Answer for Gary (5 lines)

1. **Partly.** Lights you place yourself (rig, hangar and Scene lights) can be keyed frame by frame in each Scene's own sequence today, and those keys stay in step with the Scene through rebuilds.
2. **The Passage stage lamps (Show lamps) have no timeline control.** Their only automation is distance-based Light Drama, which only runs inside the lamp's own Passage, so "dark in the Opening, on in P01" cannot be authored. Sequencer keys on them break when the Passage is rebuilt.
3. **Sound is music-only.** There is one music rail per Passage or Scene, with source in/out and fades. There is no sound-cue type, mechanism sounds are chosen but never played, and the only way to place a one-shot is a hand-placed audio section in a Scene sequence.
4. **Live operation is transport only:** →, ← and Space, plus vamps set by sequence markers. There is no GO for lights or sound.
5. **Recommendation:** add one Show-owned "Lighting & Sound cue list" that addresses lamps by GUID and places cues relative to a Passage or Scene. The first slice is about 250 lines of C++ plus tests. Its first job is the house warmers.

## 1. Lighting: what can be tuned today

| Mechanism | How you tune it | Granularity | Survives rebuild / materialize / rematch? | Time domain |
|---|---|---|---|---|
| **Show light attachments** (lamp settings) | Edit the spawned lamp in the editor. Every setting and its position write back to the Show (`ISE/Private/InfinityStageEditorModule.cpp:292-353`) [decl]. | Static: one value per lamp, not time-varying. `bEnabled` decides whether the lamp is spawned at all (`IS/Private/InfinityStagePassageActor.cpp:905-908`) [decl]. | Yes. The GUIDs are stable and materialize re-spawns from the Show (`:859-1009`) [decl]. | None |
| **Light Drama, strike** (`IS/Public/InfinityStageLightDrama.h:38-76`) | Show fields: strike distance, ramp, stutter, unstruck level, after-pass and decay. | Per lamp, in cm of camera route. | Yes, because the values are Show data [decl]. | Passage distance, **only inside the lamp's own Passage segment** (`PassageActor.cpp:1267-1270`, then the drama block at `:1620-1662`). Station-anchored lamps only (`:1642`). Game worlds only (`:1623`) [decl]. Outside the segment a lamp keeps its last state [inf]. |
| **Light Drama, slow move** (`LightDrama.h:78-104`) | Pan and tilt amplitude, period, phase. | Continuous; the phase is fixed by identity. | Yes [decl]. | Master seconds (`PassageActor.cpp:1625`), still only in-segment [decl]. |
| **Effect-source flicker and pump** (`IS/Public/InfinityStageEffectTypes.h:94-137`) | Show fields: pulse period and duty, flicker amount, linked light GUID. | Continuous. | Yes [decl]. | **World game time** (`IS/Private/InfinityStageEffectSource.cpp:710`, `:691`), so it does **not** replay identically on scrub [decl]. It stops flickering a lamp that has drama (`:452-456`) [decl]. |
| **Cue Desk** (`ISE/Private/SInfinityStageCueDesk.cpp`) | "Add Missing Stage Lights" and "Replicate First Pair's Lighting" (`:3772-3784`). The Cue details view (`:1075`). Editor-lighting presets (`:3105-3160`). | Per lamp or per pair; not timed. | Yes, because these are Show writes [decl]. | None. The Cue Desk has **no lighting timeline** [decl, from a search of all LOCTEXT strings]. |
| **Passage section channels** (`IS/Public/MovieSceneInfinityPassageTrack.h:17-34`) | Keys on the managed Passage section. | Frame. | Keys are absolute; a rebuild moves the sections but not the keys [decl, memory]. | Master. These channels are **camera and Wing only; there is no light channel**. ShowBuildTodo E.3 is unbuilt (`Docs/ShowBuildTodo.md:96`) [decl]. |
| **Hangar rise sequences** (`LS_S1…S6_HangarRise`) | Ordinary Sequencer `Intensity` float keys on level lights (`Saved/CodexConductor/hangar_light_keys_probe.json`; the byte-grep found LightComponent bindings in all six) [meas]. | Frame. | Yes. These are level actors, not materialized, and nested in the Scene, so they move with the Scene section [inf]. | Scene sequence time. |
| **Level lights keyed in Opening or Scene sequences** | The same Sequencer workflow. | Frame. | Yes, for level actors [inf]. **Not for Show lamps**, which are re-spawned on materialize (`PassageActor.cpp:885-892`) [decl]. Keying a Show lamp in the editor would also feed the capture hook and write the keyed value into the Show as its authored value [inf, from `EditorModule.cpp:292-345`]. | Scene or sequence time. `LS_Opening_Curtain_Baked` contains no LightComponent today (byte-grep) [meas], so the FOH rig in the Opening plan has not been applied yet. |
| **Artist tracks on the Master** | Allowed: a rebuild touches only the managed tracks (`ISE/Private/InfinityStageSequenceBuilderLibrary.cpp:195-480`, `RemoveStaleSections` `:42-54`) [decl]. | Frame. | The tracks survive, **but their keys are absolute**, so a Show retime leaves them behind [decl, memory]. The Master file has no float, audio or event tracks today (byte-grep of `LS_InfinityStage_V1Master`) [meas]. | Master. |
| **Lighting cue type in `FInfinityShowCue`** | **None.** The cue types are `WingPair`, `Scene` and `Sequence` (`IS/Public/InfinityStageTypes.h:21-26`) [decl]. | n/a | n/a | n/a |

**Live tweak in PIE [inf]:** drama evaluation re-reads the Show asset every frame (`PassageActor.cpp:1266`,
`:1627-1660`), and the asset is shared with PIE. Editing a *drama* lamp's Intensity or Drama fields during PIE
should therefore show up on the next frame. Lamps without drama will not update, and the PIE capture hook is
switched off (`EditorModule.cpp:306`). Neither behaviour has been measured.

## 2. Sound: what can be placed today

- **Music rails** [decl]. Each Passage or Scene binds one rail (`Start` / `Continue` / `Silence` /
  `ExplicitCrossfade`, `InfinityStageTypes.h:29-35`). A rebuild writes one managed audio section per segment
  (`SequenceBuilderLibrary.cpp:366-480`). The editable fields are Source In/Out, the rail offset and the fades
  (`Types.h:734-779`), set in the Cue Desk music panel (`CueDesk.cpp:3998`).
  - Granularity: frames, but **only fades at the segment edges**.
  - **Volume keys you add by hand are wiped on every rebuild** (`Volume->Reset()`, `SequenceBuilderLibrary.cpp:84`) [decl].
  - Time domain: Master, segment-relative, so the sections follow retimes [decl].
- **Scene-local audio** [meas, byte-grep]. Ordinary `MovieSceneAudioSection` appears in `Scenes/LS_Animals_1`,
  `KK_S2_Shrine/LS_Shrine` and two StageTest copies, and in no other `LS_*`. Sections placed in a Scene sequence
  are in Scene time and survive Master rebuilds [inf]. **Today, this is how a sound designer places a one-shot**:
  as an Audio track inside the Scene's or Opening's own sequence. Passages have no child sequence, so the only
  option there is an absolute Master artist track, which drifts on retime.
- **Mechanism sounds** [decl]. A per-Passage set with a deterministic picker (`Types.h:395-423`,
  `PassageActor.cpp:1850-1912`). **No playback path exists**: the only callers are tests
  (`InfinityStageTests/Private/InfinityStageCompilerTests.cpp:1750-1771`). The runtime contains no
  `UAudioComponent` or `PlaySound` call.
- **`Sound` attachment kind** (`Types.h:143`) [decl]. It has no sound field. It spawns only when you give it a
  custom `ActorClass`, and otherwise it is skipped (`PassageActor.cpp:919-931`). It is not timed.
- **There is no sound cue type, event track or ambience system** [decl, plus a byte-grep showing no `MovieSceneEvent` in any `LS_*` [meas]].
- **External sound** [decl]. Scenes marked `DeclaredUnpausable` refuse hold or rate changes
  (`IS/Private/InfinityStageTransportController.cpp:1802-1825`). Fast-forward mutes the **first**
  `UMovieSceneInfinityAudioTrack` only (`:1897-1937`, `FindTrack`).

## 3. Live operation

- **Keys** [decl]: → is advance, or hold for fast-forward; ← is previous segment; Space is play/pause
  (`IS/Private/InfinityStageShowGameMode.cpp:44-47`).
- **Cue Desk transport** [decl]: the same transport commands, routed through the operator rules while PIE is
  running (`CueDesk.cpp:4088-4096`, `:5694-5704`).
- **Vamps** [decl]: Scene marked frames `InfinityStage.VampStart/End` loop until → releases them
  (`TransportController.cpp:26-27`, `:152-230`).
- **There is no manual GO for a light or sound state.** Every light or sound change is either time-baked or
  distance-baked [decl].

## 4. Recommended design: a hand-tunable cue layer

**Data (Show-owned).** `TArray<FInfinityLxSxCue> CueList` on the Show. Each cue has:

- a GUID, a number and a label;
- an **anchor**: segment GUID plus an offset in segment frames, *or* Passage route distance, *or* a named marker;
- **targets**: a lamp `(CueGuid, AttachmentGuid)`, a Show-lamp group tag, or a level actor (soft reference or tag);
- per target: level (×), colour or temperature, fade-up and fade-down frames, and a curve;
- for sound: `USoundBase`, gain, fade, 2D or attached, and one-shot / stem / stop;
- an optional `bWaitForGo` flag for theatre-style manual cues.

**Why it survives rebuilds.** Anchors are relative to a segment, so the compiler resolves them to absolute Master
frames on every compile and they follow retime and rematch. Lamps are resolved at run time through the identity
tag `InfinityStage.Attachment.<cue>|<att>` (`PassageActor.cpp:967-970`), not through Sequencer bindings, so
materialize can re-spawn the actors freely.

**Evaluation.** A pure *tracking* function: `state(lamp, MasterFrame)` is the last cue at or before the frame,
cross-faded over its fade time. It is deterministic forward, in reverse and on scrub. The transport tick calls it
in game worlds for every frame, **regardless of segment**, which removes the in-segment gate.

**With Light Drama:** **multiply**, with a single writer per lamp. Final intensity = authored × drama × cue.
A cue level of 0 means `SetVisibility(false)`, so the shadow cost is kept. `ApplyToLamp` takes an extra
cue-scale argument, and outside the lamp's segment the cue layer writes alone. The effect-source flicker rule
(`EffectSource.cpp:452`) extends to "yield to drama or a cue".

**Sound.** The Master rebuild writes the sound cues as managed sections on a **second** managed audio track. Each
section's BlockGuid is the cue GUID, the same pattern as music (`SequenceBuilderLibrary.cpp:400-423`). This gives
Sequencer-native scrub and keeps segment-relative placement. The fast-forward mute must then loop over every
managed audio track. `bWaitForGo` cues need a run-time player, and this is phase 2.

**Editing.** A "Cues" panel in the Cue Desk:

- a table of cues;
- "Record at playhead", which writes the anchor relative to the current segment;
- nudge ±1 frame;
- fade fields;
- an optional read-only mirror as Master marked frames, so the cues show in Sequencer.

**C++ needed:** these touch Rig & atmosphere's and the Transport owners' files, need a build, and need Gary or
the conductor to sign off.

- `Types.h`: the cue struct and `ShowAsset.h`: the array;
- `Compiler.cpp`: resolve anchors to absolute frames;
- a new `InfinityStageCueLayer.cpp` with the pure evaluator and tests;
- a `TransportController` tick hook;
- the `LightDrama` signature change;
- `SequenceBuilderLibrary` sound sections;
- the Cue Desk panel.

**Smallest first slice (the house warmers):** lamp-intensity cues only, anchored by segment GUID plus offset,
with no sound, no UI and no GO.

- Data is filled by a Python tool through the guarded MCP route.
- The evaluator runs from the transport tick in game worlds and finds lamps by tag.
- Two cues: `Opening + 0: House L/R × 0` and `P01 + 0 (or Opening end − N): House L/R × 1, fade N`.
- Roughly 200–300 lines plus pure-function tests: monotonic tracking, reverse/scrub determinism, and that a
  missing tag warns and skips.

This is the clean version of proposal 3 in the Opening plan (`OPENING_SEQUENCE_PLAN_2026-10-04.md:157-162`). It
keeps the warmers as Show lamps, avoiding the level-actor authority change in its proposal 1, and it generalises
beyond one flag. [inf: design; not built or measured]

## UNCLEAR (what was searched)

- **How the managed Scene/Sequence sub-sections complete.** I did not determine whether they restore or keep
  level-light state at the segment's end. The only completion mode in plugin source is `KeepState` on the
  Passage section (`IS/Private/MovieSceneInfinityPassageTrack.cpp:208`), and I did not check UE 5.8's default
  for sub-sections.
- **Whether production Scenes are already keying level lights.** Byte-grep found `LightComponent` only in the
  HangarRise/Fold sequences. That grep is not a binding census, and an editor session may hold unsaved changes.
- **Whether drama edits made during PIE apply live.** This is inferred only.
- **How a reverse scrub from P01 back into the Opening leaves a lamp.** Inferred to keep its last state; not measured.
- **What the Scene-local audio sections contain.** Only their presence was grepped.
