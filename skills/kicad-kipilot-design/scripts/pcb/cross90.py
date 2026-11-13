#!/usr/bin/env python3
"""Regla de cruces para redes PWM / alta frecuencia: cuando una pista de esas redes pasa por encima de otra en
otra capa, el cruce tiene que ser a 90 grados (minimo acoplamiento). Freerouting no lo respeta, asi que se
verifica y se corrige despues del ruteo.

    python cross90.py placa.kicad_pcb layout.json            -> lista cruces fuera de regla (sale 1 si hay)
    python cross90.py placa.kicad_pcb layout.json --fix out  -> los corrige con un desvio local y guarda

layout.json:
  "hf_nets": ["PWM*", "CLK", "SW_NODE"],     # nombres o patrones (con o sin "/" inicial)
  "hf_cross": {"modo": "ambas", "tol_grados": 2, "h": 0.6}
     modo "ambas": solo cruces entre dos redes HF (lo pedido por defecto);
     modo "alguna": cualquier cruce donde al menos una red sea HF.
Correccion: la pista que se modifica da un desvio en S (sin esquinas a 90 grados) para cruzar la otra en
perpendicular a lo largo de 2*h mm. Cada desvio se valida con el DRC de KiCad (separaciones, cortos, cruces en
la misma capa); si empeora el DRC se deshace y el cruce queda informado como "sin resolver"."""
import sys, os, math, json, fnmatch, tempfile, re, subprocess, collections
import pcbnew
from pcbnew import FromMM as mm

def _n(name): return str(name).lstrip("/")

def hf_matcher(patterns):
    pats = [_n(p) for p in patterns]
    return lambda net: any(fnmatch.fnmatchcase(_n(net), p) for p in pats)

def _segs(b):
    out = []
    for t in b.GetTracks():
        if t.GetClass() != "PCB_TRACK": continue
        a, c = t.GetStart(), t.GetEnd()
        out.append((t, (pcbnew.ToMM(a.x), pcbnew.ToMM(a.y)), (pcbnew.ToMM(c.x), pcbnew.ToMM(c.y))))
    return out

def _inter(p1, p2, q1, q2, eps=1e-6):
    """interseccion propia (interior de ambos segmentos); devuelve (P, t, u) o None"""
    r = (p2[0] - p1[0], p2[1] - p1[1]); s = (q2[0] - q1[0], q2[1] - q1[1])
    den = r[0] * s[1] - r[1] * s[0]
    if abs(den) < eps: return None
    w = (q1[0] - p1[0], q1[1] - p1[1])
    t = (w[0] * s[1] - w[1] * s[0]) / den; u = (w[0] * r[1] - w[1] * r[0]) / den
    if 0.001 < t < 0.999 and 0.001 < u < 0.999:
        return (p1[0] + t * r[0], p1[1] + t * r[1]), t, u
    return None

def _ang(p1, p2, q1, q2):
    a = math.atan2(p2[1] - p1[1], p2[0] - p1[0]); c = math.atan2(q2[1] - q1[1], q2[0] - q1[0])
    d = abs(math.degrees(a - c)) % 180
    return min(d, 180 - d)          # 0..90

def crossings(b, is_hf, modo="ambas", tol=2.0):
    S = _segs(b); out = []
    for i in range(len(S)):
        ti, a1, a2 = S[i]
        for j in range(i + 1, len(S)):
            tj, b1, b2 = S[j]
            if ti.GetLayer() == tj.GetLayer() or ti.GetNetCode() == tj.GetNetCode(): continue
            hi, hj = is_hf(ti.GetNetname()), is_hf(tj.GetNetname())
            if not ((hi and hj) if modo == "ambas" else (hi or hj)): continue
            r = _inter(a1, a2, b1, b2)
            if not r: continue
            ang = _ang(a1, a2, b1, b2)
            if abs(90 - ang) > tol:
                out.append({"P": r[0], "ang": ang, "a": ti, "b": tj, "nets": (_n(ti.GetNetname()), _n(tj.GetNetname()))})
    return out

