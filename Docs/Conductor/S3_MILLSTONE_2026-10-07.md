# S3 Granite Millstone and props: import, material, placement (7 Oct 2026)

**Status:** written OFFLINE. Unreal and MCP were not called. Nothing has been imported, built, placed or saved.
The offline harness passes 135 of 135 checks (`Saved/CodexConductor/S3Millstone/test_s3_props.py`, report
`test_s3_props_report.json`). The Unreal glue has never run, so every editor-side API call below is **[inf]**
until the conductor's DRY call.

Tiers: **[decl]** = header or config, **[meas]** = read back from a file or a live probe, **[inf]** = not verified,
with the reason given.

## 1. Gary's decisions this implements

- The Rodin "GraniteMillstone" REPLACES the S3 clam pedestal. It is imported as new assets and is not attached to
  S3 Hangar Root.
- The clam sits centred on top of the stone at about 1.3 m.
- Clam_Pedastal is HIDDEN, not deleted.
- The BaseColor is imported at 8K.
- The Fab clam stays as a STAND-IN until the ~1 m Tridacna arrives (coordinator, 7 Oct).
- Re-seating the stand-in is optional. If its transform is keyed, the tool skips it and reports. No offset mechanism
  is built.
- Scope extension (coordinator, 7 Oct): IMPORT and BUILD_MAT now take any prop from one table (HoledStandingStone,
  HominidRibcage, HominidLegBone, HominidJaw).
  - Each call handles one prop.
  - There is one shared master material.
  - APPLY handles the millstone only. The other props go through PLACE once positions exist; none has been chosen.

**Asset folder decision:** every prop, the millstone included, goes under
`/Game/InfinityStage/Dev/Generated/S3Props/<Name>/`. The shared master is
`/Game/InfinityStage/Dev/Generated/S3Props/M_S3Prop`. There is no separate S3Millstone content folder. The tool's
scripts still live in `Saved/CodexConductor/S3Millstone/`.

## 2. Findings that change the plan

**F1. The Fab clam actors' transforms ARE keyed, so APPLY will NOT re-seat them.** **[meas, 12 Sep; re-checked live by DRY]**
- `Saved/CodexMocap/clam_sequence_routing.json:39-55` shows LS_Clams carrying a `MovieScene3DTransformTrack` on two
  bindings:
  - `Clam_with_Pearl_Clam_with_Pearl_0` (line 43);
  - `source_Anim` (line 67), which also carries the skeletal animation track.
- LS_Clams plays inside LS_DevScene_03, frames 103–765 at 25 fps (same file).
- Moving the actors would not hold while LS_Clams evaluates (Passage keys are absolute; memory
  puss-passage-keys-absolute). The tool therefore returns `SKIPPED_KEYED` (`s3_props_ue.py:352`).
- DRY re-reads the tracks live from LS_Clams, LS_DevScene_03 and LS_S3_HangarRise (`_sequence_tracks`,
  `s3_props_ue.py:684`). It fails closed: any sequence it cannot read counts as keyed (`clam_keyed_verdict`, `:302`).

**F1 consequence: Gary must decide this.** With the keys left where they are, the stand-in clam ends up INSIDE the
new stone. **[inf]**
- These figures assume a floor of ~11.5 and the stone base 2 cm below it. They come from the harness example; the
  real floor value comes from DRY.
- Stone top ≈ world z 138.
- `Clam_with_Pearl_Clam_with_Pearl_0` (static, z 93–114): bottom 45 cm inside the stone, top 24 cm below the stone
  top. It is fully hidden.
- `source_Anim` (skeletal, z 85–146): bottom 53 cm inside the stone, top 8 cm above it.
- So until the Tridacna arrives, S3 shows the stone with at most a sliver of clam.
- Options (none built):
  - (a) accept this until the Tridacna arrives;
  - (b) offset the LS_Clams transform keys by about +50 cm. That edits a sequence asset and needs Gary's yes;
  - (c) hold APPLY until the Tridacna arrives.

**F2. The pedestal is revealed by a Sequencer track, so hiding the actor flag alone would not hide it.** **[meas, 1 Oct]**
- `Saved/CodexStructure/s3_cast_reveal_record.json` records a binding for `tg0pfjxda_tier_0`, which is now labelled
  Clam_Pedastal. Its GUID is `2425E62E4F7051520E7154A094123BE3` and it resolves to `PersistentLevel.StaticMeshActor_4`.
