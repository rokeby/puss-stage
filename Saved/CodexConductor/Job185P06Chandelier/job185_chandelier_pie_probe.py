"""Read-only PIE probe for the exact 44 P06 chandelier fire child actors."""
import json
import os
import unreal

PREFIX = "P56_P75_P06_Chandelier_Body_Candle_"
ASSET = "/Game/Stylish_Fire_VFX/Niagara/NS_Stylish_Fire_1"
OUT = unreal.Paths.project_saved_dir() + "CodexConductor/Job185P06Chandelier/pie_probe.json"


def aid(value):
    text = str(value.get_path_name() if hasattr(value, "get_path_name") else value)
    return text.split(".", 1)[0]


world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if world is None:
    raise RuntimeError("JOB185_CHANDELIER_PIE_PROBE|NO_OWNED_PIE")
actors = sorted([a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor)
                 if str(a.get_actor_label()).startswith(PREFIX)], key=lambda a: str(a.get_actor_label()))
if len(actors) != 44:
    raise RuntimeError("JOB185_CHANDELIER_PIE_PROBE|CANDLES=%d" % len(actors))
rows = []
for actor in actors:
    comps = [c for c in actor.get_components_by_class(unreal.NiagaraComponent) if aid(c.get_asset()) == ASSET]
    if len(comps) != 1:
        raise RuntimeError("JOB185_CHANDELIER_PIE_PROBE|COMPONENTS=%d|%s" % (len(comps), actor.get_actor_label()))
    comp = comps[0]
    system = comp.get_asset()
    # UE 5.8's NiagaraSystem Python wrapper exposes this as an editor
    # property on this project build (the method exists only in some builds).
    store = None
    store_errors = []
    try:
        store = system.get_editor_property("exposed_parameters")
    except Exception as exc:
        store_errors.append(repr(exc))
    getters = ([name for name in ("get_user_parameters", "get_parameters", "get_parameter_names") if hasattr(store, name)]
               if store is not None else [])
    params = []
    for getter in getters:
        try:
            params = sorted(str(x.get_name() if hasattr(x, "get_name") else x) for x in getattr(store, getter)())
            break
        except Exception:
            pass
    rows.append({
        "label": str(actor.get_actor_label()),
        "class": str(actor.get_class().get_path_name()),
        "actor_scale": [float(v) for v in (actor.get_actor_scale3d().x, actor.get_actor_scale3d().y, actor.get_actor_scale3d().z)],
        "component_scale": [float(v) for v in (comp.get_world_scale().x, comp.get_world_scale().y, comp.get_world_scale().z)],
        "parameters": params,
        "parameter_getters": getters,
        "parameter_store_errors": store_errors,
        "actor_scale_members": sorted(x for x in dir(actor) if "scale" in x.lower() or "fire" in x.lower() or "flame" in x.lower()),
        "sprite_scale": str(actor.get_editor_property("sprite_scale")),
        "component_variable_members": sorted(x for x in dir(comp) if "variable" in x.lower() or "scale" in x.lower()),
    })
with open(OUT, "w", encoding="utf-8") as handle:
    json.dump({"rows": rows}, handle, indent=2, sort_keys=True)
unreal.log("JOB185_CHANDELIER_PIE_PROBE_OK|candles=44|class=%s|actor_scale=%s|component_scale=%s|params=%s" %
           (rows[0]["class"], rows[0]["actor_scale"], rows[0]["component_scale"], rows[0]["parameters"]))
