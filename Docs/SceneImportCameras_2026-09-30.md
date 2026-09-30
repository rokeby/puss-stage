# Importing scene sequences: the camera rules

Look & camera, 30 Sep 2026. This is for bringing complete sequences (Klara's Scene 1 and 2 content, and
any later cutscene) into a hangar Scene so the show can cut to them. It covers the camera side only; the
level setup is in `KlaraDioramaLevelSetup.md` and the scene plan in `Conductor/SCENE_BRIEF_2026-09-30.md`.
Each rule says whether it is measured, declaration-proven or inferred.

## 1. Cameras travel inside the sequence: use spawnables

**Author every camera in an imported shot sequence as a SPAWNABLE** (or a spawnable custom binding), not
a possessable.
- A possessable binds to an actor in the level the sequence was authored in. Imported into the show
  level, it binds to nothing, and its cuts show nothing.
- Measured 30 Sep: Scene 1's `LS_Animals_1` has four cuts bound to possessables labelled
  `CineCameraActor`, `…2`, `…3` and `…4`, and no actor in the show level carries those labels. In a PIE
  play-through none of them ever took the view.
- A spawnable is made by the sequence when it plays, so it resolves in any level (inferred from standard
  UE behaviour; not yet measured here).

## 2. Nested shot cuts outrank the Scene's own cuts

Measured 30 Sep, Scene 3: the nested `LS_Clams` cut took the view 0.1 s into the Scene, while the Scene's
root track still said Entry. So an imported shot's cameras win over the Scene's handoff cameras as soon
as they resolve. An unresolved nested cut still outranks the root and shows nothing, which leaves the
transport's Entry claim up for the whole Scene. That is the Scene 1 symptom (inferred from the labels;
consistent with the PIE run).

## 3. The gates, before an import is accepted

1. **Bindings resolve:** `InfinityStageCameraPilotLibrary.check_scene_cut_bindings(show, cue_guid)` (held
   patch N; available after the next build). One line per cut, root and nested. UNRESOLVED and UNCHECKED
   both fail. Until N is built, `Saved/CodexCameraPilot/probe_nested_cut_bindings.py` checks by LABEL
   only, which is weak.
2. **Cut coverage:** `Saved/CodexCameraPilot/probe_interaction_cut_binding.py`. No `NO_RULE_STRETCHES`,
   or a jump or scrub into a gap shows the previous camera (TransportController.cpp:807–880 reads ROOT
   cuts only).
3. **Length:** change a Scene's length only through Soft goods' `Saved/CodexSoftGoods/extend_scene_playback.py`.
   It rematches the handoffs and gates on coverage. Held patches K (Passage keys travel with a moved
   section) and L (no cut gap; the Exit hold survives a lengthening) must be built first.
4. **Acceptance, measured:** a PIE play-through into the Scene with
   `Saved/CodexCameraPilot/scene1_tail_view_pie.py` (the mode file takes `scene`, `end_s`, `shots`). The
   view target must switch to the imported camera at its cut time. That is how Scene 3 was confirmed.

## 4. What the dog does over imported cameras

The hangar Scenes 1–6 are `DOG_FREE_LOOK` (applied 30 Sep: "Free until we handover to the cutscene
sequences, to come").
- The dog's look is an offset on whichever camera is live, and any keyed camera rotation is the base it
  layers onto (declaration-proven: Go1RemoteReceiverComponent.cpp:88–121, :290–296).
- With held patch O, the look resets at every hard cut, so each imported shot opens as authored (Gary:
  "Reset at every cut").
- When the cutscene sequences arrive, revisit the owner: Gary's "free until we handover".

## 5. Don't author by scrubbing the Master and saving

Opening, scrubbing or playing the Master in Sequencer dirties the show map (measured 30 Sep). The only
safe cure is a discard: close without saving. Take a census of BOTH dirty lists (`census_dirty.py`)
before and after any editor work on an import.
