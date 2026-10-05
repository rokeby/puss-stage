import json, unreal
show = unreal.load_asset("/Game/InfinityStage/Dev/DA_InfinityStage_V1Show")
out = []
for r in show.get_editor_property("music_rails"):
    def p(k):
        try:
            v = r.get_editor_property(k)
            return v.get_path_name() if v else None
        except Exception as e:
            return "ERR:%s" % e
    m = None
    try:
        m = r.get_editor_property("analysis_map")
    except Exception:
        pass
    info = {"sound": p("sound"), "map": m.get_path_name() if m else None}
    if m:
        for k in ("source_analysis_path", "source_file", "bpm", "tempo_bpm", "markers", "analysis_markers", "sections"):
            try:
                v = m.get_editor_property(k)
                info[k] = len(v) if hasattr(v, "__len__") and not isinstance(v, str) else str(v)
            except Exception:
                pass
    out.append(info)
unreal.log("MUSIC_ANALYSIS_READBACK|%s" % json.dumps(out))
