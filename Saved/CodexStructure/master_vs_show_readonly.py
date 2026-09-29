"""Read-only, for the conductor: does the Master sequence (last saved 21 Sep) still
agree with the Show's compiled timeline (Show last saved 28 Sep)? If they
disagree, the spine is wrong in a way that looks exactly like transport bugs.
Compares every Passage section in the Master with the Show's compiled range for
that Passage (InfinityStageCameraPilotLibrary.GetPassageFrameRange), and the
Master's playback range with the last compiled Passage end. Scenes have no
compiled-range API, so their Master sections are listed, not compared.
Does NOT rebuild anything (never PussStageBootstrap.RebuildCurrentMaster).
Mutates nothing.
"""
import json
import os

import unreal

SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"
MASTER_PATH = "/Game/InfinityStage/Dev/Sequences/LS_InfinityStage_V1Master"
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexStructure", "master_vs_show.json")
TOL_S = 1.0 / 24.0     # one display frame

show = unreal.EditorAssetLibrary.load_asset(SHOW_PATH)
master = unreal.EditorAssetLibrary.load_asset(MASTER_PATH)
assert show and master, "Show or Master did not load"
scene = master.get_movie_scene()
tick = scene.get_tick_resolution()
display = scene.get_display_rate()
tick_rate = tick.numerator / float(tick.denominator)
display_rate = display.numerator / float(display.denominator)


def guid_str(g):
    return unreal.GuidLibrary.conv_guid_to_string(g)


def seconds(section, which):
    try:
        return round(getattr(section, f"get_{which}_frame_seconds")(), 4)
    except Exception:
        return None


def compiled_range(passage_guid):
    try:
        result = unreal.InfinityStageCameraPilotLibrary.get_passage_frame_range(show, passage_guid)
    except Exception as exc:
        return None, f"error: {exc}"
    # A bool UFUNCTION with out-params returns only the out values in UE 5.8 Python.
    if isinstance(result, tuple) and len(result) == 2:
        return (int(result[0]), int(result[1])), None
    return None, f"unexpected return {result!r}"


tracks = []
passages = []
last_compiled_end_s = None
for track in master.get_tracks():
    rec = {"track": track.get_class().get_name(), "sections": []}
    for section in track.get_sections():
        s = {"class": section.get_class().get_name(), "start_s": seconds(section, "start"),
             "end_s": seconds(section, "end")}
        for name in ("passage_guid", "owner_guid", "block_guid"):
            try:
                s[name] = guid_str(section.get_editor_property(name))
            except Exception:
                pass
        rec["sections"].append(s)
        if "passage_guid" in s:
            rng, err = compiled_range(section.get_editor_property("passage_guid"))
            row = {"passage_guid": s["passage_guid"], "master_start_s": s["start_s"], "master_end_s": s["end_s"],
                   "compiled_raw": rng, "error": err}
            if rng:
                # "Master frames": try the tick resolution first, then the display rate,
                # and record which one matches the section, so a units mistake shows.
                for label, rate in (("tick", tick_rate), ("display", display_rate)):
                    cs, ce = rng[0] / rate, rng[1] / rate
                    row[f"compiled_{label}_s"] = [round(cs, 4), round(ce, 4)]
                    if s["start_s"] is not None and s["end_s"] is not None:
                        row[f"delta_{label}_s"] = [round(s["start_s"] - cs, 4), round(s["end_s"] - ce, 4)]
                row["matches"] = [label for label in ("tick", "display")
                                  if f"delta_{label}_s" in row and all(abs(d) <= TOL_S for d in row[f"delta_{label}_s"])]
                end_s = rng[1] / tick_rate
                last_compiled_end_s = end_s if last_compiled_end_s is None else max(last_compiled_end_s, end_s)
            passages.append(row)
    tracks.append(rec)

playback = [round(master.get_playback_start_seconds(), 4), round(master.get_playback_end_seconds(), 4)]
disagree = [p for p in passages if not p.get("matches")]
report = {"tick_rate": tick_rate, "display_rate": display_rate, "master_playback_s": playback,
          "last_compiled_passage_end_s_at_tick_rate": round(last_compiled_end_s, 4) if last_compiled_end_s else None,
          "passages": passages, "passages_disagreeing": len(disagree), "tracks": tracks}
json.dump(report, open(OUT, "w"), indent=1)
dirty = (len(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
         len(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()))
unreal.log(f"MASTER_VS_SHOW_{'AGREE' if not disagree else 'DISAGREE'}|passages={len(passages)}|disagreeing={len(disagree)}"
           f"|playback_s={playback}|last_compiled_end_s={report['last_compiled_passage_end_s_at_tick_rate']}"
           f"|dirty={dirty[0]}+{dirty[1]}|mutated=0")
