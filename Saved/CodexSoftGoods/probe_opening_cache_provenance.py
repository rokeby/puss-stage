"""READ-ONLY (30 Sep): which bake is the Opening curtain playing? The artifact chain, from the level side.

For GC_CurtainDrop_Opening: its import record (source file, timestamp, and the source's MD5 if the import data exposes
it). For the Opening cue's sequence (and the five Interactions): every GeometryCache section's asset, range and offsets,
so "the Opening plays this asset, holding this sample" is read, not assumed. Offline, the source .abc is compared by
hash with DropBake/<bake_id>.abc. Writes probe_opening_cache_provenance.json; logs PUSS_SOFTGOODS_OPENING_PROVENANCE|...
Nothing is modified or saved. Crash rules: everything inside main().
"""
import json
import os

import unreal

SHOW = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
GC = "/Game/Scenes/Curtain/Baked/GC_CurtainDrop_Opening"
HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexSoftGoods")


def main():
    dirty0 = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    out = {"gc": GC}
    gc = unreal.load_asset(GC)
    aid = gc.get_editor_property("asset_import_data") if gc else None
    out["import_filenames"] = list(aid.extract_filenames()) if aid else None
    try:
        info = aid.get_editor_property("source_data")
        out["source_files"] = [{k: str(sf.get_editor_property(k)) for k in ("relative_filename", "timestamp", "file_hash")
                                if hasattr(sf, "get_editor_property")} for sf in info.get_editor_property("source_files")]
    except Exception as e:  # noqa: BLE001
        out["source_files"] = f"not exposed: {e}"
    try:
        out["gc_frames"] = [gc.get_editor_property("start_frame"), gc.get_editor_property("end_frame")]
    except Exception as e:  # noqa: BLE001
        out["gc_frames"] = f"n/a: {e}"
    show = unreal.load_asset(SHOW)
    seqs = []
    for c in show.get_editor_property("cues"):
        label = str(c.get_editor_property("label"))
        if not (label.startswith("Opening") or label.startswith("Interaction")):
            continue
        seq = c.get_editor_property("scene").get_editor_property("sequence")
        if seq is None:
            continue
        rows = []
        for b in seq.get_bindings():
            for t in b.get_tracks():
                if "GeometryCache" not in t.get_class().get_name():
                    continue
                for s in t.get_sections():
                    p = s.get_editor_property("params")
                    asset = p.get_editor_property("geometry_cache_asset")
                    row = {"binding": str(b.get_display_name()), "range": [s.get_start_frame(), s.get_end_frame()],
                           "asset": asset.get_path_name() if asset else None}
                    for k in ("start_frame_offset", "end_frame_offset", "play_rate"):
                        try:
                            v = p.get_editor_property(k)
                            row[k] = v.value if hasattr(v, "value") else v
                        except Exception:  # noqa: BLE001
                            pass
                    rows.append(row)
        rate = seq.get_display_rate()
        seqs.append({"cue": label, "sequence": seq.get_path_name(), "fps": rate.numerator / rate.denominator,
                     "gc_sections": rows})
    out["sequences"] = seqs
    dirty1 = [p.get_path_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    out["dirty_changed"] = dirty0 != dirty1
    with open(os.path.join(HERE, "probe_opening_cache_provenance.json"), "w", encoding="utf-8") as h:
        json.dump(out, h, indent=1, default=str)
    opening = next((s for s in seqs if s["cue"].startswith("Opening")), None)
    del show, gc, aid
    unreal.log(f"PUSS_SOFTGOODS_OPENING_PROVENANCE|import={out['import_filenames']}|opening="
               f"{opening['gc_sections'] if opening else None}|dirty_changed={dirty0 != dirty1}")


main()
