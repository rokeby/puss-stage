# Puss shadow cat: what the model can do (9 Oct 2026, investigation, nothing changed)

Gary asked: can the cat behind Puss's walking shadow do more (stretch, be surprised, arch), especially during an
authored breath? He also noted that the bob we see is camera motion and could vary a little.

## What runs now [declaration-proven]
- **Mesh:** AnimX "Realistic" cat `/Game/CharacterPacks/AnimX/Cats/Realistic/Mesh/SK_Cat_R`
  (`InfinityStageShadowCatComponent.cpp:21-25`). It is a child actor of the Passage camera rig. In game it renders
  as the **shadow only** (`ShouldDrawShadowCatBody`, `InfinityStageCameraRig.cpp:258-261`).
- **Two animations, picked by camera speed:**
  - walking: `A_Cat_Move_Walk_F`, looped, play rate = camera speed / 250 cm/s × 0.6, clamped 0-1.25;
  - stopped: `A_Cat_Idle_Base`.
  - Code: `InfinityStageCameraRig.cpp:37-50, 53-80, 585-591, 655-666`.
  - **So when the camera stops in a breath, the shadow already switches to the idle cat.**
- The playback is real time (`PlayAnimation(…, true)` plus play rate), **not locked to Master time** [inferred from
  the API used: scrubbing or a re-record may not land on the same pose].
- **The bob is the cat's own gait:** the camera rises and falls with the walk cycle's "Spine" bone against its rest
  pose (`bShadowCatCameraBob`, gain 1.0, roll 0.12 °/cm, `InfinityStageCameraRig.h:224-250, 301`). It looks
  mechanical because one walk loop repeats exactly.
- The vendor's AnimBP / AI / locomotion Blueprint is deliberately bypassed (`InfinityStageShadowCatComponent.h:13-16`).

## What the pack contains [measured: asset listing of Content/CharacterPacks/AnimX/_Common/CatMannequin/Anim]
All on one skeleton (`CatMnq_Skeleton_ANX`), so any of them can play on the shadow cat [inferred: same pack and
skeleton; not test-played yet].

| Group | Animations | Useful for Puss |
|---|---|---|
| Idle | Idle_Base, **Idle_Look**, **Idle_LookDown**, **Idle_LookSite**, **Idle_Stretching**, Idle_Yaw, P_ClosedEyes | the stretch; looking around / up / down / to the side |
| Rest | Sit_to / Sit_Idle / Sit_from, Lie_to / Lie_idle / Lie_from, Sleep_to / Sleep_idle / Sleep_from | sit down mid-pause, curl up |
| Action | **Shaking** (body shake), **SharpensClaws**, Licking_sit, Digging, Drink_U/D, Eat_U/D, Pet / Pet_sit / Pet_lie, Drop_L/R_sit | grooming, shake-off, claws on a wing |
| Combat | **Damage_FL/FR/SL/SR/BL/BR** (flinches), Attack_Paw_L/R, Attack_Bite_L/R, Death_L/R | **startle / surprise** = a flinch; a swipe at something |
| Jump | Jump_InPlace, Jump_Run, FromEdge, Fall_*, Land_* , EnterWater | a startled hop; jumping up onto or off something |
| Turn | Turn ±45 / ±90 L/R | turning to look at something |
| Move | Walk / Trot / Run F/L/R, Crouch F/L/R/idle/turns, Swim | **crouch-creep** (stalking), trot for variety |
| Additive | Add_Breathe, Add_Blink, Add_Ears_1-3, **Add_P_UpTail**, Add_Aim_U/F/D, Add_Incline, **Add_P_Squat** | tail up; head aim; squat. Layers, not standalone |

- **There is no "arch" (Halloween-cat back) animation** [measured: no such name]. It can be made:
  - (a) layered from Add_P_Squat + Add_P_UpTail plus a spine bend [inferred: may not read as a true arch];
  - (b) authored as a new clip on this skeleton in Blender: export the skeleton/mesh FBX from UE, pose the arch,
    import it back. It is a pose-to-pose clip, so a few seconds of work for a hand-keyed arch;
  - (c) the pack's `CtrlRig_Cat_broken` Control Rig is named broken [measured: asset name; not opened].
- Only the **silhouette** matters (it is a shadow). Ears, blinks and eyes won't read; the stretch, the arch, a
  flinch, a sit, a shake, the tail up and a head turn will.

## How to drive an action at a chosen moment (options)
1. **No-C++ prototype:**
   - A separate "action cat" level actor (same SK_Cat_R) attached to the camera rig at the shadow-cat transform.
   - It gets a Skeletal Animation track in the Master, keyed at the breath, so it is Master-timed and scrub-safe.
   - The rig's cat is hidden for those seconds with a `bEnableShadowCat` property key [inferred keyable: the property
     is EditAnywhere/BlueprintReadWrite; not tested].
   - Cost: two cats to keep aligned, and the camera bob reference must not jump at the handover.
2. **Small C++ (build window):**
   - The camera rig gets a "Cat Action" layer: an animation asset plus a start frame, keyed by Sequencer or listed in
     the Show.
   - While active, it plays that clip **locked to Master time** (position = (frame − start) / rate) instead of
     walk/idle, with blend in/out.
   - The same change can lock walk/idle to Master time (deterministic re-records) and add **bob variation**: a
     slow seeded drift of play rate and bob gain (e.g. ±5 %), or occasional Walk/Trot alternation, so the cycle stops
     repeating exactly.
   - This is the clean route for rehearsal-placed breaths.

## Proposed next steps
1. **Silhouette catalogue (one editor slot, ~15 min, no saves):** a bench cat in the level plays each candidate clip.
   Side and three-quarter shadow captures at 3-5 poses per clip, giving a contact sheet for Gary to pick from. Bench
   actors are announced and removed (memory: benches are level activity).
2. Gary picks the moves and whether "arch" is worth authoring.
3. Then C++ option 2 (Codex brief plus a build window), or the option-1 prototype for one breath first.

## GO1 (for Gary's own thinking) [inferred, nothing sent to the robot]
A stopped-and-acting Puss means the dog stops too (camera = cat in Passages). The Unitree GO1's high-level modes
generally include body pitch/roll/yaw and height changes in place, which could echo a stretch (front down), a
crouch, or a look-around. Our rules keep the GO1 read-only; any motion work is Gary's decision and needs its own
safety plan (`Docs/Go1TelemetryProgress.md`).
