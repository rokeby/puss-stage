"""Read-only: line traces from the P02 still poses (60%, 80%) forward/left/right/up/down; first hit actor+level+dist.
Also nearest 8 P02 lights with editor intensity. Marker P02TRACE|"""
import json
import math

import unreal

poses = {"0.4": (5661.07, 86133.11), "0.6": (7416.0, 84463.51), "0.8": (9170.92, 82793.92)}
yaw = math.radians(-43.5725)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
out = {}
dirs = {"fwd": (math.cos(yaw), math.sin(yaw), 0), "left": (math.sin(yaw), -math.cos(yaw), 0),
        "right": (-math.sin(yaw), math.cos(yaw), 0), "up": (0, 0, 1), "down": (0, 0, -1)}
for k, (x, y) in poses.items():
    row = {}
    s = unreal.Vector(x, y, 180.0)
    for dn, d in dirs.items():
        e = unreal.Vector(x + d[0] * 5000, y + d[1] * 5000, 180.0 + d[2] * 5000)
        hit = unreal.SystemLibrary.line_trace_single(world, s, e, unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, False, [],
                                                     unreal.DrawDebugTrace.NONE, True)
        if hit:
            t = hit.to_tuple()
            a = t[9] if len(t) > 9 else None
            dist = t[3] if len(t) > 3 else None
            row[dn] = [round(float(dist), 1) if dist is not None else None,
                       str(a.get_actor_label()) if a else None, a.get_outermost().get_name().split("/")[-1] if a else None]
        else:
            row[dn] = None
    out[k] = row
unreal.log("P02TRACE|%s" % json.dumps(out))
