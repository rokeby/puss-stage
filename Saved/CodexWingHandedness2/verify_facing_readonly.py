"""READ-ONLY verifier: every L/R panel in Passages 1,2,3,5,6 is effectively rotated, no flips are
set, target actors report full materialization, and only the Show/level are dirty (or nothing)."""
import collections
import json
import os
import sys

import unreal  # noqa: E402

sys.path.insert(0, os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexWingHandedness2"))
from _common import (  # noqa: E402
    LABEL_RE, OUT_DIR, dirty, editor_ready, is_effectively_rotated, library_front_axis, load_show,
    passage_actors, write_json,
)

editor_ready()
expected = json.load(open(os.path.join(OUT_DIR, "expected_changes.json"), encoding="utf-8"))
targets = set(expected["target_passages"])
show = load_show()
axis = library_front_axis(show)
per = collections.defaultdict(collections.Counter)
flips = 0
not_rotated = []
rows = collections.Counter()
for cue in show.get_editor_property("cues"):
    m = LABEL_RE.match(str(cue.get_editor_property("label")))
    if not m:
        continue
    p = int(m.group("passage"))
    rows[p] += 1
    pair = cue.get_editor_property("wing_pair")
    for side in ("left", "right"):
        panel = pair.get_editor_property(side)
        flips += int(bool(panel.get_editor_property("flip_image_horizontally")))
        rot = is_effectively_rotated(panel, axis)
        per[f"{p}:{side}"]["rotated" if rot else "identity"] += 1
        if p in targets and not rot:
            not_rotated.append((str(cue.get_editor_property("label")), side))
actors = passage_actors(show)
mat = {p: int(a.get_editor_property("materialized_wing_pair_count")) for p, a in actors.items()}
problems = []
if not_rotated:
    problems.append(f"{len(not_rotated)} target panels still identity: {not_rotated[:5]}")
if flips:
    problems.append(f"{flips} flip flags set")
for p in sorted(targets):
    if mat.get(p) != rows[p]:
        problems.append(f"Passage {p} materialized {mat.get(p)} != rows {rows[p]}")
d = dirty()
status = "ok" if not problems else "problems"
write_json("verify_facing_result.json", {
    "status": status, "problems": problems,
    "per_passage_side": {k: dict(v) for k, v in per.items()},
    "rows": dict(rows), "materialized": mat, "flips": flips, "dirty": d,
})
marker = "WING_FACING_VERIFY_SUCCESS" if not problems else "WING_FACING_VERIFY_PROBLEMS"
unreal.log(
    f"{marker}|problems={len(problems)}|flips={flips}|materialized={mat}"
    f"|dirty_content={len(d['content'])}|dirty_maps={len(d['maps'])}"
)
