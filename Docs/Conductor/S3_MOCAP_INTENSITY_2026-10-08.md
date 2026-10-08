# Scene 3 shore mocap intensity — 8 October 2026

## Outcome

- **[declaration-proven]** The brief names six Shore figures, their full Animation Sequences, LS_Clams frame-zero section starts, and the `Scene = LS_Clams - 22` nesting (`Docs/Conductor/codex_briefs/p5_mocap_intensity.md:2-4`).
- **[measured]** All six UE-exported binary FBXs were found, hashed, structurally parsed, and sampled at 24 fps (`DerivedAssets/S3MocapIntensity/s3_mocap_intensity_segments.json:36`).
- **[measured]** The parser used the same 16 spine/arm/head bones for every figure; source and curve counts are recorded per FBX (`DerivedAssets/S3MocapIntensity/s3_mocap_intensity_segments.json:45`).
- **[inferred]** CALM/MEDIUM/FRENZY are editorial labels, not rendered or choreographic acceptance. They identify relative intensity within each performer’s take and need Gary’s moving-image review.

## Method and thresholds

- **[measured]** Energy is the sum of angular-speed magnitudes for spine, clavicles, arms, hands, neck and head, plus pelvis/root translation speed weighted by `4.00`; it is Hann-smoothed over `1.50 s` (`DerivedAssets/S3MocapIntensity/s3_mocap_intensity_segments.json:6`).
- **[inferred]** Per-figure p10→0 / p90→1 normalization compensates for performer scale and retarget amplitude. Defaults are CALM ≤ `0.33`, FRENZY ≥ `0.67`, MEDIUM between; runs shorter than `1.00 s` source time are merged. These are exposed as arguments, not creative authority.
- **[inferred]** Current Scene 3 time uses `source / 0.600 + (-22 / 24) s`. The 0.6 rate comes from the original segment authoring (`Saved/CodexMocap/select_gentle_shore_segments.py:35`); the current -22-frame nesting is recorded by the retime probe (`Saved/CodexConductor/s3_retime.py:1-8`) and the section lengths in the brief are consistent with 0.6. This is not a fresh Unreal read-back; re-check after any Sequencer retime.

Timecodes are `MM:SS:FF` at 24 fps. Source time is the FBX/Animation Sequence time; Scene 3 time is the current nested playback time.

## Collective windows

| State | Scene 3 in | Scene 3 out | Duration | Evidence |
| --- | ---: | ---: | ---: | --- |
| ALL_CALM | 00:08:14 | 00:17:03 | 8.54 s | **measured** label intersection; interpretation inferred |
| ALL_CALM | 00:41:20 | 00:51:12 | 9.67 s | **measured** label intersection; interpretation inferred |

**[measured]** No all-six FRENZY window lasts at least 1.0 s under the default thresholds. Do not silently loosen them; use the per-figure rows to choose explicit retimes.

## Shore01_M56 / shoreguy1

**[measured]** `E:/PussStage/DerivedAssets/S3Sackcloth/bodies/Shore01_M56/Shore01_M56_Anim.fbx`; 87.867 s; SHA-256 `8d91a6cadacb9391aba6416f110fc05559638704b0b963305e58ab01b8284f46` (`DerivedAssets/S3MocapIntensity/s3_mocap_intensity_segments.json:34`).

