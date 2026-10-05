"""Velvet v2 bench wrapper (NOT RUN; written 5 Oct 2026). A NEW file: material_bench.py is not edited.

Runs NEXT TO the existing curtain material bench (Saved/CodexSoftGoods/material_bench.py, commits 78c12db/2af19c2),
which keeps owning place / pose / capture / cleanup of the ZZ_MaterialBench_Drape GeometryCache stand-in.
That bench hard-codes its MID parent (MI_CurtainVelvet_DeepRed_Drop) and validates names against the v1 parameter
record, so it cannot take a v2 parameter set. This wrapper adds only what is missing:

  {"action": "params"}                 read-only: every parameter of MI_CurtainVelvet_v2_DeepRed -> velvet_v2_bench_params.json
  {"action": "variant", "name": "V2B"} transient MID parented to MI_CurtainVelvet_v2_DeepRed with the variant's values
                                       (velvet_v2_bench_variants.json), read back, put on EVERY slot of the bench stand-in,
                                       pose re-issued; records the variant name in material_bench_state.json so the
                                       bench's own capture names the file Bench_<site>_<variant>_<tag>.png
  {"action": "lights"}                 read-only: the mouth lanterns (tag RigAtmos.MouthLantern.*) and their distance to the bench
  {"action": "spot_on", "light": "shadowplay_narrow"}
                                       spawns ONE transient SpotLight labelled ZZ_VelvetBench_Spot, placed in the bench actor's
                                       frame from the variants file's "lights" table; reads its settings back
  {"action": "spot_off"}               destroys every ZZ_VelvetBench_Spot (a scene capture cannot hide a light: always run this
                                       before any capture that must not see it, and before the bench cleanup)

Hard rules: NO save call of any kind; never modifies an asset (MIDs are transient, the spot is a level actor that the
Don't-Save restart after the bench throws away); refuses in PIE and outside the expected world; everything in main().
Mode file: Saved/CodexConductor/velvet_v2_bench_mode.json. Log line: PUSS_VELVET_V2_BENCH|<action>|...
"""
import json
import math
import os

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
MI_V2 = "/Game/Scenes/Curtain/Chaos/Materials/MI_CurtainVelvet_v2_DeepRed"
BENCH_LABEL = "ZZ_MaterialBench_Drape"
SPOT_LABEL = "ZZ_VelvetBench_Spot"
LANTERN_TAG = "RigAtmos.MouthLantern"


