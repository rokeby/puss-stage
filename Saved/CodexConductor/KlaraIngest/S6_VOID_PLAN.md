# S6 Void plan: her action in our main level, no streamed level, no hangar (7 Oct, offline)

Offline work only. Nothing was run in Unreal or over MCP. No build and no commit.

| File | Role |
|---|---|
| `klara_void_s6.py` | The tool, with DRY, APPLY and REVERT modes. It supersedes `klara_hookin_s6.py`, which was never run. |
| `klara_void_s6_run.py`, `klara_void_s6_request.json` | The runner and the MCP request |
| `klara_void_s6_args.json` | The arguments. Mode is **DRY**. The file also holds the measured facts. |
| `test_klara_void_s6_offline.py` | The harness. It re-derives every [meas] fact from the package bytes on each run. |

The harness passes **15 of 15** tests and catches **12 of 12** seeded mutations. Every claim of exactness has a
negative control that must fail.

Tiers: **[decl]** means header or signature (file:line). **[prec]** means repo precedent. **[meas]** means bytes or a
record that was read back. **[inf]** means inferred, with the reason given.

## 1. What her sequence really is (bytes, [meas])

The brief's premise is wrong. **LS_Void has 0 spawnables and 14 possessables.** Every actor binding points into
`L_KK_Void` through `PersistentLevel.*` locators. Without her level, nothing binds.

| Binding | Level object | Tracks | Keys absolute world? |
|---|---|---|---|
| CineCameraActor5 (**first cut**, 0.4–17.53 s) | CineCameraActor_5 | transform with defaults only: (-1699, 80, 45), rot 0 | yes: no AttachParent on any root |
| CineCameraActor, CineCameraActor2, CineCameraActor3, CineCameraActor4 | _1, _3, _0, _4 | transform with defaults only (static) | yes |
| 5 × CameraComponent (children) | – | 3 float keys each: 35 mm, f/2.8, focus 100000 | – |
| NS_BeeSwarm | NiagaraActor_29 (/Game/FX/NS_BeeSwarm) | the **only keyed** transform: LINEAR keys from 18.7 s, and X/Y/Z key times differ | yes |
| BP_MHC_Elder_Female | BP_MHC_Elder_Female_C_1 | **none**. She stands where her level put her: (1570, 100, -40), yaw 146 | – |
| Body / Face (children) | – | Body: ControlRig + AS_MHP_Void_woman. Face: ControlRig. | relative to her |

Her level also holds the set her sequence never binds:
- SpotLight_1 (3 cd, pointing down) and SpotLight_3 (8 cd);
- DirectionalLight_1 (class defaults; it faces +X, which is her front);
- SkyAtmosphere_1;
- the BlackWater floor at z = -40.

## 2. Mechanism

APPLY saves **only LS_DevScene_06 and the copy**. It makes no map write.

### The copy, `/Game/InfinityStage/KlaraHookin/LS_Void_S6`

1. Each top-level possessable is rebuilt as a **spawnable of the same class**:
   - `add_spawnable_from_class` [decl MovieSceneSequenceExtensions.h:435; prec curtain_sleight.py:1897];
   - `MoveBindingContents`, which moves tracks and child bindings [decl MovieSceneBindingExtensions.h:200-208];
   - children are re-parented if the move did not do it [decl :199];
   - cuts are re-pointed [prec curtain_sleight.py:2118];
   - the old possessables are removed.
2. Measured template settings are carried over: focus Disable on 4 cameras, two saturation overrides, and the NS asset.
3. The woman gets a constant transform equal to T applied to her level pose.
4. The set pieces are added as spawnables: spots, floor and directional ON; sky atmosphere OFF.

### Placement: T = (29339.28, 399920, 135), yaw 0

This puts her Cam5 exactly on our S6 Entry Handoff camera at (27640.28, 400000, 180). That camera position is [meas]
from the records; DRY re-reads it live. The harness shows a residual of 0.

Re-keying is exact:
- translation for any key;
- yaw for keys at the same times;
- for linear curves with differing key times, a union of the key times. The harness shows an error of 4e-13; the
  naive control is off by 230 cm.

### Scene: `LS_DevScene_06`

- **Shots** section → the copy, over [104, 5923).
- **Score** is deactivated, never deleted.
- **Hangar Fold** (LS_S6_HangarRise) is deactivated. This removes the rise, the wave and the strikes.
- Every actor tagged `RigAtmos.Scene6Hangar` gets bHiddenInGame over [0, end) with RESTORE_STATE.
- Every hangar light gets Intensity 0. The hangar PPV gets bEnabled false.
- Our sun, moon, sky and fog are hidden.
- The **glimmer** is added.