| Class | Source in | Source out | Scene 3 in | Scene 3 out | Evidence |
| --- | ---: | ---: | ---: | ---: | --- |
| FRENZY | 00:00:00 | 00:05:17 | -00:00:22 | 00:08:14 | **measured** curve; class inferred |
| CALM | 00:05:17 | 00:12:02 | 00:08:14 | 00:19:05 | **measured** curve; class inferred |
| FRENZY | 00:12:02 | 00:14:07 | 00:19:05 | 00:22:22 | **measured** curve; class inferred |
| CALM | 00:14:07 | 00:18:20 | 00:22:22 | 00:30:11 | **measured** curve; class inferred |
| MEDIUM | 00:18:20 | 00:21:05 | 00:30:11 | 00:34:10 | **measured** curve; class inferred |
| CALM | 00:21:05 | 00:24:05 | 00:34:10 | 00:39:10 | **measured** curve; class inferred |
| MEDIUM | 00:24:05 | 00:25:16 | 00:39:10 | 00:41:21 | **measured** curve; class inferred |
| CALM | 00:25:16 | 00:32:21 | 00:41:21 | 00:53:21 | **measured** curve; class inferred |
| MEDIUM | 00:32:21 | 00:34:04 | 00:53:21 | 00:56:01 | **measured** curve; class inferred |
| CALM | 00:34:04 | 00:36:09 | 00:56:01 | 00:59:17 | **measured** curve; class inferred |
| FRENZY | 00:36:09 | 00:39:16 | 00:59:17 | 01:05:05 | **measured** curve; class inferred |
| MEDIUM | 00:39:16 | 00:40:16 | 01:05:05 | 01:06:21 | **measured** curve; class inferred |
| FRENZY | 00:40:16 | 00:51:02 | 01:06:21 | 01:24:05 | **measured** curve; class inferred |
| MEDIUM | 00:51:02 | 00:53:13 | 01:24:05 | 01:28:08 | **measured** curve; class inferred |
| CALM | 00:53:13 | 00:54:18 | 01:28:08 | 01:30:08 | **measured** curve; class inferred |
| FRENZY | 00:54:18 | 00:56:10 | 01:30:08 | 01:33:03 | **measured** curve; class inferred |
| MEDIUM | 00:56:10 | 00:58:15 | 01:33:03 | 01:36:19 | **measured** curve; class inferred |
| CALM | 00:58:15 | 01:04:12 | 01:36:19 | 01:46:14 | **measured** curve; class inferred |
| MEDIUM | 01:04:12 | 01:06:12 | 01:46:14 | 01:49:22 | **measured** curve; class inferred |
| FRENZY | 01:06:12 | 01:07:15 | 01:49:22 | 01:51:19 | **measured** curve; class inferred |
| MEDIUM | 01:07:15 | 01:08:15 | 01:51:19 | 01:53:11 | **measured** curve; class inferred |
| FRENZY | 01:08:15 | 01:10:21 | 01:53:11 | 01:57:05 | **measured** curve; class inferred |
| CALM | 01:10:21 | 01:13:01 | 01:57:05 | 02:00:20 | **measured** curve; class inferred |
| FRENZY | 01:13:01 | 01:15:05 | 02:00:20 | 02:04:10 | **measured** curve; class inferred |
| CALM | 01:15:05 | 01:16:06 | 02:04:10 | 02:06:04 | **measured** curve; class inferred |
| MEDIUM | 01:16:06 | 01:19:02 | 02:06:04 | 02:10:21 | **measured** curve; class inferred |
| CALM | 01:19:02 | 01:25:08 | 02:10:21 | 02:21:07 | **measured** curve; class inferred |
| MEDIUM | 01:25:08 | 01:27:22 | 02:21:07 | 02:25:15 | **measured** curve; class inferred |

## Shore02_F52 / shoreguy12

**[measured]** `E:/PussStage/DerivedAssets/S3Sackcloth/bodies/Shore02_F52/Shore02_F52_Anim.fbx`; 87.967 s; SHA-256 `e2db7fd16944785aff9accec24d7517b037db255fae8d9af952aed536d9e3fd3` (`DerivedAssets/S3MocapIntensity/s3_mocap_intensity_segments.json:421`).

| Class | Source in | Source out | Scene 3 in | Scene 3 out | Evidence |
| --- | ---: | ---: | ---: | ---: | --- |
| FRENZY | 00:00:00 | 00:02:18 | -00:00:22 | 00:03:16 | **measured** curve; class inferred |
| MEDIUM | 00:02:18 | 00:04:09 | 00:03:16 | 00:06:09 | **measured** curve; class inferred |
| CALM | 00:04:09 | 00:13:05 | 00:06:09 | 00:21:02 | **measured** curve; class inferred |
| MEDIUM | 00:13:05 | 00:16:11 | 00:21:02 | 00:26:12 | **measured** curve; class inferred |
| CALM | 00:16:11 | 01:03:05 | 00:26:12 | 01:44:10 | **measured** curve; class inferred |
| FRENZY | 01:03:05 | 01:11:03 | 01:44:10 | 01:57:15 | **measured** curve; class inferred |
| MEDIUM | 01:11:03 | 01:15:11 | 01:57:15 | 02:04:20 | **measured** curve; class inferred |
| FRENZY | 01:15:11 | 01:18:21 | 02:04:20 | 02:10:13 | **measured** curve; class inferred |
| MEDIUM | 01:18:21 | 01:21:17 | 02:10:13 | 02:15:06 | **measured** curve; class inferred |
| FRENZY | 01:21:17 | 01:28:00 | 02:15:06 | 02:25:18 | **measured** curve; class inferred |

## Shore03_M59 / shoreguy3

