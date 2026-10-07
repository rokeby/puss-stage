"""Decode the tagged BoolCurve of every visibility section in a LevelSequence. Read-only."""
import struct, sys
sys.path.insert(0, '.')
import s3_seq_sem as S
m = S.Model(sys.argv[1]); p = m.p
for i in range(1, len(p.exports) + 1):
    if p.cls(i) != 'MovieSceneVisibilitySection':
        continue
    e = p.exports[i - 1]; data = p.b[e['so']:e['so'] + e['ss']]
    r = S.V.R(data); ctl = r.raw(1)[0]
    if ctl & 2: r.raw(1)
    out = {}
    while r.o < len(data):
        tg = S.read_tag(p, r)
        if tg is None: break
        out[tg[0]] = tg
    rng = S.V.frange(out['SectionRange'][4]) if 'SectionRange' in out else None
    sub, _ = S.tags_until_none(p, out['BoolCurve'][4])
    d = {t[0]: t for t in sub}
    tv = d['Times'][4]; n = struct.unpack_from('<i', tv, 0)[0]; times = list(struct.unpack_from('<%di' % n, tv, 4))
    vv = d['Values'][4]; nv = struct.unpack_from('<i', vv, 0)[0]; vals = [bool(b) for b in vv[4:4 + nv]]
    extra = {k: (v[4].hex(), v[2]) for k, v in d.items() if k not in ('Times', 'Values')}
    owner = p.path(i).split('.')[2]
    print(owner, 'range', rng, 'keys', list(zip(times, vals)), 'extra', extra, 'evalopts' if 'EvalOptions' in out else 'no-evalopts')
