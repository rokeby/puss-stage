"""READ-ONLY: every binding whose name mentions 'Pearl' in LS_DevScene_03, LS_S3_HangarRise, LS_Clams: its parent label,
tracks, and Visibility keys (frame, value), plus section ranges. PROBE_PEARLVIS|json"""
import json
import unreal
out = {}
for path in ("/Game/InfinityStage/Dev/Sequences/LS_DevScene_03", "/Game/InfinityStage/Dev/Sequences/LS_S3_HangarRise", "/Game/InfinityStage/Dev/Sequences/LS_Clams"):
    seq = unreal.load_asset(path)
    if seq is None:
        hits = unreal.AssetRegistryHelpers.get_asset_registry().get_assets_by_package_name(path) if False else None
        out[path] = "MISSING"; continue
    rows = []
    for b in seq.get_bindings():
        nm = str(b.get_display_name()); p = b.get_parent()
        own = str(p.get_display_name()) if p is not None and p.is_valid() else ""
        if "pearl" not in (nm + own).lower():
            continue
        tr = []
        for t in b.get_tracks():
            d = {"cls": t.get_class().get_name(), "name": str(t.get_display_name())}
            if d["cls"] == "MovieSceneVisibilityTrack":
                d["secs"] = []
                for s in t.get_sections():
                    ch = list(s.get_all_channels())[0]
                    d["secs"].append({"range": [s.get_start_frame() if s.has_start_frame() else None, s.get_end_frame() if s.has_end_frame() else None],
                                      "keys": [[k.get_time().frame_number.value, bool(k.get_value())] for k in ch.get_keys()],
                                      "default": ch.get_default() if hasattr(ch, "get_default") else None})
            tr.append(d)
        rows.append({"binding": nm, "owner": own, "tracks": tr})
    out[path.split("/")[-1]] = rows
unreal.log("PROBE_PEARLVIS|" + json.dumps(out, default=str))