**[measured]** `E:/PussStage/DerivedAssets/S3Sackcloth/bodies/Shore03_M59/Shore03_M59_Anim.fbx`; 88.300 s; SHA-256 `e01f5d1a13632e012801af4f13c644bf5f86fdeed7330174bd598a620ca3f731` (`DerivedAssets/S3MocapIntensity/s3_mocap_intensity_segments.json:592`).

| Class | Source in | Source out | Scene 3 in | Scene 3 out | Evidence |
| --- | ---: | ---: | ---: | ---: | --- |
| FRENZY | 00:00:00 | 00:01:04 | -00:00:22 | 00:01:01 | **measured** curve; class inferred |
| CALM | 00:01:04 | 00:19:03 | 00:01:01 | 00:30:23 | **measured** curve; class inferred |
| FRENZY | 00:19:03 | 00:23:22 | 00:30:23 | 00:38:23 | **measured** curve; class inferred |
| CALM | 00:23:22 | 00:31:11 | 00:38:23 | 00:51:12 | **measured** curve; class inferred |
| FRENZY | 00:31:11 | 00:33:08 | 00:51:12 | 00:54:15 | **measured** curve; class inferred |
| MEDIUM | 00:33:08 | 00:37:23 | 00:54:15 | 01:02:08 | **measured** curve; class inferred |
| CALM | 00:37:23 | 00:52:12 | 01:02:08 | 01:26:14 | **measured** curve; class inferred |
| FRENZY | 00:52:12 | 00:54:21 | 01:26:14 | 01:30:13 | **measured** curve; class inferred |
| CALM | 00:54:21 | 00:55:22 | 01:30:13 | 01:32:07 | **measured** curve; class inferred |
| MEDIUM | 00:55:22 | 00:57:12 | 01:32:07 | 01:34:22 | **measured** curve; class inferred |
| CALM | 00:57:12 | 01:01:06 | 01:34:22 | 01:41:04 | **measured** curve; class inferred |
| MEDIUM | 01:01:06 | 01:10:01 | 01:41:04 | 01:55:20 | **measured** curve; class inferred |
| CALM | 01:10:01 | 01:13:23 | 01:55:20 | 02:02:08 | **measured** curve; class inferred |
| MEDIUM | 01:13:23 | 01:16:10 | 02:02:08 | 02:06:11 | **measured** curve; class inferred |
| CALM | 01:16:10 | 01:17:19 | 02:06:11 | 02:08:18 | **measured** curve; class inferred |
| MEDIUM | 01:17:19 | 01:19:07 | 02:08:18 | 02:11:06 | **measured** curve; class inferred |
| FRENZY | 01:19:07 | 01:21:23 | 02:11:06 | 02:15:16 | **measured** curve; class inferred |
| MEDIUM | 01:21:23 | 01:26:13 | 02:15:16 | 02:23:08 | **measured** curve; class inferred |
| FRENZY | 01:26:13 | 01:28:08 | 02:23:08 | 02:26:07 | **measured** curve; class inferred |

## Shore04_F55 / shoreguy4

**[measured]** `E:/PussStage/DerivedAssets/S3Sackcloth/bodies/Shore04_F55/Shore04_F55_Anim.fbx`; 118.667 s; SHA-256 `aa275365070cf534633a384d37c50a1c0276e4e856a185fcf3aa45822f2e8b27` (`DerivedAssets/S3MocapIntensity/s3_mocap_intensity_segments.json:871`).

