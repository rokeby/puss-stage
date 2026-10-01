"""Temporary, no-asset-write curtain material comparison bench."""
import json
import math
import os

import unreal


def main():
    expected_world = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
    parent_path = "/Game/Scenes/Curtain/Baked/MI_CurtainVelvet_DeepRed_Drop"
    cache_path = "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening"
    bench_label = "ZZ_MaterialBench_Drape"
    capture_label = "ZZ_TransientCapture"
    here = os.path.join(
        unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
        "CodexSoftGoods",
    )
    mode_path = os.path.join(here, "material_bench_mode.json")
    params_path = os.path.join(here, "material_bench_params.json")
    variants_path = os.path.join(here, "material_bench_variants.json")
    state_path = os.path.join(here, "material_bench_state.json")
    action = "unknown"

    def finish(detail):
        clean = str(detail).replace("\r", " ").replace("\n", " ")
        return unreal.log(f"PUSS_SOFTGOODS_MATERIAL_BENCH|{action}|{clean}")

    def dirty_packages():
        return sorted(
            [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
            + [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()]
        )

    def write_json(path, value):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=1, sort_keys=True)

    def read_json(path):
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)

    def apply_pose(component, cache_time):
        calls = {}
        try:
            component.set_manual_tick(True)
            calls["set_manual_tick"] = {"worked": True}
        except Exception as exc:
            calls["set_manual_tick"] = {"worked": False, "error": f"{type(exc).__name__}: {exc}"}
        try:
            component.tick_at_this_time(float(cache_time), False, False, False)
            calls["tick_at_this_time"] = {"worked": True}
        except Exception as exc:
            calls["tick_at_this_time"] = {"worked": False, "error": f"{type(exc).__name__}: {exc}"}
        return calls

    def show_flags():
        flags = []
        for name, enabled in (("VolumetricFog", True), ("Editor", False), ("BillboardSprites", False)):
            setting = unreal.EngineShowFlagsSetting()
            setting.set_editor_property("show_flag_name", name)
            setting.set_editor_property("enabled", enabled)
            flags.append(setting)
        return flags

    def find_bench(actor_subsystem):
        matches = [a for a in actor_subsystem.get_all_level_actors() if a.get_actor_label() == bench_label]
        if len(matches) != 1:
            raise RuntimeError(f"expected one {bench_label}, found {len(matches)}")
        if not isinstance(matches[0], unreal.GeometryCacheActor):
            raise RuntimeError(f"{bench_label} is {matches[0].get_class().get_name()}, not GeometryCacheActor")
        return matches[0]

    try:
        cfg = read_json(mode_path)
        action = str(cfg.get("action", "unknown"))

        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        if editor.get_game_world() is not None:
            return finish("refused: PIE is running")
        world = editor.get_editor_world()
        if world is None or world.get_path_name().split(".", 1)[0] != expected_world:
            actual = None if world is None else world.get_path_name().split(".", 1)[0]
            return finish(f"refused: unexpected world {actual}")

        actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

        if action == "params":
            parent = unreal.load_asset(parent_path)
            if parent is None:
                return finish(f"refused: could not load {parent_path}")
            report = {
                "material": parent.get_path_name(),
                "parent_chain": [],
                "scalars": {},
                "vectors": {},
                "textures": {},
                "errors": {},
            }
            current = parent
            seen = {current.get_path_name()}
            while "MaterialInstance" in current.get_class().get_name():
                try:
                    ancestor = current.get_editor_property("parent")
                except Exception as exc:
                    report["errors"]["parent_chain"] = f"{type(exc).__name__}: {exc}"
                    break
                if ancestor is None:
                    break
                ancestor_path = ancestor.get_path_name()
                if ancestor_path in seen:
                    report["errors"]["parent_chain"] = f"cycle at {ancestor_path}"
                    break
                report["parent_chain"].append(ancestor_path)
                seen.add(ancestor_path)
                current = ancestor

            mel = unreal.MaterialEditingLibrary
            parameter_specs = (
                (
                    "scalars",
                    "get_scalar_parameter_names",
                    "get_material_instance_scalar_parameter_value",
                    lambda value: float(value),
                ),
                (
                    "vectors",
                    "get_vector_parameter_names",
                    "get_material_instance_vector_parameter_value",
                    lambda value: [float(value.r), float(value.g), float(value.b), float(value.a)],
                ),
                (
                    "textures",
                    "get_texture_parameter_names",
                    "get_material_instance_texture_parameter_value",
                    lambda value: value.get_path_name() if value else None,
                ),
            )
            for category, names_getter, value_getter, convert in parameter_specs:
                try:
                    names = getattr(mel, names_getter)(parent)
                except Exception as exc:
                    report["errors"][category] = f"{type(exc).__name__}: {exc}"
                    continue
                for parameter_name in names:
                    key = str(parameter_name)
                    try:
                        value = getattr(mel, value_getter)(parent, parameter_name)
                        report[category][key] = convert(value)
                    except Exception as exc:
                        report[category][key] = {"error": f"{type(exc).__name__}: {exc}"}
            write_json(params_path, report)
            return finish(f"wrote={params_path}|material={report['material']}|errors={report['errors']}")

        if action == "place":
            if not os.path.isfile(params_path):
                return finish(f"refused: params record missing at {params_path}")
            dirty_content = sorted(
                p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
            )
            if dirty_content:
                return finish(f"refused: dirty content packages {dirty_content}")
            existing = [a for a in actor_subsystem.get_all_level_actors() if a.get_actor_label() == bench_label]
            if existing:
                return finish(f"refused: {len(existing)} actor(s) already labelled {bench_label}")
            sites = {
                "P01": ([0.0, 0.0, 0.0], 0.0),
                "P02": ([0.0, 80000.0, 0.0], 22.908),
            }
            site = str(cfg.get("site", ""))
            if site not in sites:
                return finish(f"refused: site must be P01 or P02, got {site!r}")
            cache = unreal.load_asset(cache_path)
            if cache is None:
                return finish(f"refused: could not load {cache_path}")
            location_values, yaw = sites[site]
            actor = actor_subsystem.spawn_actor_from_class(
                unreal.GeometryCacheActor,
                unreal.Vector(*location_values),
                unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw),
            )
            if actor is None:
                return finish("refused: GeometryCacheActor spawn returned None")
            actor.set_actor_label(bench_label)
            component = actor.get_editor_property("geometry_cache_component")
            component.set_editor_property("geometry_cache", cache)
            pose_calls = apply_pose(component, 0.9667)
            state = {
                "actor_label": bench_label,
                "site": site,
                "variant": "A",
                "cache_time": 0.9667,
                "pose_calls": pose_calls,
            }
            write_json(state_path, state)
            return finish(f"placed={site}|yaw={yaw}|cache_time=0.9667|calls={pose_calls}")

        if action == "variant":
            if not os.path.isfile(params_path):
                return finish(f"refused: params record missing at {params_path}")
            if not os.path.isfile(state_path):
                return finish(f"refused: state missing at {state_path}")
            variants = read_json(variants_path)
            name = str(cfg.get("name", ""))
            if name not in variants:
                return finish(f"refused: unknown variant {name!r}")
            variant = variants[name]
            scalars = variant.get("scalars", {})
            vectors = variant.get("vectors", {})
            textures = variant.get("textures", {})
            if not isinstance(scalars, dict) or not isinstance(vectors, dict) or not isinstance(textures, dict):
                return finish(
                    f"refused: variant {name!r} scalars, vectors, and textures must be dictionaries"
                )
            params = read_json(params_path)
            unknown_scalars = sorted(set(scalars) - set(params.get("scalars", {})))
            unknown_vectors = sorted(set(vectors) - set(params.get("vectors", {})))
            unknown_textures = sorted(set(textures) - set(params.get("textures", {})))
            if unknown_scalars or unknown_vectors or unknown_textures:
                return finish(
                    f"refused: unknown parameters scalars={unknown_scalars} vectors={unknown_vectors} "
                    f"textures={unknown_textures}"
                )
            loaded_textures = {}
            for parameter_name, texture_path in textures.items():
                texture = unreal.load_asset(str(texture_path))
                if texture is None:
                    return finish(
                        f"refused: texture {parameter_name!r} could not load asset {texture_path!r}"
                    )
                loaded_textures[parameter_name] = texture
            parent = unreal.load_asset(parent_path)
            if parent is None:
                return finish(f"refused: could not load {parent_path}")
            actor = find_bench(actor_subsystem)
            component = actor.get_editor_property("geometry_cache_component")
            slot_count = int(component.get_num_materials())
            if slot_count < 1:
                return finish("refused: bench component exposes no material slots")
            mid = unreal.MaterialLibrary.create_dynamic_material_instance(world, parent)
            if mid is None:
                return finish("refused: transient MID creation returned None")
            for parameter_name, value in scalars.items():
                mid.set_scalar_parameter_value(parameter_name, float(value))
            for parameter_name, value in vectors.items():
                if not isinstance(value, (list, tuple)) or len(value) != 4:
                    return finish(f"refused: vector {parameter_name!r} must contain four values")
                mid.set_vector_parameter_value(parameter_name, unreal.LinearColor(*[float(x) for x in value]))
            for parameter_name, texture in loaded_textures.items():
                mid.set_texture_parameter_value(parameter_name, texture)
            for slot_index in range(slot_count):
                component.set_material(slot_index, mid)
            state = read_json(state_path)
            cache_time = float(state.get("cache_time", 0.9667))
            pose_calls = apply_pose(component, cache_time)
            state.update({"variant": name, "cache_time": cache_time, "pose_calls": pose_calls})
            write_json(state_path, state)
            return finish(f"variant={name}|slots={slot_count}|cache_time={cache_time}|calls={pose_calls}")

        if action == "pose":
            if not os.path.isfile(state_path):
                return finish(f"refused: state missing at {state_path}")
            cache_time = float(cfg["cache_time"])
            actor = find_bench(actor_subsystem)
            component = actor.get_editor_property("geometry_cache_component")
            pose_calls = apply_pose(component, cache_time)
            state = read_json(state_path)
            state.update({"cache_time": cache_time, "pose_calls": pose_calls})
            write_json(state_path, state)
            return finish(f"cache_time={cache_time}|calls={pose_calls}")

        if action == "capture":
            if not os.path.isfile(state_path):
                return finish(f"refused: state missing at {state_path}")
            find_bench(actor_subsystem)
            state = read_json(state_path)
            actors = actor_subsystem.get_all_level_actors()
            camera_label = str(cfg.get("camera", ""))
            cameras = [
                a for a in actors if isinstance(a, unreal.CineCameraActor) and a.get_actor_label() == camera_label
            ]
            if len(cameras) != 1:
                return finish(f"refused: {len(cameras)} cameras labelled {camera_label}")
            tag = str(cfg.get("tag", ""))
            if not tag or tag != os.path.basename(tag) or any(ch in tag for ch in ("/", "\\")):
                return finish(f"refused: invalid capture tag {tag!r}")
            camera_component = cameras[0].get_cine_camera_component()
            width = camera_component.get_editor_property("filmback").get_editor_property("sensor_width")
            focal_length = camera_component.get_editor_property("current_focal_length")
            fov = math.degrees(2.0 * math.atan(width / (2.0 * focal_length)))
            hidden = [
                a
                for a in actors
                if "Camera + Shadow Figures" in a.get_actor_label()
                or a.get_class().get_name() == "InfinityStageShadowCatActor"
            ]
            target = unreal.RenderingLibrary.create_render_target2d(
                world, 1920, 1080, unreal.TextureRenderTargetFormat.RTF_RGBA8_SRGB
            )
            out_dir = os.path.join(here, "RenderCheck")
            os.makedirs(out_dir, exist_ok=True)
            image_name = f"Bench_{state['site']}_{state.get('variant', 'A')}_{tag}"
            capture_actor = unreal.EditorLevelLibrary.spawn_actor_from_class(
                unreal.SceneCapture2D,
                camera_component.get_world_location(),
                camera_component.get_world_rotation(),
            )
            if capture_actor is None:
                return finish("refused: SceneCapture2D spawn returned None")
            try:
                capture_actor.set_actor_label(capture_label)
                capture_component = capture_actor.capture_component2d
                capture_component.set_editor_property("texture_target", target)
                capture_component.set_editor_property(
                    "capture_source", unreal.SceneCaptureSource.SCS_FINAL_TONE_CURVE_HDR
                )
                capture_component.set_editor_property("fov_angle", fov)
                capture_component.set_editor_property("capture_every_frame", False)
                capture_component.set_editor_property("capture_on_movement", False)
                capture_component.set_editor_property("show_flag_settings", show_flags())
                for hidden_actor in hidden:
                    capture_component.hide_actor_components(hidden_actor, True)
                capture_component.capture_scene()
                unreal.RenderingLibrary.export_render_target(world, target, out_dir, image_name + ".png")
            finally:
                unreal.EditorLevelLibrary.destroy_actor(capture_actor)
            return finish(f"captured={os.path.join(out_dir, image_name + '.png')}|fov={fov:.2f}")

        if action == "cleanup":
            targets = [
                a
                for a in actor_subsystem.get_all_level_actors()
                if a.get_actor_label() in (bench_label, capture_label)
            ]
            labels = [a.get_actor_label() for a in targets]
            for actor in targets:
                unreal.EditorLevelLibrary.destroy_actor(actor)
            if os.path.isfile(state_path):
                os.remove(state_path)
            return finish(f"destroyed={labels}|dirty={dirty_packages()}|state_deleted={not os.path.exists(state_path)}")

        return finish(f"refused: unknown action {action!r}")
    except Exception as exc:
        return finish(f"refused: {type(exc).__name__}: {exc}")


main()