- That binding gives it a visibility track in `LS_S3_HangarRise`, keyed hidden at 0 and visible 0.5 s after landing
  (`s3_cast_reveal_apply.py:1-8`, plan `reveal_s` 4.6261).
- The probe's `hidden_game: true` (`probe_s3_clam_rock.json`) is the level state that this track overrides at 4.6 s.
- APPLY therefore hides the pedestal at the COMPONENT level: visibility off and hidden-in-game on
  (`_set_flags`, `s3_props_ue.py:673-681`). It still records and sets the actor flag.
- **[inf]:** the visibility track drives the actor's bHidden and not the component's bVisible. The header does not
  say which property it drives (`MovieSceneVisibilityTrack.h:11-35` **[decl]** lists no property). The cast-reveal
  author marked the semantics UNCLEAR for the same reason.
- To verify: PIE past the landing and check that the pedestal stays unseen.

**F3. The new stone needs the same reveal, or it shows before the hangar lands.** **[inf]**
- The stone is unattached (Gary's rule). The hangar is sunk at BeginPlay (memory
  puss-level-saved-landed-frame-trap), so a visible stone would stand alone in open sky until the box rises around it.
- With `reveal: "rise_track"` (the default), APPLY:
  - spawns the stone hidden in game;
  - adds ONE possessable binding to LS_S3_HangarRise for it;
  - gives that binding a visibility track that is an exact COPY of the pedestal's live section: range, completion
    mode and display-rate keys (`_add_reveal` `:843`, verified by `_verify_reveal` `:863`).
- **This writes LS_S3_HangarRise** (one new binding). The save census is exactly that asset plus the map.
- Set `"reveal": "none"` to avoid touching the sequence; the stone is then always visible.

**F4. The ~1 m clam fits the top with no overhang.** **[meas offline from the FBX that IMPORT reads]**
- Source: `fbx_top_measure.py` → `s3_millstone_fbx_measure.json`, a 2 cm upper-surface height map from 1,699,697
  vertices.
- The FBX geometry matches the manifest: 143.89 × 147.61 × 130.0 cm. It is stored Z-up under a model
  `Lcl Rotation (-90,0,0)`.
- The top is a gentle dome. Upper-surface median by radius:

  | Radius | Height | Note |
  |---|---|---|
  | r = 0 | 128.6 | |
  | r = 30 | 127.9 | |
  | r = 50 | 125.7 | rim lump to 130.0 near r ≈ 50 |
  | r = 60 | 124.9 | |
  | r = 70 | 108.4 | the edge falls away here |

- A 100 cm disc centred on the axis is 100 % supported within 5 cm below the axis top. The first point more than
  5 cm below sits at r = 58.8 cm, so the margin is about 9 cm per side and **overhang = 0**.
- Strictly flat (±1.5 cm of the axis top): 0.69 m², extent 108 × 104 cm, equivalent Ø 94 cm. A 1 m footprint
  therefore reaches ~3 cm past the strictly flat zone at its rim, onto surface 2–3 cm lower.
- The coordinator's "83 × 87 cm flat top" does not match this measurement. It looks like the BASE band: the lowest
  2.6 cm spans 94.8 × 83.4 (also in the manifest).
- `top_offset_cm` default = 128.6 (the axis top). The harness asserts that it equals the measured value (B2).
- A clam with a convex underside resting near r ≈ 50 may touch the 130.0 lump first. The re-seat uses the clam's
  AABB bottom, so expect up to ~1.4 cm float or contact there. **[inf]**

**F5. The floor at the spot is not known to the centimetre.**
- Brief: sand top ≈ 14 **[meas there]**.
- The shore prep implies sand ≈ 10, from "pedestal embedded 8.6 cm" (S3_SHORE_GROUND_PREP:244) with the pedestal base
  at 1.38. **[inf]**
- So APPLY measures the floor live and does not trust either number:
  - it reads the vertices of the highest VISIBLE floor among `S3 Shore Ground`, `S3 Beach V2 Sand Floor` and
    `S3 Hangar Deck` (a box, so its AABB top is used) within 45 cm of the target xy, i.e. inside the stone's flat base
    band (`_floor_samples` `:746`);
  - it seats the base at the median minus 2 cm;
  - it refuses if the spread is above 8 cm unless `accept_floor_spread` is set.
- The vertex reads use `get_static_mesh_description(0)` + `get_vertex_position(VertexID(i))`. Precedent:
  `Scripts/build_curtain_chaos_asset.py:362-366`, which ran then. **[inf]** for these meshes.