| Class | Source in | Source out | Scene 3 in | Scene 3 out | Evidence |
| --- | ---: | ---: | ---: | ---: | --- |
| FRENZY | 00:00:00 | 00:03:14 | -00:00:22 | 00:05:01 | **measured** curve; class inferred |
| CALM | 00:03:14 | 00:20:12 | 00:05:01 | 00:33:06 | **measured** curve; class inferred |
| MEDIUM | 00:20:12 | 00:21:20 | 00:33:06 | 00:35:11 | **measured** curve; class inferred |
| CALM | 00:21:20 | 00:23:06 | 00:35:11 | 00:37:20 | **measured** curve; class inferred |
| MEDIUM | 00:23:06 | 00:24:09 | 00:37:20 | 00:39:17 | **measured** curve; class inferred |
| CALM | 00:24:09 | 00:35:00 | 00:39:17 | 00:57:10 | **measured** curve; class inferred |
| MEDIUM | 00:35:00 | 00:39:20 | 00:57:10 | 01:05:11 | **measured** curve; class inferred |
| CALM | 00:39:20 | 00:41:01 | 01:05:11 | 01:07:12 | **measured** curve; class inferred |
| MEDIUM | 00:41:01 | 00:46:02 | 01:07:12 | 01:15:21 | **measured** curve; class inferred |
| FRENZY | 00:46:02 | 00:49:14 | 01:15:21 | 01:21:17 | **measured** curve; class inferred |
| MEDIUM | 00:49:14 | 00:50:18 | 01:21:17 | 01:23:16 | **measured** curve; class inferred |
| FRENZY | 00:50:18 | 00:54:12 | 01:23:16 | 01:29:22 | **measured** curve; class inferred |
| MEDIUM | 00:54:12 | 00:59:11 | 01:29:22 | 01:38:04 | **measured** curve; class inferred |
| FRENZY | 00:59:11 | 01:00:21 | 01:38:04 | 01:40:13 | **measured** curve; class inferred |
| MEDIUM | 01:00:21 | 01:02:17 | 01:40:13 | 01:43:14 | **measured** curve; class inferred |
| FRENZY | 01:02:17 | 01:05:17 | 01:43:14 | 01:48:14 | **measured** curve; class inferred |
| CALM | 01:05:17 | 01:06:18 | 01:48:14 | 01:50:08 | **measured** curve; class inferred |
| FRENZY | 01:06:18 | 01:09:19 | 01:50:08 | 01:55:10 | **measured** curve; class inferred |
| MEDIUM | 01:09:19 | 01:11:17 | 01:55:10 | 01:58:14 | **measured** curve; class inferred |
| CALM | 01:11:17 | 01:29:13 | 01:58:14 | 02:28:08 | **measured** curve; class inferred |
| MEDIUM | 01:29:13 | 01:31:15 | 02:28:08 | 02:31:19 | **measured** curve; class inferred |
| FRENZY | 01:31:15 | 01:33:16 | 02:31:19 | 02:35:05 | **measured** curve; class inferred |
| CALM | 01:33:16 | 01:35:12 | 02:35:05 | 02:38:06 | **measured** curve; class inferred |
| FRENZY | 01:35:12 | 01:39:04 | 02:38:06 | 02:44:09 | **measured** curve; class inferred |
| MEDIUM | 01:39:04 | 01:40:10 | 02:44:09 | 02:46:11 | **measured** curve; class inferred |
| CALM | 01:40:10 | 01:44:16 | 02:46:11 | 02:53:13 | **measured** curve; class inferred |
| MEDIUM | 01:44:16 | 01:46:00 | 02:53:13 | 02:55:18 | **measured** curve; class inferred |
| CALM | 01:46:00 | 01:48:06 | 02:55:18 | 02:59:12 | **measured** curve; class inferred |
| MEDIUM | 01:48:06 | 01:50:13 | 02:59:12 | 03:03:08 | **measured** curve; class inferred |
| FRENZY | 01:50:13 | 01:55:06 | 03:03:08 | 03:11:04 | **measured** curve; class inferred |
| MEDIUM | 01:55:06 | 01:56:08 | 03:11:04 | 03:12:23 | **measured** curve; class inferred |
| FRENZY | 01:56:08 | 01:58:17 | 03:12:23 | 03:16:22 | **measured** curve; class inferred |

## Shore05_M53 / shoreguy5

**[measured]** `E:/PussStage/DerivedAssets/S3Sackcloth/bodies/Shore05_M53/Shore05_M53_Anim.fbx`; 86.433 s; SHA-256 `3eac3fff05ffdb896486283b6e06b2adafc424cdb2eda134f381a088fdacf6d8` (`DerivedAssets/S3MocapIntensity/s3_mocap_intensity_segments.json:1306`).

