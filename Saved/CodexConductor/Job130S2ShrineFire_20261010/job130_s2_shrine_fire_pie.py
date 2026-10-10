"""Job 130 PIE-only t=Scene 2 +5 s probe. Never starts/stops PIE or saves."""
import datetime
import json
import math
import os

import unreal


FOLDER = "Job130S2ShrineFire_20261010"
OFFSET_SECONDS = 5.0
SETTLE_TICKS = 30
DEFAULT_RADIUS_CM = 12000.0


def path(obj):
    try:
        return obj.get_path_name()
    except Exception:
        return None


def safe(obj, name, default=None):
    try:
        return obj.get_editor_property(name)
    except Exception:
        return default


def level_name(actor):
    try:
        return actor.get_level().get_path_name()
    except Exception:
        return "UNKNOWN"


def location(obj):
    try:
        value = obj.get_world_location()
    except Exception:
        try:
            value = obj.get_actor_location()
        except Exception:
            return None
    return [float(value.x), float(value.y), float(value.z)]


def distance(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def actor_mentions_shrine(actor):
    hay = [path(actor) or "", str(actor.get_actor_label())]
    for comp in actor.get_components_by_class(unreal.ActorComponent):
        hay.append(path(comp) or "")
        for prop in ("static_mesh", "skeletal_mesh", "asset", "template"):
            hay.append(path(safe(comp, prop)) or "")
    joined = "|".join(hay).upper()
    return "SHRINE" in joined or "KK_S2" in joined


def particle_count(component):
    # UNiagaraComponent inherits UFXSystemComponent; UE declares GetNumActiveParticles.
    for name in ("get_num_active_particles", "get_num_particles"):
        try:
            return {"value": int(getattr(component, name)()), "api": name}
        except Exception:
            pass
    return {"value": None, "api": "UNEXPOSED_TO_PYTHON"}


def streaming(world):
    out = []
    try:
        levels = world.get_streaming_levels()
    except Exception:
        levels = []
    for item in levels:
        row = {"object": path(item), "world_asset": str(safe(item, "world_asset") or "")}
        for name in ("is_level_loaded", "is_level_visible"):
            try:
                row[name] = bool(getattr(item, name)())
            except Exception:
                row[name] = None
        row["should_be_loaded"] = safe(item, "should_be_loaded")
        row["should_be_visible"] = safe(item, "should_be_visible")
        out.append(row)
    return out


def main():
    run = "JOB130-PIE-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if world is None:
        unreal.log_error("JOB130_PIE_FAILED|run=%s|NO_PIE" % run)
        return
    # UE 5.8 PIE trap: use load_asset, never editor-only find calls.
    unreal.load_asset("/Game/InfinityStage/Dev/Sequences/LS_DevScene_02")
    roots = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.InfinityStageShowRoot))
    if len(roots) != 1:
        unreal.log_error("JOB130_PIE_FAILED|run=%s|SHOW_ROOTS=%d" % (run, len(roots)))
        return
    root = roots[0]
    transport, player = root.transport, root.sequence_player
    matches = [s for s in list(transport.segments) if str(s.label).strip().lower().startswith("scene 2")]
    if len(matches) != 1:
        unreal.log_error("JOB130_PIE_FAILED|run=%s|SCENE2_SEGMENTS=%d" % (run, len(matches)))
        return
    segment = matches[0]
    target = int(segment.start_frame.value + OFFSET_SECONDS * 24000)
    player.pause()
    transport.scrub_to_master_frame(unreal.FrameNumber(target))
    state = {"ticks": SETTLE_TICKS, "handle": None, "done": False}

    def tick(_delta):
        if state["done"]:
            return
        state["ticks"] -= 1
        if state["ticks"] > 0:
            return
        try:
            all_actors = list(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor))
            points = [location(actor) for actor in all_actors if actor_mentions_shrine(actor)]
            points = [point for point in points if point is not None]
            if not points:
                raise RuntimeError("SHRINE_ANCHOR_NOT_FOUND_IN_PIE")
            anchor = [sum(p[i] for p in points) / len(points) for i in range(3)]
            rows = []
            for actor in all_actors:
                for comp in actor.get_components_by_class(unreal.NiagaraComponent):
                    comp_location = location(comp)
                    if comp_location is None or distance(anchor, comp_location) > DEFAULT_RADIUS_CM:
                        continue
                    system = comp.get_asset()
                    rows.append({"component": path(comp), "owner": path(actor), "owner_level": level_name(actor),
                                 "system": path(system), "auto_activate": safe(comp, "auto_activate"),
                                 "is_active": comp.is_active(), "particle_count": particle_count(comp),
                                 "visible": comp.is_visible(), "hidden_in_game": safe(comp, "hidden_in_game"),
                                 "owner_hidden": safe(actor, "hidden"), "location": comp_location,
                                 "distance_to_shrine_cm": round(distance(anchor, comp_location), 2)})
            result = {"job": 130, "run": run, "scene2_offset_seconds": OFFSET_SECONDS,
                      "master_frame_ticks": target, "anchor": anchor, "radius_cm": DEFAULT_RADIUS_CM,
                      "components": rows, "streaming": streaming(world)}
            here = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                                "CodexConductor", FOLDER)
            os.makedirs(here, exist_ok=True)
            out = os.path.join(here, "job130_pie_probe_%s.json" % run)
            with open(out, "w", encoding="utf-8") as handle:
                json.dump(result, handle, indent=2, sort_keys=True, default=str)
                handle.write("\n")
            unreal.log("JOB130_PIE_OK|run=%s|t=+5.0|components=%d|out=%s" % (run, len(rows), out))
        except Exception as exc:
            unreal.log_error("JOB130_PIE_FAILED|run=%s|%r" % (run, exc))
        finally:
            state["done"] = True
            unreal.unregister_slate_post_tick_callback(state["handle"])

    state["handle"] = unreal.register_slate_post_tick_callback(tick)
    unreal.log("JOB130_PIE_ARMED|run=%s|scene2_master_ticks=%d|settle_ticks=%d" % (run, target, SETTLE_TICKS))


main()
