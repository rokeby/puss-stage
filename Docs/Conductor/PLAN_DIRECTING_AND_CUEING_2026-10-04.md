# Plan: directing and live cueing (Cueing stream, revised 4 Oct, evening)

**What this replaces.** It supersedes the Show-owned lamp-cue evaluator in `SPEC_LAMP_CUES_2026-10-04.md`.
- That spec put lamp levels in a new data store and a new evaluator.
- This plan uses **Sequencer as the directing surface** and adds only what Sequencer lacks.
- The conductor's notes on that spec still apply where marked: cheap re-resolve, a negative control on editor worlds, and the warmers' editor view.

**Tags.** Each claim is tagged with how it is known:
- **[decl]**: read in plugin or engine headers today.
- **[meas]**: read from a file on disk today.
- **[inf]**: design or belief, not yet checked.

**Paths.** `IS/`, `ISE/` and `IST/` are the plugin's runtime, editor and tests modules, under `Plugins/InfinityStage/Source/`.

## The idea in one paragraph

**The timeline is the content; the cue list is how you run it.** You direct in Sequencer: keys, audio, Niagara, gobos and lamps, with native scrub, loop, repeat and audio-scrub.

- **Passages.** Every Passage gets a **Choreography sequence** locked to its song. Everything in it dances to the music, and it moves with the Passage when the Show is retimed.
- **Scenes and other sequences.** The Scenes, the Opening, the shadow interactions and the finale are already sequences, so you direct them where they are.
- **Show lamps.** A new **attachment binding** lets Sequencer key the stage lamps. Today they are the one thing it cannot key, because materialize re-spawns them.
- **The cue list.** Cue points are **GO markers** dropped on any timeline. The transport **holds** at them until GO. A QLab-style **Cue List** shows every GO in show order, with number, label, operator notes and an automatic "what this cue does" summary, and offers GO / Back / Jump / Re-run.

## Part 1. Passages: choreography to the music

**What exists today.**
- Each Passage has one music rail section on the Master. It is placed at the segment start plus `RailOffsetFrames` and plays the rail from `SourceInFrame` (`IS/Public/InfinityStageTypes.h:734-779`) [decl].
- There is **no child sequence**, so anything keyed for a Passage is an absolute Master key that drifts when the Show is retimed (audit §1) [decl].

**What we add.**
1. **`LS_<Passage>_Choreo`**, one per Passage.
   - A tool creates them. A new Show field, `PassageSettings.Choreography` (a soft reference), points at each one.
   - The Master rebuild nests each one as a managed sub-section on the existing Scene track. The rebuild already writes managed sub-sections at `ISE/Private/InfinityStageSequenceBuilderLibrary.cpp:312-315` [decl].
   - The sub-section starts **at the music section's start**, and its inner time is **song time**. One second in the Choreo is one second of the song.
   - It follows retime, rematch and Passage resize because the rebuild moves it [inf; the same mechanism Scenes rely on, which the audit records as surviving rebuilds].
2. **A beat and section grid.** The tool copies the song's analysis markers (`UInfinityStageMusicMapAsset` markers, `IS/Public/InfinityStageMusicMapAsset.h:40-52`) [decl] into the Choreo as marked frames, so keys can snap to musical moments.
   - Whether every rail has a map is not yet checked [inf].
3. **The song is heard while you work.** When you double-click into the Choreo from the Master, Sequencer plays it in the Master's context, so the Passage music plays as you scrub [inf; this is standard Sequencer behaviour and will be checked on the first open].
4. **What goes in a Choreo:**
   - level lights, gobos, spot actors and Niagara: native today;
   - sound one-shots and stems: native Audio tracks;
   - Show lamps and attachments: through the binding in Part 4;
   - events: native.
