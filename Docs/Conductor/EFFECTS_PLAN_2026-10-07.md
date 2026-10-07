# Effects plan — 7 Oct 2026 (offline)

Gary's effects list (7 Oct): (1) smoke-machine plumes along passages, (2) candle + wing-burn, (3) beam
texture / motes rollout, (4) rain, (5) bees appearing earlier, in smaller numbers.

This was written offline. Nothing was run in Unreal, nothing was built and nothing was committed.

**Proof tiers, marked on each claim:**
- **[decl]**: a header, signature or config we can read.
- **[bin]**: package or DLL bytes.
- **[meas]**: a file or record that was read back.
- **[prec]**: an in-repo tool that has already run live.
- **[inf]**: inferred, with the reason given.

## 0. The finding that changes the plan

Every earlier note says "Niagara is not authorable from Python, so wait for a Niagara session". That holds for
*authoring* Niagara: the classic graph and the stateless emitter were both measured not authorable
(`CodexConductor/P04RainBench/p04_rain_bench_probe.json`: `authorable false`,
`class_not_exposed NiagaraStatelessEmitter`) [meas].

The rain bench's content scan, however, only searched for `NiagaraSystem` (`p04_rain_bench.py:10-11`) [meas].
It missed **Cascade particle systems the project already owns** [bin, re-derived by
`Effects_20261007/test_fx_content_probe_offline.py`, 25/0]:

| Asset | What the bytes say |
|---|---|
| `/Game/Japanese_Alley/VFX/Rain2` | GPU, AccelerationConstant, SizeScaleBySpeed, i.e. rain streaks |
| `/Game/Japanese_Alley/VFX/Humo_Par` | GPU, SubUV smoke |
| `.../StarterContent/Particles/P_Smoke`, `P_Steam_Lit` | smoke and steam |
| `.../P_Fire` | fire. Carries a **ParticleModuleLight**, a perf and VSM risk |
| `.../P_Ambient_Dust` | GPU dust, i.e. motes |

Why these can be used without new C++:
- The Effect source activates and deactivates **every `UFXSystemComponent`** by camera distance
  (`InfinityStageEffectSource.cpp:529-549`) [decl]. Cascade components are FXSystemComponents [inf: UE class
  hierarchy; the probe confirms].
- `AEmitter` still exists in 5.8 (`Engine/Classes/Particles/Emitter.h:54`) [decl].
- Whether 5.8 still renders Cascade, and what Python can read on it, is **unknown**. The read-only probe below
  measures it.

## 1. Inventory: what already exists