- If the shore ground is applied later, the floor changes and the stone needs REVERT → APPLY, which re-measures.

## 3. Tool, files, gates

All files are in `Saved/CodexConductor/S3Millstone/`:

| File | What it does |
|---|---|
| `s3_props_ue.py` | The tool. Pure planning sits above `# Unreal glue` (`:599`); editor code is below it. |
| `s3_props_run.py` | Runner: purges Saved/ modules, then runs `main()`. |
| `s3_props_args.json` | Args. Set to DRY. |
| `s3_props_placements.json` | Empty on purpose: no positions chosen yet. |
| `fbx_top_measure.py` | Offline FBX measurement. |
| `test_s3_props.py` | The harness. |

The MCP request is `Saved/CodexConductor/s3_props_request.json`.

**Prop table** (`PROPS`, `:94`). Sizes and pivots come from each manifest. The harness asserts table = manifest = FBX
geometry for all five props (A, B2).

| Prop | Size (cm) | Pivot |
|---|---|---|
| GraniteMillstone | 143.9 × 147.6 × 130 | base |
| HoledStandingStone | 143.65 × 102.73 × 330 | sand line, min z −30 |
| HominidRibcage | 21.34 × 22.0 × 10.54 | base |
| HominidLegBone | 28.0 × 8.48 × 4.16 | base |
| HominidJaw | 7.79 × 8.0 × 4.21 | base |

**IMPORT_MESH** (`run_import_mesh`, `:1082`):
- Uses the shore ground's Interchange override: materials and textures OFF, Nanite ON, no LODs, collision off. Its
  names are header-cited in `S3Shore/s3_shore_ground_ue.py` `_pipeline`.
- Gates:
  - 1 LOD;
  - Nanite on;
  - one slot;
  - `bounds_check` (`:164`): every axis's size and min/max within 1 cm for the stones, or max(0.3 cm, 0.5 %) for the
    bones. It names `SCALE_100X` and `AXES_PERMUTED`;
  - no stray assets (folder diff);
  - census exactly that one package.
- **Known limit:** on the jaw (7.79 vs 8.0 cm) a 90° yaw swap is inside tolerance and cannot be detected. The harness
  states this explicitly. It is harmless because placement yaw is a parameter.
- **[inf]:** the expected UE bounds assume Interchange keeps Blender X → UE X and maps Y with a sign flip only. The
  sizes are symmetric about the centre, so a mirror would pass the size gate. Mirroring would show only in the
  texture, and is unverified until a render.

**IMPORT_TEX** (`run_import_tex`):
- Before import, it gates each PNG on its IHDR: 4096², or 8192 for the millstone BaseColor. The 12K source is
  refused (harness A, − control).
- Settings per role (`TEX_ROLES`, `:84`):

  | Role | Compression | sRGB | Green flip |
  |---|---|---|---|
  | BaseColor | TC_DEFAULT | on | — |
  | N (already DirectX) | TC_NORMALMAP | off | no |
  | Roughness | TC_MASKS | off | — |

- Every setting and size is read back.
- The millstone BaseColor must go ALONE in its call (memory ue58-bulk-import-oom-crash). The tool enforces this. GC
  runs after the call.
- **[meas]:** none of the 15 source PNGs carries an sRGB, gAMA or iCCP chunk. The texture's sRGB flag therefore
  comes only from the explicit setting above.

**PREP_TEXTURES** (offline: `python s3_props_ue.py PREP_TEXTURES`):
- Converts the 12288² BaseColor to `DerivedAssets/GraniteMillstone/Export/8K/T_GraniteMillstone_BaseColor.png` at
  8192² with PIL LANCZOS.
- Keeps the mode and every colour-space chunk, re-reads the written file, and writes
  `s3_props_prep_textures_record.json` with its sha256.
- Expect about 0.5 GB RAM and a minute or two. It refuses if the destination already exists.

**BUILD_MAT** (`run_build_mat`):
- Creates the shared master `M_S3Prop` once and only verifies it afterwards.
  - Its parameters are BaseColor / Normal / Roughness, plus `RoughnessMultiplier` (1.0) and `RoughnessOverride`
    (−1 = off; ≥ 0 replaces the map).
  - Roughness = `O >= 0 ? sat(O) : sat(R*M)` (`ROUGH_CODE`, `:91`).
