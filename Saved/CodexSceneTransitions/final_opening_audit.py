import difflib,hashlib,json,pathlib,re
project=pathlib.Path('E:/PussStage');folder=project/'Saved/CodexSceneTransitions'
backup=pathlib.Path((folder/'opening_backup_path.txt').read_text(encoding='utf-8-sig').strip())
opening=json.loads((folder/'opening_verification.json').read_text())
transitions=json.loads((folder/'opening_transition_regression.json').read_text())
shore_render=json.loads((folder/'opening_shore_render.json').read_text())
curtains=json.loads((folder/'curtain_inspection.json').read_text())
assert opening['status']=='passed',opening['errors']
assert transitions['status']=='passed',transitions.get('errors')
assert shore_render['status']=='passed' and shore_render['renders'][-1]['camera']=='ClamCam1'
assert not curtains['dirty_after']
hashes=json.loads((folder/'opening_user_saved_hashes.json').read_text(encoding='utf-8-sig'))
preserved=[]
for row in hashes:
    actual=hashlib.sha256(pathlib.Path(row['Path']).read_bytes()).hexdigest().upper()
    assert actual==row['Hash'],row['Path']
    preserved.append(row['Path'])
log=(project/'Saved/Logs/OpeningPlayback-Boundary-Full.log').read_text(encoding='utf-8',errors='replace')
success=len(re.findall(r'Test Completed\. Result=\{Success\}',log))
failures=len(re.findall(r'Test Completed\. Result=\{Fail\}',log))
errors=[line for line in log.splitlines() if 'LogAutomationController: Error: Expected' in line]
assert success==43 and failures==1 and len(errors)==1 and 'hidden-changeover' in errors[0]
diffs=[];changed=[]
for original in sorted((backup/'Source').rglob('*')):
    if not original.is_file():continue
    relative=original.relative_to(backup/'Source');current=project/'Plugins/InfinityStage/Source'/relative
    if current.read_bytes()==original.read_bytes():continue
    changed.append(str(relative))
    diffs.extend(difflib.unified_diff(original.read_text(encoding='utf-8-sig').splitlines(True),current.read_text(encoding='utf-8-sig').splitlines(True),fromfile='before/'+relative.as_posix(),tofile='after/'+relative.as_posix()))
(folder/'opening_source.diff').write_text(''.join(diffs),encoding='utf-8')
out={'status':'passed','opening':opening['status'],'opening_hold_tick':opening['held_frame'],'scene_after_right_arrow':opening['advance_settled_view'],'transition_regression':transitions['status'],'transitions':len(transitions['transitions']),'shore_samples':len(transitions['samples']),'tests_passed':success,'tests_failed':failures,'remaining_failure':errors[0],'preserved_user_assets':preserved,'source_changes':changed,'backup':str(backup),'dirty_packages':curtains['dirty_after'],'renders':opening['renders']}
out['uninterrupted_shore_render']=shore_render['renders']
(folder/'opening_final_audit.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
