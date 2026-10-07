import json,sys
a=json.load(open(sys.argv[1]));b=json.load(open(sys.argv[2]))
A={r["path"]:r for r in a["rows"]};B={r["path"]:r for r in b["rows"]}
for k in sorted(set(A)-set(B)): print("REMOVED",A[k]["cls"],k)
for k in sorted(set(B)-set(A)): print("ADDED",B[k]["cls"],k, json.dumps({x:y for x,y in B[k]["props"].items() if not isinstance(y,dict) or "n" in y or "sub" in y})[:600])
for k in sorted(set(A)&set(B)):
  pa,pb=A[k]["props"],B[k]["props"]
  if pa!=pb:
    for x in sorted(set(pa)|set(pb)):
      if pa.get(x)!=pb.get(x):
        print("CHANGED",A[k]["cls"],k,x,"\n   was",json.dumps(pa.get(x))[:500],"\n   now",json.dumps(pb.get(x))[:500])