| Item | State |
|---|---|
| Show `Effect` attachment kind | Exists (`InfinityStageTypes.h:140-147`) [decl]. Sub-types Haze, Smoke, Steam, Fire, WingBurn, Motes (`InfinityStageEffectTypes.h:47-61`) [decl]. Placement, replication and write-back are inherited from attachments. 8 tests passed on 26 Sep (`EffectsSourcesDesign.md:8-21`) [meas, doc] |
| Default Effect classes `BP_Effect_{HazePot,SmokePot,SteamKettle,FireBasket,WingBurn,Motes}` | Looked up by path (`EffectSource.cpp:47-64`). **None exist.** `Content/Scenes/Effects` holds only the candle set, so every type falls back to the greybox (`:123-144`) [meas listing + decl] |
| Pump | `User.Pump` is pushed every tick (`:727-731`) [decl]. It runs on world time, period and duty (`EffectTypes.h:92-101`). It is **not a cue**: it is not tied to Master time |
| Cue schedules to copy | Shadow-spot cues give Passage-relative seconds plus attack/hold/release, as a pure function of Master time (`InfinityStageCameraRig.h:37-60, :108-117`) [decl]. The Sweep light gives segment-relative time plus `ActiveSegmentGuids` (`place_p06_car_light.py:5-8`, which cites `SweepLight.h:80-112`) [prec, run CAR6] |
| LD light events | `InfinityStageLightEvents.h` is a **diagnostic printer**, not a trigger (`:13-24`) [decl] |
| Candle | `BP_Effect_Candle` exists: wax cylinder, an emissive-sphere flame, and an *empty* `FlameFX` Niagara component (`fx_candle_blueprint_readback.json`) [meas]. It was applied in S6 on 4 Oct, then **reverted on 5 Oct after Gary said "lose the candle"** (commit `91e5280`) [meas]. `fx_candle_s6.py` has proved DRY, APPLY and REVERT [prec] |
| Wing-burn | C++ is done: custom data and a camera-travel front. `fx_wingburn_test.py` (P06 Wing 032 R) was **never run**: P06-032 uses shared MIs, so a per-flat child MI route is needed (`CONDUCTOR_START_PROMPT.md:164-166`) [meas]. The Billboard master has `UseBurn`, `BurnPreview` and `BurnMask` (`CodexFlatV3/gloss/build_billboard_master_v2_result.json`) [meas]. There is **no flame system**, and `BP_Effect_WingBurn` is absent |
| Beam look | P03 has it: GSB slats gobo on 4 beams, 4 noise boxes, fog ×0.5 and 3 smoke-test boxes (`p03_atmos.py`, APPLY `20261006-233515`, `8bcf377`) [prec]. Assets are in `/Game/InfinityStage/Lighting/BeamLook` [meas listing]. Motes were **skipped** (`beam_texture_bench.py:68-72`) [meas] |
| Rain | The P04 bench failed: it was the Niagara route (`GARY_PIE_NOTES_2026-10-06_overnight.md:76`) [meas] |
| Bees | Klara's `/Game/FX/NS_BeeSwarm` is in S6 as a Sequencer glimmer spawnable from 1 s (`klara_void_s6.py:40-44`, `4c110e4`) [prec]. It has **no `User.` parameters**, and its spawn rate is a constant [bin]. Our C++ swarm (`BeeSwarmActor.h`, BeeCount default 200, `BeeSwarmSimulation.h:21`) needs `/Game/Scenes/Effects/Swarm/NS_BeeSwarm` (`BeeSwarmActor.cpp:24`). **That asset is absent** [meas], so the C++ swarm cannot render |

## 2. Plan per effect

### (1) Smoke plumes: "an ejection of a thick plume"

**Mechanism, phase A (no build):**
- `fx_effect_bps.py` (drafted) creates `BP_Effect_SmokePot`: an Effect source carrying a Cascade `PlumeFX`, using
  Humo_Par or P_Smoke.
- Plumes are then **Show Effect attachments** of type Smoke, placed with the proven `fx_candle_s6.py` route (scratch-pair GUID
  minting) [prec].
- The C++ fires the plume when the camera comes within `ActiveRadiusCm`. That gives a distance-driven ejection as
  Puss approaches [decl `:509-549`]. It is continuous while in range, not a single puff [inf].
- Set `bFeedsLocalMedium false` (the Smoke default is LFV density 0.25, `EffectLibrary.cpp:39-45`) [decl]. Gary
  called P03 "ridiculously foggy".

**Mechanism, phase B (C++ build):** add a `BurstCues` array to `FInfinityStageEffectSettings`, copied from
`FInfinityShadowSpotCue`. It would hold Passage seconds and an envelope, evaluated from Master time, driving
Activate/Deactivate. The result is a cued ejection on a musical moment. Propose it as held patch EB. **It has not
been written** (not needed tonight).

**Where:**
- P03: 2 pots on the B08/B13 smoke-test bays, to replace the static boxes.
- P04: 1 pot by the strobe.
- P01 and P05: Gary to choose.
- P06: none (its last third is fire).

**Cost:** about 0.2–0.5 ms per active GPU plume, with ≤ 2–3 in range [inf: unmeasured]. Measure in PIE with
`stat GPU`.

### (2) Candle and wing-burn

**Candle:**
- Ready: one `fx_candle_s6.py` APPLY with a new cue label.
- **Blocker:** Gary removed it on 5 Oct, so where does it go now?

**Wing-burn:**
- Needs a per-flat child MI with `UseBurn` on the chosen wing. That is a Wings & Textures (W&T) material slot.
- Then re-DRY `fx_wingburn_test.py`: the P06 chinoiserie→towers swap of 6 Oct may have changed Wing 032's mesh [inf].
- Char-only burn first. For flames, P_Fire in `BP_Effect_WingBurn` sits static at the ignition point, because
  Cascade cannot read `User.FrontRadiusCm` [inf].
- Place it in **P06's last third**, per Gary 5 Oct: "last third fires (Niagara, tomorrow)" (`GARY_PIE_NOTES_2026-10-05.md:270`).