5. **Limits.**
   - **Light Drama strike lamps** are written again later in the same frame by the camera rig. It ticks in `TG_LastDemotable` (`IS/Private/InfinityStageCameraRig.cpp:99`), after Sequencer [decl]. So drama wins inside its Passage. Keying intensity on a strike lamp is warned against and refused by the tools until a follow-up patch multiplies the two.
   - **Wing movements** stay as they are (the camera and Wing channels on the Passage section, plus distance-driven mechanisms). **Wing arrangement** per Passage is Show data in the Cue Desk. Keying wing motions in the Choreo is Phase 2; see question Q3.
   - **Puss** is the camera, and the camera is the cat's score. It is out of scope here.

## Part 2. Scenes, the Opening, transitions, the shadow interactions and the finale

These are already sequences nested in the Master, and **level lights are keyed in them today**. The hangar rise sequences carry `Intensity` keys [meas, audit §1]. What they lack:

- **Show lamps.** For example, the House warmers off in the Opening. They need the attachment binding (Part 4).
- **Cueing instead of one soundtrack.** These need GO holds (Part 3).
- **Loops that continue through a hold.**
  - A Sequencer audio section **stops when playback holds** [inf].
  - An ambience or loop that must keep running through a hold should therefore be an actor in the level that the sequence switches on (an Ambient Sound or Niagara actor activated by a key or event). It then keeps running on world time.
  - Alternatively, use the existing **Vamp**: a region that loops until GO (`IS/Private/InfinityStageTransportController.cpp:152-230`) [decl].
  - The tool will flag Sequencer audio that crosses a hold.

## Part 3. The cue system (QLab-style)

**A cue** is a marked frame on any sequence (the Master, a Scene, the Opening or a Choreo). Its label reads **`GO <number> <label>`**, for example `GO 14 Warmers out, Puss enters`.
- Because it is a marked frame, you drag it in Sequencer like any other marker.
- Its **mode** comes from the Cue Sheet:
  - **Hold** (the default in sequences): playback stops on the frame until GO;
  - **Vamp**: the region from this cue to the next loops until GO;
  - **Pass** (the default in Passages): the cue is labelled and listed, but the music never waits.

**The Cue Sheet** is a Show array keyed by cue number. It holds the mode, notes for the stage manager (live performers, real lights, sound desk), standby text and an optional auto-follow delay. Marker position is the truth for *when* a cue fires; the Cue Sheet is the truth for *what the operator reads*.

**What a cue does** is everything keyed between GO n and GO n+1. The list summarises it automatically from the tracks that have keys in that span, for example "3 lamps, 1 sound, House L intensity". The timeline stays the only content, so the cue list and the show cannot disagree.

