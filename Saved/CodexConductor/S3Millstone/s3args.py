import json,sys,datetime
p="Saved/CodexConductor/S3Millstone/s3_props_args.json"
d=json.loads(sys.argv[1]); d["run"]="S3PROPS-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
json.dump(d,open(p,"w",encoding="utf-8"),indent=1); print(d["run"])