def validate_variants(doc, params=None):
    """Pure-Python check of velvet_v2_bench_variants.json. Returns a list of problems (empty = valid).
    `params` is the record written by the "params" action ({"scalars": {...}, "vectors": {...}, "textures": {...}});
    without it, names are checked against the builder's declared parameter list."""
    problems = []
    if params is None:
        import importlib.util
        here = os.path.dirname(os.path.abspath(__file__))
        old = os.environ.get("VV2_NO_AUTORUN")
        os.environ["VV2_NO_AUTORUN"] = "1"
        try:
            spec = importlib.util.spec_from_file_location("velvet_v2_build_spec", os.path.join(here, "velvet_v2_build.py"))
            build = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(build)
        finally:
            if old is None:
                os.environ.pop("VV2_NO_AUTORUN", None)
            else:
                os.environ["VV2_NO_AUTORUN"] = old
        params = {"scalars": dict.fromkeys(build.SCALARS), "vectors": dict.fromkeys(build.VECTORS),
                  "textures": dict.fromkeys(build.TEX)}
    variants = doc.get("variants")
    if not isinstance(variants, dict) or not variants:
        return ["variants must be a non-empty dict"]
    for name, row in variants.items():
        if not isinstance(row, dict) or set(row) - {"scalars", "vectors", "textures", "note"}:
            problems.append(f"{name}: keys must be among scalars, vectors, textures, note")
            continue
        for kind in ("scalars", "vectors", "textures"):
            values = row.get(kind, {})
            if not isinstance(values, dict):
                problems.append(f"{name}.{kind} must be a dict")
                continue
            unknown = sorted(set(values) - set(params.get(kind, {})))
            if unknown:
                problems.append(f"{name}.{kind} unknown {unknown}")
        for key, value in row.get("scalars", {}).items():
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0.0:
                problems.append(f"{name}.{key} must be a finite number >= 0")
            elif key in ("Roughness", "SheenAmount", "FoldDarken", "CrushAmount") and value > 1.0:
                problems.append(f"{name}.{key} must be <= 1")
            elif key in ("PileScale", "CrushScale") and value <= 0.0:
                problems.append(f"{name}.{key} must be > 0")
        for key, value in row.get("vectors", {}).items():
            if not isinstance(value, list) or len(value) != 4 or not all(isinstance(x, (int, float)) for x in value):
                problems.append(f"{name}.{key} must be four numbers")
            elif any(x < 0.0 or x > 1.0 for x in value[:3]):
                problems.append(f"{name}.{key} RGB must be within 0..1 (linear albedo)")
    lights = doc.get("lights", {})
    for name, light in lights.items():
        need = {"local_cm", "aim_local_cm", "candela", "outer_deg", "inner_deg", "kelvin", "radius_cm", "shadows"}
        if not isinstance(light, dict) or set(light) - need - {"note"} or need - set(light):
            problems.append(f"lights.{name} must have exactly {sorted(need)} (+ note)")
            continue
        if not (0.0 < light["inner_deg"] <= light["outer_deg"] <= 80.0):
            problems.append(f"lights.{name} cone angles must satisfy 0 < inner <= outer <= 80")
        if light["candela"] <= 0.0 or light["candela"] > 20000.0:
            problems.append(f"lights.{name} candela out of range")
    return problems