**The operator Cue List** is a panel in the Cue Desk (`ISE/Private/SInfinityStageCueDesk.cpp`). It shows:
- one ordered list across the whole show, built by resolving every GO to its absolute Master frame;
- **current and next** cues in large type, with notes and the time elapsed in the current cue;
- **GO**, **Back**, **Jump to cue**, and **Re-run cue** (jump to the cue's frame, then play; this is the rehearsal loop for "repeat that moment");
- a hold indicator;
- in PIE, the GO key (question Q1).

**Later, out of the 24 h scope:** sending OSC or MIDI to a real lighting or sound desk when a cue fires. The Cue Sheet gains an "external" column for this.

## Part 4. The attachment binding: keys that survive materialize

**What we add.** A new `UInfinityStageAttachmentBinding`, which subclasses `UMovieSceneCustomBinding`. UE 5.8 declares this API (`Engine/Source/Runtime/MovieScene/Public/Bindings/MovieSceneCustomBinding.h:79-170`: `ResolveBinding`, `SupportsBindingCreationFromObject`, `CreateNewCustomBinding`) [decl].
- It stores the attachment tag `InfinityStage.Attachment.<cue>|<att>`, which is minted at `IS/Private/InfinityStagePassageActor.cpp:967-970` [decl].
- At play time it resolves the actor by that tag. It looks up **one tag per stale entry** through a world-level cache, never a full actor iteration per tick (conductor's note). A counter is logged.
- When you add a Show lamp to Sequencer, it binds this way automatically (`SupportsBindingCreationFromObject`).
- Whether Sequencer's editor UI honours this for drag-in is [inf]. The fallback is a "Bind selected stage lamps" tool button.

**Capture guard.** The editor writes any Details change on a stage lamp back to the Show (`ISE/Private/InfinityStageEditorModule.cpp:292-345`) [decl]. If you edit a lamp while it is keyed, that would write the *keyed* value into the Show as its authored value.
- The guard skips that write when an open Sequencer binds the actor, and logs `INFINITY_CAPTURE_SKIPPED_SEQUENCER`.
- How "binds the actor" is detected is [inf] until it is written.

**Restore state.** Sections that touch Show lamps are set to **Restore State**. The lamp then returns to its authored Show value when the section ends, and scrubbing backwards behaves the same way.
- This is how the warmers work: they are keyed to 0 inside the Opening and restore to the authored 1740 cd at P01.

## Build plan (24 h, about 24 % of Claude usage)

| Step | What | Files and owners | Needs |
|---|---|---|---|
| **A1** | Attachment binding, capture guard, tests | new `IS/…AttachmentBinding.*` (mine); held patch to `ISE/…EditorModule.cpp` | build |
| **A2** | `PassageSettings.Choreography`; rebuild nests the Choreo at the music start | held patches to `IS/…Types.h` and `ISE/…SequenceBuilderLibrary.cpp` | build |
| **A3** | GO markers: Hold, Vamp and Pass modes in the transport. Fast-forward mutes **all** audio, nested included | held patch to `TransportController` (`:131-230`, `:1897-1937`) | build |
| **T1** | Tools (Python, no build): create the six Choreos, copy the beat markers, add/rename/number GO, warn on strike lamps and on audio across holds | `Saved/CodexCueing/*` (mine) | editor slot |
| **B1** | Cue Sheet array and Cue List panel | held patch to `SInfinityStageCueDesk.cpp`; new Slate file (mine) | second build |

**The first build** carries A1, A2 and A3, one build with all three patches.

**Tests**, under `InfinityStage.Cueing.*`:
- `Binding.ResolvesByTag`, plus a control: a respawned lamp still resolves.
- `Binding.StaleReresolveIsSingleLookup`.
- `Capture.SkippedWhenSequencerBound`, plus a control: an unbound lamp is still captured.
- `Choreo.FollowsRetime`, plus a control: an absolute key does not follow.
- `GO.HoldStopsAtMarker`, `GO.PassNeverHolds` and `GO.VampLoopsUntilGo`.
- `FastForward.MutesNested`.
- `Binding.EditorWorldDoesNotWrite`.

After APPLY, run `SavedMasterMatchesShow` and `SceneCutBindingsResolve` singly.

**PIE proof.**
1. The warmers are keyed to 0 in the Opening and restore at P01.
2. A test cue `GO 1` holds the Opening until →.
3. One P01 Choreo key, a lamp flash on a beat, lands on the beat after a ±N-second retime dry run.

The probe is read-only and never ends PIE.

**Tomorrow, if A lands tonight:** you direct in Sequencer, Passage by Passage in the Choreos and Scene by Scene in their sequences, and drop GO markers as you go. B1, the operator panel, follows. **If the build slips**, Scenes and the Opening can still be directed today for level lights and sound. Show lamps and Passages wait for A1 and A2.

## Questions for Gary (sent as a questionnaire)

- **Q1.** Which key is GO?
- **Q2.** Choreo time base: song time, or Passage start?
- **Q3.** Do wing motions need to be keyable in the Choreo tomorrow?
- **Q4.** How do the warmers come on at the Opening→P01 seam?

## UNCLEAR, and what would settle it

| Question | Status | How it gets settled |
|---|---|---|
| Does the custom binding resolve inside nested sub-sequences, in editor and PIE? | declared only | Test, then PIE |
| What completion mode do sub-sections default to? | not searched past the audit | Set it explicitly instead |
| Does the music play while a focused Choreo is open? | not checked | First editor open |
| Does every rail have a music map? | not checked | Tool INSPECT |
