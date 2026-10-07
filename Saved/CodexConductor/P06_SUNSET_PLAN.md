# P06 sunset — plan (7 Oct, offline only, nothing run in Unreal)

Gary, 7 Oct: P06 opens with a low sun already up. It sets over about 40 s, with the light raking across the route ahead of
Puss, and then comes TOTAL darkness, with only the artificial lights, for the rest of P06.

Tool: `p06_sunset.py` (+ `_run.py`, `_args.json` (DRY), `_request.json`). Harness: `test_p06_sunset_offline.py`, which passes 55/0 and includes negative controls.

Tiers: **decl** = proven by source we can read, **meas** = proven by an earlier run's record or log, **inf** = inferred (the reason is given).

## 1. How the sky is driven
| Claim | Tier | Evidence |
|---|---|---|
| Temporality is on **FInfinityPassageSettings**, not on a cue. The brief's "FInfinityShowCue.CelestialCycle" is wrong: line 1022 is inside the PassageSettings struct, which starts at :947 | decl | InfinityStageTypes.h:947, :1020-1022 |
| It is matched to its Passage by PassageGuid | decl | InfinityStageCompiler.cpp:437-445 |
| phase = Initial + Σ offsets up to P + full spans of earlier Passages × rate/duration + elapsed in P. Elapsed is clamped to the segment and measured from SegmentStart, which includes the lead-in. Rate = 0 when animation is off | decl | Compiler.cpp:413-470, :254 |
| sin(elev) = −cos 2πφ. On the setting half, elev = 270 − 360φ. Sun yaw = SunAzimuthDegrees, so the afternoon sun stands AT that azimuth | decl + harness | CelestialRig.cpp:451-490 |
| daylight = SmoothStep(±Band, sin elev). Sun lux = Max × daylight. Moon lux = MaxMoon × (mirror of daylight). Sky light = lerp(Night, Day, daylight). Fog = lerp(NightFog, DayFog), with directional inscatter lerp(Moon, Horizon) | decl | CelestialRig.cpp:452-535 |
| Evaluated only on Passage frames. In a Scene the rig holds the last Passage state, so Scene 6 inherits P06's dark end | decl | MovieSceneInfinityPassageTrack.cpp:230-236 |
| A jump from mid-P06 straight into a Scene leaves the sun lit until the next Passage frame | inf | The transport has no celestial call (grep) |

## 2. Blockers: the Show write alone is INERT
| Fact | Tier | Evidence |
|---|---|---|
| The production pin `bApplyManualLightingInGame` is ON, so PIE uses hour 0 and ignores the Master phase | meas | reopen_step1.py:8; `CELESTIAL_MANUAL_LIGHTING_IN_GAME|hours=0.00` in Saved/Logs, last seen 2026.10.07-03:32 |
| MaximumSunIntensity = 0. Moon, day and night sky light are all 0. Stars are off | meas | black_void_record.json, 5 Oct |
| All other Passages: animation off, offset 0. InitialPhaseCycles = 0 | meas (18 Sep; DRY re-reads) | CodexLighting/apply_night_stage1_result.json |
| P06 is the last of 6 Passages | meas | probe_routes.json, 5 Oct |

**Chosen (narrowest, no C++):** turn the in-game pin OFF and give the sun lux. With every other Passage frozen at phase 0, which is exactly the pinned hour 0, they evaluate to daylight 0, so their light is unchanged (decl maths + the DRY gate). Because P06 is last, its time advance reaches no later Passage. The night is already total: moon, sky light and stars are all 0, so after sunset only the artificial lights remain. **Nothing about the moon needs to change** (meas).

The alternative is a held C++ change: a per-Passage flag that lets the Master phase override the pin. It would leave the pin on everywhere else, but it needs a build. Not chosen.

