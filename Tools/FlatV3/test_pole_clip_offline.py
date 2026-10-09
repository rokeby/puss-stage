"""Offline positive/negative controls for pole clipping; never imports or runs Blender."""
import json, os, sys
from pole_clip import art_full_segments, boolean_runs, with_buried_feet
from socket_contract import make_socket_payload

HERE=os.path.dirname(os.path.abspath(__file__)); R=[]
def check(name, ok, detail=None): R.append({"check":name,"ok":bool(ok),"detail":detail})

def mask(points):
    # Art from z=.10 to 2.0, with a base notch [.20,.35) and a hole [.80,1.00) on the pole column.
    return [(.10 <= z <= 2.0 and not (.20 <= z < .35) and not (.80 <= z < 1.00)) for _y,z in points]

segments, rows = art_full_segments(mask,[0.0],2.0,.06,.01,step_m=.01)
check("POS base notch and internal hole split the visible pole",len(segments[0])==3,segments)
check("POS margins keep all segments clear of gap edges",segments[0][0][0]>=.11 and segments[0][0][1]<=.19 and segments[0][1][0]>=.36 and segments[0][1][1]<=.79,segments)
full=with_buried_feet(segments,-1.0)
check("POS buried foot remains a separate contract segment",full[0][0]==[-1.0,0.0] and full[0][1:]==segments[0],full)
check("POS boolean run endpoints",boolean_runs([False,True,True,False,True])==[(1,3),(4,5)])
payload=make_socket_payload(asset="SM_Test",side="L",mount="wing",height_cm=200,width_m=1,
    pole_positions_y_m=[0],pole_extension_cm=100,pole_segments_z_cm=[[[a*100,b*100] for a,b in full[0]]])
g=payload["baked_pole_geometry"]
check("POS socket contract records art-full segments and highest top",g["top_mode"]=="art-full" and g["pole_top_z_cm"]==[segments[0][-1][1]*100],g)
try: art_full_segments(lambda pts:[False]*len(pts),[0],2,.06,.01,.01); refused=False
except ValueError: refused=True
check("NEG no art coverage refuses",refused)
try: with_buried_feet(segments,0); refused=False
except ValueError: refused=True
check("NEG non-buried foot refuses",refused)
legacy=make_socket_payload(asset="SM_Test",side="L",mount="wing",height_cm=200,width_m=1,
    pole_positions_y_m=[0],pole_extension_cm=100)
check("POS default socket contract byte-shape unchanged",legacy["baked_pole_geometry"]=={"extension_below_panel_cm":100.0,"bottom_z_cm":-100.0,"top_above_panel_cm":20.0},legacy)
out={"passed":sum(x["ok"] for x in R),"failed":sum(not x["ok"] for x in R),"results":R,
     "tier":"measured offline pure geometry; Blender rebuild and Unreal import unproven"}
json.dump(out,open(os.path.join(HERE,"test_pole_clip_offline_report.json"),"w"),indent=2)
print("TOTAL %d passed, %d failed"%(out["passed"],out["failed"])); sys.exit(0 if not out["failed"] else 1)