- Creates `MI_<Name>` and reads back its parent, textures and scalars.
- HominidLegBone gets `RoughnessMultiplier` 1.95. That takes its map median of 0.40 (manifest) to 0.78 and keeps the
  map's variation. The override is still available for Gary to tune.

**APPLY** (`run_apply`, `:924`), millstone only:
1. Gates:
   - confirm string;
   - no PIE;
   - the show level;
   - census 0 + 0;
   - no ZZ_/TEMP actors;
   - root LANDED within 1 cm;
   - label free;
   - assets exist;
   - pedestal object is `StaticMeshActor_4` with no parent;
   - floor measured;
   - stone box inside the landed root-local guard (`GUARD_LOCAL`, `:78`);
   - pedestal reveal binding found.
2. Writes the record FIRST (`s3_millstone_apply_record.json`).
3. Backs up to `Backups/PreS3Millstone-<run>/`: umap + LS_S3_HangarRise.uasset + record, each sha-checked.
4. Spawns "S3 Granite Millstone" with yaw 0 and scale 1, unattached, mobility copied from the pedestal (STATIC), tags
   `RigAtmos.S3Props`, folder RigAtmos/S3Props.
5. Adds the reveal copy and hides the pedestal.
6. Re-seats the clams only if none is keyed (F1).
7. Reads back, then saves with the census exactly {LS_S3_HangarRise, map}, then reads back again from fresh lookups.
8. Prints `S3MILL_APPLY_OK`.

On yaw: the top dome is near-radial (F4), so no yaw is better than another for the top. 0 is kept, per the brief.

**REVERT:**
- Refuses if anything drifted since APPLY.
- Takes its own backup.
- Restores clams (if moved), then the pedestal flags, removes OUR binding (by GUID, after proving it resolves to our
  actor; `remove()` is judged by re-listing), and destroys our actor.
- Saves and reads back against the RECORD's numbers. The marker is `S3MILL_REVERT_OK`.

**PLACE / UNPLACE:**
- Same discipline as APPLY / REVERT, driven by a placements JSON.
- `burial_cm` = how far the pivot sits below the measured surface.
  - HoledStandingStone: pivot = sand line, so `burial_cm: 0` buries its 30 cm root (harness G).
  - Bones: a few cm for "part-buried".
- Nothing is placed until Gary picks positions.

**Harness controls** (135 checks; all pass):

| Check | Controls |
|---|---|
| A | table = manifest; PNG headers vs PIL; 12K BaseColor refused (−) |
| B | per prop: exact and ±1 mm pass (+); 100× and 0.01× (−); pitched 90° (−); yaw-swap (−, except the jaw: documented); standing stone with its pivot at the base refused (−) and at −30 passed (+) |
| B2 | every FBX's geometry = manifest; `top_offset` = measured axis top |
| C | graph clean (+); orphan node caught (−); roughness maths |
| D | dirty census refuses (−); DRY tolerates it; confirm, twice-apply and no-record refusals |
| E | plan built from the live probe + the 12 Sep track list: keyed → SKIPPED_KEYED; unkeyed → MOVE with the lowest bottom exactly on the top; unreadable or missing track data fails closed (−); 9 refusals (not landed, ZZ_, label, assets, pedestal object, no reveal binding, floor spread, floor unmeasured, clam missing) plus outside-box; deck fallback when the sand is hidden |
| F | apply → revert ops round trip restores the world exactly (+); a tampered record is caught (−); a foreign binding is refused (−) |
| G | standing stone 30 cm buried; root-local xy; jaw part-buried; empty and outside placements refused |
| H | 8K-path downscale on synthetic PNGs keeps dims, mode, and the sRGB / gAMA / iCCP chunks (+); a plain PIL save drops sRGB (− control, which shows the preserve step matters) |

**What the harness does NOT cover [inf]:**
- the Unreal API calls themselves;
- whether Interchange honours the override (the shore precedent was written, not run);
- `add_possessable` / `add_track` / `add_key` / `set_completion_mode` (precedent: `s3_cast_reveal_apply.py:476-500`,
  run 1 Oct);
- the vertex-read speed on a dense shore ground (cap 4M vertices).

## 4. Run order (conductor; each step is one MCP call)

`python Saved/CodexMocap/mcp_request.py tools/call --params-file Saved/CodexConductor/s3_props_request.json --timeout 600`
after editing `S3Millstone/s3_props_args.json`. After every call, grep `Saved/Logs/PussStage.log` for the marker
**with this run id**.

