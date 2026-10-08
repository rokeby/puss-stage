"""OFFLINE numpy/scipy: exact point-to-triangle distance from query points to a large triangle mesh, with a sign.

dist(points) -> (unsigned cm, signed cm, closest point).  Candidates = every triangle touching any of the K nearest
mesh VERTICES (cKDTree, K = 8); the exact closest point on each candidate (Ericson, Real-Time Collision Detection 5.1.5) is
taken.  Sign = side of the winning triangle's face normal (positive = the side the normal points to).  The shells'
normals point OUT of the shell material [meas: sign_sanity() in validate_slime.py], so a NEGATIVE distance means the
point is inside shell material.  With the shells' ~0.2 cm vertex spacing, K = 8 covers the true nearest triangle
for points within a few cm of the surface [inf: not proven for every geometry; the exactness check in
validate_slime.py compares against brute force on a random subset].
"""
import numpy as np
from scipy.spatial import cKDTree


class Surface:
    def __init__(self, verts, tris, k=8):
        self.v = np.asarray(verts, float)
        self.t = np.asarray(tris, np.int64)
        self.k = k
        self.tree = cKDTree(self.v)
        n = len(self.v)
        order = np.argsort(self.t.ravel(), kind="stable")
        vid = self.t.ravel()[order]
        self.adj_tri = order // 3
        self.adj_ptr = np.searchsorted(vid, np.arange(n + 1))
        a, b, c = self.v[self.t[:, 0]], self.v[self.t[:, 1]], self.v[self.t[:, 2]]
        fn = np.cross(b - a, c - a)
        ln = np.linalg.norm(fn, axis=1)
        ln[ln == 0] = 1.0
        self.fn = fn / ln[:, None]

    def _padded_adjacency(self):
        if getattr(self, "_adj", None) is None:
            val = np.diff(self.adj_ptr)
            m = int(val.max())
            adj = np.full((len(val), m), -1, np.int64)
            for j in range(m):
                has = val > j
                adj[has, j] = self.adj_tri[self.adj_ptr[:-1][has] + j]
            self._adj = adj
        return self._adj

    def dist(self, points, chunk=4000):
        """Vectorised: K nearest vertices -> their incident triangles (padded) -> exact closest points."""
        ud, sd, cp, _n = self.closest(points, chunk)
        return ud, sd, cp

    def closest(self, points, chunk=4000):
        """-> (unsigned, signed, closest point, unit outward normal there)."""
        P = np.atleast_2d(np.asarray(points, float))
        adj = self._padded_adjacency()
        ud = np.empty(len(P))
        sd = np.empty(len(P))
        cp = np.empty_like(P)
        nn = np.empty_like(P)
        for s0 in range(0, len(P), chunk):
            Q = P[s0:s0 + chunk]
            _d, idx = self.tree.query(Q, k=self.k)
            cand = adj[idx].reshape(len(Q), -1)                       # (n, K*valence), -1 padded
            valid = cand >= 0
            cs = np.where(valid, cand, 0)
            a = self.v[self.t[cs, 0]]
            b = self.v[self.t[cs, 1]]
            c = self.v[self.t[cs, 2]]
            n, m = cs.shape
            q = closest_on_tris(np.repeat(Q, m, axis=0), a.reshape(-1, 3), b.reshape(-1, 3),
                                c.reshape(-1, 3)).reshape(n, m, 3)
            dd = np.linalg.norm(q - Q[:, None, :], axis=2)
            dd[~valid] = np.inf
            j = np.argmin(dd, axis=1)
            best = dd[np.arange(n), j]
            near = (dd <= best[:, None] + 1e-6) & valid
            nrm = (self.fn[cs] * near[:, :, None]).sum(axis=1)       # edge/vertex case: average incident normals
            qb = q[np.arange(n), j]
            side = np.einsum("ij,ij->i", Q - qb, nrm)
            ud[s0:s0 + chunk] = best
            sd[s0:s0 + chunk] = np.where(side >= 0, best, -best)
            cp[s0:s0 + chunk] = qb
            nn[s0:s0 + chunk] = nrm / np.maximum(np.linalg.norm(nrm, axis=1), 1e-12)[:, None]
        return ud, sd, cp, nn


