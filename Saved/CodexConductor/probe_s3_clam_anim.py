"""READ-ONLY: every track bound to clam/pearl actors in LS_DevScene_03 and LS_Clams (+ nested shots), key frames/values;
pearl/mantle MI emissive-ish params; clam world positions. Marker PROBE_S3_CLAM_ANIM_OK / _FAILED. Writes probe_s3_clam_anim.json."""
import json
OUT = "E:/PussStage/Saved/CodexConductor/probe_s3_clam_anim.json"
def main():
    import unreal
    out = {"seqs": {}, "actors": {}, "mis": {}}
    def walk(seq, depth, offs):
        if seq is None or depth > 3:
            return
        dr = seq.get_display_rate(); fps = dr.numerator / float(dr.denominator)
        rows = []
        for b in seq.get_bindings():
            nm = str(b.get_display_name())
            p = b.get_parent(); pn = str(p.get_display_name()) if p is not None and p.is_valid() else ""
            if not any(w in (nm + pn).lower() for w in ("clam", "pearl", "lid", "mantle")):
                continue
            for t in b.get_tracks():
                for s in t.get_sections():
                    chs = []
                    for ch in s.get_all_channels():
                        try:
                            ks = ch.get_keys()
                        except Exception:
                            continue
                        if ks:
                            chs.append([str(ch.get_name()), [(int(k.get_time().frame_number.value), round(float(k.get_value()), 3) if not isinstance(k.get_value(), bool) else k.get_value()) for k in ks][:12], len(ks)])
                    rows.append({"b": nm, "parent": pn, "track": str(t.get_display_name()), "cls": t.get_class().get_name(),
                                 "range": [s.get_start_frame() if s.has_start_frame() else None, s.get_end_frame() if s.has_end_frame() else None],
                                 "chs": chs})
        out["seqs"][seq.get_path_name()] = {"fps": fps, "rows": rows}
        for mt in seq.get_tracks():
            for s in mt.get_sections():
                try:
                    sub = s.get_sequence()
                except Exception:
                    sub = None
                if sub is not None and "HangarRise" not in sub.get_path_name():
                    walk(sub, depth + 1, offs)
    walk(unreal.load_asset("/Game/InfinityStage/Dev/Sequences/LS_DevScene_03"), 0, 0)
    ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    w = ed.get_editor_world()
    for a in unreal.GameplayStatics.get_all_actors_of_class(w, unreal.Actor):
        lab = str(a.get_actor_label())
        if any(x in lab for x in ("PearlClam", "Clam_with_Pearl", "Ghost Light", "WaveV3", "Hangar Root")) and lab.startswith(("S3", "Clam")):
            l = a.get_actor_location(); r = a.get_actor_rotation()
            bb = a.get_actor_bounds(False)
            out["actors"][lab] = {"loc": [round(l.x, 1), round(l.y, 1), round(l.z, 1)], "rot": [round(r.roll, 1), round(r.pitch, 1), round(r.yaw, 1)],
                                  "bounds_c": [round(bb[0].x, 1), round(bb[0].y, 1), round(bb[0].z, 1)], "ext": [round(bb[1].x, 1), round(bb[1].y, 1), round(bb[1].z, 1)],
                                  "parent": str(a.get_attach_parent_actor().get_actor_label()) if a.get_attach_parent_actor() else None}
    for mi in ("/Game/InfinityStage/Dev/Generated/S3Props/PearlClam/MI_PearlClam_Pearl_v2", "/Game/InfinityStage/Dev/Generated/S3Props/PearlClam/MI_PearlClam_Mantle"):
        m = unreal.load_asset(mi)
        if m is None:
            out["mis"][mi] = None; continue
        out["mis"][mi] = {"scalars": {str(p.parameter_info.name): round(p.parameter_value, 4) for p in m.get_editor_property("scalar_parameter_values")},
                          "vectors": {str(p.parameter_info.name): str(p.parameter_value) for p in m.get_editor_property("vector_parameter_values")},
                          "parent": m.get_editor_property("parent").get_path_name() if m.get_editor_property("parent") else None}
        try:
            out["mis"][mi]["parent_scalars"] = [str(x) for x in unreal.MaterialEditingLibrary.get_scalar_parameter_names(m.get_editor_property("parent"))]
            out["mis"][mi]["parent_vectors"] = [str(x) for x in unreal.MaterialEditingLibrary.get_vector_parameter_names(m.get_editor_property("parent"))]
        except Exception as e:
            out["mis"][mi]["err"] = repr(e)
    json.dump(out, open(OUT, "w"), indent=1, default=str)
    unreal.log("PROBE_S3_CLAM_ANIM_OK|seqs=%d|actors=%d" % (len(out["seqs"]), len(out["actors"])))
try:
    main()
except Exception as exc:
    import unreal, traceback
    unreal.log_error("PROBE_S3_CLAM_ANIM_FAILED|%r|%s" % (exc, traceback.format_exc()[-500:].replace("\n", " / ")))