SEVERE = ("clearance", "shorting_items", "tracks_crossing", "hole_clearance", "copper_edge_clearance", "via_dangling")

_DRC = ("import sys, pcbnew\nb = pcbnew.LoadBoard(sys.argv[1])\n"
        "if len(list(b.Zones())): pcbnew.ZONE_FILLER(b).Fill(b.Zones())\n"
        "pcbnew.WriteDRCReport(b, sys.argv[2], pcbnew.EDA_UNITS_MILLIMETRES, True)\n")

def drc_count(b):
    """DRC en un proceso aparte sobre una copia guardada: el DRC en memoria tras borrar pistas hace segfault en pcbnew 7"""
    d = tempfile.mkdtemp(); f = os.path.join(d, "t.kicad_pcb"); rpt = os.path.join(d, "drc.rpt")
    b.Save(f); subprocess.run([sys.executable, "-c", _DRC, f, rpt], check=True, capture_output=True)
    txt = open(rpt, errors="ignore").read()
    sev = sum(len(re.findall(r"^\[" + k + r"\]", txt, re.M)) for k in SEVERE)
    m = re.search(r"Found (\d+) unconnected", txt)
    return sev + (int(m.group(1)) if m else 0)

def _pt(v): return (pcbnew.ToMM(v.x), pcbnew.ToMM(v.y))
def _k(p): return (round(p[0], 3), round(p[1], 3))

def _cadena(b, mover):
    """tramos consecutivos de la misma red y capa que pasan por 'mover', sin atravesar pads ni vias.
    Devuelve (puntos ordenados, pistas en orden)."""
    lay, net = mover.GetLayer(), mover.GetNetCode()
    uid = lambda t: t.m_Uuid.AsString()       # pcbnew crea un objeto Python nuevo en cada recorrido: comparar por UUID
    segs = {uid(t): t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetLayer() == lay and t.GetNetCode() == net}
    nodo = collections.defaultdict(list)
    for u, t in segs.items():
        nodo[_k(_pt(t.GetStart()))].append(u); nodo[_k(_pt(t.GetEnd()))].append(u)
    vias = {_k(_pt(v.GetPosition())) for v in b.GetTracks() if v.GetClass() == "PCB_VIA"}
    pads = [pd for pd in b.GetPads() if pd.GetNetCode() == net]
    def tope(p):
        if p in vias or len(nodo[p]) != 2: return True
        v = pcbnew.VECTOR2I(mm(p[0]), mm(p[1]))
        return any(pd.HitTest(v) for pd in pads)
    m0 = uid(mover)
    def andar(u, p):          # desde la pista u saliendo por el punto p
        pts, trs, vistos = [], [], {m0}
        while not tope(p):
            u = [o for o in nodo[p] if o != u][0]
            if u in vistos: break                 # lazo cerrado
            vistos.add(u); t = segs[u]; a, c = _k(_pt(t.GetStart())), _k(_pt(t.GetEnd()))
            p = c if a == p else a; pts.append(p); trs.append(t)
        return pts, trs
    a, c = _k(_pt(mover.GetStart())), _k(_pt(mover.GetEnd()))
    pa, ta = andar(m0, a); pc, tc = andar(m0, c)
    return list(reversed(pa)) + [a, c] + pc, list(reversed(ta)) + [segs[m0]] + tc

def _giro(u, v):
    d = max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1])); return math.degrees(math.acos(d))

def _se_cruzan(p1, p2, q1, q2): return _inter(p1, p2, q1, q2) is not None

MOTIVO = ""

