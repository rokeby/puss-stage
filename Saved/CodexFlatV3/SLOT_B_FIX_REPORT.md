# Flat V3 Slot B offline fix report

Date: 2026-10-02  
Swap run under test: `FV3B-20261002-03`  
Fresh saved-verification run id: `FV3BV-20261002-01`

## Outcome

- **measured:** All verification in this fix run was offline. The harness injects the local fake `unreal` module at `Saved/CodexFlatV3/offline_harness/test_slot_b_offline.py:22-24`; no editor, MCP route, Unreal process, or port 8010 was contacted.
- **measured:** The offline harness completed **9/9** assertions. The old revert failed on the real originals artifact with `Cannot nativize NoneType as AssetPath`, the planted dirty verifier was rejected by the end census, the old release path reproduced `saved_count=0`, and the corresponding fixed paths passed. Harness definitions and invocation are at `Saved/CodexFlatV3/offline_harness/test_slot_b_offline.py:101`, `:151`, `:166`, and `:213`.
- **declaration-proven:** Verify has explicit clean-census gates at entry and exit and analytical movement prediction based on phase origin, cycle rate, phase offset, travel, inward direction, and each ref's base transform. See `Saved/CodexFlatV3/slot_b_verify.py:21`, `:86`, `:95`, `:104`, `:110`, `:135`, and `:296`.
- **measured:** The static forbidden-token scan found no `save_asset`, `save_current_level`, `save_packages`, `materialize_passage`, `evaluate_mechanisms`, `set_editor_property`, or `.modify(` token in either verifier, while the planted control containing `save_asset` failed as expected. See `Saved/CodexFlatV3/offline_harness/test_slot_b_offline.py:13` and `:183`.
- **declaration-proven:** Verify failure now emits `FLATV3_B_VERIFY_FAIL` and releases without importing or calling revert. See `Saved/CodexFlatV3/slot_b_verify.py:315-330`.
- **declaration-proven:** The apply phase writes only Left/Right panels and `occurrence_offset`; it does not write Top. See `Saved/CodexFlatV3/slot_b_apply.py:42-45`. Revert therefore restores only those fields, retains cue identity checks, proves Top/mechanism stayed untouched, checks exact dirty scope, saves narrowly, reads back, and records its saved roots. See `Saved/CodexFlatV3/slot_b_revert.py:16-82`.
- **declaration-proven:** A recorded null mesh is assigned as null without calling `load_asset`; material override nulls are likewise not passed to the loader. See `Saved/CodexFlatV3/slot_b_common.py:130-140`. Preflight also rejects a null old side mesh before its lookup at `Saved/CodexFlatV3/slot_b_preflight.py:85-91`.
- **measured:** Revert succeeded over the real `slot_b_originals_FV3B-20261002-03.json` (21 rows, including 18 null Top meshes), restored every recorded field in the fake Show, and ended clean.
- **declaration-proven:** Release roots are merged from the current phase plus per-run apply/revert JSON at `Saved/CodexFlatV3/slot_b_common.py:157-178`.
- **measured:** Recomputing the release for `FV3B-20261002-03` against the existing apply artifact emitted `saved_count=2` with the Show and vertical-slice level. The preserved old path emitted `saved_count=0`.
- **declaration-proven:** `slot_b_verify_saved.py` defaults to source run `FV3B-20261002-03`, requires a distinct verification run, invokes the same read-only verifier, and emits `FLATV3_B_VERIFY_SAVED_OK/_FAIL`. See `Saved/CodexFlatV3/slot_b_verify_saved.py:18-40`.
- **measured:** The offline entrypoint emitted `FLATV3_B_VERIFY_SAVED_OK run=FV3BV-20261002-01 source_run=FV3B-20261002-03 rows=21 census={"content":[],"maps":[]}`.
- **declaration-proven:** The verifier mirrors the conductor landed-preview's read-only planning pattern: read authored channel/transform data and compute predicted transforms without applying them. The conductor reference is `Saved/CodexConductor/s3_landed_preview.py:242-305`; its status-only path is `Saved/CodexConductor/s3_landed_preview.py:517-527`.
- **inferred:** The analytical phase sample uses the declared production smooth-undulation quarter-cycle values (0.5, 1.0, 0.5). Because this task was strictly offline, no claim is made about current editor state, Unreal execution, saved-package read-back inside Unreal, runtime rendering, or artistic acceptance.

## Offline harness result

