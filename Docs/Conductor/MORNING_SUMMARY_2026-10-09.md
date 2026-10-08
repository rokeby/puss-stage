# Morning summary, Fri 9 Oct 2026 (Conductor 5, night of 8→9 Oct)

## FIRST: the machine needs a reboot
The GPU was lost at ~09:12 UTC on 8 Oct. `nvidia-smi` says "GPU is lost. Reboot the system". Unreal can't start until
the PC is rebooted.

**Before rebooting, check whether Codex P17 (bone dune) has finished.** The curtain bake has already stopped, see
below.

**Curtain bake p02** [measured]:
- The simulation completed: all 390 frames are in `DropBake/unfurl_sleight_b1hop10_p02_stream.f32`.
- Blender then crashed at the final Alembic export (no OpenGL: the lost GPU), so the `.abc` and report `.json` are
  missing.
- A re-bake is not needed to get the file: `Tools/CurtainBake/stream_to_abc.py` (P19) rebuilds the ABC headless after
  the reboot (P19 doc has the commands).
- **BUT the take itself fails two stillness gates** [measured from the stream]:
  - U2, motion before release: 72 mm/frame, limit 1.5;
  - U7, motion in the last 30 frames: 391 mm/frame, limit 2.0. The cloth is still moving hard at the end of the bake.
- The importer will refuse it until acceptance is re-run.
- Your call: look at a preview of the recovered take, or re-bake with more settle frames.

After the reboot:
1. Run `editor_sky_toggle.py` (or the P18 auto-hide, once installed).
2. Test **P03 in Play** before anything else.

**What happened** [measured]: the P03 "after" stills in Play crashed with DEVICE_REMOVED in volumetric-fog light
scattering, about a minute after the P03 relight was saved.

**Cause NOT proven** [inferred]: the relight adds ~91 lights inside P03's fog. Against it, the GPU had already hung
once at editor startup at 08:59, before that change.

**If P03 crashes again:** REVERT `p03_lighting_as_p01.py` (confirm `REVERT P03ASP01`) and re-test.

## Done and saved (each reversible, tests green after each)
| What | Run | Undo |
|---|---|---|
| Pendulum's own swing off in S4 (your 7 Oct call, re-confirmed). PIE: static during the glide, follows Klara's keys after the cut. | KLARAPENDULUM-20261008-041003 | klara_pendulum_s4 REVERT |
| P01 smoke pots hidden (Show `enabled=false`) | FXENABLE 20261008-042536 | fx_attach_enable REVERT |
| Stage front: P01 bay-1 rococo wings either side of the curtain (inner edges ±7 m) | FRONTWINGS-20261008-043305 | stage_front_wings REVERT |
| P03 lit like P01 (structure/position; P03 hues; specials + score lights kept; atmosphere matched to P01) | P03ASP01 20261008-051137 | REVERT P03ASP01 (see above) |
| Pearl: green-orange MI + swap + twin sync + twin opacity 0.5 (finishing-touches session, your pick "the 4th") | S3PROPS-…-044838/044841, MIS-…-044828 | their undo order |

## Waiting for your yes
- **Pearl step 4** (`s3_pearl_twin_vis.py`, DRY-clean): solid pearl hidden for the whole scene; the twin visible from
  the clam reveal (1080) to 5040; the fade is unchanged. This completes your pick. One tap: APPLY.
- **Handprints** (S3 B06 wall, 198 marks = 2×, darker cores). Pick one of two layouts:
  - Codex: 4 tall columns;
  - mine: 20 shorter scrabbling climbs ("many people").
  Previews: `Saved/CodexFlatV3/handprints/p12_dense/previews/` and `previews/many/`.
- **S4 entry v5** (you chose v5: Klara's first shot is NOT black). Tooling is ready (P8 runbook):
  backcloth hold → v5 → pre-roll → stills, then you approve.
- **Opening lighting** (P13): tight soft spots moving to centre + corner flurry lights; flurries set to your order
  (1 curtain 0:37, 2 lights 0:57, 3 move-in 1:10).
  - Your note "parcans on the facade + some P01 lights inside at flurry 2" is NOT in the tool yet; it needs one more
    pass.
  - The perspective move is focal-only by default; "moving in" may mean a camera move.
- **Passage timing = music** (P11): the Master shrinks by 188.5 s, almost all of it P05 (186 → 42 s). Two P05
  camera keys fall past the new end. P06 uses 110.6 s of its 125 s WAV: confirm.
- **Sky** (P18):
  - S1 and S4 bring Klara's own sky in Play (S1: sun 17.4 + skylight 0.8; S4: sun 4.9 + skylight 1.0).
  - The tool is ready: S4 sky+sun off; S1 skylight off and sun kept, "you decide". It also has a draft message to
    Klara.
  - The editor auto-hide (no more sky after a restart) is a held startup patch.
- **Pearl glow**: you kept the 40 cd glow; a 3 cd A/B is held if you change your mind.

## Built overnight, not applied (Codex team, all harness-green, committed)
- P9: Interaction transitions (white cards out, slow shadow-play spot).
- P10: stage front / S6 Void / Ending design report.
- P14: rehearsal robustness.
  - Operator runbook: `REHEARSAL_OPERATOR_RUNBOOK_2026-10-08.md`.
  - Held patch: Rehearsal mode not pushed to new PIE sessions.
  - S1/S4 completion-mode review list.
  - No blackout / crash-restart command exists yet.
- P15: video placeholder (1080p25 test card + WAV) for rehearsing the video Scenes, a held video-transition subsystem,
  and an aspect/LED report. **Needs the LED screen's pixel size**.
- P16: (applied, above).
- P17: P03 bone dune (8×6×3.5 m, wind-shaped, proposed at bay 13) + 6 new Rodin bone specs. The toolchain is ready (58/58), but NOT generated: Codex's sandbox can't read the Rodin key, so 0 credits were used. The conductor runs the asset step after the reboot.
- P7: P06 FX cue sheet + tools. P6: animated gobo tool. P3: dunes ×2 field.

## Findings
- **S3 spoiler light at 0:04** [inferred]: P03's pyre/score lights (up to 1600 cd, 11 m away) stay lit through the
  S3 dark arrival. Nothing switches on at 0:04 near the camera [measured]. Fix: P03 score lights out by the S3 cut
  (not done yet).
- S4 entry [measured]: children in bind pose and the pigeon frozen 4.4-16.2 s; pendulum fixed (above).