0. Offline: `cd Saved/CodexConductor/S3Millstone && python test_s3_props.py`, then `python s3_props_ue.py PREP_TEXTURES`.
1. `DRY`. Read `s3_props_dry_<run>.json`:
   - the floor rows and spread;
   - the clam verdicts (KEYED expected);
   - the pedestal reveal section;
   - `apply` = would_apply (it refuses until assets exist; that is expected at this stage).
2. `IMPORT_MESH` prop GraniteMillstone → `S3PROPS_IMPORT_MESH_OK`.
3. `IMPORT_TEX` GraniteMillstone `"textures": ["BaseColor"]` (the 8K, alone).
4. `IMPORT_TEX` GraniteMillstone `"textures": ["N", "Roughness"]`.
5. `BUILD_MAT` GraniteMillstone. This creates M_S3Prop and MI_GraniteMillstone. Wait ~20 s, then grep the log for
   "Failed to compile".
6. `DRY` again: `apply` must read `would_apply`. **Show Gary F1 (clam inside the stone) and get his choice first.**
7. `APPLY` (confirm "APPLY S3PROPS") → `S3MILL_APPLY_OK`. Then:
   - PIE past the S3 landing;
   - check that the pedestal stays unseen, the stone appears with the cast, and how the clam reads;
   - then queue `InfinityStage.Editor.SavedMasterMatchesShow` and `SceneCutBindingsResolve` after a run-id marker.
8. Other props, whenever wanted: for each prop, run `IMPORT_MESH` → `IMPORT_TEX` (all three in one call) →
   `BUILD_MAT`, one call each. `PLACE` waits for positions.
9. Undo: `REVERT` (confirm "REVERT S3PROPS"). Assets stay.

**Coordination:**
- APPLY saves `LS_S3_HangarRise`. The hangar-hold stream (HANGAR_HOLD_FLOAT_EXTENSION_2026-10-07) also targets rise
  sequences, so do not run the two together. The census gate refuses if the sequence is dirty.
- Re-seating the clam is left to whoever brings in the Tridacna. The tool's re-seat is generic:
  - it is parameterised by `clam_labels` and seats the lowest AABB bottom on `top_z`;
  - it only moves actors that have no transform track.

## 5. PearlClam extension (7 Oct evening): written OFFLINE, never run in Unreal

Gary approved importing the PearlClam AS DELIVERED, including the thin mantle slit. The same tool now covers it.
Harness: 364 checks, 0 failed after the v2 update (`test_s3_props.py`, sections I1–I11). Tiers per claim: **[decl]** header,
**[meas]** read from a file here, **[inf]** not verified, with the reason.

**Live-run lessons folded in**

- IMPORT_TEX is now ONE texture per call for every prop (`check_mode`, `s3_props_ue.py:307`). It does not save and
  does not gate the size, because a texture read 32×32 in its own import call **[meas, 7 Oct live run]**. It writes
  `s3_props_tex_pending.json` and leaves exactly that package dirty.
- **VERIFY_TEX** (`run_verify_tex`, `:1859`) is a separate call. It needs the census to be exactly the pending
  package (`gate_census`, `:291`), checks size = PNG IHDR and the settings, then saves. Every other write mode
  refuses while a pending file exists. If the size still reads wrong, it saves nothing; retry VERIFY_TEX later.
- The tool refuses PIE, and every asset load is `unreal.load_asset`. In PIE, `EditorAssetLibrary.load_asset`
  returns None **[meas]**.

**Findings**

- **P1. Y flip.** The FBX is Blender Z-up in metres×100 with `Lcl Rotation (-90,0,0)` on every part, the same
  layout as the millstone **[meas, FBX parse]**. The expected UE frame is (x, −y, z) **[inf until IMPORT_MESH]**.
  - Bounds can detect a missing flip only on the LID: y [−2.0, 96.45] flipped vs [−96.45, 2.0] unflipped. Bottom,
    mantle and pearl are within 0.15 cm of symmetric in Y (harness I3 marks them UNDETECTABLE).
  - A vertex-centroid gate covers the rest (`clam_centroid_check`, `:819`). The bottom/lid/mantle centroids sit
    about 1.1 cm off-axis in X, so an X mirror is caught (`X_MIRRORED`). The bottom's −1.69 cm Y offset catches a
    missing Y flip.
  - The centroid is a strided sample of about 20k vertices of `get_static_mesh_description(0)` **[inf on a fresh
    Nanite import]**. `"centroid_gate": false` in the args skips it and is recorded.