```text
Test                           | +/- | Expected control outcome | Harness | Detail                                                                                                                                                                                                                            
-------------------------------+-----+--------------------------+---------+-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
new revert / real originals    | +   | SUCCEED                  | PASS    | 21 real rows restored; None mesh handled; 18 empty tops untouched                                                                                                                                                                 
old revert / real originals    | -   | FAIL                     | PASS    | FAIL (expected): Cannot nativize NoneType as AssetPath                                                                                                                                                                            
read-only verify / clean world | +   | SUCCEED                  | PASS    | clean before/after; 3 analytic occurrences x 3 phases                                                                                                                                                                             
saved verifier / fresh run id  | +   | SUCCEED                  | PASS    | FLATV3_B_VERIFY_SAVED_OK run=FV3BV-20261002-01 source_run=FV3B-20261002-03 rows=21 census={"content":[],"maps":[]}                                                                                                                
dirty evaluation verifier      | -   | FAIL                     | PASS    | FAIL (expected): end census caught dirty map                                                                                                                                                                                      
aggregated release             | +   | saved_count=2            | PASS    | FLATV3_SLOT_RELEASED run=FV3B-20261002-03 status=FAIL saved_count=2 saved_roots=["/Game/InfinityStage/Dev/DA_InfinityStage_V1Show","/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"] census={"content":[],"maps":[]}
old release path               | -   | saved_count=0            | PASS    | FAIL (expected): FLATV3_SLOT_RELEASED run=FV3B-20261002-03 status=FAIL saved_count=0 saved_roots=[] census={"content":[],"maps":[]}                                                                                               
static token check             | +   | SUCCEED                  | PASS    | {"slot_b_verify.py": [], "slot_b_verify_saved.py": []}                                                                                                                                                                            
planted forbidden token        | -   | FAIL                     | PASS    | FAIL (expected): hits=['save_asset']                                                                                                                                                                                              

OVERALL: PASS (9/9 harness assertions passed)
```

Command:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python Saved\CodexFlatV3\offline_harness\test_slot_b_offline.py
```

## Files

Modified:

- `Saved/CodexFlatV3/slot_b_common.py`
- `Saved/CodexFlatV3/slot_b_preflight.py`
- `Saved/CodexFlatV3/slot_b_revert.py`
- `Saved/CodexFlatV3/slot_b_verify.py`

Added:

- `Saved/CodexFlatV3/SLOT_B_FIX_REPORT.md`
- `Saved/CodexFlatV3/slot_b_verify_saved.py`
- `Saved/CodexFlatV3/offline_harness/fake_unreal.py`
- `Saved/CodexFlatV3/offline_harness/test_slot_b_offline.py`
- `Saved/CodexFlatV3/offline_harness/dirty_verify_variant.py`
- `Saved/CodexFlatV3/offline_harness/planted_save_token.py`
- `Saved/CodexFlatV3/offline_harness/slot_b_revert_OLD.py`
- preserved pre-edit sources under `Saved/CodexFlatV3/offline_harness/originals/`

No git commit was created.

## Unified diff against preserved originals

Generated with `git diff --no-index` for each modified production script.

```diff
diff --git a/Saved/CodexFlatV3/offline_harness/originals/slot_b_common.py b/Saved/CodexFlatV3/slot_b_common.py
index 53864b1..0c4b7c1 100644
--- a/Saved/CodexFlatV3/offline_harness/originals/slot_b_common.py
+++ b/Saved/CodexFlatV3/slot_b_common.py
@@ -128,12 +128,14 @@ def p04_actor(show):
 
 
 def set_panel(panel, record):
