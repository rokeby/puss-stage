import unreal


SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MARKER = "P02_INSPECT_SUCCESS"


def get_prop(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return default


def asset_path(value):
    if value is None:
        return "None"
    try:
        return value.get_path_name()
    except Exception:
        return str(value)


show = unreal.load_asset(SHOW_PATH)
if show is None:
    raise RuntimeError(f"Show Asset did not load: {SHOW_PATH}")

editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
unreal.log(f"P02_INSPECT|world={asset_path(world)}")

for method_name in ("get_dirty_content_packages", "get_dirty_map_packages"):
    method = getattr(unreal.EditorLoadingAndSavingUtils, method_name, None)
    if method is None:
        unreal.log(f"P02_INSPECT|{method_name}=unavailable")
        continue
    try:
        packages = method()
        unreal.log(
            f"P02_INSPECT|{method_name}="
            + ",".join(sorted(asset_path(package) for package in packages))
        )
    except Exception as exc:
        unreal.log_warning(f"P02_INSPECT|{method_name}_error={exc}")

actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
passage_actors = []
for actor in actor_subsystem.get_all_level_actors():
    if actor.get_class().get_name() != "InfinityStagePassageActor":
        continue
    label = actor.get_actor_label()
    values = []
    for prop in (
        "passage_index",
        "passage_number",
        "passage_id",
        "show_asset",
        "infinity_stage_show_asset",
    ):
        value = get_prop(actor, prop, "<unavailable>")
        values.append(f"{prop}={asset_path(value)}")
    unreal.log(
        "P02_INSPECT|actor="
        + label
        + f"|path={actor.get_path_name()}|"
        + "|".join(values)
    )
    passage_actors.append(actor)

cues = list(show.get_editor_property("cues"))
if not cues:
    raise RuntimeError("Show Asset contains no cues")

unreal.log(
    "P02_INSPECT|cue_fields="
    + ",".join(name for name in dir(cues[0]) if not name.startswith("_"))
)

label_prop = None
for candidate in ("label", "cue_label", "name"):
    if get_prop(cues[0], candidate, None) is not None:
        label_prop = candidate
        break
if label_prop is None:
    raise RuntimeError("Could not discover cue label property")

p02_rows = []
for index, cue in enumerate(cues):
    label = str(get_prop(cue, label_prop, ""))
    if not label.startswith("P02 Wing "):
        continue
    p02_rows.append((index, cue, label))

if not p02_rows:
    sample_labels = [str(get_prop(cue, label_prop, "")) for cue in cues[:40]]
    unreal.log_error("P02_INSPECT|sample_labels=" + " || ".join(sample_labels))
    raise RuntimeError("No P02 Wing rows found")

sample_pair = None
for candidate in ("wing_pair", "wings", "wing_assignment"):
    sample_pair = get_prop(p02_rows[0][1], candidate, None)
    if sample_pair is not None:
        pair_prop = candidate
        break
else:
    raise RuntimeError("Could not discover cue wing-pair property")

unreal.log(
    "P02_INSPECT|pair_prop="
    + pair_prop
    + "|pair_fields="
    + ",".join(name for name in dir(sample_pair) if not name.startswith("_"))
)

for row_number, (cue_index, cue, label) in enumerate(p02_rows):
    pair = get_prop(cue, pair_prop)
    values = []
    for prop in (
        "left",
        "right",
        "top",
        "left_wing",
        "right_wing",
        "top_wing",
        "left_mesh",
        "right_mesh",
        "top_mesh",
        "has_top",
    ):
        value = get_prop(pair, prop, "<unavailable>")
        values.append(f"{prop}={asset_path(value)}")
    unreal.log(
        f"P02_ROW|row={row_number + 1}|cue_index={cue_index}|label={label}|"
        + "|".join(values)
    )

unreal.log(
    f"{MARKER}|rows={len(p02_rows)}|first={p02_rows[0][2]}|last={p02_rows[-1][2]}"
    f"|passage_actors={len(passage_actors)}|label_prop={label_prop}|pair_prop={pair_prop}"
)