def main():
    import unreal  # inside main: nothing UE-owned survives the call

    here = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexConductor")
    soft = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")
    mode_path = os.path.join(here, "velvet_v2_bench_mode.json")
    params_path = os.path.join(here, "velvet_v2_bench_params.json")
    variants_path = os.path.join(here, "velvet_v2_bench_variants.json")
    state_path = os.path.join(soft, "material_bench_state.json")   # the bench's own runtime state (deleted by its cleanup)
    action = "unknown"

    def finish(detail):
        clean = str(detail).replace("\r", " ").replace("\n", " ")
        unreal.log(f"PUSS_VELVET_V2_BENCH|{action}|{clean}")
        return clean

    def read_json(path):
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    def write_json(path, value):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=1, sort_keys=True)

    def find_labelled(actor_subsystem, label):
        return [a for a in actor_subsystem.get_all_level_actors() if a.get_actor_label() == label]

    def apply_pose(component, cache_time):
        calls = {}
        for name, fn in (("set_manual_tick", lambda: component.set_manual_tick(True)),
                         ("tick_at_this_time", lambda: component.tick_at_this_time(float(cache_time), False, False, False))):
            try:
                fn()
                calls[name] = {"worked": True}
            except Exception as exc:  # noqa: BLE001
                calls[name] = {"worked": False, "error": f"{type(exc).__name__}: {exc}"}
        return calls

    try:
        cfg = read_json(mode_path)
        action = str(cfg.get("action", "unknown"))
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        if editor.get_game_world() is not None:
            return finish("refused: PIE is running")
        world = editor.get_editor_world()
        actual = None if world is None else world.get_path_name().split(".", 1)[0]
        if actual != EXPECTED_WORLD:
            return finish(f"refused: unexpected world {actual}")
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        mel = unreal.MaterialEditingLibrary

        if action == "params":
            mi = unreal.load_asset(MI_V2)
            if mi is None:
                return finish(f"refused: {MI_V2} does not load (run velvet_v2_build.py APPLY first)")
            record = {"material": mi.get_path_name(), "scalars": {}, "vectors": {}, "textures": {}}
            for name in mel.get_scalar_parameter_names(mi):
                record["scalars"][str(name)] = float(mel.get_material_instance_scalar_parameter_value(mi, name))
            for name in mel.get_vector_parameter_names(mi):
                c = mel.get_material_instance_vector_parameter_value(mi, name)
                record["vectors"][str(name)] = [float(c.r), float(c.g), float(c.b), float(c.a)]
            for name in mel.get_texture_parameter_names(mi):
                t = mel.get_material_instance_texture_parameter_value(mi, name)
                record["textures"][str(name)] = t.get_path_name() if t else None
            write_json(params_path, record)
            return finish(f"wrote={params_path}|scalars={len(record['scalars'])}|vectors={len(record['vectors'])}")

        if action == "variant":
            if not os.path.isfile(params_path):
                return finish(f"refused: params record missing at {params_path}")
            if not os.path.isfile(state_path):
                return finish(f"refused: bench state missing at {state_path} (run material_bench place first)")
            doc = read_json(variants_path)
            params = read_json(params_path)
            problems = validate_variants(doc, params)
            if problems:
                return finish(f"refused: variants file invalid {problems}")
            name = str(cfg.get("name", ""))
            if name not in doc["variants"]:
                return finish(f"refused: unknown variant {name!r}")
            row = doc["variants"][name]
            bench = find_labelled(actors, BENCH_LABEL)
            if len(bench) != 1 or not isinstance(bench[0], unreal.GeometryCacheActor):
                return finish(f"refused: expected one GeometryCacheActor {BENCH_LABEL}, found {len(bench)}")
            component = bench[0].get_editor_property("geometry_cache_component")
            slots = int(component.get_num_materials())
            if slots < 1:
                return finish("refused: bench component exposes no material slots")
            textures = {}
            for key, path in row.get("textures", {}).items():
                t = unreal.load_asset(str(path))
                if t is None:
                    return finish(f"refused: texture {key} does not load {path}")
                textures[key] = t
            parent = unreal.load_asset(MI_V2)
            if parent is None:
                return finish(f"refused: could not load {MI_V2}")
            mid = unreal.MaterialLibrary.create_dynamic_material_instance(world, parent)
            if mid is None:
                return finish("refused: transient MID creation returned None")
            for key, value in row.get("scalars", {}).items():
                mid.set_scalar_parameter_value(key, float(value))
            for key, value in row.get("vectors", {}).items():
                mid.set_vector_parameter_value(key, unreal.LinearColor(*[float(x) for x in value]))
            for key, t in textures.items():
                mid.set_texture_parameter_value(key, t)
            bad = []
            for key, value in row.get("scalars", {}).items():
                got = float(mid.get_scalar_parameter_value(key))
                if abs(got - float(value)) > 1e-4:
                    bad.append(f"{key}={got}")
            for key, value in row.get("vectors", {}).items():
                got = mid.get_vector_parameter_value(key)
                if any(abs(a - float(b)) > 1e-4 for a, b in zip((got.r, got.g, got.b, got.a), value)):
                    bad.append(f"{key}={got}")
            if bad:
                return finish(f"refused: MID read-back {bad}; slots NOT changed")
            for i in range(slots):
                component.set_material(i, mid)
            wrong = [i for i in range(slots) if component.get_material(i) != mid]
            state = read_json(state_path)
            cache_time = float(state.get("cache_time", 0.9667))
            pose_calls = apply_pose(component, cache_time)
            state.update({"variant": name, "cache_time": cache_time, "pose_calls": pose_calls})
            write_json(state_path, state)
            return finish(f"variant={name}|slots={slots}|slots_wrong={wrong}|cache_time={cache_time}|calls={pose_calls}")

        if action == "lights":
            bench = find_labelled(actors, BENCH_LABEL)
            origin = bench[0].get_actor_location() if len(bench) == 1 else None
            rows = []
            for a in actors.get_all_level_actors():
                tags = [str(t) for t in a.get_editor_property("tags")]
                if not any(t.startswith(LANTERN_TAG) for t in tags):
                    continue
                comp = a.get_component_by_class(unreal.SpotLightComponent)
                loc = a.get_actor_location()
                rows.append({"label": a.get_actor_label(), "tags": tags,
                             "candela": None if comp is None else float(comp.get_editor_property("intensity")),
                             "distance_to_bench_m": None if origin is None else round((loc - origin).length() / 100.0, 2)})
            rows.sort(key=lambda r: (r["distance_to_bench_m"] is None, r["distance_to_bench_m"]))
            return finish(f"lanterns={json.dumps(rows)}")

        if action == "spot_on":
            doc = read_json(variants_path)
            problems = validate_variants(doc, read_json(params_path)) if os.path.isfile(params_path) else []
            if problems:
                return finish(f"refused: variants file invalid {problems}")
            key = str(cfg.get("light", ""))
            light = doc.get("lights", {}).get(key)
            if light is None:
                return finish(f"refused: unknown light {key!r}")
            if find_labelled(actors, SPOT_LABEL):
                return finish(f"refused: {SPOT_LABEL} already exists")
            bench = find_labelled(actors, BENCH_LABEL)
            if len(bench) != 1:
                return finish(f"refused: expected one {BENCH_LABEL}, found {len(bench)}")
            frame = bench[0].get_actor_transform()
            loc = frame.transform_location(unreal.Vector(*light["local_cm"]))
            aim = frame.transform_location(unreal.Vector(*light["aim_local_cm"]))
            d = aim - loc
            rot = unreal.Rotator(roll=0.0, pitch=math.degrees(math.atan2(d.z, math.hypot(d.x, d.y))),
                                 yaw=math.degrees(math.atan2(d.y, d.x)))
            spot = actors.spawn_actor_from_class(unreal.SpotLight, loc, rot)
            if spot is None:
                return finish("refused: SpotLight spawn returned None")
            spot.set_actor_label(SPOT_LABEL)
            c = spot.get_component_by_class(unreal.SpotLightComponent)
            c.set_editor_property("intensity_units", unreal.LightUnits.CANDELAS)
            c.set_editor_property("intensity", float(light["candela"]))
            c.set_editor_property("outer_cone_angle", float(light["outer_deg"]))
            c.set_editor_property("inner_cone_angle", float(light["inner_deg"]))
            c.set_editor_property("use_temperature", True)
            c.set_editor_property("temperature", float(light["kelvin"]))
            c.set_editor_property("attenuation_radius", float(light["radius_cm"]))
            c.set_editor_property("cast_shadows", bool(light["shadows"]))
            back = {k: float(c.get_editor_property(p)) for k, p in (("cd", "intensity"), ("outer", "outer_cone_angle"),
                                                                     ("inner", "inner_cone_angle"), ("k", "temperature"))}
            ok = (abs(back["cd"] - light["candela"]) < 1e-3 and abs(back["outer"] - light["outer_deg"]) < 1e-3
                  and abs(back["inner"] - light["inner_deg"]) < 1e-3 and abs(back["k"] - light["kelvin"]) < 1e-2)
            return finish(f"spot={key}|ok={ok}|readback={back}|throw_m={d.length() / 100.0:.2f}")

        if action == "spot_off":
            spots = find_labelled(actors, SPOT_LABEL)
            for s in spots:
                actors.destroy_actor(s)
            left = len(find_labelled(actors, SPOT_LABEL))
            return finish(f"destroyed={len(spots)}|remaining={left}")

        return finish(f"refused: unknown action {action!r}")
    except Exception as exc:  # noqa: BLE001
        return finish(f"refused: {type(exc).__name__}: {exc}")


if os.environ.get("VV2_NO_AUTORUN") != "1":
    main()
