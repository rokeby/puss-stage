import unreal
ed = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
g, e = ed.get_game_world(), ed.get_editor_world()
t1 = unreal.EditorAssetLibrary.load_asset("/Game/ZZ_Bench/S3MarbleGrime/Textures/T_S3MG_Marble021_RoughGrime")
t2 = unreal.load_asset("/Game/ZZ_Bench/S3MarbleGrime/Textures/T_S3MG_Marble021_RoughGrime")
unreal.log("PROBE_WORLDS|game=%s|editor=%s|eal_load=%s|load=%s" % (g.get_path_name() if g else None, e.get_path_name() if e else None, t1 is not None, t2 is not None))
