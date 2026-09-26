import unreal
pkg = [m for m in dir(unreal.Package) if 'dirt' in m.lower() or 'flag' in m.lower()]
unreal.log("PKG_MEMBERS|%s" % pkg)
els = [m for m in dir(unreal.EditorLoadingAndSavingUtils) if 'dirt' in m.lower() or 'mark' in m.lower()]
unreal.log("ELS_MEMBERS|%s" % els)
sysl = [m for m in dir(unreal.SystemLibrary) if 'dirt' in m.lower()]
unreal.log("SYS_MEMBERS|%s" % sysl)
ea = [m for m in dir(unreal.EditorAssetLibrary) if 'dirt' in m.lower() or 'load' in m.lower()]
unreal.log("EAL_MEMBERS|%s" % ea)