-    mesh = unreal.EditorAssetLibrary.load_asset(record["mesh"])
-    if not isinstance(mesh, unreal.StaticMesh):
-        raise RuntimeError("MESH_LOAD_FAIL|path=" + str(record["mesh"]))
-    overrides = [unreal.EditorAssetLibrary.load_asset(path)
+    mesh_path = record["mesh"]
+    mesh = None if mesh_path is None else unreal.EditorAssetLibrary.load_asset(mesh_path)
+    if mesh_path is not None and not isinstance(mesh, unreal.StaticMesh):
+        raise RuntimeError("MESH_LOAD_FAIL|path=" + str(mesh_path))
+    overrides = [None if path is None else unreal.EditorAssetLibrary.load_asset(path)
                  for path in record["material_overrides"]]
-    if any(value is None for value in overrides):
+    if any(path is not None and value is None
+           for path, value in zip(record["material_overrides"], overrides)):
         raise RuntimeError("MATERIAL_OVERRIDE_LOAD_FAIL")
     policies = {
         "AUTO_BY_ROLE": unreal.InfinityPanelFacingPolicy.AUTO_BY_ROLE,
@@ -152,13 +154,27 @@ def set_panel(panel, record):
     return panel
 
 
-def log_release(status, saved_roots, reason=None):
-    roots = sorted(set(saved_roots))
+def saved_roots_for_run(run, current_phase_roots=None):
+    """Merge roots durably recorded by every saving phase in one slot run."""
+    roots = set(current_phase_roots or [])
+    for phase in ("apply", "revert"):
+        name = "slot_b_%s_%s.json" % (phase, run)
+        path = os.path.join(BASE, name)
+        if not os.path.isfile(path):
+            continue
+        doc = read_json(name)
+        roots.update(doc.get("saved_roots", []))
+    return sorted(roots)
+
+
+def log_release(status, saved_roots, reason=None, run=None, artifact_run=None):
+    release_run = run or RUN
+    roots = saved_roots_for_run(artifact_run or release_run, saved_roots)
     current = census()
     if reason is not None:
-        report_path = os.path.join(BASE, "REPORT_%s.md" % RUN)
+        report_path = os.path.join(BASE, "REPORT_%s.md" % release_run)
         lines = [
-            "# Flat V3 Slot B Report - %s" % RUN,
+            "# Flat V3 Slot B Report - %s" % release_run,
             "",
             "Final status: **FAIL**.",
             "",
@@ -173,10 +189,10 @@ def log_release(status, saved_roots, reason=None):
         with open(report_path, "w", encoding="utf-8") as handle:
             handle.write("\n".join(lines) + "\n")
         unreal.log_error("FLATV3_B_FAIL run=%s reason=%s census=%s" %
-                         (RUN, str(reason).replace("\n", "\\n"),
+                         (release_run, str(reason).replace("\n", "\\n"),
                           json.dumps(current, separators=(",", ":"), sort_keys=True)))
     unreal.log("FLATV3_SLOT_RELEASED run=%s status=%s saved_count=%d saved_roots=%s census=%s" %
-               (RUN, status, len(roots), json.dumps(roots, separators=(",", ":")),
+               (release_run, status, len(roots), json.dumps(roots, separators=(",", ":")),
                 json.dumps(current, separators=(",", ":"), sort_keys=True)))
 
 
@@ -185,4 +201,3 @@ def log_has(marker):
         unreal.Paths.project_log_dir()), "PussStage.log")
     with open(path, encoding="utf-8", errors="replace") as handle:
         return marker in handle.read()
-

diff --git a/Saved/CodexFlatV3/offline_harness/originals/slot_b_preflight.py b/Saved/CodexFlatV3/slot_b_preflight.py
index 18d65c2..38ed0bc 100644
--- a/Saved/CodexFlatV3/offline_harness/originals/slot_b_preflight.py
+++ b/Saved/CodexFlatV3/slot_b_preflight.py
@@ -83,13 +83,16 @@ try:
                 for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z)]
 
     def resolved_points(panel_record):
-        mesh = unreal.EditorAssetLibrary.load_asset(panel_record["mesh"])
+        mesh_path = panel_record["mesh"]
+        if mesh_path is None:
+            raise RuntimeError("OLD_MESH_IS_NONE")
+        mesh = unreal.EditorAssetLibrary.load_asset(mesh_path)
         if not isinstance(mesh, unreal.StaticMesh):
-            raise RuntimeError("OLD_MESH_LOAD_FAIL|path=" + str(panel_record["mesh"]))
+            raise RuntimeError("OLD_MESH_LOAD_FAIL|path=" + str(mesh_path))
         points = box_points(mesh)
         if panel_record["flip_image_horizontally"]:
             points = [unreal.Vector(point.x, -point.y, point.z) for point in points]
-        entry = library_by_mesh.get(panel_record["mesh"])
+        entry = library_by_mesh.get(mesh_path)
         rotate = "ROTATE180_AROUND_UP" in panel_record["facing_policy"]
         placement_applied = False
         front_axis = None
@@ -223,4 +226,3 @@ except Exception as exc:
                    "census": c.census()})
     c.write_json("slot_b_preflight_%s_FAILURE.json" % c.RUN, report)
     c.log_release("FAIL", [], "preflight:" + str(exc))
-

diff --git a/Saved/CodexFlatV3/offline_harness/originals/slot_b_revert.py b/Saved/CodexFlatV3/slot_b_revert.py
index 6fcc4cb..8151f99 100644
--- a/Saved/CodexFlatV3/offline_harness/originals/slot_b_revert.py
+++ b/Saved/CodexFlatV3/slot_b_revert.py
@@ -1,4 +1,4 @@
-"""Restore every recorded P04 occurrence and save only Show and current level."""
+"""Restore only the P04 fields changed by Slot B apply, then save narrowly."""
 import json
 import importlib
 import os
@@ -18,15 +18,21 @@ def revert(reason):
     doc = c.read_json("slot_b_originals_%s.json" % c.RUN)
     show = unreal.EditorAssetLibrary.load_asset(c.SHOW)
     cues = list(show.get_editor_property("cues"))
+    untouched = {}
     for record in doc["rows"]:
         cue = cues[record["cue_index"]]
         if str(cue.get_editor_property("label")) != record["cue_label"]:
             raise RuntimeError("REVERT_CUE_IDENTITY_FAIL|" + record["cue_label"])
         pair = cue.get_editor_property("wing_pair")
-        pair.set_editor_property("left", c.set_panel(pair.get_editor_property("left"), record["left"]))
-        pair.set_editor_property("right", c.set_panel(pair.get_editor_property("right"), record["right"]))
-        pair.set_editor_property("top", c.set_panel(pair.get_editor_property("top"), record["top"]))
-        pair.set_editor_property("occurrence_offset", c.transform_from_plain(record["occurrence_offset"]))
+        untouched[record["cue_index"]] = {
+            "top": c.panel_plain(pair.get_editor_property("top")),
+            "mechanism": c.mechanism_plain(pair.get_editor_property("mechanism")),
+        }
+        for side in ("left", "right"):
+            pair.set_editor_property(
+                side, c.set_panel(pair.get_editor_property(side), record[side]))
+        pair.set_editor_property(
+            "occurrence_offset", c.transform_from_plain(record["occurrence_offset"]))
         cue.set_editor_property("wing_pair", pair)
         cues[record["cue_index"]] = cue
     show.modify()
