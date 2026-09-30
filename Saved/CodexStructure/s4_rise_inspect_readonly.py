"""READ-ONLY (30 Sep): what LS_S4_HangarRise keys today, WITHOUT opening Sequencer (asset API only; opening Master-bound
sequences dirties the map). Per binding: name, tracks, and for float/intensity channels their keys; plus the Scene 4
exposure volume(s) near the S4 dock: label, blend weight, unbound, priority, exposure pins. Marker S4_RISE_INSPECT|run."""
import datetime
import json
import os

import unreal

HERE = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CodexStructure")


def main():
    run = datetime.datetime.now().strftime("%H%M%S")
    seq = unreal.load_asset("/Game/InfinityStage/RigAtmos/LS_S4_HangarRise")
    rate = seq.get_display_rate()
    fps = rate.numerator / float(rate.denominator)
    out = {"fps": fps, "playback_s": [seq.get_playback_start_seconds(), seq.get_playback_end_seconds()], "bindings": []}
    for b in seq.get_bindings():
        row = {"name": str(b.get_display_name()), "tracks": []}
        for t in b.get_tracks():
            tr = {"class": t.get_class().get_name(), "name": str(t.get_display_name())}
            try:
                tr["property"] = str(t.get_property_name())
            except Exception:  # noqa: BLE001
                pass
            chans = []
            for s in t.get_sections():
                for ch in s.get_all_channels():
                    ks = ch.get_keys()
                    if ks:
                        chans.append({"ch": str(ch.get_name()), "keys": [[round(k.get_time().frame_number.value / fps, 3), round(float(k.get_value()), 3)] for k in ks[:8]]})
            tr["channels"] = chans[:9]
            row["tracks"].append(tr)
        out["bindings"].append(row)
    ppvs = []
    for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        if isinstance(a, unreal.PostProcessVolume) and ("S4" in a.get_actor_label() or "Scene 4" in a.get_actor_label() or abs(a.get_actor_location().y - 240000) < 5000):
            st = a.get_editor_property("settings")
            ppvs.append({"label": a.get_actor_label(), "loc": [round(v) for v in (a.get_actor_location().x, a.get_actor_location().y, a.get_actor_location().z)],
                         "blend_weight": a.get_editor_property("blend_weight"), "unbound": a.get_editor_property("unbound"),
                         "priority": a.get_editor_property("priority"), "blend_radius": a.get_editor_property("blend_radius"),
                         "ae_min": st.get_editor_property("auto_exposure_min_brightness"), "ae_max": st.get_editor_property("auto_exposure_max_brightness"),
                         "override_min": st.get_editor_property("override_auto_exposure_min_brightness")})
    out["ppvs"] = ppvs
    with open(os.path.join(HERE, f"s4_rise_inspect_{run}.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    d = [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()] + [str(p.get_name()) for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
    unreal.log(f"S4_RISE_INSPECT|run={run}|bindings={len(out['bindings'])}|ppvs={len(ppvs)}|dirty_after={d}")


main()
