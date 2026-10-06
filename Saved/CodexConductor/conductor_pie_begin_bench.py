"""Conductor's OWN PIE for a bench whose PREPARE leaves unsaved create-only materials under /Game/ZZ_Bench/.
Same as conductor_pie_begin.py, except dirty content is allowed when EVERY dirty package is under /Game/ZZ_Bench/."""
import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
lib = unreal.EditorLoadingAndSavingUtils
if ed.get_game_world() is not None:
    raise RuntimeError("PIE already active; refusing")
dirty = [p.get_name() for p in lib.get_dirty_content_packages()]
foreign = [n for n in dirty if not n.startswith("/Game/ZZ_Bench/")]
if foreign:
    raise RuntimeError("dirty non-bench content packages; refusing: %s" % foreign)
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_begin_play()
unreal.log("CONDUCTOR_PIE_BEGIN_REQUESTED|bench_dirty=%d" % len(dirty))
