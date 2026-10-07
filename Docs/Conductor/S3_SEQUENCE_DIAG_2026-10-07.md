# S3 sequence diagnosis: Right arrow and disappearing figures (7 Oct 2026)

**Scope.** This was read-only. There was no MCP, no editor, and no Content writes. Every byte claim below was read
offline with the KlaraIngest UE5 1018 reader (`Saved/CodexConductor/KlaraIngest/test_klara_void_s6_offline.py:44-178`).
I extended that reader in `Saved/CodexConductor/S3Diag/`:
- `s3_seq_sem.py` decodes tracks, sections, channels, cuts and markers, keyed by binding GUID;
- `sem_diff.py` is the name-keyed diff;
- `bool_keys.py` decodes the tagged visibility BoolCurve;
- `s3_seq_dump.py` and `diff.py` give a raw export diff.

The outputs are in the same folder: `*_sem.json`, `ds03_sem_diff.txt` and `ds03_diff.txt`.

**Tiers** (AGENTS.md):
- **[decl]** a header, project source or config we can read;
- **[bytes]** decoded from the .uasset, a measurement of the saved data;
- **[meas]** a log or record of a live run;
- **[inf]** a conclusion that could not be verified, with the reason given.

**Inputs.**

| Asset | Snapshot / backup | Current |
|---|---|---|
| `LS_DevScene_03` | `D:\PussStageBackups\FullSnapshot-20261007-1458` copy, sha `c4a2a34a…` | 17:24, sha `4922e511…` |
| `LS_S3_HangarRise` | snapshot, sha `db899747…` | 17:34, sha `817fec93…` |

- The snapshot's `LS_DevScene_03` sha equals the `saved_sha256` in `s3_hangar_float_hold_record.json`. So it is
  exactly the post-float-hold (13:29) file **[bytes]**.
- The only writer to `LS_DevScene_03` between the snapshot and now is Gary's 17:24 save **[inf: file mtimes and
  records. No other record names this asset after 13:29]**.
- The snapshot's rise equals `Backups/PreS3Millstone-S3PROPS-20261007-173446/LS_S3_HangarRise.uasset` (same sha). So
  the rise diff is the millstone tool alone **[bytes]**.

## 1. What changed

### `LS_DevScene_03`: snapshot → Gary's 17:24 save

| # | Change | Camera-related? | Tier |
|---|---|---|---|
| 1 | Spawnable camera binding `1aefe401…` renamed "Cine Camera Actor 0" → **"S3 Shot B02"**. A transform track was added with no keys (defaults only). | CAMERA | [bytes] |
| 2 | "Cine Camera Actor 2" (cut B04, 1440–2880): new transform track, 2 keys at frames 1442 and 2880 | CAMERA | [bytes] |
| 3 | "Cine Camera Actor 4" (cut B06, 3000–3480): new transform track, 4 keys at 3002–3432. New CameraComponent keys at 3230–3353: focal 100 → 80.1, aperture 2.8 → 17.4, focus 102 → 4163 cm | CAMERA (incl. focal) | [bytes] |
| 4 | "Cine Camera Actor 5" (B07 orbit) CameraComponent: aperture, focal and focus tracks added, with no keys (defaults) | CAMERA | [bytes] |
| 5 | "Cine Camera Actor 8" (cut B10): transform with 2 keys at 5045–5509, plus a focus track (default) | CAMERA | [bytes] |
| 6 | "Cine Camera Actor 11" (cut B12): transform with 2 keys at 5884–6219 | CAMERA | [bytes] |
| 7 | Cut sections 3, 5, 7, 11 and 13 gained an editor-recorded `InitialCameraCutTransform` | CAMERA | [bytes] |
| 8 | Spawnable camera templates: labels changed ("Cine Camera Actor N"). Template focus distances changed (100000 → 46–905 cm). Template location and rotation changed on _1, _7, _8, _9 and _10 | CAMERA | [bytes] |
| 9 | **Camera-cut ranges and bindings: UNCHANGED.** All 14 sections (0, 95, 6216, 360 … 5880) are identical | (camera, unchanged) | [bytes] |
| 10 | **MarkedFrames 21 → 14.** Removed: **`InfinityStage.VampStart`@3480**, B02@360, B03@960, B06@3000, B08@4200, "S3 5 Chorus…"@2880 and "S3 7 Finish / out"@5520. Moved: B10 5040 → 5045 and B11 5520 → 5525. `InfinityStage.VampEnd`@4200 **remains** | NOT camera (VampStart is transport) | [bytes] |
| 11 | Sub-track `SortingOrder` = 2 | NOT camera (UI only) | [bytes] |
| 12 | Hangar Fold sub-section [0,744), the LS_Clams shot section and `LS_Clams.uasset` (sha equal): **unchanged** | NOT camera | [bytes] |
| 13 | Float-hold, wave and B07-orbit channels: times and values identical. Only the per-channel tick-resolution metadata changed (60000 → 24000), and Scale defaults are now serialised explicitly | NOT camera; no-op | [bytes]; "no-op" is [inf], because the stamp is curve-editor metadata and times are in sequence ticks |

