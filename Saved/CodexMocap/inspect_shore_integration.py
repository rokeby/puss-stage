"""Read scene bindings, cloth settings and native authoring API documentation."""
import json
import pathlib
import unreal

folder = pathlib.Path('E:/PussStage/Saved/CodexMocap')
assert pathlib.Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())).resolve() == folder.parent.parent.resolve()
assert not unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()

def path(obj):
    return obj.get_path_name() if isinstance(obj, unreal.Object) else str(obj)

def props(obj, names):
    result = {}
    for name in names:
        try:
            result[name] = path(obj.get_editor_property(name))
        except Exception as exc:
            result[name] = 'UNAVAILABLE: ' + str(exc)
    return result

report = {'sequences': [], 'cloth_components': [], 'cloth_assets': [], 'api': {}}
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_editor_world()
for name in ['LS_Clams', 'LS_OrtalanSheetSway']:
    seq = unreal.load_asset('/Game/Scenes/' + name)
    entry = {'path': path(seq), 'start': seq.get_playback_start(), 'end': seq.get_playback_end(),
             'fps': str(seq.get_display_rate()), 'bindings': [], 'tracks': []}
    for binding in seq.get_bindings():
        guid = binding.get_id()
        b = {'name': str(binding.get_name()), 'guid': str(guid), 'tracks': []}
        try:
            b['bound_objects'] = [path(x) for x in unreal.SequencerTools.get_bound_objects(world, seq, [binding], seq.get_playback_range())[0].bound_objects]
        except Exception as exc:
            b['bound_error'] = str(exc)
        for tr in binding.get_tracks():
            b['tracks'].append({'class': tr.get_class().get_name(), 'sections': [
                {'class': s.get_class().get_name(), 'start': s.get_start_frame() if s.has_start_frame() else None,
                 'end': s.get_end_frame() if s.has_end_frame() else None, 'properties': props(s, ['params', 'sub_sequence'])}
                for s in tr.get_sections()]})
        entry['bindings'].append(b)
    for tr in seq.get_tracks():
        entry['tracks'].append({'class': tr.get_class().get_name(), 'sections': [
            {'class': s.get_class().get_name(), 'start': s.get_start_frame() if s.has_start_frame() else None,
             'end': s.get_end_frame() if s.has_end_frame() else None, 'properties': props(s, ['sub_sequence', 'params'])}
            for s in tr.get_sections()]})
    report['sequences'].append(entry)
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if actor.get_class().get_name() == 'BP_OrtalanSheet_C':
        cloth = actor.get_components_by_class(unreal.ChaosClothComponent)[0]
        report['cloth_components'].append({'actor': path(actor), 'label': actor.get_actor_label(),
            'cloth': path(cloth), 'asset': path(cloth.get_asset()),
            'settings': props(cloth, ['use_attached_parent_as_pose_component', 'bind_to_leader_component',
                'leader_pose_component', 'simulate_in_editor', 'enable_simulation', 'physics_asset_override',
                'relative_location', 'relative_rotation', 'relative_scale3d', 'attach_socket_name']),
            'parent': path(cloth.get_attach_parent()), 'simulation_enabled': cloth.is_simulation_enabled(),
            'bounds': str(cloth.get_local_bounds()) if hasattr(cloth, 'get_local_bounds') else ''})
asset = unreal.load_asset('/Game/Scenes/CA__OrtolanSheets')
report['cloth_assets'].append({'path': path(asset), 'settings': props(asset, ['skeleton', 'physics_asset', 'dataflow_asset', 'dataflow_terminal', 'materials'])})
for name in ['Guid', 'GuidLibrary', 'SubobjectDataSubsystem', 'SubobjectDataBlueprintFunctionLibrary', 'AddNewSubobjectParams',
             'ChaosClothComponent', 'ChaosClothAsset', 'SequencerTools', 'LevelSequenceEditorBlueprintLibrary',
             'EditorActorSubsystem', 'AnimationLibrary', 'MovieSceneSkeletalAnimationParams']:
    cls = getattr(unreal, name, None)
    if cls:
        report['api'][name] = {'doc': cls.__doc__, 'methods': {n: getattr(cls, n).__doc__ for n in dir(cls)
            if any(k in n for k in ['string', 'subobject', 'attach', 'collision', 'pose', 'bone', 'animation', 'position', 'bound', 'spawn_actor', 'create', 'parent', 'asset', 'play', 'skeletal'])}}
(folder / 'shore_integration_inspection.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
unreal.log('SHORE_INTEGRATION_INSPECTION_SUCCESS')
