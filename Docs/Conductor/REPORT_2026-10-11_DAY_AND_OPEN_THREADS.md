# Puss: report for 11 Oct 2026, and open threads (Conductor 5)

For reading on the laptop while the PC travels. Details and evidence:
- `APPLY_PASS_REPORT_2026-10-10.md` (Jobs 185–198);
- `HANDOVER_2026-10-10_CONDUCTOR5_EVENING.md`;
- `GARY_PIE_NOTES_2026-10-09_evening.md` (Gary's own words).

"Applied" means saved and read back in Unreal. "Visual" verdicts are from looking at the stills.

## Done today (11 Oct)

### Builds (both passed)
- **Job 180, parcan auto-rebuild.** When a light is moved, only that passage's parcans and lines rebuild. A per-light "no parcan" flag is also added. Caveat: the rebuild fires, but the automatic check found no body at the moved light. **Try it once by hand.**
- **Job 187, test fixes.** CrossingSettle and ShadowCatPIE are fixed (both tests were stale).
- **Job 195, room tone.** A looping sound owned by the Show Root, at −18 dB, with a −12 dB dip as the S6 warp builds. **It waits on Cameron's file**; the APPLY is not run.
- **Job 192, S5 fade from white.** The overlay fade for when S5 plays as video.

### Applied live
| Item | Visual |
|---|---|
| S1 ending: camera to the corner fire, then a fade to black by 3899 | PASS |
| P06 no-parcan on "P06 EVT B02 BLACK F00 CAMERA" | Saved; one fewer parcan body |
| Nested `LS_Clams` trimmed to fit S3 (260 s) | Its test now passes |
| P05 → S5 whiteout (3D route; the S5 Arrival/hangar disabled) | Pure white at the seam PASS. S5 is dark afterwards, as expected until the S5 video exists |
| S6 warp (preset "both"), without the move-in | Applied and read back. **The warp is not visible in the stills or the recording: check it in PIE first** |
| P06 sun disc, chandelier candles (from job 185) | Sun passes; chandelier fails. Both are ON HOLD (Gary: effects wait) |

### Prepared offline (ready, not run)
- **P04 shadow reach** (job 186).
- **S6 move-in with no cut** (job 198 plan): a 2.8 s push ending on Klara's `CineCameraActor5` start pose.
- **Laptop briefs L1–L3:** `codex_briefs/laptop_11oct_offline_jobs.md`.
- **Shadow shot list** for I1–I5 (`SHADOW_SHOTLIST_INTERACTIONS_2026-10-11.md`). The Gobo session reviewed it with Gary and sent PG8 to Codex.
- **UE 5.8 API preflight** (`Scripts/ue58_api_preflight.py`). It is now a house rule.
- **S3 song surtitles:** 8 lines in `Content/InfinityStage/CueSheet/Puss_Surtitles.csv` (S3, 2:09–3:07). Not yet seen on screen, and not yet in the Cue Book.

### Seam audit (whole show, 16 seams; 15 flagged)
- **Real faults:**
  - 06 I2→P3: a 29 m camera jump;
  - 12 I4→Nap Interlude: 3.2 km / 42°;
  - 14 S5→I5: 7 m / 86°;
  - 15 I5→P6: a brightness pop.
- **Others** are mostly intended cuts through black.
- The contact sheets are at `Saved/CodexConductor/Job191TransitionAudit_20261011/runs/J191-SEAMS-J196A2/index.html`.

### Machine and other projects
- **GPU crash at 13:00 (Windows event 4101):** the editor was IDLE and hung presenting a frame (`EndDrawingViewport`), and the machine then hard-reset.
  - Mitigations: viewport Realtime is now left OFF.
  - **TdrDelay is still not set (Gary).** The Parsec display path is a suspect. Consider a driver update.
- **Metamall:** the night build + 3 h soak passed with no crash. 7 series grew: DroppedExperience, FlushFailures and DroppedBackpressure are worth a look. The backup is on `F:`. Two packages were built (night, then the museum build today).
- **P05 cloud wings for Rob:** on the shared drive (UE 5.8 uassets).
- **PussStage full snapshot to `F:\PussStageBackups\FullSnapshot-20261011-*`** (run at pack-down).

## Gary's decisions today
- Priority: **transitions + rehearsal**; effects (chandelier, sun) are on hold.
- **S6:** the old lady is an animated MetaHuman; warp the live 3D render. The void fade is optional.
- **P05→S5:** remove the hangar, a cloud whiteout, then dissolve into the S5 video.
- **All scenes can play as video;** the videos are not rendered yet.
- **Room tone** loops under the whole show, with a dip in the void.
- **Interactions:**
  - lengths follow the script pace, about 60 s or less;
  - digital puppets;
  - I3 is the pearl only; I5 is the crown, then the boots;
  - the boy gets a hinged jaw.
- **Lighting:** parcans auto-follow lights; no more bay replication.
- **Later idea:** a doorway transition in the back wall (not now).

## Open threads (from last week, still open)
1. **The S6 warp is invisible in captures.** Check in PIE; then apply the no-cut move-in (laptop L2).
2. **Seam faults 06/12/14/15** (laptop L1), then rerun the seam audit.
3. **Interaction relength** to script pace (laptop L3), after the gobo first pass.
4. **Scene videos:** render them, then write `cue_director.txt` with `use_video = S<n>`. The S5 fade from white is already built.
5. **Room tone:** waiting on Cameron's wav.
6. **P02 haze:** the partial trim is applied. **Gary: keep it as a tuning start, or trim further?**
7. **Ending 101:** needs Gary in the studio.
8. **TdrDelay = 10** (Gary, as Administrator), plus a possible NVIDIA driver update.
9. **Not yet seen:** S3 fire colour (blue-grey) and S3 hair. Gary: keep the hair, since its job is to cover faces.
10. **3D stage front:** the uplights are in; the textures read only faintly; the middle of the wide shot is blown out.
11. **SavedFixturePIE** still fails (the transport-count assertion), cause unclear. NestedSequences is now fixed.
12. **Parked:** chandelier candles/body, swarm placement (the gold cluster in P06), garment stains, girders everywhere (job 116), the S6 old-lady cuts, gobo content, the doorway transition, the P04 shadow reach (ready).
13. **Surtitles:** add the 8 S3 lines to the Cue Book too, so a pull keeps them.
14. **Metamall:** look into the growing DroppedExperience/FlushFailures/DroppedBackpressure series.