- **P2. Lid opening sign.** UE roll r maps local +Y to (0, cos r, −sin r) (`rot_matrix`; harness I5 asserts this).
  After the flip the lid reaches +Y, so **opening = lid relative Roll −80°** (`lid_open_roll`, `:887`). The front
  tip rises about 80 cm at mid-height at any root yaw, and +80 drops it (− control). If the import came in
  unflipped, the sign follows the measured lid bounds. **[inf until seen]**
- **P3. Reveal must go on all four actors.** Actor.h:1917-1922 **[decl]** says SetActorHiddenInGame hides "the
  actor and all its components". Nothing propagates to attached actors **[inf from that wording]**.
  - CLAM_APPLY therefore spawns all four hidden in game, each with its own copy of the stone's LS_S3_HangarRise
    reveal section (4 new bindings).
  - `reveal_targets: "root"` is available but warns.
  - `reveal_range_s` / `reveal_completion_mode` override the copied section for the 31 s question. The override
    refuses a range that cuts the keys.
- **P4. Camera yaw.** Read from an offline dump of today's LS_DevScene_03 (`S3Diag/ds03_now_sem.json`, 17:44)
  **[meas offline]**:
  - The root cut at B05 (2880–3000) binds **"Cine Camera Actor 3"**, which has no transform track.
  - The cut at B06 (3000–3480) binds **"Cine Camera Actor 4"**, which is KEYED, moving (14072.6, 160990.6) →
    (14866.2, 160994.0), yaw −0.9 → −43.7.
  - The shot cameras were renamed since 1 Oct. Actor 3's template pose cannot be read offline.
  - Using Actor 3's 1 Oct pose (x 14122, on the axis), B05 + B06 give yaw ≈ 26° with B05 63° off the opening
    direction. That passes the 70° gate, but it is a compromise. **CLAM_DRY reads the real poses**: spawnable
    template root transform, or evaluated keys at the cut's start, middle and last frame (`_clam_cameras`,
    `:2220`). It refuses a beat covered by a nested sequence with its own cut track. If the yaw it reports is not
    what Directing wants, pass `apply_clam.yaw_deg`. Without cameras and without a yaw, the tool refuses.
- **P5. Seat.** The clam rests on the highest stone point under its footprint. That is 128.97 cm above the stone
  base: max of the radial rings within the 32.4 cm half-diagonal of the 43.1 × 48.3 footprint
  (`s3_millstone_fbx_measure.json`) **[meas offline]**.
  - The footprint centre (−0.4, −3.4 Blender → −0.4, +3.4 UE) is placed on the stone axis at any yaw (harness I6).
  - Root z = stone z (−7.0) + 128.97 − `sink_cm` (0). Expect up to about 1 cm float off-axis.
- **P6. Stand-ins.** `source_Anim` (skeletal) and `Clam_with_Pearl_Clam_with_Pearl_0` are hidden on EVERY primitive
  component (visible off, hidden in game on). Per-component flags are recorded and restored exactly. The actor flag
  is untouched, because the LS_S3_HangarRise reveal drives it. Their LS_Clams keys are not touched.
  **[inf]** that component flags beat the reveal track (same premise as the pedestal; check in PIE).

**What the tool does**

| Mode | What it covers |
|---|---|
| IMPORT_MESH `part` | Bottom, Lid, Mantle or Pearl (`run_import_clam_part`, `:1901`): vertex colours REPLACE (read back), slot names = manifest, bounds and centroid gates, `has_vertex_colors` required on the mantle, census then save |
| IMPORT_TEX + VERIFY_TEX | one texture each: Shell BaseColor 8192 (coral, sha256 recorded at import), Shell N/Roughness and Mantle × 3 at 4096 |
| BUILD_MAT `material` | one MI per call (`run_build_clam_mat`, `:2087`) |

The BUILD_MAT materials:

| Material | Built on | Settings |
|---|---|---|
| Shell | M_S3Prop | the existing master |
| Mantle | M_S3PropBreathe (create-only) | M_S3Prop graph + WPO Z = BreathAmp·VC.R·(0.5−0.5cos 2πt/BreathPeriod); Amp 0 (off), Period 5; MaxWPO 5 cm (Material.h:1214-1220 **[decl]**, which also clamps per axis) |
| ~~Interior~~ | RETIRED in v2 (see 5b) | |
| Pearl | PearlClam/M_PearlClam_Pearl (create-only) | DefaultLit; base (0.86, 0.83, 0.78); Fresnel(exp 3) lerps WarmTint→CoolTint × base by TintAmount 0.6; Roughness 0.18; Specular 0.55; Glow emissive (0); the same breathing WPO with R = 1 so the pearl rides the flesh |

