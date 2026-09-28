import unreal
lib = unreal.LevelSequenceEditorBlueprintLibrary
ms = [m for m in dir(lib) if not m.startswith('_')]
unreal.log("SEQ_LIB|%s" % [m for m in ms if any(k in m for k in ('open','play','time','close','current','sequence'))])
