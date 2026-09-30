"""Read-only: for P01 Wing 041 "Entry High -Y" (the blinking spot), the flicker's
parameters, and what occupies its beam: a fan of rays inside the cone, reporting
the first thing each hits. Mutates nothing."""
import collections
import json
import math
import os

import unreal


def main():
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    world = ed.get_editor_world()
    assert world and ed.get_game_world() is None, "PIE or no editor world"
    lf = unreal.EditorAssetLibrary.load_asset("/Game/InfinityStage/Lighting/MI_LF_Flicker_Buzz")
    params = {}
    if lf:
        MEL = unreal.MaterialEditingLibrary
        for n in MEL.get_scalar_parameter_names(lf):
            params[str(n)] = MEL.get_material_instance_scalar_parameter_value(lf, n)
        params["_parent"] = lf.get_editor_property("parent").get_path_name() if lf.get_editor_property("parent") else None
    loc = unreal.Vector(23740, -1257, 1886)
    pitch, yaw = math.radians(-52.4), math.radians(66.4)
    fwd = unreal.Vector(math.cos(pitch) * math.cos(yaw), math.cos(pitch) * math.sin(yaw), math.sin(pitch))
    up = unreal.Vector(0, 0, 1)
    right = fwd.cross(up).normal()
    up2 = right.cross(fwd).normal()
    half = math.radians(11.7)
    hits = collections.Counter()
    samples = []
    for ring in (0.0, 0.33, 0.66, 1.0):
        n = 1 if ring == 0 else 12
        for k in range(n):
            a = 2 * math.pi * k / n
            d = fwd + right * (math.tan(half * ring) * math.cos(a)) + up2 * (math.tan(half * ring) * math.sin(a))
            d = d.normal()
            hit = unreal.SystemLibrary.line_trace_single(world, loc, loc + d * 6000.0, unreal.TraceTypeQuery.ECC_VISIBILITY,
                                                         True, [], unreal.DrawDebugTrace.NONE, True)
            h = hit.to_tuple() if hit else None
            if h and h[0]:
                actor = next((x for x in h if isinstance(x, unreal.Actor)), None)
                comp = next((x for x in h if isinstance(x, unreal.PrimitiveComponent)), None)
                key = f"{actor.get_actor_label() if actor else None} / {comp.get_name() if comp else None}"
                hits[key] += 1
                p = h[4]
                samples.append({"ring": ring, "hit": key, "at": [round(p.x), round(p.y), round(p.z)], "dist": round(h[3])})
            else:
                hits["(nothing within 60 m)"] += 1
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                       "CodexStructure", "p01_blinking_spot_cone.json")
    json.dump({"flicker_params": params, "hits": dict(hits), "samples": samples}, open(out, "w"), indent=1)
    unreal.log(f"P01_BLINKING_CONE_OK|rays={sum(hits.values())}|kinds={len(hits)}|mutated=0")


main()