There are no clear-coat pins. Gary sets BreathAmp on BOTH the mantle and the pearl MIs, and they share `Time`.

**CLAM_APPLY** (`run_clam_apply`, `:2390`):
1. The record is written first.
2. Backup to `Backups/PreS3PearlClam-<run>/`: the umap, LS_S3_HangarRise and the record.
3. Spawns "S3 PearlClam" (Bottom, MOVABLE). Lid, Mantle and Pearl are attached KEEP_WORLD at the manifest relative
   transforms:
   - Lid (0, −47.86, 30.02);
   - Mantle (0, 0, 0);
   - Pearl (0, 0, 35.64).
4. Read back:
   - relative transforms within 0.05 cm;
   - the lid's world origin = root × hinge within 1 cm (`HINGE_PIVOT`);
   - every material slot.
5. Adds the 4 reveals and hides the stand-ins.
6. Saves with the census exactly {LS_S3_HangarRise, map}, then reads back again. The marker is `S3CLAM_APPLY_OK`.

The lid is NOT keyed. Its relative Roll is the hinge, so Sequencer keys Rotation.X (open = −80, recorded in
`plan.lid`).

**CLAM_REVERT:**
- Refuses on drift. So if the lid has been keyed and the level saved with a non-zero roll, REVERT refuses; zero the
  roll first.
- Restores the stand-in flags.
- Removes the 4 bindings by GUID.
- Destroys the children, then the root.
- Saves and reads back. The marker is `S3CLAM_REVERT_OK`.

**Not covered by the harness [inf]:**
- the editor calls themselves (only the IMPORT_TEX/VERIFY_TEX split is exercised against a fake editor, I9b);
- `has_vertex_colors` on a Nanite mesh;
- `evaluate_keys` / `get_object_template` on today's renamed cameras;
- `attach_to_actor`;
- WPO on Nanite (manifest risk note);
- the Fresnel / VertexColor / Time pin names (`""` and `"R"`).

### 5b. PearlClam v2 (manifest 7 Oct 18:16): what changed

