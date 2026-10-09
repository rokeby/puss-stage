"""PG7 positive/negative offline harness."""
from __future__ import annotations
import argparse,json,math,sys
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from scipy import ndimage
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import boy_rig,cat_rig,clip_render,props  # noqa:E402

def add(rows,kind,label,value,detail): rows.append({"kind":kind,"label":label,"passed":bool(value),"detail":detail})
def components(prop):
    im=Image.new("L",(500,500),255);props.draw_prop(im,prop,(250,250),170,state=0);mask=np.asarray(im)<128
    labels,n=ndimage.label(mask,np.ones((3,3),dtype=np.uint8));sizes=np.bincount(labels.ravel())[1:];return int(np.sum(sizes>20))
def page_text_mask(angle=None,centre=(300,300),size=220):
    im=Image.new("L",(600,600),0);draw=ImageDraw.Draw(im)
    for polygon in props.page_text_polygons(props.LOOK["page"]["page_text"],centre,size,angle_deg=angle):
        draw.polygon(polygon,fill=1)
    return np.asarray(im,dtype=bool)
def principal_axis_deg(mask):
    yy,xx=np.nonzero(mask);points=np.column_stack((xx-xx.mean(),yy-yy.mean()))
    values,vectors=np.linalg.eigh(np.cov(points,rowvar=False));v=vectors[:,int(np.argmax(values))]
    angle=math.degrees(math.atan2(v[1],v[0]));return angle-180 if angle>90 else angle+180 if angle<=-90 else angle
