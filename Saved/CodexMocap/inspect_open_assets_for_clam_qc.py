import json
import pathlib
import unreal
dirty=list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())
out={'dirty_packages':[p.get_path_name() for p in dirty],'asset_editor_api':[n for n in dir(unreal.AssetEditorSubsystem) if 'editor' in n or 'asset' in n]}
pathlib.Path('E:/PussStage/Saved/CodexMocap/open_assets_for_clam_qc.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
unreal.log('CLAM_QC_OPEN_ASSETS_READ|'+json.dumps(out))
