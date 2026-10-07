"""Probe on the UNSAVED half-built copy LS_Void_S6 (already dirty after a stopped APPLY; Don't-Save restart follows).
Lists possessables, retries remove() on parentless empty ones, lists again. Saves nothing. Marker PROBE_PREMOVE|..."""
import json

import unreal

G = unreal.GuidLibrary.conv_guid_to_string
seq = unreal.load_asset("/Game/InfinityStage/KlaraHookin/LS_Void_S6")


def rows():
    out = []
    for b in seq.get_possessables():
        par = b.get_parent()
        out.append({"name": str(b.get_display_name()), "valid": b.is_valid(), "guid": G(b.get_id()),
                    "parent": None if par is None else G(par.get_id()), "tracks": len(b.get_tracks()),
                    "children": len(b.get_child_possessables()) if hasattr(b, "get_child_possessables") else None})
    return out


res = {"before": rows(), "spawnables": [str(s.get_display_name()) for s in seq.get_spawnables()],
       "bindings": len(seq.get_bindings())}
for b in seq.get_possessables():
    if not str(b.get_display_name()) and b.get_parent() is not None and G(b.get_parent().get_id()) == "0" * 32:
        res.setdefault("retry", []).append(str(b.remove()))
res["after"] = rows()
unreal.log("PROBE_PREMOVE|%s" % json.dumps(res))
