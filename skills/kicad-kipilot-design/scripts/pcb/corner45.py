#!/usr/bin/env python3
"""corner45.py in.kicad_pcb --check             : lista esquinas y T a 90 grados (sale con 1 si hay)
   corner45.py in.kicad_pcb --fix out.kicad_pcb : las reemplaza por chaflanes de 45 grados."""
import sys, math, pcbnew
from pcbnew import FromMM as mm
EPS = 0.005
def L(s): return math.hypot(s[1][0]-s[0][0], s[1][1]-s[0][1])
def eq(p, q): return abs(p[0]-q[0]) < EPS and abs(p[1]-q[1]) < EPS
def unit(p, q):
    l = math.hypot(q[0]-p[0], q[1]-p[1]); return ((q[0]-p[0])/l, (q[1]-p[1])/l)
def perp(u, v): return abs(u[0]*v[0] + u[1]*v[1]) < 0.02

def issues(S):
    out = []
    for i in range(len(S)):
        if L(S[i]) < EPS: continue
        for ei in (0, 1):
            P = S[i][ei]; ui = unit(P, S[i][1-ei])
            same = [(j, ej) for j in range(len(S)) if j != i and S[j][3] == S[i][3] and S[j][4] == S[i][4]
                    for ej in (0, 1) if eq(S[j][ej], P) and L(S[j]) > EPS]
            if len(same) == 1:
                j, ej = same[0]
                if i < j and perp(ui, unit(P, S[j][1-ej])): out.append(("C", i, ei, j, ej, P))
            for j in range(len(S)):
                if j == i or S[j][3] != S[i][3] or S[j][4] != S[i][4] or L(S[j]) < EPS: continue
                a, c = S[j][0], S[j][1]; lj = L(S[j])
                t = ((P[0]-a[0])*(c[0]-a[0]) + (P[1]-a[1])*(c[1]-a[1])) / (lj*lj)
                if 0.002 < t < 0.998 and abs((P[0]-a[0])*(c[1]-a[1]) - (P[1]-a[1])*(c[0]-a[0])) / lj < EPS \
                        and perp(ui, unit(a, c)):
                    out.append(("T", i, ei, j, None, P))
    return out

def cleanup(S, mn=0.07):
    """elimina microtramos fusionando sus extremos"""
    ch = True
    while ch:
        ch = False
        for k, s_ in enumerate(S):
            if L(s_) < mn:
                a, c = s_[0], s_[1]
                for o in S:
                    if o is s_: continue
                    for e in (0, 1):
                        if math.hypot(o[e][0]-c[0], o[e][1]-c[1]) < 0.02: o[e] = a
                S.pop(k); ch = True; break
    return S

def merge_collinear(S):
    ch = True
    while ch:
        ch = False
        for i in range(len(S)):
            for ei in (0, 1):
                P = S[i][ei]
                same = [(j, ej) for j in range(len(S)) if j != i and S[j][2:5] == S[i][2:5]
                        for ej in (0, 1) if eq(S[j][ej], P)]
                if len(same) != 1: continue
                allhere = [k for k in range(len(S)) if any(eq(S[k][e], P) for e in (0, 1))]
                if len(allhere) != 2: continue
                j, ej = same[0]
                if L(S[i]) < EPS or L(S[j]) < EPS: continue
                u = unit(P, S[i][1-ei]); v = unit(P, S[j][1-ej])
                if u[0]*v[0] + u[1]*v[1] < -0.9995:   # colineales opuestas
                    S[i][ei] = S[j][1-ej]; S.pop(j); ch = True; break
            if ch: break
    return S

def load(b):
    mmv = lambda p: (pcbnew.ToMM(p.x), pcbnew.ToMM(p.y))
    return [[mmv(t.GetStart()), mmv(t.GetEnd()), pcbnew.ToMM(t.GetWidth()), t.GetLayer(), t.GetNetCode()]
            for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"]

def fix(S, dmax=0.6):
    skipped = []
    for _ in range(3000):
        todo = [x for x in issues(S) if not any(eq(x[5], q) for q in skipped)]
        if not todo: break
        kind, i, ei, j, ej, P = todo[0]
        if kind == "C":
            d = min(dmax, 0.45 * L(S[i]), 0.45 * L(S[j]))
            if d < 0.08: skipped.append(P); continue
            ui = unit(P, S[i][1-ei]); uj = unit(P, S[j][1-ej])
            A = (P[0]+ui[0]*d, P[1]+ui[1]*d); B = (P[0]+uj[0]*d, P[1]+uj[1]*d)
            S[i][ei] = A; S[j][ej] = B
            S.append([A, B, S[i][2], S[i][3], S[i][4]])
        else:
            ub = unit(P, S[i][1-ei]); a, c = S[j][0], S[j][1]; ut = unit(a, c)
            ra = math.hypot(P[0]-a[0], P[1]-a[1]); rc = math.hypot(P[0]-c[0], P[1]-c[1])
            room, sg = (rc, 1) if rc >= ra else (ra, -1)
            d = min(dmax, 0.45 * L(S[i]), 0.9 * room)
            if d < 0.08: skipped.append(P); continue
            A = (P[0]+ub[0]*d, P[1]+ub[1]*d); R = (P[0]+sg*ut[0]*d, P[1]+sg*ut[1]*d)
            S[i][ei] = A
            S.append([A, R, S[i][2], S[i][3], S[i][4]])
    return S, skipped

if __name__ == "__main__":
    b = pcbnew.LoadBoard(sys.argv[1]); S = load(b)
    if sys.argv[2] == "--check":
        iss = issues(S)
        for k in iss: print("  %s90 en (%.2f, %.2f) capa %d red %d" % (k[0], k[5][0], k[5][1], S[k[1]][3], S[k[1]][4]))
        print("TOTAL 90 grados:", len(iss), "| segmentos:", len(S)); sys.exit(1 if iss else 0)
    S = merge_collinear(cleanup(S)); S, sk = fix(S); S = merge_collinear(cleanup(S)); S, sk = fix(S); S = merge_collinear(cleanup(S))
    for t in [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"]: b.Delete(t)
    nets = {n.GetNetCode(): n for n in b.GetNetInfo().NetsByNetcode().values()}
    for a, c, w, lay, nc in S:
        if math.hypot(c[0]-a[0], c[1]-a[1]) < 0.001: continue
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1]))); t.SetEnd(pcbnew.VECTOR2I(mm(c[0]), mm(c[1])))
        t.SetWidth(mm(w)); t.SetLayer(lay); t.SetNet(nets[nc]); b.Add(t)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(sys.argv[3]); print("chaflanes aplicados; segmentos:", len(S), "| sin resolver:", len(sk), sk[:5])