| Class | Source in | Source out | Scene 3 in | Scene 3 out | Evidence |
| --- | ---: | ---: | ---: | ---: | --- |
| CALM | 00:00:00 | 00:10:21 | -00:00:22 | 00:17:05 | **measured** curve; class inferred |
| MEDIUM | 00:10:21 | 00:18:08 | 00:17:05 | 00:29:15 | **measured** curve; class inferred |
| CALM | 00:18:08 | 00:32:09 | 00:29:15 | 00:53:01 | **measured** curve; class inferred |
| MEDIUM | 00:32:09 | 00:33:19 | 00:53:01 | 00:55:10 | **measured** curve; class inferred |
| CALM | 00:33:19 | 00:36:07 | 00:55:10 | 00:59:14 | **measured** curve; class inferred |
| MEDIUM | 00:36:07 | 00:39:02 | 00:59:14 | 01:04:05 | **measured** curve; class inferred |
| FRENZY | 00:39:02 | 00:53:10 | 01:04:05 | 01:28:03 | **measured** curve; class inferred |
| MEDIUM | 00:53:10 | 00:55:13 | 01:28:03 | 01:31:16 | **measured** curve; class inferred |
| FRENZY | 00:55:13 | 00:57:00 | 01:31:16 | 01:34:02 | **measured** curve; class inferred |
| CALM | 00:57:00 | 00:58:19 | 01:34:02 | 01:37:02 | **measured** curve; class inferred |
| FRENZY | 00:58:19 | 01:00:14 | 01:37:02 | 01:40:01 | **measured** curve; class inferred |
| CALM | 01:00:14 | 01:02:08 | 01:40:01 | 01:42:23 | **measured** curve; class inferred |
| MEDIUM | 01:02:08 | 01:03:17 | 01:42:23 | 01:45:06 | **measured** curve; class inferred |
| CALM | 01:03:17 | 01:04:21 | 01:45:06 | 01:47:05 | **measured** curve; class inferred |
| MEDIUM | 01:04:21 | 01:07:03 | 01:47:05 | 01:50:23 | **measured** curve; class inferred |
| FRENZY | 01:07:03 | 01:08:07 | 01:50:23 | 01:52:22 | **measured** curve; class inferred |
| MEDIUM | 01:08:07 | 01:11:10 | 01:52:22 | 01:58:03 | **measured** curve; class inferred |
| FRENZY | 01:11:10 | 01:14:09 | 01:58:03 | 02:03:01 | **measured** curve; class inferred |
| CALM | 01:14:09 | 01:26:11 | 02:03:01 | 02:23:04 | **measured** curve; class inferred |

## Shore06_F25 / shoreguy6

**[measured]** `E:/PussStage/DerivedAssets/S3Sackcloth/bodies/Shore06_F25/Shore06_F25_Anim.fbx`; 91.433 s; SHA-256 `3b3e2e80ca601292de3a2c7630c9a92003618a946ec0ed812e9ec1e4ccfef7a9` (`DerivedAssets/S3MocapIntensity/s3_mocap_intensity_segments.json:1585`).

| Class | Source in | Source out | Scene 3 in | Scene 3 out | Evidence |
| --- | ---: | ---: | ---: | ---: | --- |
| FRENZY | 00:00:00 | 00:01:08 | -00:00:22 | 00:01:07 | **measured** curve; class inferred |
| CALM | 00:01:08 | 00:10:20 | 00:01:07 | 00:17:03 | **measured** curve; class inferred |
| MEDIUM | 00:10:20 | 00:14:01 | 00:17:03 | 00:22:12 | **measured** curve; class inferred |
| CALM | 00:14:01 | 00:50:03 | 00:22:12 | 01:22:15 | **measured** curve; class inferred |
| MEDIUM | 00:50:03 | 00:54:01 | 01:22:15 | 01:29:04 | **measured** curve; class inferred |
| FRENZY | 00:54:01 | 00:58:15 | 01:29:04 | 01:36:19 | **measured** curve; class inferred |
| MEDIUM | 00:58:15 | 00:59:21 | 01:36:19 | 01:38:21 | **measured** curve; class inferred |
| FRENZY | 00:59:21 | 01:10:05 | 01:38:21 | 01:56:02 | **measured** curve; class inferred |
| MEDIUM | 01:10:05 | 01:14:13 | 01:56:02 | 02:03:08 | **measured** curve; class inferred |
| FRENZY | 01:14:13 | 01:18:04 | 02:03:08 | 02:09:09 | **measured** curve; class inferred |
| CALM | 01:18:04 | 01:31:11 | 02:09:09 | 02:31:12 | **measured** curve; class inferred |

## Use and acceptance boundary

1. **[declaration-proven]** Use the JSON segment boundaries or the aligned PNG as placement references; do not change the Animation Sequences (`Docs/Conductor/codex_briefs/p5_mocap_intensity.md:2-4`).
2. **[inferred]** Prefer long CALM spans for first fabric checks, then the listed collective FRENZY spans for stress tests. Threshold changes must be explicit CLI arguments and produce a new preview.
3. **[inferred]** Final acceptance remains a rendered motion/fabric review. Offline FBX analysis cannot prove cloth stability, staging readability, or whether the performance reads as calm/frenzied to Gary.

## Reproduce

```powershell
python Tools/Mocap/test_shore_mocap_intensity.py
python Tools/Mocap/shore_mocap_intensity.py --mode DRY --source-root E:/PussStage
python Tools/Mocap/shore_mocap_intensity.py --mode APPLY --confirm "APPLY S3MOCAPINTENSITY" --run S3MOCAP-20261008-P5R2 --source-root E:/PussStage
```
