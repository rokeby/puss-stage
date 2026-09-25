import json
from pathlib import Path
folder=Path('E:/PussStage/Saved/CodexMocap')
def read(name):return json.loads((folder/name).read_text(encoding='utf-8'))
def write(name,data):(folder/name).write_text(json.dumps(data,indent=2),encoding='utf-8')
runtime=read('shore_clam_runtime_qc.json')
assert runtime['status']=='passed' and not runtime['errors'] and runtime['last_frame']>=795
brief=read('shore_cast_brief.json')
brief['current_state']='All six characters rigged, textured, Optimized/Medium assembled, full animations fitted and saved. Six draped actors and six independent animation bindings saved by the clam in the production level. Complete 797-frame play-mode motion and attachment test passed; native rendered visual review is separate.'
brief['performance_direction']['state']='Implemented as selected sections of each fitted recording at 0.60 play rate in LS_Clams; full takes preserved. Canopy corrected with spatial crown pinning and a separate skull-top attachment for the deeply bowed Shore02.'
brief['scene_integration']['state']='Saved in L_InfinityStage_V1VerticalSlice and LS_Clams; existing Show/Scene03 routing and timing retained. Four replaced mannequin originals retained hidden.'
brief['scene_integration']['manifest']='Saved/CodexMocap/shore_clam_integration.json'
brief['scene_integration']['runtime_validation']='Saved/CodexMocap/shore_clam_runtime_qc.json'
write('shore_cast_brief.json',brief)
cast=read('shore_draped_cast_components.json')
for p in cast:
    p['graph_status']='Configured and compiled: Construction and BeginPlay attach cloth to Body head and register the private drape collision asset.'
    p['physics_asset']='/Game/Metahuman/ShoreCast_20260910/Cloth/PHYS_'+p['id']+'_Drape.PHYS_'+p['id']+'_Drape'
write('shore_draped_cast_components.json',cast)
pilot=read('shore_drape_pilot.json');pilot['collision_graph']='configured';pilot['physics_asset']=cast[0]['physics_asset'];pilot['rendered_fit']='Canopy superseded by spatial crown pins; final production manifests are authoritative.';write('shore_drape_pilot.json',pilot)
old=read('shore_pinned_drape.json');old['status']='SUPERSEDED: numbered pins produced a canopy; do not reapply';old['replacement']='shore_spatial_crown_attachment.json and shore_bowed_drape.json';write('shore_pinned_drape.json',old)
spatial=read('shore_spatial_crown_attachment.json');spatial['render_validation']='Canopy removed in six-character playback and production renders; all six attachments passed the full runtime sequence test. Shore02 uses the separate bowed drape asset.';spatial['runtime_report']='shore_clam_runtime_qc.json';write('shore_spatial_crown_attachment.json',spatial)
bowed=read('shore_bowed_drape.json');bowed['coverage_validation']='Previously exposed bowed head now covered in the corrected group playback renders; attachment and moving body verified through full production runtime playback.';write('shore_bowed_drape.json',bowed)
print('SHORE_DELIVERY_RECORDS_UPDATED')