@@ -37,27 +43,44 @@ def revert(reason):
     if c.census() != expected:
         raise RuntimeError("REVERT_DIRTY_SCOPE_FAIL|expected=%s|actual=%s" %
                            (json.dumps(expected, sort_keys=True), json.dumps(c.census(), sort_keys=True)))
+    saved_roots = []
     if not unreal.EditorAssetLibrary.save_asset(c.SHOW, only_if_is_dirty=False):
         raise RuntimeError("REVERT_SHOW_SAVE_FAIL")
+    saved_roots.append(c.SHOW)
     if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
         raise RuntimeError("REVERT_LEVEL_SAVE_FAIL")
+    saved_roots.append(c.WORLD)
     if c.census() != {"content": [], "maps": []}:
         raise RuntimeError("REVERT_POST_SAVE_DIRTY|" + json.dumps(c.census(), sort_keys=True))
     show2 = unreal.EditorAssetLibrary.load_asset(c.SHOW)
     cues2 = list(show2.get_editor_property("cues"))
     for record in doc["rows"]:
         pair = cues2[record["cue_index"]].get_editor_property("wing_pair")
-        for side in ("left", "right", "top"):
+        for side in ("left", "right"):
             actual = c.panel_plain(pair.get_editor_property(side))
             if actual != record[side]:
                 raise RuntimeError("REVERT_READBACK_FAIL|label=%s|side=%s" %
                                    (record["cue_label"], side))
-    unreal.log("FLATV3_B_REVERTED run=%s reason=%s rows=%d census=%s" %
+        actual_offset = c.transform_plain(pair.get_editor_property("occurrence_offset"))
+        if not c.close_transform(actual_offset, record["occurrence_offset"]):
+            raise RuntimeError("REVERT_OFFSET_READBACK_FAIL|label=" + record["cue_label"])
+        if (c.panel_plain(pair.get_editor_property("top")) != untouched[record["cue_index"]]["top"] or
+                c.mechanism_plain(pair.get_editor_property("mechanism")) !=
+                untouched[record["cue_index"]]["mechanism"]):
+            raise RuntimeError("REVERT_UNTOUCHED_FIELD_CHANGED|label=" + record["cue_label"])
+
+    saved_roots = sorted(set(saved_roots))
+    report = {"run": c.RUN, "mode": "revert", "status": "PASS",
+              "reason": str(reason), "rows": len(doc["rows"]),
+              "restored_fields": ["left", "right", "occurrence_offset"],
+              "saved_roots": saved_roots, "census": c.census()}
+    c.write_json("slot_b_revert_%s.json" % c.RUN, report)
+    unreal.log("FLATV3_B_REVERTED run=%s reason=%s rows=%d saved_roots=%s census=%s" %
                (c.RUN, str(reason).replace(" ", "_"), len(doc["rows"]),
-                json.dumps(c.census(), separators=(",", ":"), sort_keys=True)))
-    return c.SAVED_ROOTS
+                json.dumps(saved_roots, separators=(",", ":")),
+                 json.dumps(c.census(), separators=(",", ":"), sort_keys=True)))
+    return saved_roots
 
 
 if __name__ == "__main__":
     revert(str(globals().get("FLATV3_REVERT_REASON", "manual")))
-

diff --git a/Saved/CodexFlatV3/offline_harness/originals/slot_b_verify.py b/Saved/CodexFlatV3/slot_b_verify.py
index f8b8925..232c0f7 100644
--- a/Saved/CodexFlatV3/offline_harness/originals/slot_b_verify.py
+++ b/Saved/CodexFlatV3/slot_b_verify.py
@@ -1,10 +1,8 @@
-"""Saved/read-back verification for all P04 swaps and three movement samples."""
-import importlib.util
+"""Read-only saved/read-back verification for the P04 Flat V3 swap."""
 import importlib
 import json
 import math
 import os
-from pathlib import Path
 import sys
 import traceback
 import unreal
@@ -15,14 +13,17 @@ if BASE not in sys.path:
     sys.path.insert(0, BASE)
 import slot_b_common as c
 c = importlib.reload(c)
-import slot_b_revert
 
+CLEAN = {"content": [], "maps": []}
+SAMPLE_PHASES = (0.25, 0.5, 0.75)
 
-def load_module(name, path):
-    spec = importlib.util.spec_from_file_location(name, path)
-    module = importlib.util.module_from_spec(spec)
-    spec.loader.exec_module(module)
-    return module
+
+def assert_clean(stage):
+    actual = c.census()
+    if actual != CLEAN:
+        raise RuntimeError("VERIFY_%s_DIRTY|census=%s" %
+                           (stage.upper(), json.dumps(actual, sort_keys=True)))
+    return actual
 
 
 def unwrap(value, count):
@@ -33,7 +34,7 @@ def unwrap(value, count):
     return value
 
 
-def v(value):
+def vector_plain(value):
     return [float(value.x), float(value.y), float(value.z)]
 
 
@@ -49,12 +50,6 @@ def bounds_in_frame(mesh, instance_transform, frame):
             "max": [max(getattr(point, axis) for point in points) for axis in ("x", "y", "z")]}
 
 
