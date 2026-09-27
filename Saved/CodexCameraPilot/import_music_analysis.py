"""Gary, 2026-09-26: import the music analysis into Unreal.

Runs UInfinityStageCameraPilotLibrary.ImportMusicAnalysis (the Cue Desk's
Link / Reimport, unchanged). It imports Saved/InfinityStage/MusicAnalysis into
MM_P01..P06_Analysis, relinks the Show's rails, and saves the maps and the Show.
Asserts the world, no PIE and zero dirty first. Afterwards requires curves and
sections in every map, no Confirmed marker lost, and nothing left dirty.
Backup: Backups/PreMusicAnalysisImport-20260926-203858.
Success marker: PUSS_MUSIC_IMPORT_DONE
"""

import json
import os

import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
SHOW_PATH = "/Game/InfinityStage/Dev/DA_InfinityStage_V1Show"


def dirty():
    return sorted(
        [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()]
        + [p.get_name() for p in unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()])


def census(show):
    rows = {}
    for index, rail in enumerate(show.get_editor_property("music_rails")):
        amap = rail.get_editor_property("analysis_map")
        if amap is None:
            rows[f"rail{index + 1}"] = None
            continue
        markers = {}
        confirmed = 0
        for field in ("beat_proposals", "onset_proposals", "major_change_proposals"):
            values = amap.get_editor_property(field)
            markers[field] = len(values)
            confirmed += sum(1 for m in values if m.get_editor_property("state") != unreal.InfinityMusicProposalState.SUGGESTED)
        rows[amap.get_name()] = {
            "curves": len(amap.get_editor_property("feature_curves")),
            "sections": len(amap.get_editor_property("expressive_sections")),
            "markers": markers,
            "confirmed_markers": confirmed,
        }
    return rows


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
    raise RuntimeError("Unexpected editor world")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE/SIE is active")
if dirty():
    raise RuntimeError(f"Refusing: already dirty {dirty()}")

show = unreal.load_asset(SHOW_PATH)
before = census(show)
result = unreal.InfinityStageCameraPilotLibrary.import_music_analysis(show)
report = result[1] if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], bool) else result
if result is None or (isinstance(result, tuple) and result[0] is False):
    raise RuntimeError(f"Import failed: {result}")
after = census(show)

problems = []
for name, row in after.items():
    if row is None:
        problems.append(f"{name}: no analysis map linked")
        continue
    if row["curves"] == 0 or row["sections"] == 0:
        problems.append(f"{name}: curves={row['curves']} sections={row['sections']}")
    prior = before.get(name)
    if prior and row["confirmed_markers"] < prior["confirmed_markers"]:
        problems.append(f"{name}: confirmed markers {prior['confirmed_markers']} -> {row['confirmed_markers']}")
left_dirty = dirty()
if left_dirty:
    problems.append(f"left dirty: {left_dirty}")

out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
                   "CodexCameraPilot", "import_music_analysis.json")
with open(out, "w", encoding="utf-8") as handle:
    json.dump({"before": before, "after": after, "report": str(report), "problems": problems}, handle, indent=2)
if problems:
    raise RuntimeError(f"Music import read-back failed: {problems}")
unreal.log(
    "PUSS_MUSIC_IMPORT_DONE"
    f"|maps={len(after)}|curves={[r['curves'] for r in after.values()]}"
    f"|sections={[r['sections'] for r in after.values()]}|report={report}")