**What the marker pattern suggests [inf]:**
- Most removed markers shared a frame with another marker: 360, 960, 2880, 3480, 4200 and 5520. That looks like
  stacked markers being deleted or dragged by hand.
- The B10 and B11 markers moved 5 frames, to match Gary's new B10 keys at 5045.

### `LS_S3_HangarRise`: snapshot → millstone tool (17:34)

- One new binding, "S3 Granite Millstone", with one visibility track [0, 744001]. Its keys are byte-identical to the
  pedestal's **[bytes]**.
- The 9 cast visibility tracks are unchanged:
  - covered: Shore01–06 Clam, Clam_with_Pearl, source_Anim, tg0pfjxda_tier_0;
  - range [0, 744000];
  - keys `(0, False), (111200, True)`.

  These are identical in the 1 Oct post-cast-reveal backup (`E-Archive…/PreS3Strike-20261001-123043`) **[bytes]**.
- Every other diff is an EvaluationField hash or an easing-object index that shifted by +2 with the 4 new exports.
  These are renumbering, not content **[inf from the cyclic sha pattern in `rise_*` raw diffs]**.

## 2. Figures disappearing: a pre-existing fold-end revert, not Gary's edit

- The cast reveal keys are at rise ticks 0 and 111200; the rise runs at 24000 ticks/s. So the reveal lands at **4.63 s**
  and the section ends at **744000 = 31.0 s = S3 frame 744**. The fold sub-section maps the rise 1:1 (no
  Parameters serialised, i.e. defaults) **[bytes]**.
- Frame 744 falls inside cut B02 [360, 960), "Figures sway". That matches Gary's "halfway through the shots" **[inf]**.
- The saved level holds the nine cast actors hidden: `s3_cast_reveal_record.json` `after_states` has `hidden: true`.
  The tool's header says so too (`Saved/CodexStructure/s3_cast_reveal_apply.py:1-8`) **[meas, 1 Oct record]**.
- Past the fold end, rise tracks stop evaluating. This was measured for floats: S3 exposure weight was 1.0 at +30 s
  and 0 at +33 s (`s4_hangar_hold.py:603-607`). It was also measured for transforms, which is why the transform hold
  exists. The nest's own `KEEP_STATE` does not keep them **[meas]**.
- Neither the rise float sections nor its visibility sections serialise `EvalOptions`, so both carry their class
  default.
  - The float sections read back live as PROJECT_DEFAULT (`s3_hangar_float_hold_dry_…132933.json`) **[meas]**.
  - PROJECT_DEFAULT resolves to RestoreState: `MovieSceneSequence.h:403-405` and `BaseEngine.ini:3692-3693`
    **[decl]**.
  - The visibility class default is **UNCLEAR**. The section constructor is in an absent .cpp, and the struct default
    is KeepState (`MovieSceneSection.h:92-95`).
- **Verdict:** the figures revert to hidden at 31 s because of the fold-end mechanism. It has been latent since the
  1 Oct cast reveal. That tool checked only the nest's completion mode (`s3_cast_reveal_apply.py:262-288`).
  - **Not Gary's edit**: the fold section and every visibility track are byte-identical before and after it
    **[bytes]**.
  - The revert itself is **[inf]**: it is the same mechanism as the measured floats, and it matches Gary's report. No
    probe has read the figures at +30 s and +33 s.
- **The millstone tool did not alter the figure tracks [bytes].** It did copy the same 31 s keys onto the millstone,
  so the millstone will disappear at 31 s too **[inf, same mechanism]**.
- **A semantics conflict to resolve.** The two tools read the visibility channel oppositely:
  - The cast-reveal tool keyed with the assumption "True = visible" (`s3_cast_reveal_apply.py:55-61`, `:112`).
  - The hold tool's DRY text says "True = HIDDEN" (`s4_hangar_hold.py:716`; `HANGAR_HOLD_FLOAT_EXTENSION_2026-10-07.md:84`,
    citing `klara_reveal.py:3190-3201`).

  Gary's report fits "True = visible": figures shown from 4.6 s, gone at 31 s. Under "True = hidden" he would only see
  them for the first 4.6 s, before any shot **[inf]**. The hold copies the last key's value whatever it means, so the
  fix below is unaffected. But `klara_reveal`'s `_add_visibility(default=hidden)` may be inverted **[inf, flag only]**.

## 3. Right arrow in S3: refused by design; the one exception was deleted

- **What Right does.** Key-down tries `ReleaseActiveHold() || ReleaseActiveVamp()`. Otherwise a tap goes
  `StepShotForward` → `JumpToMasterFrame` (`InfinityStageShowGameMode.cpp:45-46`, `:111-121`, `:158-162`)
  **[decl]**.