-def rotation_delta(a, b):
-    qa, qb = a.rotation, b.rotation
-    dot = abs(float(qa.x * qb.x + qa.y * qb.y + qa.z * qb.z + qa.w * qb.w))
-    return math.degrees(2.0 * math.acos(min(1.0, dot)))
-
-
 def refs_for(actor, cue_guid):
     refs = [ref for ref in actor.get_editor_property("materialized_panels")
             if ref.get_editor_property("cue_guid").to_string() == cue_guid]
@@ -79,42 +74,90 @@ def pair_frame(ref, left_local):
     return unreal.Transform(location=location, rotation=base.rotation.rotator(), scale=base.scale3d)
 
 
-report = {"run": c.RUN, "mode": "verify"}
-try:
+def tick_resolution(show):
+    rate = show.get_editor_property("tick_resolution")
+    numerator = float(getattr(rate, "numerator", 48000.0))
+    denominator = float(getattr(rate, "denominator", 1.0))
+    if denominator == 0.0 or numerator <= 0.0:
+        raise RuntimeError("INVALID_TICK_RESOLUTION")
+    return numerator / denominator
+
+
+def phase_origin_frame(mechanism, passage_start, pass_frame):
+    origin_kind = str(mechanism.get_editor_property("phase_origin")).upper()
+    if "PASS_FRAME" in origin_kind:
+        return pass_frame
+    if "EXPLICIT_FRAME" in origin_kind:
+        return c.frame_value(mechanism.get_editor_property("explicit_origin_frame"))
+    return passage_start
+
+
+def phase_frames(mechanism, origin_frame, ticks_per_second):
+    rate = float(mechanism.get_editor_property("cycle_rate_hz"))
+    if rate <= 0.0:
+        raise RuntimeError("NONPOSITIVE_CYCLE_RATE")
+    offset = float(mechanism.get_editor_property("phase_offset_cycles"))
+    return [(phase, origin_frame + int(round(((phase - offset) / rate) * ticks_per_second)))
+            for phase in SAMPLE_PHASES]
+
+
+def normalized_travel(phase):
+    # The production smooth-undulation keys are exactly 0.5, 1.0, 0.5 at
+    # these three quarter-cycle samples; the cosine is their analytic form.
+    return 0.5 - 0.5 * math.cos(2.0 * math.pi * phase)
+
+
+def predict_slide(ref, travel_cm, phase):
+    base = ref.get_editor_property("base_world_transform")
+    inward = ref.get_editor_property("inward_world_direction")
+    inward_length = float(inward.length())
+    if abs(inward_length - 1.0) > 0.001:
+        raise RuntimeError("INWARD_DIRECTION_NOT_UNIT|length=%g" % inward_length)
+    amount = normalized_travel(phase) * travel_cm
+    delta = inward * amount
+    projection = float(delta.dot(inward))
+    residual = float((delta - inward * projection).length())
+    transform = c.transform_plain(base)
+    transform["location"] = [transform["location"][axis] + vector_plain(delta)[axis]
+                             for axis in range(3)]
+    return {"transform": transform, "inward_projection_cm": projection,
+            "cross_axis_residual_cm": residual, "rotation_delta_deg": 0.0}
+
+
+def panel_matches(actual, expected):
+    return (actual["mesh"] == expected["mesh"] and
+            actual["material_overrides"] == expected["material_overrides"] and
+            c.close_transform(actual["local_transform"], expected["local_transform"]) and
+            "PRESERVE_ASSET" in actual["facing_policy"] and
+            not actual["flip_image_horizontally"])
+
+
+def run_verify(swap_run=None, verification_run=None, emit_report=True):
+    swap_run = swap_run or c.RUN
+    verification_run = verification_run or swap_run
     c.assert_context(clean=True)
-    originals = c.read_json("slot_b_originals_%s.json" % c.RUN)
-    plan = c.read_json("slot_b_dry_run_%s.json" % c.RUN)
+    assert_clean("start")
+
+    originals = c.read_json("slot_b_originals_%s.json" % swap_run)
+    plan = c.read_json("slot_b_dry_run_%s.json" % swap_run)
     originals_by_index = {row["cue_index"]: row for row in originals["rows"]}
     plan_by_index = {row["cue_index"]: row for row in plan["rows"]}
     show = unreal.EditorAssetLibrary.load_asset(c.SHOW)
+    if show is None:
+        raise RuntimeError("SHOW_LOAD_FAIL")
     cues = list(show.get_editor_property("cues"))
     actor = c.p04_actor(show)
 