def closest_on_tris(p, a, b, c):
    """Closest points on triangles (a,b,c arrays (n,3)) to point(s) p ((3,) or (n,3)) (Ericson 5.1.5), vectorised."""
    ab, ac, ap = b - a, c - a, p - a
    d1 = np.einsum("ij,ij->i", ab, ap)
    d2 = np.einsum("ij,ij->i", ac, ap)
    bp = p - b
    d3 = np.einsum("ij,ij->i", ab, bp)
    d4 = np.einsum("ij,ij->i", ac, bp)
    cpp = p - c
    d5 = np.einsum("ij,ij->i", ab, cpp)
    d6 = np.einsum("ij,ij->i", ac, cpp)
    va = d3 * d6 - d5 * d4
    vb = d5 * d2 - d1 * d6
    vc = d1 * d4 - d3 * d2
    out = np.empty_like(a)
    done = np.zeros(len(a), bool)

    def put(mask, val):
        m = mask & ~done
        out[m] = val[m] if val.ndim == 2 else val
        done[:] = done | m
    put((d1 <= 0) & (d2 <= 0), a)
    put((d3 >= 0) & (d4 <= d3), b)
    with np.errstate(divide="ignore", invalid="ignore"):
        v = d1 / (d1 - d3)
        put((vc <= 0) & (d1 >= 0) & (d3 <= 0), a + v[:, None] * ab)
        put((d6 >= 0) & (d5 <= d6), c)
        w = d2 / (d2 - d6)
        put((vb <= 0) & (d2 >= 0) & (d6 <= 0), a + w[:, None] * ac)
        w2 = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        put((va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0), b + w2[:, None] * (c - b))
        den = 1.0 / (va + vb + vc)
        vv, ww = vb * den, vc * den
        put(np.ones(len(a), bool), a + ab * vv[:, None] + ac * ww[:, None])
    return out


class Solid(Surface):
    """A WATERTIGHT triangle mesh as a solid: inside(points) by ray parity along +Z (xy grid of triangles).
    The shells are closed [meas 8 Oct: bottom 0 boundary edges; lid 2 boundary edges + 1 non-manifold edge out of
    1.56 M].  The query xy is nudged by an irrational offset so the vertical ray never runs exactly through an edge
    or vertex [inf: probability-zero degeneracy, not excluded by proof]."""
    CELL = 1.0
    NUDGE = np.array([1.3e-5 * np.sqrt(2.0), 0.7e-5 * np.sqrt(3.0)])

    def __init__(self, verts, tris, k=8):
        Surface.__init__(self, verts, tris, k)
        a, b, c = self.v[self.t[:, 0]], self.v[self.t[:, 1]], self.v[self.t[:, 2]]
        lo = np.minimum(np.minimum(a, b), c)[:, :2]
        hi = np.maximum(np.maximum(a, b), c)[:, :2]
        self.origin = lo.min(axis=0) - 1.0
        i0 = np.floor((lo - self.origin) / self.CELL).astype(np.int64)
        i1 = np.floor((hi - self.origin) / self.CELL).astype(np.int64)
        self.ny = int(i1[:, 1].max()) + 2
        cells, tri = [], []
        span = (i1 - i0 + 1)
        for dx in range(int(span[:, 0].max())):
            for dy in range(int(span[:, 1].max())):
                m = (span[:, 0] > dx) & (span[:, 1] > dy)
                cells.append((i0[m, 0] + dx) * self.ny + (i0[m, 1] + dy))
                tri.append(np.nonzero(m)[0])
        cells, tri = np.concatenate(cells), np.concatenate(tri)
        o = np.argsort(cells, kind="stable")
        self.cell_keys, self.cell_tris = cells[o], tri[o]

    def inside(self, points):
        P = np.atleast_2d(np.asarray(points, float)).copy()
        P[:, :2] += self.NUDGE
        ij = np.floor((P[:, :2] - self.origin) / self.CELL).astype(np.int64)
        key = ij[:, 0] * self.ny + ij[:, 1]
        out = np.zeros(len(P), bool)
        for kk in np.unique(key):
            lo = np.searchsorted(self.cell_keys, kk, side="left")
            hi = np.searchsorted(self.cell_keys, kk, side="right")
            if hi == lo:
                continue
            tri = self.cell_tris[lo:hi]
            q = P[key == kk]
            a, b, c = self.v[self.t[tri, 0]], self.v[self.t[tri, 1]], self.v[self.t[tri, 2]]
            # 2D barycentric of every query xy in every candidate triangle
            v0 = (b - a)[None, :, :2]
            v1 = (c - a)[None, :, :2]
            v2 = q[:, None, :2] - a[None, :, :2]
            den = v0[..., 0] * v1[..., 1] - v1[..., 0] * v0[..., 1]
            with np.errstate(divide="ignore", invalid="ignore"):
                u = (v2[..., 0] * v1[..., 1] - v1[..., 0] * v2[..., 1]) / den
                w = (v0[..., 0] * v2[..., 1] - v2[..., 0] * v0[..., 1]) / den
                hit = (den != 0) & (u >= 0) & (w >= 0) & (u + w <= 1)
                z = a[None, :, 2] + u * (b - a)[None, :, 2] + w * (c - a)[None, :, 2]
            cross = hit & (z > q[:, None, 2])
            out[key == kk] = (cross.sum(axis=1) % 2) == 1
        return out

    def depth(self, points):
        """cm inside the solid (0 outside) = unsigned distance to the surface for inside points."""
        ins = self.inside(points)
        d = np.zeros(len(ins))
        if ins.any():
            u, _s, _c = self.dist(np.atleast_2d(points)[ins])
            d[ins] = u
        return d