**Fire:** P_Fire's light module must be measured first. Rig owns the fire's light, which is a linked,
non-shadow light (`EffectsSourcesDesign.md:302-311`).

### (3) Beam texture and motes rollout

`passage_atmos.py` (drafted) runs the **unchanged** `p03_atmos.py` as a private module, re-pointed per passage:
- The core is SHA-pinned.
- Fog cut and smoke are off.
- Bays are chosen by list or stride.
- `max_beams` (8) caps the number of noise boxes.
- The leftover gate is fixed: the core counts P03's live boxes as leftovers, which would refuse every other
  passage (`p03_atmos.py:1092-1094, :1514`) [decl].

Beam counts by passage [meas, score records]:

| Passage | Beams | Notes |
|---|---:|---|
| P01 | 28 | |
| P02 | 12 | |
| P04 | 5 | 1 Fault flicker |
| P05 | 51 | |
| P06 | 17 | 15 Buzz flicker, carried |

**Suggested first step:** P01 bay 20 alone. Gary called it the beam that "flickers nicely". Then stride 4
(7 beams), then P04 and P06.

**Blockers:**
- The P01/P02/P04/P06 hand-tuned lamps (`LIGHTING_DRIFT_2026-10-06.md`). Lighting score records must be acked as
  foreign.
- The held rescoring will later see these fields as drift.

**Motes:** `BP_Effect_Motes` with P_Ambient_Dust (drafted), placed as Motes on beam bays (`SelectBeamBays`).
Motes are cheap [inf].

### (4) Rain

P04, the stormy strobe passage (Gary 5 and 6 Oct). Next step is a non-saving PIE bench that spawns Rain2 with
`GameplayStatics.spawn_emitter_at_location`, the same PIE-only route as `p04_rain_bench.py:15-24` [prec pattern;
API presence is checked by the probe]. Then stills for Gary.

For production, use a few Rain2 tiles as P04-attached level actors, tagged and recorded like the P03 noise
boxes [prec]. Alternatively, one tile riding the camera rig, which needs segment gating (C++) [inf].

Not drafted: it depends on the probe.

### (5) Earlier bees, smaller volumes

**Mechanism:**
- Klara's NS as short-lived NiagaraActor spawnables in `LS_Choreo_Passage_6` (Passage-relative).
- **Window length sets the count:** a fresh system starts empty, fills, and dies out when despawned
  (`klara_void_s6.py:43-44`) [prec]. Spawn rate and lifetime are unmeasured, so measure them in PIE.
- The Choreo sequence is the cueing stream's file, so coordinate with them.
- Rejected route: the C++ swarm via a Prop attachment needs its missing renderer NS, which needs a Niagara session.

**Where, proposed:** P06 inside the sunset dark (dark from 52 s; P06 is 126 s, `f84b65b`) [meas]:
- ~80 s: a few glints, after the 68.55 s car.
- ~100 s: a handful.
- ~118 s: growing into S6's glimmer at 1 s.

Optionally one fly-by in P05.

## 3. Drafted tonight (offline; all harnesses green)

Location: `Saved/CodexConductor/Effects_20261007/`.

| Tool | Harness |
|---|---|
| `passage_atmos.py` + runner/args/request | `test_passage_atmos_offline.py` **44/0** |
| `fx_content_probe.py` (read-only, census-checked) | `test_fx_content_probe_offline.py` **25/0** |
| `fx_effect_bps.py` (create-only SmokePot + Motes BPs; gated on the probe; REVERT deletes only recorded, unreferenced assets) | `test_fx_effect_bps_offline.py` **24/0** |

**Run order (Gary's go, editor free):** probe → `fx_effect_bps` DRY/APPLY → `passage_atmos` P01 DRY → P01 APPLY →
stills.

## 4. Gary questions

1. Candle: where, now that it is gone from S6? Or drop it?
2. Which wing burns in P06's last third, and with flames, or char only?
3. Plumes: continuous-while-near now, or wait for the build that adds a cue on a musical moment?
4. Beam look: P01 bay 20 first, and how dense elsewhere?
5. Rain: P04 only? And during the strobe?
6. Bees: P06 dark glints at ~80/100/118 s? Should P05 get any?
