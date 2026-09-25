import json
import os

import unreal


SEQUENCE_PATH = "/Game/InfinityStage/Interactions/LS_Interaction_01_WashingTheBoy"

sequence = unreal.load_asset(SEQUENCE_PATH)
if sequence is None:
    raise RuntimeError(f"Missing {SEQUENCE_PATH}")

sequence_methods = sorted(name for name in dir(sequence) if "marked_frame" in name.lower())
extension_methods = sorted(
    name for name in dir(unreal.MovieSceneSequenceExtensions)
    if "marked_frame" in name.lower()
)
probes = {}

for label, callback in (
    (
        "sequence.get_marked_frames_display",
        lambda: sequence.get_marked_frames(unreal.MovieSceneTimeUnit.DISPLAY_RATE),
    ),
    (
        "extensions.get_marked_frames_from_sequence_display",
        lambda: unreal.MovieSceneSequenceExtensions.get_marked_frames_from_sequence(
            sequence, unreal.MovieSceneTimeUnit.DISPLAY_RATE
        ),
    ),
):
    try:
        values = list(callback())
        probes[label] = {
            "ok": True,
            "frames": [int(value.frame_number.value) for value in values],
            "labels": [str(value.label) for value in values],
        }
    except Exception as exc:
        probes[label] = {"ok": False, "error": repr(exc)}

payload = {
    "sequence_methods": sequence_methods,
    "extension_methods": extension_methods,
    "probes": probes,
}
output_path = os.path.join(
    unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()),
    "CodexCurtainAuthoring",
    "inspect_marked_frame_timeunit_api.json",
)
with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)

unreal.log(
    "PUSS_MARKED_FRAME_TIMEUNIT_API"
    f"|sequence_methods={sequence_methods}|extension_methods={extension_methods}"
)
