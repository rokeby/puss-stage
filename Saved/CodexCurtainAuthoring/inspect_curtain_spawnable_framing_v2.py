import json
import os

import unreal


SEQUENCE_PATH = "/Game/InfinityStage/Interactions/LS_Interaction_01_WashingTheBoy"


sequence = unreal.load_asset(SEQUENCE_PATH)
if sequence is None:
    raise RuntimeError(f"Missing {SEQUENCE_PATH}")

spawnables = list(sequence.get_spawnables())
bindings = list(sequence.get_bindings())
if len(spawnables) != 1 or len(bindings) != 1:
    raise RuntimeError(f"Unexpected spawnable/binding counts: {len(spawnables)}/{len(bindings)}")

spawnable = spawnables[0]
binding = bindings[0]
spawnable_methods = sorted(
    name for name in dir(spawnable)
    if "template" in name.lower() or "object" in name.lower() or "spawn" in name.lower()
)
binding_methods = sorted(
    name for name in dir(binding)
    if "template" in name.lower() or "object" in name.lower() or "spawn" in name.lower()
)

payload = {
    "sequence": SEQUENCE_PATH,
    "spawnable_type": type(spawnable).__name__,
    "binding_type": type(binding).__name__,
    "spawnable_methods": spawnable_methods,
    "binding_methods": binding_methods,
    "probes": {},
}

for owner_name, owner, methods in (
    ("spawnable", spawnable, spawnable_methods),
    ("binding", binding, binding_methods),
):
    for method_name in methods:
        try:
            value = getattr(owner, method_name)
            if callable(value) and method_name.startswith(("get_", "find_")):
                value = value()
            payload["probes"][f"{owner_name}.{method_name}"] = {
                "type": type(value).__name__,
                "value": str(value),
                "class": value.get_class().get_name() if hasattr(value, "get_class") else None,
            }
        except Exception as exc:
            payload["probes"][f"{owner_name}.{method_name}"] = {"error": repr(exc)}

output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCurtainAuthoring",
    "inspect_curtain_spawnable_framing_v2.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(
    "PUSS_CURTAIN_SPAWNABLE_FRAMING_API"
    f"|spawnable_methods={spawnable_methods}|binding_methods={binding_methods}"
)
