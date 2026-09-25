import builtins
import json
import pathlib
import unreal
folder = pathlib.Path('E:/PussStage/Saved/CodexMocap')
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
assert editor.get_editor_world().get_path_name().startswith('/Game/Metahuman/ShoreCast_20260910/Review/L_ShoreDrape_Pilot.')
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
camera = next(a for a in actors if a.get_actor_label() == 'Shore Drape Review Camera')
actor = next(a for a in actors if a.get_actor_label() == 'Shore01_M56 Drape Pilot')
body = next(c for c in actor.get_components_by_class(unreal.SkeletalMeshComponent) if c.get_name() == 'Body')
cloth = actor.get_component_by_class(unreal.ChaosClothComponent)
report = {'head': body.get_socket_transform('head').export_text(), 'cloth_parent': cloth.get_attach_parent().get_name(),
          'socket': str(cloth.get_attach_socket_name()), 'cloth_relative': cloth.get_editor_property('relative_location').export_text(),
          'cloth_bounds': str(unreal.SystemLibrary.get_component_bounds(cloth)),
          'body_bounds': str(unreal.SystemLibrary.get_component_bounds(body))}
(folder / 'shore_drape_pilot_render_state.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_set_game_view(True)
builtins.PUSS_SHORE_SCREENSHOT_TASK = unreal.AutomationLibrary.take_high_res_screenshot(1440, 1080,
    str(folder / 'ShoreDrape_Pilot_Settled.png'), camera=camera, delay=0.0)
unreal.log('SHORE_DRAPE_SCREENSHOT_REQUESTED|' + json.dumps(report))