- **Slots.**
  - Bottom = [M_PearlClam_Shell, M_PearlClam_InteriorBottom].
  - Lid = [M_PearlClam_Shell, M_PearlClam_InteriorLid].
  - Mantle and Pearl are unchanged.
  - The table, the manifest `slots`, and `validation_reexport` agree **[meas]**.
  - IMPORT_MESH refuses any other slot list. CLAM_DRY/APPLY refuse a live mesh whose slots differ (harness I11:
    v1 names, swapped order and the wrong part's interior are each refused).
  - The untextured interior master (M_S3PropSolid) and its blush values are removed.
- **Geometry.** The re-exported Bottom/Lid have the same vertex count, bounds and centroids as v1 **[meas, FBX
  parse]**. So the Y-flip, centroid and assembly gates are unchanged.
- **Normals come from the FBX.**
  - The FBX carries per-corner normals (`LayerElementNormal`, ByPolygonVertex) on Bottom and Lid **[meas]**.
  - The Interchange option is `common_meshes_properties.recompute_normals = False`
    (InterchangeGenericAssetsPipelineSharedSettings.h:125-127: "normals in the imported mesh are ignored and
    recomputed" when true) **[decl]**. Tangents are rebuilt: `recompute_tangents = True`, `use_mikk_t_space = True`
    (:129-135), matching Blender's MikkTSpace bake. **[inf]** that Interchange keeps split normals exactly.
  - The millstone import already set `recompute_normals = False`; its pipeline is unchanged (harness asserts).
  - The settings are a pure spec (`pipeline_wanted`, `pipeline_problems`) and are read back.
  - After import, `StaticMeshEditorSubsystem.get_lod_build_settings(mesh, 0).recompute_normals` must be False
    (StaticMeshEditorSubsystem.h:80-81; EngineTypes.h:2948-2956 **[decl]**). The out-param-as-return is
    **[inf]**. If it is unreadable, the import refuses unless `"allow_unreadable_normals": true` (then the pipeline
    read-back is the only evidence).
- **NEW FINDING: the v2 Bottom/Lid FBX carry an undeclared vertex-colour layer "LipGrad"** (R 0.69–0.97, G
  0.12–0.93; a bake leftover) **[meas]**. The manifest does not list it.
  - These parts now import with `vertex_color_import_option = IVCIO_IGNORE` (header :43: "Ignore vertex colors from
    the translated source") **[decl]**. Only the Mantle uses REPLACE.
  - No material reads vertex colour on the shell/interior, so this only avoids storing dead data.
  - If the Blender side meant LipGrad to be used, say so and flip `clam_vc_option`.
- **Textures.**
  - InteriorBottom and InteriorLid each have BaseColor 8192 (sRGB), N 8192 (DirectX) and Roughness 4096 (linear)
    **[meas IHDR]**.
  - `ALLOW_8K` (`s3_props_ue.py:182`) is the only route above 4096: millstone BaseColor, Shell BaseColor, and the
    two interiors' BaseColor and N. Any other 8K is refused `TEX_8K_NOT_ALLOWED` (− controls on Roughness and
    Shell N).
  - One texture per call as before. The memory note on bulk imports (ue58-bulk-import-oom-crash) is honoured by one
    8K per call, with GC after VERIFY_TEX.
  - Shell BaseColor is the final crimson grade, overwritten in place. IMPORT_TEX records the sha256 of whatever is on
    disk.
- **Interior MIs** MI_PearlClam_InteriorBottom / InteriorLid are on the shared textured **M_S3Prop**. Roughness comes
  from the map (multiplier 1, override −1 = off): porcelain 0.20, lip 0.40. The interior faces share UV0 with the
  shell in their own 0–1 islands (manifest).

**Run order v2 (one MCP call each, same request file; grep the marker WITH the run id):**

0. Offline: `python Saved/CodexConductor/S3Millstone/test_s3_props.py` → `TOTAL 364 FAILED 0`.
1. CLAM_DRY `{"mode":"CLAM_DRY","run":"<id>"}` → `S3CLAM_DRY_OK`. Read the camera poses and the yaw. It refuses
   ASSETS_MISSING until step 6.
2. IMPORT_MESH, `"confirm":"IMPORT_MESH S3PROPS","prop":"PearlClam"`, with `"part"` = Lid, then Bottom, then Mantle,
   then Pearl (4 calls) → `S3PROPS_IMPORT_MESH_OK`. Check the record's `normals.recompute_normals = false` on
   Bottom/Lid.
3. Textures: IMPORT_TEX → `S3PROPS_IMPORT_TEX_PENDING`, then VERIFY_TEX → `S3PROPS_VERIFY_TEX_OK`, one pair per
   texture (`"textures":[<role>]`, `"tex_set":<set>`). 12 pairs in this order:
   - Shell: BaseColor (8K), N, Roughness;
   - InteriorBottom: BaseColor (8K), N (8K), Roughness;
   - InteriorLid: BaseColor (8K), N (8K), Roughness;
   - Mantle: BaseColor, N, Roughness.

   If VERIFY_TEX fails on size, nothing is saved; repeat VERIFY_TEX. If an MCP call returns 10054, check the log for a
   crash before retrying.
4. BUILD_MAT `"prop":"PearlClam"`, `"material"` = Shell, then InteriorBottom, then InteriorLid (all three on
   M_S3Prop), then Mantle (creates M_S3PropBreathe), then Pearl (creates M_PearlClam_Pearl). That is 5 calls. After
   each, wait about 20 s and grep "Failed to compile".
5. (No interior-solid step: retired.)
6. CLAM_DRY again → would_apply. Get the yaw approved by Directing/Gary, or set `"apply_clam":{"yaw_deg":<deg>}`.
7. CLAM_APPLY `"confirm":"CLAM_APPLY S3PROPS"` → `S3CLAM_APPLY_OK`. Then:
   - PIE past the landing: the clam appears with the stone, and the stand-ins are unseen;
   - in Sequencer, check lid Roll −80 by eye (do not save);
   - look at the interior shading close up (custom normals);
   - then queue SavedMasterMatchesShow + SceneCutBindingsResolve after a run-id marker.
8. Undo: CLAM_REVERT `"confirm":"CLAM_REVERT S3PROPS"` → `S3CLAM_REVERT_OK`. Assets stay. Zero any keyed lid roll
   before reverting.