- **Why it refuses.** `JumpToMasterFrame` refuses with `UnsafeExternalClock` (result 4) when `IsUnsafeExternalMove`
  is true (`InfinityStageTransportController.cpp:1800-1803`). That is the case when `bPerformanceMode` is set (default
  true, `.h:453`) and the current segment is `DeclaredUnpausable` (`.cpp:2580-2590`) **[decl]**.
  - Hold-Right fast-forward is refused the same way (`.cpp:1377-1381`) **[decl]**.
  - GO holds in S3 are demoted to PASS (`.cpp:1026-1037`) **[decl]**.
  - S3 is `DeclaredUnpausable`, the cellist clock (`Saved/CodexCueing/last_mcp_extsound-apply-1.json`: Scene 3
    before = after = DECLARED_UNPAUSABLE, change = 0) **[meas, 4 Oct]**.
- **Gary's PIE at 21:39–21:40 UTC (17:39–17:40 local)** shows 38 × `INFINITY_STAGE_VIEWPORT_TRANSPORT result=4` and
  0 × result=0. The log lines are `INFINITY_SHOT_STEP … segment=8 … result=4` (`Saved/Logs/PussStage.log:9044-9106`)
  **[meas]**. So performance mode is currently ON: result 4 is unreachable with it off **[decl + meas]**.
- **What changed with Gary's save.**
  - Before it, the log has `INFINITY_VAMP_RANGE segment=8 … start=22364545 end=23084545` at 20:02 and 20:24 UTC
    (`PussStage.log:3127`, `:4967`).
  - After it, every PIE logs `INFINITY_VAMP_UNPAIRED … marker=InfinityStage.VampEnd offset=4200000` (`:7570`, `:8508`,
    `:8692`, `:8864`, `:9002`) **[meas]**.
  - So the B07 orbit (`s3_vamp_apply.py`, frames 3480–4200) no longer loops. That vamp was **the one place in S3 where
    Right did something** (`ReleaseActiveVamp`, `.cpp:1503-1535`) **[decl + meas]**.
- **What Right should do in S3.** In performance mode it should only release the B07 vamp, which plays on at 1x to
  the end of S3. Everywhere else it is refused by design. To step through S3's shots in rehearsal, set `bPerformanceMode`
  to False on the Show Root transport (memory note; `transport_rehearsal_mode.py`), and set it back to True for
  performance.
- **Shot stepping itself is unaffected.** It walks camera-cut starts (`CollectSceneShotStarts`, `.cpp:351-404`), and
  those are unchanged (the log shows 14 shots) **[bytes + meas]**.

## 4. Minimal fix that keeps Gary's camera timing

Do **not** restore any backup or snapshot of `LS_DevScene_03`. Every one of them predates 17:24 and would discard
Gary's camera work (rows 1–8, 10 above).

**A. Figures stay revealed to the end of S3.** Opt visibility into the existing S3 float hold. Gary has to say yes,
because this is a creative change (`HANGAR_HOLD_FLOAT_EXTENSION…md`, the 9-visibility-tracks section).
- The hold record already exists, so a second APPLY stops `RECORD_EXISTS` (`s4_hangar_hold.py:1039-1040`). Run it in
  three steps, all with `Saved/CodexConductor/s4_hangar_hold_args.json` via `s4_hangar_hold_request.json` →
  `s4_hangar_hold_run.py`:
  1. `{"mode":"REVERT","scene":3,"hold":"FLOAT","hold_kinds":["float"],"completion":"KEEP_STATE","confirm":"REVERT S3FLOATHOLD"}`.
     This removes only the 50 recorded float tracks and the empty bindings it created (by GUID + class + path +
     display name). Gary's camera bindings are untouched; their GUIDs are not in the record **[bytes]**.
  2. `{"mode":"DRY","scene":3,"hold":"FLOAT","hold_kinds":["float","visibility"],"completion":"KEEP_STATE"}`. Expect
     50 float targets plus **10** visibility targets (the 9 cast tracks + S3 Granite Millstone), each "hold True from
     last_key", with 0 refused, 0 conflicts and 0 identity mismatches. `source_Anim` and `Clam_with_Pearl…` are object
     names, so watch `identity_mismatch`.
  3. `{"mode":"APPLY",…same…,"confirm":"APPLY S3FLOATHOLD","decided_by":"Gary 7 Oct: figures must not vanish mid-S3 (<his yes>)"}`.
- Between steps 1 and 3, S3 renders white past 31 s. That is temporary.
- Verify: `S3FLOATHOLD_APPLY_OK`, then in PIE the figures are visible at S3 +30 s and +40 s.

**B. Restore Right's job in S3.** Re-add one marked frame to `LS_DevScene_03`: frame **3480**, label exactly
`InfinityStage.VampStart`. Gary can do it by hand in Sequencer, since it is his file. A tool write is backed up and
touches only that marker. Ask Gary whether deleting it was intended. Verify that PIE logs `INFINITY_VAMP_RANGE
segment=8 start=22364545 end=23084545` and no `VAMP_UNPAIRED`.
- Optionally restore the deleted B-markers (labels only, no runtime effect). That is Gary's call.

Nothing else needs reverting: every other change is camera, or a no-op re-serialisation.