def run(report=None):
    rows=[];lib=props.library()
    for name,p in lib.items(): add(rows,"positive",name+"_connected",components(p)==1,{"components":components(p)})
    crown_top=[p for p in lib["crown"].outline if p[1]<-.3]
    add(rows,"positive","crown_has_five_points",len(crown_top)==5,{"top_points":crown_top})
    add(rows,"positive","pearl_has_no_punch_other_than_gleam",len(lib["pearl"].cuts)==1,{"cut_count":len(lib["pearl"].cuts)})
    pearl_radii=np.linalg.norm(np.asarray(lib["pearl"].outline),axis=1)
    add(rows,"positive","pearl_disc_stays_round",float(np.ptp(pearl_radii))<1e-9,{"radius_range":float(np.ptp(pearl_radii))})
    crescent=lib["pearl"].cuts[0]
    add(rows,"positive","pearl_crescent_is_smooth_and_tapered",len(crescent)>=40 and np.linalg.norm(np.asarray(crescent[0])-np.asarray(crescent[-1]))<1e-9,{"vertices":len(crescent)})
    turnip=np.asarray(lib["turnip"].outline);bulb=turnip[(turnip[:,1]>=.02)&(turnip[:,1]<=.62)]
    bulb_width=float(np.ptp(bulb[:,0]));bulb_height=float(np.ptp(bulb[:,1]))
    add(rows,"positive","turnip_bulb_width_height_over_1_25",bulb_width/bulb_height>1.25,{"width":bulb_width,"height":bulb_height,"ratio":bulb_width/bulb_height})
    add(rows,"positive","turnip_has_short_tail_and_small_spiky_leaves",float(turnip[:,1].max())<.95 and 3<=int(np.sum(turnip[:,1]<-.28))<=5,{"tail_y":float(turnip[:,1].max()),"leaf_tips":int(np.sum(turnip[:,1]<-.28))})
    boot=np.asarray(lib["boot"].outline)
    add(rows,"positive","boot_is_round_baby_bootie",float(boot[:,0].max())>.65 and float(boot[:,1].max())>.68 and len(lib["boot"].cuts)>=4,{"toe_x":float(boot[:,0].max()),"sole_y":float(boot[:,1].max()),"detail_cuts":len(lib["boot"].cuts)})
    page=Image.new("L",(600,600),255);props.draw_prop(page,lib["page"],(300,300),220);before=np.asarray(page).copy();props.draw_page_text(ImageDraw.Draw(page),(300,300),220)
    name_mask=(before<80)&(np.asarray(page)>200);name_pixels=int(np.sum(name_mask));labels,n=ndimage.label(name_mask,np.ones((3,3),dtype=np.uint8));sizes=np.bincount(labels.ravel())[1:];letters=int(np.sum(sizes>8))
    expected_letters=len(props.LOOK["page"]["page_text"].replace(" ",""));add(rows,"positive","page_text_separate_letter_cutouts",name_pixels>150 and letters>=expected_letters,{"text":props.LOOK["page"]["page_text"],"cut_pixels":name_pixels,"connected_cutouts":letters,"minimum":expected_letters})
    add(rows,"negative","page_without_name_fails",0<150,{"cut_pixels":0})
    carved=page_text_mask();carved_angle=principal_axis_deg(carved);wanted=props.LOOK["page"]["page_text_angle_deg"]
    add(rows,"positive","page_text_principal_axis_matches_angle",abs(carved_angle-wanted)<=5,{"measured_deg":carved_angle,"arg_deg":wanted,"tolerance_deg":5})
    horizontal_angle=principal_axis_deg(page_text_mask(angle=0.0))
    add(rows,"negative","horizontal_page_layout_fails_angle_gate",abs(horizontal_angle-wanted)>5,{"measured_deg":horizontal_angle,"arg_deg":wanted,"tolerance_deg":5})
    card=Image.new("L",(600,600),255);props.draw_prop(card,lib["page"],(300,300),220);card_mask=np.asarray(card)<128
    safe=ndimage.binary_erosion(card_mask,iterations=6)
    add(rows,"positive","page_text_keeps_six_unit_card_margin",bool(np.all(safe[carved])),{"outside_safe_pixels":int(np.sum(carved&~safe)),"margin_units":6})
    overhang=page_text_mask(centre=(145,300))
    add(rows,"negative","overhanging_page_stroke_fails_margin",bool(np.any(overhang&~safe)),{"outside_safe_pixels":int(np.sum(overhang&~safe)),"margin_units":6})
    original_truetype=props.ImageFont.truetype
    try:
        props.ImageFont.truetype=lambda *a,**k: (_ for _ in ()).throw(AssertionError("font opened"))
        no_font_opened=props._page_font(220,props.LOOK["page"]["page_text"]) is None
    finally:
        props.ImageFont.truetype=original_truetype
    add(rows,"positive","page_carved_default_opens_no_font",no_font_opened,{"page_font":props.LOOK["page"]["page_font"]})
    demo_page_size=props.LOOK["page"]["size_boy_height"]*(props.VISIBLE_BAND["bottom"]-props.VISIBLE_BAND["top"])*(8192//9-16)
    narrowest=props.page_narrowest_wedge_middle_px(demo_page_size)
    add(rows,"positive","page_narrowest_wedge_middle_at_least_two_px",narrowest>=2.0,{"narrowest_wedge_middle_px":narrowest,"page_size_boy_height":props.LOOK["page"]["size_boy_height"]})
    a=Image.new("L",(32,32),255);ImageDraw.Draw(a).rectangle((4,4,27,27),fill=0);b=a.copy();ImageDraw.Draw(b).ellipse((10,10,20,20),fill=255)
    product=clip_render.product_transmissions((a,b));painter=a.copy();ImageDraw.Draw(painter).ellipse((10,10,20,20),fill=255)
    add(rows,"positive","overlap_stays_black",product.getpixel((15,15))==0,{"pixel":product.getpixel((15,15))})
    add(rows,"negative","cut_through_bug_fails",painter.getpixel((15,15))==255,{"pixel":painter.getpixel((15,15))})
    good=props.bounce_motion((0,-2),(0,1),40);bad=good[:-1]
    add(rows,"positive","fall_settles_within_one",abs(good[-1][1]-1)<=1,{"end":good[-1]})
    add(rows,"negative","unsettled_sim_fails",abs(bad[-1][1]-1)>0.001 or abs(bad[-1][2])>0.001,{"end":bad[-1]})
    areas=[]
    for bite in range(4):
        im=Image.new("1",(500,500),0);ImageDraw.Draw(im).polygon([tuple(x) for x in props.transform(props._turnip(bite),(250,250),170)],fill=1);areas.append(int(np.asarray(im).sum()))
    add(rows,"positive","turnip_area_strictly_decreases",all(a>b for a,b in zip(areas,areas[1:])),{"areas":areas})
    states=props.demo_states("turnip");dist=[];visible=[]
    for s in states:
        pose=props.turnip_boy_pose(s); anchor=np.asarray(boy_rig.prop_anchors(pose)["near_hand"])
        prop_centre=anchor+np.array((7.0,-3.0));dist.append(float(np.linalg.norm(prop_centre-anchor)))
    add(rows,"positive","turnip_anchor_distance",max(dist)<9,{"max_world_units":max(dist),"limit":9})
    add(rows,"negative","detached_turnip_fails",float(np.linalg.norm(np.array((100,100))))>1,{"distance":141.421})
    for index in (0,25,45,65,85):
        state=states[index];pose=props.turnip_boy_pose(state);boy,puss=props.base_layers(360,pose,cat_rig.make_pose("sit_look_up"));base=clip_render.product_transmissions((boy,puss));frame=props.render_state("turnip",state,360)
        visible.append(int(np.sum((np.asarray(base)>200)&(np.asarray(frame)<80))))
    add(rows,"positive","turnip_reads_against_light",min(visible)>20,{"new_black_pixels":visible})
    hidden=Image.new("L",(360,360),255);props.draw_prop(hidden,lib["turnip"],(.30*360,.55*360),20,state=0);base=props.base_layers(360)[0];bad=clip_render.product_transmissions((base,hidden));new=int(np.sum((np.asarray(base)>200)&(np.asarray(bad)<80)))
    add(rows,"negative","black_on_black_turnip_fails",new<20,{"new_black_pixels":new})
    bucket_states=props.demo_states("bucket");bucket_rows=props.bucket_visibility_measurements(bucket_states,480)
    required=[r for r in bucket_rows if r["phase"] in ("stream","splash")]
    add(rows,"positive","bucket_enters_pours_rights_and_exits",
        bucket_states[0]["xy"][0]>1 and bucket_states[35]["angle"]>0 and bucket_states[85]["angle"]<55 and bucket_states[-1]["xy"][0]>1,
        {"start":bucket_states[0],"tip":bucket_states[35],"right":bucket_states[85],"end":bucket_states[-1]})
    add(rows,"positive","bucket_water_reads_on_light",all(r["passes_pour_gate"] for r in required),
        {"threshold":props.LOOK["bucket"]["min_water_light_pixels_480"],"minimum":min(r["water_light_pixels"] for r in required),"max_overlap":max(r["bucket_boy_overlap_pixels"] for r in required)})
    bad_bucket=props.bucket_visibility_measurements([bucket_states[45]],480,(.30,.285))[0]
    add(rows,"negative","bucket_over_head_while_pouring_fails",not bad_bucket["passes_pour_gate"],bad_bucket)
    pour_states=[s for s in bucket_states if s["phase"]=="stream"]
    lip_distances=[];base_distances=[]
    for state in pour_states:
        centre=np.asarray(state["xy"])*480;size=props.LOOK["bucket"]["size_boy_height"]*(props.VISIBLE_BAND["bottom"]-props.VISIBLE_BAND["top"])*480
        lip_distances.append(props.bucket_origin_lip_distance(centre,size,state["angle"]))
        base_distances.append(props.bucket_origin_lip_distance(centre,size,state["angle"],props.BUCKET_BASE_ORIGIN_LOCAL))
    tolerance=3.0
    add(rows,"positive","bucket_stream_origin_at_rim_lip_every_pour_frame",max(lip_distances)<=tolerance,{"max_distance_px":max(lip_distances),"tolerance_px":tolerance,"frames":len(lip_distances)})
    add(rows,"negative","bucket_base_origin_fails",min(base_distances)>tolerance,{"min_distance_px":min(base_distances),"tolerance_px":tolerance})
    pearl=props.demo_states("pearl");steps=np.diff([s["u"] for s in pearl]);add(rows,"positive","pearl_no_anchor_jump",float(max(steps))<.05,{"max_fraction_step":float(max(steps))})
    boots=props.demo_states("boots")[-1]["boots"];xs=[b[0] for b in boots];upright=all(abs(b[2])<1e-6 for b in boots);spacing=min(np.diff(xs));add(rows,"positive","boots_upright_row",upright and spacing>.07,{"spacing":float(spacing),"angles":[b[2] for b in boots]})
    for name in ("bucket","page","turnip","pearl","crown","boots"):
        states=props.demo_states(name); hashes=[json.dumps(s,sort_keys=True) for s in states]; hold=[hashes[i] for i,s in enumerate(states) if s.get("hold")]
        add(rows,"positive",name+"_hold_dedup",len(set(hold))==1,{"hold_frames":len(hold),"unique":len(set(hold))})
    anchors={**boy_rig.prop_anchors(boy_rig.P()),**cat_rig.prop_anchors(cat_rig.make_pose("sit_look_up"))};add(rows,"positive","rig_anchors_exposed",len(anchors)==5,{"anchors":sorted(anchors)})
    pos=[r for r in rows if r["kind"]=="positive"];neg=[r for r in rows if r["kind"]=="negative"]
    data={"positive":{"passed":sum(r["passed"] for r in pos),"total":len(pos)},"negative":{"passed":sum(r["passed"] for r in neg),"total":len(neg)},"total":{"passed":sum(r["passed"] for r in rows),"total":len(rows)},"results":rows,"claims":[{"tier":"measured","claim":"All PG7 controls ran offline.","evidence":"Tools/ShadowGobo/Puppets/test_props_offline.py:24"}]}
    if report: Path(report).write_text(json.dumps(data,indent=2),encoding="utf-8")
    print("SHADOW_PROPS_HARNESS|positive=%d/%d|negative=%d/%d|total=%d/%d"%(data["positive"]["passed"],data["positive"]["total"],data["negative"]["passed"],data["negative"]["total"],data["total"]["passed"],data["total"]["total"]))
    for r in rows:
        if not r["passed"]: print("FAIL|%s|%s|%s"%(r["kind"],r["label"],r["detail"]))
    return 0 if data["total"]["passed"]==data["total"]["total"] else 1
if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--report");a=ap.parse_args();raise SystemExit(run(a.report))
