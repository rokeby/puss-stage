"""Read-only ownership probe for Job 181 shadow-reach diagnosis."""
import importlib.util
import json
import os

import unreal


HERE = "E:/PussStage/Saved/CodexConductor"
path = os.path.join(HERE, "shadow_radius_reach.py")
spec = importlib.util.spec_from_file_location("job181_shadow_scope_module", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
args = module.check_args(json.load(open(os.path.join(HERE, "shadow_radius_reach_args.json"), encoding="utf-8")))
live = module.gather_live(args)
summary = {}
for key, passage in sorted(live["passages"].items()):
    managed = list(passage.get_editor_property("managed_attachment_actors"))
    tagged = []
    for actor in managed:
        identity = module.parse_attachment_tag(actor)
        comps = module.light_components(actor)
        tagged.append({
            "label": actor.get_actor_label(),
            "path": actor.get_path_name(),
            "level": module.actor_level_package(actor),
            "identity": identity,
            "tags": [str(tag) for tag in list(actor.tags)],
            "light_components": [c.get_name() for c in comps],
        })
    summary[key] = {
        "passage_label": passage.get_actor_label(),
        "managed_count": len(managed),
        "tagged_count": sum(row["identity"] is not None for row in tagged),
        "managed_with_light_count": sum(bool(row["light_components"]) for row in tagged),
        "included_rows": sum(row["passage"] == key for row in live["rows"]),
        "actors": tagged,
    }
out = os.path.join(HERE, "job181_shadow_scope_probe.json")
with open(out, "w", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2, sort_keys=True, default=str)
unreal.log("JOB181_SHADOW_SCOPE_PROBE_OK|summary=%s|out=%s" %
           (json.dumps({k: {x: v[x] for x in ("managed_count", "tagged_count", "managed_with_light_count", "included_rows")} for k, v in summary.items()}, sort_keys=True), out))
