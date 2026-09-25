import json,math,pathlib,shutil,unreal
folder=pathlib.Path('E:/PussStage/Saved/CodexSceneTransitions')
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world=editor.get_editor_world()
assert world.get_path_name().startswith('/Game/InfinityStage/Dev/Maps/L_InfinityStage_V1VerticalSlice.')
assert editor.get_game_world() is None
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
seq=unreal.load_asset('/Game/InfinityStage/Interactions/LS_Opening_Curtain')
assert (seq.get_playback_start(),seq.get_playback_end(),seq.get_display_rate().numerator)==(0,375,25)
assert len(seq.get_bindings())==1 and not seq.get_tracks()
binding=seq.get_bindings()[0];template=binding.get_object_template()
assert template and template.get_editor_property('curtain_distance_cm')==1500.0
roots=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
root=next(a for a in roots if isinstance(a,unreal.InfinityStageShowRoot))
show=root.show_asset
first=show.passage_settings[0]
assert '1' in str(first.label), str(first.label)
camera=next(a for a in roots if isinstance(a,unreal.InfinityStageCameraRig) and a.passage_actor and unreal.GuidLibrary.conv_guid_to_string(a.passage_actor.passage_guid)==unreal.GuidLibrary.conv_guid_to_string(first.passage_guid))
view=camera.get_camera_view_at_master_frame(unreal.FrameNumber(360000))
assert view
focal=view[1];sensor=camera.camera.filmback.sensor_width;aspect=camera.camera.aspect_ratio
bounds=template.curtain_mesh.static_mesh.get_bounding_box()
size=bounds.max-bounds.min;center=(bounds.max+bounds.min)*0.5
assert size.y>1000 and size.z>500
distance=100.0
screen_width=distance*sensor/focal
screen_height=screen_width/aspect
scale=max(screen_width/size.y,screen_height/size.z)*1.2
assert 0.01<scale<0.5
def transform(z):return unreal.Transform(location=unreal.Vector(0,-center.y*scale,z),scale=unreal.Vector(scale,scale,scale))
closed=transform(-center.z*scale)
opened=transform(screen_height*0.6-bounds.min.z*scale+5.0)
result={'focal':focal,'sensor_width':sensor,'aspect':aspect,'mesh_bounds':bounds.export_text(),'distance_cm':distance,'scale':scale,'closed':closed.export_text(),'opened':opened.export_text(),'before':{'distance':template.curtain_distance_cm,'open':template.curtain_open_relative_transform.export_text(),'closed':template.curtain_closed_relative_transform.export_text()}}
backup=pathlib.Path((folder/'opening_backup_path.txt').read_text().strip())/'BeforeOpeningAsset'
backup.mkdir(exist_ok=False)
shutil.copy2('E:/PussStage/Content/InfinityStage/Interactions/LS_Opening_Curtain.uasset',backup/'LS_Opening_Curtain.uasset')
seq.modify();template.modify()
template.set_editor_property('curtain_distance_cm',distance)
template.set_editor_property('curtain_view_local_offset_cm',unreal.Vector())
template.set_editor_property('curtain_open_relative_transform',opened)
template.set_editor_property('curtain_closed_relative_transform',closed)
spawn=next(t for t in binding.get_tracks() if isinstance(t,unreal.MovieSceneSpawnTrack))
for section in spawn.get_sections():section.set_range(0,375)
assert unreal.EditorAssetLibrary.save_loaded_asset(seq,False)
assert template.curtain_distance_cm==100.0
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
assert not unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
(folder/'opening_asset_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
unreal.log('OPENING_ASSET_REPAIR_SAVED|distance=100|frames=375')