### The glimmer

The glimmer is a NiagaraActor spawnable using her NS_BeeSwarm. It sits at her swarm's first world pose,
(31643.0, 400033.4, 361.7): 40 m straight ahead of the entry camera, 1.8 m above it.

It spawns at frame 25 (1.0 s) and is alive until frame 154 (her start + 2 s). A fresh system starts **empty** because
WarmupTime is unset [meas]. The glints appear and multiply, which gives "the first glimmer, growing".

The swarm can be driven from the Scene sequence through a spawn track and a transform. It has no user parameters
[meas], so it has no brightness key.

Our C++ swarm actor cannot render: `/Game/Scenes/Effects/Swarm/NS_BeeSwarm` does not exist [meas]. Its soft default
therefore resolves to nothing [decl InfinityStageBeeSwarmActor.cpp:23-24, 52-56].

## 3. Timeline (25 fps)

| Frame | s | What happens |
|---|---|---|
| 0 | 0 | S6 begins. P06 ends in total dark. The hangar is hidden and dark. The root cut shows the Entry Handoff camera. |
| 25 | 1.0 | Glimmer spawns 40 m ahead and fills in. |
| 104 | 4.16 | Her section starts, and her music starts. Her spawnables and lights spawn. Her Cam5 equals our entry pose, so the seam is exact. |
| 114 | 4.56 | Her first cut (0.4 s into her section). |
| 154 | 6.16 | The glimmer despawns. Her own swarm has been filling since 104. |
| 4804 | 192.16 | Her music ends. |
| 5488 | 219.53 | Her last cut ends. The root camera shows for 17.4 s (warning HER_TAIL_WITHOUT_CUTS). |
| 5923 | 236.92 | Scene end. That is 104 + ceil(232.733 × 25) = 104 + 5819. |

**Markers.** All five line up only with S = 104 (harness-proven). With S = 0 every marker is 4.16 s late. This assumes
her audio is the same recording as ours [inf]: same name stem, 188.0 s each, and 34 bytes apart in WAV size. The PCM is
compressed, so it could not be compared.

**Extend row to run next:** `{"scene_label": "Scene 6 — External Sound", "new_end_s": 236.92, "dry_run": true}`.

**Alternative ending:** with `end_rule her_last_cut`, the scene ends at 5489 (219.56 s).

## 4. Risks marked [inf], and what DRY must confirm

1. The API table must be all ok:
   - `move_binding_contents`;
   - the deprecated `add_spawnable_from_class`;
   - `set_camera_binding_id`;
   - `CameraFocusMethod`, `LightUnits`, PostProcessSettings names, and `NiagaraComponent.set_asset`.
2. The live binding census must equal the bytes (refusal `HER_BINDINGS_DRIFTED`). Every binding prints its kind,
   tracks and absolute flag.
3. The live Entry Handoff pose must hold. The S6 label and `camera_owner` must be TIMELINE.
4. The score section must be exactly 1 at [104, 4804). There must be exactly 1 Hangar Fold section.
5. The hangar report must show the actor count, the current root rotation, and **lights lit now**. The S6 tracks cannot
   hide the hangar **during P06**. If DRY shows it lit or risen there, that needs a P06 or level hide.
6. The asset loads must succeed: the BP class, NS_BeeSwarm, the floor mesh and the material. Audio durations, hers and
   ours, must be printed.

These need PIE after APPLY [inf]:
- that a hidden light emits nothing;
- that her spawnables evaluate inside the nested shot;
- the MetaHuman spawn hitch at 4.16 s;
- exposure in the dark;
- the overlap pop.

These instance settings are not carried over [meas]:
- the woman's ForcedLod 4 and 8;
- the Face construction MIDs;
- the LODSync mapping;
- the Niagara OverrideParameters.

## 5. Decisions for Gary (proposed defaults)

- Placement is `match_entry_yaw`, which gives an exact camera seam. Her floor lands at z = 95, while ours is at 0.
  `match_entry_floor` instead drops the camera 95 cm in the dark.
- Her directional light is ON. It is global and lights whatever her cameras see.
- Glimmer distance is 40 m (`her_first`). `ahead` puts it 12 m out, but it then jumps at the handoff.
- Overlap is 2 s. With 0 the swarm empties and refills instead.
