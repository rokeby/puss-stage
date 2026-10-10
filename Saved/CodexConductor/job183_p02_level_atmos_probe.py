"""Read-only P02 route census for level fog, local fog and beam light authority."""
import json
import unreal


rows=[]
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    label=str(actor.get_actor_label()); cls=actor.get_class().get_name(); loc=actor.get_actor_location()
    in_route=(-1500.0<=loc.x<=30000.0 and 77000.0<=loc.y<=83000.0 and -1000.0<=loc.z<=5000.0)
    named="P02" in label.upper()
    fogish=any(token in cls.upper() for token in ("FOG","VOLUMETRIC")) or any(token in label.upper() for token in ("FOG","HAZE","SMOKE","ATMOS"))
    lights=[]
    for component in actor.get_components_by_class(unreal.LightComponent):
        row={"class":component.get_class().get_name()}
        for prop in ("intensity","volumetric_scattering_intensity","cast_shadows","cast_volumetric_shadow","visible"):
            try:row[prop]=component.get_editor_property(prop)
            except Exception:pass
        lights.append(row)
    beamish=any(float(row.get("volumetric_scattering_intensity",0.0) or 0.0)>0.0 for row in lights)
    if (in_route and (fogish or beamish or named)) or (named and (fogish or lights)):
        row={"label":label,"class":cls,"path":str(actor.get_path_name()),"location_cm":[loc.x,loc.y,loc.z],"in_route":in_route,"tags":[str(t) for t in actor.get_editor_property("tags")],"lights":lights}
        for component_class in (unreal.ExponentialHeightFogComponent,):
            for component in actor.get_components_by_class(component_class):
                props={}
                for prop in ("fog_density","fog_height_falloff","volumetric_fog","volumetric_fog_scattering_distribution","volumetric_fog_albedo","volumetric_fog_emissive","volumetric_fog_extinction_scale","visible"):
                    try:props[prop]=component.get_editor_property(prop)
                    except Exception:pass
                row["fog"]=props
        rows.append(row)
path="E:/PussStage/Saved/CodexConductor/job183_p02_level_atmos_probe.json"
with open(path,"w",encoding="utf-8") as handle:json.dump({"rows":rows},handle,indent=2,sort_keys=True,default=str)
unreal.log("JOB183_P02_LEVEL_ATMOS_PROBE_OK|rows=%d|path=%s"%(len(rows),path))
