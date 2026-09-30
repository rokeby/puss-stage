import json, re, collections, sys
L = open('E:/PussStage/Saved/Logs/PussStage.log', encoding='utf-8', errors='replace').read().splitlines()
b = max(i for i, l in enumerate(L) if 'PUSS_WING_LISTTEXTURES_BEGIN' in l)
e = max(i for i, l in enumerate(L) if 'PUSS_WING_LISTTEXTURES_END' in l)
listed = {}
for l in L[b:e]:
    m = re.search(r'\](\d+)x(\d+) \((\d+) KB, [-\d]+\), (\d+)x(\d+) \((\d+) KB\), (\w+), (\w+), (\S+?)\.\S+, (\w+), (\w+), (\w+), (\d+), (\d+), (\w+)', l)
    if m:
        listed[m.group(9)] = {"size": [int(m.group(1)), int(m.group(2))], "kb": int(m.group(6)), "format": m.group(7), "mips": int(m.group(14))}
targets = json.load(open('mips_rollback.json'))
got = {t: listed.get(t) for t in targets}
missing = [t for t, v in got.items() if v is None]
mips = collections.Counter(v["mips"] for v in got.values() if v)
print('targets', len(targets), '| listed', len(targets) - len(missing), '| not loaded/listed', len(missing))
print('mip counts:', dict(sorted(mips.items())))
one = [t for t, v in got.items() if v and v["mips"] == 1]
print('still 1 mip:', len(one), one[:5])
json.dump(got, open('mips_readback.json', 'w'), indent=1)