def _jog(b, mover, fixed, P, h, rank=0):
    """desvio en S que cruza 'fixed' en perpendicular; puede recorrer varios tramos de 'mover' (chaflanes)"""
    pts, trs = _cadena(b, mover)
    cum = [0.0]
    for a, c in zip(pts, pts[1:]): cum.append(cum[-1] + math.hypot(c[0] - a[0], c[1] - a[1]))
    i = [t.m_Uuid.AsString() for t in trs].index(mover.m_Uuid.AsString()); arc = cum[i] + math.hypot(P[0] - pts[i][0], P[1] - pts[i][1])
    def en(s):
        for k in range(len(pts) - 1):
            if cum[k] - 1e-9 <= s <= cum[k + 1] + 1e-9:
                l = cum[k + 1] - cum[k]; f = (s - cum[k]) / l if l else 0
                return (pts[k][0] + f * (pts[k + 1][0] - pts[k][0]), pts[k][1] + f * (pts[k + 1][1] - pts[k][1]))
    f1, f2 = _pt(fixed.GetStart()), _pt(fixed.GetEnd()); fa = (f2[0] - f1[0], f2[1] - f1[1]); la = math.hypot(*fa)
    n0 = (-fa[1] / la, fa[0] / la)
    global MOTIVO
    def armar(sa, sb, hh):
        """polilinea con Q1 a 'sa' mm antes de P y Q4 a 'sb' mm despues (medidos sobre la cadena)"""
        if arc - sa < 0.05 or arc + sb > cum[-1] - 0.05: return None, "sin lugar (%.1f/%.1f)" % (arc, cum[-1])
        Q1, Q4 = en(arc - sa), en(arc + sb)
        n = n0 if n0[0] * (P[0] - Q1[0]) + n0[1] * (P[1] - Q1[1]) > 0 else (-n0[0], -n0[1])
        if n[0] * (Q4[0] - P[0]) + n[1] * (Q4[1] - P[1]) <= 0: return None, "no cruza entre Q1 y Q4"
        Q2 = (P[0] - n[0] * hh, P[1] - n[1] * hh); Q3 = (P[0] + n[0] * hh, P[1] + n[1] * hh)
        poly = [p for p, c in zip(pts, cum) if c < arc - sa - 1e-6] + [Q1, Q2, Q3, Q4] + [p for p, c in zip(pts, cum) if c > arc + sb + 1e-6]
        poly = [p for k, p in enumerate(poly) if k == 0 or math.hypot(p[0] - poly[k - 1][0], p[1] - poly[k - 1][1]) > 0.02]
        S = list(zip(poly, poly[1:])); peor = 0
        for k in range(len(S) - 1):                         # sin esquinas de 90 ni giros cerrados
            u = (S[k][1][0] - S[k][0][0], S[k][1][1] - S[k][0][1]); v = (S[k + 1][1][0] - S[k + 1][0][0], S[k + 1][1][1] - S[k + 1][0][1])
            lu, lv = math.hypot(*u), math.hypot(*v); g = _giro((u[0] / lu, u[1] / lu), (v[0] / lv, v[1] / lv))
            if abs(g - 90) < 3 or g > 100: return None, "giro %.0f" % g
            peor = max(peor, g)
        for x in range(len(S)):                             # la pista no se cruza a si misma
            for y in range(x + 2, len(S)):
                if _se_cruzan(S[x][0], S[x][1], S[y][0], S[y][1]): return None, "autocruce"
        return (peor, sa + sb, S), ""
    cands, MOTIVO = [], ""
    pasos = [0.4, 0.7, 1.0, 1.5, 2.0, 3.0, 4.0, 5.5]
    for hh in (h, h * 0.7, h * 0.5, h * 0.35, h * 1.4):
        for sa in pasos:
            for sb in pasos:
                r, why = armar(sa, sb, hh)
                if r is None: MOTIVO = MOTIVO or why; continue
                cands.append(r)
    cands.sort(key=lambda r: (r[0], r[1]))
    vistos, distintos = set(), []                      # alternativas distintas, de la mas suave a la menos
    for r in cands:
        key = tuple((round(a[0], 1), round(a[1], 1)) for a, _ in r[2])
        if key not in vistos: vistos.add(key); distintos.append(r)
    if rank >= len(distintos): return None
    S = distintos[rank][2]
    w, lay, net = mover.GetWidth(), mover.GetLayer(), mover.GetNet()
    orig = [(_pt(t.GetStart()), _pt(t.GetEnd()), w, lay, net) for t in trs]
    for t in trs: b.Delete(t)
    new = []
    for a, c in S:
        t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1]))); t.SetEnd(pcbnew.VECTOR2I(mm(c[0]), mm(c[1])))
        t.SetWidth(w); t.SetLayer(lay); t.SetNet(net); b.Add(t); new.append(t)
    return new, orig, P

