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
