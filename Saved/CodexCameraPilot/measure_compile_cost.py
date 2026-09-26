"""Read-only: time AInfinityStageShowRoot::GetCameraOwnerAtFrame, which compiles the whole Show per call.
Success marker: PUSS_COMPILE_COST_MEASURED"""
import time
import unreal

EXPECTED_WORLD = "/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice"
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
if world is None or world.get_path_name().split(".", 1)[0] != EXPECTED_WORLD:
    raise RuntimeError("Unexpected editor world")
if editor.get_game_world() is not None:
    raise RuntimeError("PIE/SIE is active")
roots = [a for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
         if a.get_class().get_name() == "InfinityStageShowRoot"]
if len(roots) != 1:
    raise RuntimeError(f"Expected one Show Root, found {len(roots)}")
root = roots[0]
show = root.get_editor_property("show_asset")
cues = len(show.get_editor_property("cues"))

frame = unreal.FrameNumber(1000)
for _ in range(5):
    root.get_camera_owner_at_frame(frame)
samples = []
for _ in range(10):
    start = time.perf_counter()
    for _ in range(20):
        root.get_camera_owner_at_frame(frame)
    samples.append((time.perf_counter() - start) / 20.0 * 1000.0)
samples.sort()
median_ms = samples[len(samples) // 2]

# Baseline for Python call overhead: a trivial UFUNCTION on the same actor.
start = time.perf_counter()
for _ in range(200):
    root.get_actor_location()
overhead_ms = (time.perf_counter() - start) / 200.0 * 1000.0

unreal.log(
    "PUSS_COMPILE_COST_MEASURED"
    f"|cues={cues}|owner_query_median_ms={median_ms:.4f}|min_ms={samples[0]:.4f}|max_ms={samples[-1]:.4f}"
    f"|python_call_overhead_ms={overhead_ms:.4f}"
)