## 3. Design (shipped args)
| | Value |
|---|---|
| P06 length | 126.0012 s (Master section [47949592, 50973621), meas p06_tail_extend_record.json) |
| Start elevation / horizon | +7.0° at t=0, 0° at 37.0 s (0.189°/s) |
| CelestialCycle | animate on, CycleDurationSeconds **1902.857**, rate 1.0, EntryPhaseOffsetCycles **0.730556** (prior phase 0) |
| TwilightAltitudeBand | **0.05** (global, was 0.12). Full sun until 21.9 s, half at 37 s, **zero at 52.1 s**, then 73.9 s of total dark. Keeping 0.12 means dark only at 73.4 s |
| End | −16.8° at 126 s. The next sunrise would come at 988 s, so there is none |
| Route heading | world yaw 0.0 (straight; meas probe_routes.json; DRY re-reads the spline) |
| Azimuth | the live value 278.8° is **81.2° off-axis**, to the camera's left (meas lighting_dump.json, 18 Sep). Proposed: route + 30° = **30°**, ahead-right inside ±50°, so the flats' shadows stretch diagonally across the floor toward camera-left |
| Sun lux | **2.0**. With an exposure window of EV100 −5..−1, a sun-facing surface of albedo 0.5 sits ≈ 0.53 after exposure, so it should not blow out (inf: maths only). The PPV and exposure window are 18 Sep values; DRY re-reads them |

The global writes (pin, lux, azimuth, band) only show where daylight > 0, and daylight > 0 happens only in P06 (decl + gate). Rotating the rig actor does nothing: the sun's yaw is a property, written to the sun actor in world space (decl CelestialRig.cpp:490).

## 4. Interactions to flag
- The **black-mode bays 2-10** at P06's start get sunlit. That is the sunset itself, but it is Gary's look call.
- **The sun appears in one frame at the S5→P06 crossing.** P05 ends at 0 lux and P06 frame 0 is at full 2 lux. The lux is not animatable without C++. (inf)
- **The disc itself is not visible.** No sky atmosphere is bound and the dome's "Sun brightness" is held at 0 (decl :574). What can be seen is raking light, shadows, and volumetric-fog forward scatter toward the sun. Fog density is 0.022 and the scattering distribution is 0.55 (meas p03_atmos DRY, 6 Oct); whether volumetric fog is enabled could not be read (UNCLEAR). Fog colours are black (void), but the directional-inscatter colour turns orange at dusk (decl :529).
- **Possible VSM/perf cost.** The sun rotates every frame for 126 s, which invalidates the shadow cache (inf; see the stutter memory).
- **Scene 6** expects a total void ("NO strike... dimmer", Scene6BeatSheet_2026-10-02.md:29). P06 hands over dark, which fits.
- Master and compiled segment boundaries differ by about 2 ticks (GARY_PIE_NOTES_2026-10-06_overnight.md:19). That is negligible here.

## 5. Run order
1. DRY → p06_sunset_dry.json. It re-reads all six cycles, the rig, segments, route yaw, PPV, fog, sun light and ZZ_ actors. It must report `apply_ready=1`.
2. **Gary's own yes** on lux, azimuth, band and the bay-lighting interaction. These are look values. Then set `decided_by` and `confirm "APPLY P06SUNSET"`.
3. APPLY:
   - guards: no PIE, Sequencer closed, clean census, no record
   - backups: Backups/PreP06Sunset-<run> with the Show and the umap, sha-checked
   - an exclusive fsynced record
   - the Show write and the rig write, each read back
   - a **probe**: manual lighting off in the editor, the real `EvaluateAtMasterFrame` run at t = 0/20/37/52/90/125.9 s and gated against the mirror (≤ 0.01 cycle, ≤ 0.05°), then the editor pin restored and the sun checked back to its exact before-state
   - census == {Show, level}, save those two only, read back, census clean, then `P06_SUNSET_APPLY_OK`
   - no Master rebuild and no materialise: the phase is compiled live (Compiler.cpp:425-429) and no actor reads CelestialCycle
4. Then PIE stills at the same times. That is the **rendered** proof, which none of the steps above give.
5. REVERT restores the recorded cycle and the four rig values after a drift check.
