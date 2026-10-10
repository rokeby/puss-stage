"""Pure geometry/safety contract for Job 178B. No Unreal import."""
from __future__ import annotations
import hashlib, json, math

CONFIRM={"DRY":"DRY JOB178B P06 SUN DISC","APPLY":"APPLY JOB178B P06 SUN DISC","REVERT":"REVERT JOB178B P06 SUN DISC"}
class ContractError(RuntimeError):pass
def require(v,m):
    if not v:raise ContractError(m)
def stable_hash(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()
def validate_args(raw,active=False):
    a=dict(raw);mode=str(a.get("mode","DRY")).upper();require(mode in CONFIRM,"MODE");require(a.get("confirm")==CONFIRM[mode],"CONFIRM|"+CONFIRM[mode])
    require(not active if mode=="APPLY" else True,"ACTIVE_RECORD_EXISTS");require(active if mode=="REVERT" else True,"ACTIVE_RECORD_REQUIRED")
    defaults={"passage_guid":"9BFC29C45D47911FF7836BB8537230D2","passage_label":"Passage 6","arrival_seconds":.25,
      "near_end_margin_seconds":2.0,"trace_step_deg":.25,"trace_limit_deg":25.0,"trace_distance_cm":1000000.0,
      "camera_ticks_per_second":24000.0,
      "fit_fraction":.8,"fit_sample":"near_end","center_sample":"arrival","max_sunset_shift_seconds":10.0,
      "center_tolerance_deg":.3,"sun_actor_label":"Infinity Stage - Dusk Sun","sky_actor_label":"Infinity Stage - Dusk Sky Atmosphere"}
    for k,v in defaults.items():a.setdefault(k,v)
    for k,lo,hi in (("arrival_seconds",0,10),("near_end_margin_seconds",.1,10),("trace_step_deg",.05,1),
                    ("trace_limit_deg",3,45),("trace_distance_cm",10000,5000000),("fit_fraction",.5,.95),
                    ("camera_ticks_per_second",1,100000),("max_sunset_shift_seconds",0,60),("center_tolerance_deg",0,.75)):
        a[k]=float(a[k]);require(lo<=a[k]<=hi,"ARG_RANGE|"+k)
    require(a["fit_sample"] in ("arrival","near_end") and a["center_sample"] in ("arrival","near_end"),"SAMPLE_NAME")
    a["mode"]=mode;return a
def opening_from_clearance(clearance, trace_limit_deg=45.0):
    values={k:(None if clearance.get(k) is None else float(clearance[k])) for k in ("left","right","down","up")}
    for k,v in values.items():require(v is None or v>0,"WINDOW_BOUND|"+k)
    unbounded=[k for k,v in values.items() if v is None]
    require(len(unbounded)<=1,"WINDOW_MULTIPLE_UNBOUNDED|"+",".join(unbounded))
    left,right,down,up=(values[k] for k in ("left","right","down","up"))
    horizontal_bounded=left is not None and right is not None
    vertical_bounded=down is not None and up is not None
    require(horizontal_bounded or vertical_bounded,"WINDOW_NO_BOUNDED_AXIS")
    horizontal=(left+right) if horizontal_bounded else (left or float(trace_limit_deg))+(right or float(trace_limit_deg))
    vertical=(down+up) if vertical_bounded else (down or float(trace_limit_deg))+(up or float(trace_limit_deg))
    if horizontal_bounded and vertical_bounded:
        extent=min(horizontal,vertical);axis="smaller_of_bounded_axes"
    elif vertical_bounded:
        extent=vertical;axis="vertical"
    else:
        extent=horizontal;axis="horizontal"
    return {"horizontal_deg":horizontal,"vertical_deg":vertical,
            "horizontal_bounded":horizontal_bounded,"vertical_bounded":vertical_bounded,
            "unbounded_edges":unbounded,"fit_axis":axis,"bounded_extent_deg":extent,
            "center_h_deg":(right-left)/2.0 if horizontal_bounded else 0.0,
            "center_v_deg":(up-down)/2.0 if vertical_bounded else 0.0,
            "clearance_deg":values,"smaller_deg":extent,
            "fit_rule":"80pct_bounded_axis_centered_on_bounded_extent"}
def target_size(window,fraction):return float(window["bounded_extent_deg"])*float(fraction)
def setting_phase_for_elevation(elev):
    require(-89.0<=float(elev)<=89.0,"ELEVATION_SETTING_BRANCH");return (270.0-float(elev))/360.0
def phase_elevation(phase):return math.degrees(math.asin(max(-1.0,min(1.0,-math.cos(2*math.pi*(float(phase)%1.0))))))
def center_plan(current,window_center_world,sample_seconds,duration,max_shift):
    x,y,z=window_center_world;n=math.sqrt(x*x+y*y+z*z);require(n>0,"CENTER_VECTOR");x,y,z=x/n,y/n,z/n
    az=math.degrees(math.atan2(y,x))%360.0;elev=math.degrees(math.asin(z));phase=setting_phase_for_elevation(elev)
    entry=(phase-float(sample_seconds)/float(duration))%1.0
    old=float(current["entry_phase_offset_cycles"]);delta=((entry-old+.5)%1.0)-.5;shift=delta*float(duration)
    require(abs(shift)<=float(max_shift),"CENTER_WOULD_RETIME_SUNSET|%.3f>%s"%(abs(shift),max_shift))
    return {"sun_azimuth_degrees":az,"target_elevation_deg":elev,"entry_phase_offset_cycles":entry,
            "sunset_shift_seconds":shift,"world_direction":[x,y,z]}
def disc_fits(size,window,fraction,tol=1e-4):return abs(float(size)-target_size(window,fraction))<=tol and float(size)<float(window["bounded_extent_deg"])