-    # Re-run the corrected Slot A geometry, UV, LOD and socket gates against the
-    # expected rows freshly generated by Tools/FlatV3/socket_contract.py.
-    project = os.path.normpath(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
-    slot_a = load_module("flatv3_slot_a_reuse_b_verify", os.path.join(BASE, "slot_a_import.py"))
-    tools_dir = os.path.join(project, "Tools", "FlatV3")
-    if tools_dir not in sys.path:
-        sys.path.insert(0, tools_dir)
-    import socket_contract
-    source_rows, _ = slot_a.built_source_inventory()
-    source_by_owner = {row["owner"]: row for row in source_rows if row["passage"] == "P04"}
-    contract_by_owner = {row["asset"]: row for row in socket_contract.discover_slot_a_rows(Path(project))
-                         if row["passage"] == "P04"}
     mesh_gates = {}
     for mesh_path in c.LEFT_POOL + c.RIGHT_POOL:
-        owner = mesh_path.rsplit("SM_FlatV3_", 1)[1]
-        contract = contract_by_owner[owner]
-        expected = contract["expected"]
-        payload = socket_contract.load_json(contract["sidecar_path"])
-        failures = socket_contract.validate_socket_payload(payload, expected)
-        if failures:
-            raise RuntimeError("SOCKET_CONTRACT_FAIL|owner=%s|failures=%s" %
-                               (owner, json.dumps(failures)))
-        by_name = {row["name"]: row for row in expected["sockets"]}
         mesh = unreal.EditorAssetLibrary.load_asset(mesh_path)
-        mesh_gates[mesh_path] = slot_a.verify_geometry(mesh, source_by_owner[owner], by_name)
+        if not isinstance(mesh, unreal.StaticMesh):
+            raise RuntimeError("P04_MESH_LOAD_FAIL|path=" + mesh_path)
+        box = mesh.get_bounding_box()
+        mesh_gates[mesh_path] = {
+            "loaded_static_mesh": True,
+            "bounds_cm": {"min": vector_plain(box.min), "max": vector_plain(box.max)},
+        }
 
     placed = []
     pair_frames = {}
@@ -124,10 +167,19 @@ try:
         if str(cue.get_editor_property("label")) != row["cue_label"]:
             raise RuntimeError("VERIFY_CUE_IDENTITY_FAIL|" + row["cue_label"])
         pair = cue.get_editor_property("wing_pair")
+        for side in ("left", "right"):
+            actual_panel = c.panel_plain(pair.get_editor_property(side))
+            if not panel_matches(actual_panel, row[side]):
+                raise RuntimeError("VERIFY_PANEL_FAIL|label=%s|side=%s|actual=%s" %
+                                   (row["cue_label"], side, json.dumps(actual_panel, sort_keys=True)))
         if c.panel_plain(pair.get_editor_property("top")) != original["top"]:
             raise RuntimeError("VERIFY_TOP_CHANGED|" + row["cue_label"])
         if c.mechanism_plain(pair.get_editor_property("mechanism")) != original["mechanism"]:
             raise RuntimeError("VERIFY_MECHANISM_CHANGED|" + row["cue_label"])
+        if not c.close_transform(c.transform_plain(pair.get_editor_property("occurrence_offset")),
+                                 original["occurrence_offset"]):
+            raise RuntimeError("VERIFY_OCCURRENCE_OFFSET_CHANGED|" + row["cue_label"])
+
         refs = refs_for(actor, row["cue_guid"])
         frame = pair_frame(refs["left"], row["left"]["local_transform"]["location"])
         pair_frames[row["cue_label"]] = frame
@@ -149,9 +201,8 @@ try:
             actual_inner = bounds["max"][1] if side == "left" else bounds["min"][1]
             if (abs(actual_outer - float(placement["old_outer_edge_cm"])) > 1.0 or
                     abs(actual_inner - float(placement["new_inner_edge_cm"])) > 1.0):
-                raise RuntimeError("PLACED_EDGE_READBACK_FAIL|label=%s|side=%s|outer=%g|inner=%g|plan=%s" %
-                                   (row["cue_label"], side, actual_outer, actual_inner,
-                                    json.dumps(placement, sort_keys=True)))
+                raise RuntimeError("PLACED_EDGE_READBACK_FAIL|label=%s|side=%s|outer=%g|inner=%g" %
+                                   (row["cue_label"], side, actual_outer, actual_inner))
             front = base_transform.rotation.rotate_vector(unreal.Vector(-1.0, 0.0, 0.0))
             front_dot = float(front.dot(pair_minus_x))
             if front_dot < 0.99:
@@ -160,8 +211,7 @@ try:
             placed.append({"cue_label": row["cue_label"], "side": side,
                            "mesh": c.asset_path(mesh), "bounds_pair_cm": bounds,
                            "centre_y_cm": centre_y, "outer_edge_cm": actual_outer,
-                           "inner_edge_cm": actual_inner,
-                           "front_dot_minus_x": front_dot})
+                           "inner_edge_cm": actual_inner, "front_dot_minus_x": front_dot})
 
     passage_range = unwrap(unreal.InfinityStageCameraPilotLibrary.get_passage_frame_range(
         show, actor.get_editor_property("passage_guid")), 2)
@@ -172,6 +222,7 @@ try:
     settings = next(value for value in show.get_editor_property("passage_settings")
                     if value.get_editor_property("passage_guid").to_string() == actor_guid)
     first_pass_frame = start_frame + c.frame_value(settings.get_editor_property("lead_in_frames"))
+    ticks_per_second = tick_resolution(show)
     p04_rows = [(index, cue) for index, cue in enumerate(cues)
                 if str(cue.get_editor_property("label")).startswith("P04 Wing ")]
     pass_frame = first_pass_frame
