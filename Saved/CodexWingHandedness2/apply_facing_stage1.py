"""STAGE 1 (no save): set FacingPolicy = Rotate180AroundUp on every Left/Right Wing panel in
Passages 1,2,3,5,6 that is currently effectively identity-facing, then rematerialize those
Passages. Flip flags are asserted absent and left untouched. Records before-state for revert."""
import collections
import json
import os
import sys

import unreal  # noqa: E402

sys.path.insert(0, os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexWingHandedness2"))
from _common import (  # noqa: E402
    EXPECTED_WORLD, LABEL_RE, OUT_DIR, SHOW_PATH, dirty, editor_ready, is_effectively_rotated,
    library_front_axis, load_show, passage_actors, require, write_json,
)

editor_ready()
expected = json.load(open(os.path.join(OUT_DIR, "expected_changes.json"), encoding="utf-8"))
targets = set(expected["target_passages"])
backup_file = os.path.join(OUT_DIR, "backup_folder.txt")
require(os.path.isfile(backup_file), "backup_folder.txt missing: take the timestamped backup first")
backup = open(backup_file, encoding="utf-8").read().strip()
proj = unreal.Paths.project_dir()
require(os.path.isfile(os.path.join(proj, backup, "DA_InfinityStage_V1Show.uasset")), "Show backup missing")
require(os.path.isfile(os.path.join(proj, backup, "L_InfinityStage_V1VerticalSlice.umap")), "Level backup missing")
d0 = dirty()
require(set(d0["content"]) <= {SHOW_PATH} and set(d0["maps"]) <= {EXPECTED_WORLD},
        f"Out-of-scope dirty packages before mutation: {d0}")

show = load_show()
axis = library_front_axis(show)
cues = list(show.get_editor_property("cues"))
counts = collections.Counter()
changes = collections.Counter()
flips = 0
before = []
for i, cue in enumerate(cues):
    m = LABEL_RE.match(str(cue.get_editor_property("label")))
    if not m:
        continue
    passage = int(m.group("passage"))
    counts[passage] += 1
    pair = cue.get_editor_property("wing_pair")
    touched = False
    for side in ("left", "right"):
        panel = pair.get_editor_property(side)
        flips += int(bool(panel.get_editor_property("flip_image_horizontally")))
        if passage in targets and not is_effectively_rotated(panel, axis):
            before.append({
                "index": i,
                "label": str(cue.get_editor_property("label")),
                "side": side,
                "facing_before": str(panel.get_editor_property("facing_policy")),
            })
            panel.set_editor_property("facing_policy", unreal.InfinityPanelFacingPolicy.ROTATE180_AROUND_UP)
            pair.set_editor_property(side, panel)
            touched = True
            changes[f"{passage}:{side}"] += 1
    if touched:
        cue.set_editor_property("wing_pair", pair)
        cues[i] = cue

require({str(k): v for k, v in counts.items()} == expected["expected_row_counts"],
        f"Row counts changed: {dict(counts)}")
require(flips == expected["expected_total_flips"],
        f"Flip count {flips} != expected {expected['expected_total_flips']}")
require(dict(changes) == expected["expected_changes"],
        f"Change set {dict(changes)} != expected {expected['expected_changes']}")
show.modify()
show.set_editor_property("cues", cues)

actors = passage_actors(show)
require(targets <= set(actors), f"Missing Passage actors for {sorted(targets - set(actors))}")
materialized = {}
for p in sorted(targets):
    require(bool(actors[p].materialize_passage()), f"Materialization failed for Passage {p}")
    materialized[p] = int(actors[p].get_editor_property("materialized_wing_pair_count"))
d1 = dirty()
require(set(d1["content"]) <= {SHOW_PATH} and set(d1["maps"]) <= {EXPECTED_WORLD},
        f"Unexpected dirty after: {d1}")
write_json("apply_stage1_result.json", {
    "status": "ok", "saved": False, "backup_folder": backup,
    "changes": dict(changes), "panels_changed": sum(changes.values()), "before": before,
    "materialized": materialized, "dirty_before": d0, "dirty_after": d1,
})
unreal.log(
    "WING_FACING_STAGE1_SUCCESS"
    f"|panels={sum(changes.values())}|rows={len({b['index'] for b in before})}"
    f"|materialized={materialized}|saved=0"
)
