"""Read-only probe: find the handoff-watch subsystem instance from Python. Marker: PUSS_WATCH_PROBE"""
import unreal
cls = unreal.load_class(None, "/Script/InfinityStageEditor.InfinityStageHandoffWatchSubsystem")
results = {"class": str(cls.get_name()) if cls else None}
try:
    results["get_editor_subsystem"] = str(unreal.get_editor_subsystem(cls))
except Exception as error:
    results["get_editor_subsystem"] = f"error: {error}"
for engine_name in ("UnrealEdEngine_0", "EditorEngine_0"):
    path = f"/Engine/Transient.{engine_name}:InfinityStageHandoffWatchSubsystem_0"
    found = unreal.find_object(None, path)
    results[path] = str(found.get_path_name()) if found else None
unreal.log(f"PUSS_WATCH_PROBE|{results}")