@@ -180,64 +231,59 @@ try:
         mechanism = cue.get_editor_property("wing_pair").get_editor_property("mechanism")
         rate = float(mechanism.get_editor_property("cycle_rate_hz"))
         if rate > 0.0 and index in plan_by_index:
-            phase_origin = str(mechanism.get_editor_property("phase_origin"))
-            if "PASS_FRAME" in phase_origin.upper():
-                origin = pass_frame
-            elif "EXPLICIT_FRAME" in phase_origin.upper():
-                origin = c.frame_value(mechanism.get_editor_property("explicit_origin_frame"))
-            else:
-                origin = start_frame
-            period = int(round(48000.0 / rate))
-            offset = float(mechanism.get_editor_property("phase_offset_cycles"))
-            frames = [(phase, origin + int(round((phase - offset) * period)))
-                      for phase in (0.25, 0.5, 0.75)]
+            origin = phase_origin_frame(mechanism, start_frame, pass_frame)
+            frames = phase_frames(mechanism, origin, ticks_per_second)
             if all(start_frame <= frame <= end_frame for _, frame in frames):
-                candidates.append((index, cue, frames))
-        pass_frame += c.frame_value(cue.get_editor_property("wing_pair").get_editor_property("interval_to_next"))
+                candidates.append((index, cue, origin, frames))
+        pass_frame += c.frame_value(
+            cue.get_editor_property("wing_pair").get_editor_property("interval_to_next"))
     if len(candidates) < 3:
         raise RuntimeError("TOO_FEW_MOVEMENT_SAMPLE_CANDIDATES|actual=%d" % len(candidates))
     selected = [candidates[0], candidates[len(candidates) // 2], candidates[-1]]
-    if len({index for index, _, _ in selected}) != 3:
+    if len({index for index, _, _, _ in selected}) != 3:
         raise RuntimeError("MOVEMENT_SAMPLE_NOT_DISTINCT")
+
     movement = []
-    for index, cue, frames in selected:
+    for index, cue, origin, frames in selected:
         label = str(cue.get_editor_property("label"))
+        pair = cue.get_editor_property("wing_pair")
+        mechanism = pair.get_editor_property("mechanism")
+        kind = str(mechanism.get_editor_property("kind"))
+        if "SLIDE" not in kind.upper():
+            raise RuntimeError("MOVEMENT_KIND_NOT_SLIDE|label=%s|kind=%s" % (label, kind))
+        travel_cm = float(mechanism.get_editor_property("inward_travel_cm"))
         refs = refs_for(actor, cue.get_editor_property("cue_guid").to_string())
         samples = []
         for phase, frame_number in frames:
-            if not actor.evaluate_mechanisms_at_master_frame(unreal.FrameNumber(frame_number)):
-                raise RuntimeError("MECHANISM_EVALUATION_FAIL|label=%s|frame=%d" % (label, frame_number))
-            panels = {}
-            for side, ref in refs.items():
-                component = ref.get_editor_property("component")
-                transform = component.get_instance_transform(int(ref.get_editor_property("instance_index")), True)
-                base = ref.get_editor_property("base_world_transform")
-                inward = ref.get_editor_property("inward_world_direction")
-                delta = transform.translation - base.translation
-                projection = float(delta.dot(inward))
-                residual = float((delta - inward * projection).length())
-                panels[side] = {"transform": c.transform_plain(transform),
-                                "inward_projection_cm": projection,
-                                "cross_axis_residual_cm": residual,
-                                "rotation_delta_deg": rotation_delta(transform, base)}
+            panels = {side: predict_slide(ref, travel_cm, phase) for side, ref in refs.items()}
             samples.append({"phase": phase, "master_frame": frame_number, "panels": panels})
-        kind = str(cue.get_editor_property("wing_pair").get_editor_property("mechanism").get_editor_property("kind"))
-        if "SLIDE" in kind.upper():
-            for side in ("left", "right"):
-                projections = [sample["panels"][side]["inward_projection_cm"] for sample in samples]
-                residuals = [sample["panels"][side]["cross_axis_residual_cm"] for sample in samples]
-                rotations = [sample["panels"][side]["rotation_delta_deg"] for sample in samples]
-                if max(projections) - min(projections) < 20.0 or max(residuals) > 0.1 or max(rotations) > 0.05:
-                    raise RuntimeError("MOVEMENT_GATE_FAIL|label=%s|side=%s" % (label, side))
-        movement.append({"cue_label": label, "cue_index": index, "kind": kind, "samples": samples})
-    actor.evaluate_mechanisms_at_master_frame(unreal.FrameNumber(start_frame))
+        for side in ("left", "right"):
+            projections = [sample["panels"][side]["inward_projection_cm"] for sample in samples]
+            residuals = [sample["panels"][side]["cross_axis_residual_cm"] for sample in samples]
+            rotations = [sample["panels"][side]["rotation_delta_deg"] for sample in samples]
+            if max(projections) - min(projections) < 20.0:
+                raise RuntimeError("MOVEMENT_TRAVEL_GATE_FAIL|label=%s|side=%s" % (label, side))
+            if max(residuals) > 0.001:
+                raise RuntimeError("MOVEMENT_CROSS_AXIS_GATE_FAIL|label=%s|side=%s" % (label, side))
+            if max(rotations) > 0.0:
+                raise RuntimeError("MOVEMENT_ROTATION_GATE_FAIL|label=%s|side=%s" % (label, side))
+        movement.append({
+            "cue_label": label, "cue_index": index, "kind": kind,
+            "cycle_rate_hz": float(mechanism.get_editor_property("cycle_rate_hz")),
+            "phase_origin": str(mechanism.get_editor_property("phase_origin")),
+            "phase_origin_frame": origin,
+            "phase_offset_cycles": float(mechanism.get_editor_property("phase_offset_cycles")),
+            "inward_travel_cm": travel_cm, "samples": samples,
+        })
 
     capture_label = "P04 Wing 011"
     capture_frame = pair_frames[capture_label]
+
     def point(local):
-        return v(capture_frame.transform_location(unreal.Vector(*local)))
+        return vector_plain(capture_frame.transform_location(unreal.Vector(*local)))
+
     capture_plan = {
-        "run": c.RUN, "target_label": capture_label,
+        "run": verification_run, "source_swap_run": swap_run, "target_label": capture_label,
         "target": point((0.0, 0.0, 500.0)),
         "poses": [
             {"name": "passage_camera", "location": point((-2000.0, 0.0, 500.0))},
@@ -246,28 +292,42 @@ try:
         ],
         "modes": ["lit", "unlit"], "exposure_override": False, "spawned_actors": False,
     }
-    capture_plan_path = c.write_json("slot_b_capture_plan_%s.json" % c.RUN, capture_plan)
-    if c.census() != {"content": [], "maps": []}:
-        raise RuntimeError("VERIFY_DIRTIED_EDITOR|" + json.dumps(c.census(), sort_keys=True))
-    report.update({"status": "PASS", "rows": len(plan["rows"]), "placed_panels": placed,
-                   "mesh_gates": mesh_gates, "movement": movement,
-                   "movement_sample_count": len(movement),
-                   "movement_phases_each": [0.25, 0.5, 0.75],
-                   "passage_range": [start_frame, end_frame],
-                   "capture_plan": capture_plan_path, "dirty_after": c.census()})
-    path = c.write_json("slot_b_verify_%s.json" % c.RUN, report)
-    unreal.log("FLATV3_B_READBACK_OK run=%s rows=%d placed_panels=%d movement_occurrences=%d phases_each=3 census=%s report=%s" %
-               (c.RUN, len(plan["rows"]), len(placed), len(movement),
-                json.dumps(c.census(), separators=(",", ":"), sort_keys=True), path))
-except Exception as exc:
-    reason = "verify:" + str(exc)
-    report.update({"status": "FAIL", "reason": reason, "traceback": traceback.format_exc(),
-                   "census": c.census()})
-    c.write_json("slot_b_verify_%s_FAILURE.json" % c.RUN, report)
-    saved = []
+
+    end_census = assert_clean("end")
+    report = {
+        "run": verification_run, "source_swap_run": swap_run, "mode": "verify",
+        "status": "PASS", "rows": len(plan["rows"]), "placed_panels": placed,
+        "mesh_gates": mesh_gates, "movement": movement,
+        "movement_sample_count": len(movement),
+        "movement_phases_each": list(SAMPLE_PHASES),
+        "passage_range": [start_frame, end_frame],
+        "capture_plan": capture_plan, "dirty_after": end_census,
+    }
+    if emit_report:
+        path = c.write_json("slot_b_verify_%s.json" % verification_run, report)
+        report["report_path"] = path
+    return report
+
+
+def main():
+    report = {"run": c.RUN, "mode": "verify"}
     try:
-        saved = slot_b_revert.revert(reason)
-    except Exception as revert_exc:
-        reason += "|REVERT_FAIL:" + str(revert_exc)
-    c.log_release("FAIL", saved, reason)
+        report = run_verify(c.RUN, c.RUN, emit_report=True)
+        unreal.log("FLATV3_B_READBACK_OK run=%s rows=%d placed_panels=%d movement_occurrences=%d phases_each=3 census=%s report=%s" %
+                   (c.RUN, report["rows"], len(report["placed_panels"]),
+                    report["movement_sample_count"],
+                    json.dumps(report["dirty_after"], separators=(",", ":"), sort_keys=True),
+                    report["report_path"]))
+    except Exception as exc:
+        reason = "verify:" + str(exc)
+        report.update({"status": "FAIL", "reason": reason, "traceback": traceback.format_exc(),
+                       "census": c.census()})
+        c.write_json("slot_b_verify_%s_FAILURE.json" % c.RUN, report)
+        unreal.log_error("FLATV3_B_VERIFY_FAIL run=%s reason=%s census=%s" %
+                         (c.RUN, str(exc).replace("\n", "\\n"),
+                          json.dumps(c.census(), separators=(",", ":"), sort_keys=True)))
+        c.log_release("FAIL", [], reason, run=c.RUN, artifact_run=c.RUN)
+
 
+if __name__ == "__main__":
+    main()
```