def _dist_seg(P, S, E):
    dx, dy = E[0] - S[0], E[1] - S[1]; l2 = dx * dx + dy * dy
    t = 0 if l2 == 0 else max(0, min(1, ((P[0] - S[0]) * dx + (P[1] - S[1]) * dy) / l2))
    return math.hypot(P[0] - S[0] - t * dx, P[1] - S[1] - t * dy)

def _undo(b, new, orig, P):
    for t in new: b.Delete(t)
    rec = []
    for S, E, w, lay, net in orig:
        t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(mm(S[0]), mm(S[1]))); t.SetEnd(pcbnew.VECTOR2I(mm(E[0]), mm(E[1])))
        t.SetWidth(w); t.SetLayer(lay); t.SetNet(net); b.Add(t); rec.append((_dist_seg(P, S, E), t))
    return min(rec, key=lambda x: x[0])[1]    # la pista recreada que pasa por P (el objeto viejo ya no existe)

def fix(b, is_hf, modo="ambas", tol=2.0, h=0.6, log=print):
    base = drc_count(b); done, pend = 0, []
    for _ in range(200):
        todos = crossings(b, is_hf, modo, tol)
        cs = [c for c in todos if not any(math.hypot(c["P"][0] - p[0], c["P"][1] - p[1]) < 0.01 for p, _, _ in pend)]
        if not cs: break
        c = cs[0]; ok = False
        tr = {"a": c["a"], "b": c["b"]}
        for km, kf in (("b", "a"), ("a", "b")):
            for rank in range(12):                 # hasta 12 alternativas por pista antes de rendirse
                r = _jog(b, tr[km], tr[kf], c["P"], h, rank)
                if not r: break
                # el desvio no puede crear cruces nuevos fuera de regla ni empeorar el DRC
                if len(crossings(b, is_hf, modo, tol)) < len(todos):
                    now = drc_count(b)
                    if now <= base:
                        ok = True; base = now; break
                tr[km] = _undo(b, *r)
            if ok: break
        if ok: done += 1
        else: pend.append((c["P"], c["nets"], round(c["ang"], 1)))
    log("cruces HF corregidos: %d | sin resolver: %d %s" % (done, len(pend),
        ["%s x %s en (%.1f, %.1f) a %.0f grados" % (p[1][0], p[1][1], p[0][0], p[0][1], p[2]) for p in pend]))
    return done, pend

def cfg_from_layout(L):
    hc = L.get("hf_cross", {})
    return hf_matcher(L.get("hf_nets", [])), hc.get("modo", "ambas"), hc.get("tol_grados", 2.0), hc.get("h", 0.6)

if __name__ == "__main__":
    b = pcbnew.LoadBoard(sys.argv[1]); L = json.load(open(sys.argv[2])); is_hf, modo, tol, h = cfg_from_layout(L)
    if "--fix" in sys.argv:
        fix(b, is_hf, modo, tol, h); b.Save(sys.argv[sys.argv.index("--fix") + 1])
    else:
        cs = crossings(b, is_hf, modo, tol)
        for c in cs: print("  %s x %s en (%.2f, %.2f): %.1f grados" % (c["nets"][0], c["nets"][1], c["P"][0], c["P"][1], c["ang"]))
        print("cruces HF fuera de regla:", len(cs)); sys.exit(1 if cs else 0)
