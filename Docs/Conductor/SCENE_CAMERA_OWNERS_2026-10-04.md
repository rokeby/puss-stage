# Scene camera owners → Timeline; dog free-look as an operator option (4 Oct 2026)

**Decision (Gary, 4 Oct):** "Keep all camera locked and let dog freelook be optional."
(`Docs/Conductor/MORNING_SUMMARY_2026-10-04.md:82`). All six Scene cues go to
`CameraOwner = Timeline`. Today they are all `DogFreeLook` (applied 30 Sep 17:42,
`Saved/CodexCameraPilot/camera_owner_plan.json` _note; backup `Backups/PreCameraOwners-20260930-174243`).

Tiers: **declaration-proven** = read in source/header; **measured** = run and read back;
**inferred** = not verified, reason given.

## 1. The authoring change (offline-built, NOT yet run)

Tool: `Saved/CodexConductor/scene_camera_owner_apply.py` (DRY / APPLY / REVERT), runners
`scene_camera_owner_{dry,apply,revert}_run.py`, MCP requests `scene_camera_owner_{dry,apply,revert}_request.json`.
Harness: `Saved/CodexConductor/test_scene_camera_owner_apply.py`.

| Cue GUID | Label |
|---|---|
| 91030A272145EBEF25D33BA016458739 | Scene 1 — External Sound |
| 42D2F59416487AF7018DAEB62639C9BB | Scene 2 — External Sound |
| D8F61D9DF94F1E6080CC8D9028EE49D3 | Scene 3 — External Sound |
| 5C960C0C7A462BFEA4C86F93ADF5558D | Scene 4 — External Sound |
| 730D67269F425DDC45C72A867BA04217 | Scene 5 — External Sound |
| 673B3535884DEBAE99723B8CC6BE877B | Scene 6 — External Sound |

GUIDs from `Saved/CodexStructure/arrivals_probe.json` (measured by an earlier probe; the
harness asserts the tool's table equals that file).

- Field: `FInfinityShowCue::Scene` → `FInfinitySceneCueData::CameraOwner`, enum
  `EInfinityCameraOwner { Timeline, DogFreeLook, DogGazeOnly }` — **declaration-proven**
  (`InfinityStageTypes.h:45-55, 812-814, 928`). Python names `cues/scene/camera_owner/cue_guid`
  and `unreal.InfinityCameraOwner.TIMELINE` — **measured** (used by
  `Saved/CodexCameraPilot/apply_camera_owners.py` on 30 Sep; `audit_camera_owners.json` prints
  `<InfinityCameraOwner.TIMELINE: 0>`).
- Only the Show asset is saved; the level is not touched — the Scene owner is read at runtime from
  the Show (`InfinityStageShowRoot.cpp:266-279`), **declaration-proven**. That nothing in the level
  caches it is **inferred**; the tool asserts the map stays clean and refuses otherwise.

## 2. How an operator turns dog free-look on (the "optional" part)

**Cue Desk → View → Live Camera Owner → Force Dog** — **declaration-proven**:
- Submenu built in `SInfinityStageCueDesk.cpp:2979-2986` inside `BuildViewMenu` (`:2916`), on the
  Cue Desk toolbar's **View** button (`:1119-1127`).
- Entries (`:5442-5478`): *Follow Show* (authored owners), *Force Timeline*, *Force Dog*
  (→ `DogFreeLook`), *Force Dog (Gaze Only)* (→ `DogGazeOnly`).
- `SetLiveCameraOwner` (`:5480-5510`) writes the transient `bOverrideCameraOwner` /
  `CameraOwnerOverride` (`InfinityStageShowRoot.h:47-51`, `Transient`) on every Show Root **in
  running PIE worlds** using the desk's Show. The Show is not edited.
- `GetCameraOwnerAtFrame` (`InfinityStageShowRoot.cpp:233-283`): Force Timeline wins everywhere
  (`:236`); a Dog override applies in Passages (`:261-263`) and **Scenes** (`:275-278`) and is
  refused only in Sequence cues (Opening, Interactions, Closing). Covered by
  `InfinityStageCameraOwnerLockTests.cpp:60-66`.
- The GO1 receiver maps the owner to its rotation mode (`Go1RemoteReceiverComponent.cpp:719-751`,
  needs `bUseShowCameraOwnership`, default true, `.h:143`). With no telemetry the mouse stands in,
  only where the dog would (`.h:255-266`, `bMouseLookWhenNoTelemetry`).

No other trigger exists — **measured by search**: no console command or CVar sets the override
(the editor module registers only `CreateVerticalSlice`, `OpenCueDesk`, audit/correction commands,
`InfinityStageEditorModule.cpp:141-160`); no `Content/` or `Config/` file contains
`OverrideCameraOwner` (grep, 4 Oct), so no Blueprint or input binding sets it.

Operator caveats (each **declaration-proven** unless marked):
1. **Set it after PIE starts.** It only reaches Show Roots already in a PIE world; a new PIE session
   starts un-overridden (`Transient`, default false) and `HandlePostPieStarted` (`:5389-5438`) does
   not re-apply it, though the menu radio may still show *Force Dog* checked (`IsLiveCameraOwner`,
   `:5512-5515`, reads the desk's own flag). Re-select it after every PIE restart. (That clicking a
   checked radio entry re-runs the action is **inferred**: standard Slate behaviour, not verified.)
2. **Force Dog is not Scene-only.** It also takes every Passage (`:261-263`), switching them from
   their authored owner (Gaze Only as of the 26 Sep audit, `audit_camera_owners.json` — re-measure)
   to free look. Return to *Follow Show* when the Scene ends, or use *Force Dog (Gaze Only)*.
3. **The look resets at every camera cut** while `bResetLookAtCut` is true (default,
   `Go1RemoteReceiverComponent.h:209`). Carrying the look across a Scene's own cuts is what the
   parked GL patch (`Scripts/patches/2026-10-04_GL_go1_live_scene.patch`) would add; it is not
   applied.
4. Editor/PIE only: the control lives in the editor Cue Desk. A packaged/`-game` run has no way to
   set the override (**inferred** from the search above; not tested).

## 3. Scene 6 "GO1 live"

`Docs/Scene6BeatSheet_2026-10-02.md:70-71` (Gary, 2 Oct night) made S6 the one Scene where the dog
drives the camera. The 4 Oct decision supersedes that as an **authored** state: S6 goes to Timeline
with the other five, and "GO1 live in S6" becomes exactly this optional Force Dog override, chosen
by the operator at run time (Morning summary `:82`, "including S6"). Whether Gary still wants the
S6 cameras made "walkable" for that option, and whether the parked GL patch is revived, is his call
— not decided here (**inferred**: the summary says only "GL patch PARKED").

## Not yet proven
- No run in Unreal: the DRY must be run first and its `found` block read (enum members, export
  tokens, scene set, census) before APPLY.
- `StructBase.export_text()` (used for the outside-target hash) is **inferred** to exist and to emit
  `CameraOwner=<Name>`; DRY stops on either assumption failing.
- The on-disk re-read is a SHA change of the `.uasset` plus the in-memory read after save; no package
  reload is done (deliberately — reloads crashed the editor before).
