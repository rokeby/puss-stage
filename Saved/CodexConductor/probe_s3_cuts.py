"""READ-ONLY: LS_DevScene_03 root camera cut sections (range, camera binding name).  PROBE_S3CUTS_OK / _FAILED."""
import json
def main():
    import unreal as u
    seq = u.load_asset("/Game/InfinityStage/Dev/Sequences/LS_DevScene_03")
    names = {b.get_id().export_text(): str(b.get_display_name()) for b in seq.get_bindings()}
    rows = []
    for t in seq.get_tracks():
        if t.get_class().get_name() == "MovieSceneCameraCutTrack":
            for s in t.get_sections():
                cid = s.get_camera_binding_id()
                g = cid.get_editor_property("guid").export_text() if hasattr(cid, "get_editor_property") else str(cid)
                rows.append([int(s.get_start_frame()), int(s.get_end_frame()), names.get(g, g), bool(s.is_active())])
    rows.sort()
    json.dump(rows, open("E:/PussStage/Saved/CodexConductor/probe_s3_cuts.json", "w"), indent=1)
    u.log("PROBE_S3CUTS_OK|%s" % json.dumps(rows))
try:
    main()
except Exception as exc:
    import unreal
    unreal.log_error("PROBE_S3CUTS_FAILED|%r" % (exc,))
