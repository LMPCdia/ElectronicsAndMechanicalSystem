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
import sys, os, math, json, fnmatch, tempfile, re, subprocess
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

def _jog(b, mover, fixed, P, h):
    """reemplaza la pista 'mover' por: inicio -> Q1 -> Q2 -> Q3 -> Q4 -> fin, con Q2-Q3 perpendicular a 'fixed'"""
    s0, e0 = mover.GetStart(), mover.GetEnd()
    S = (pcbnew.ToMM(s0.x), pcbnew.ToMM(s0.y)); E = (pcbnew.ToMM(e0.x), pcbnew.ToMM(e0.y))
    f1, f2 = fixed.GetStart(), fixed.GetEnd()
    fa = (pcbnew.ToMM(f2.x) - pcbnew.ToMM(f1.x), pcbnew.ToMM(f2.y) - pcbnew.ToMM(f1.y)); la = math.hypot(*fa)
    L = math.hypot(E[0] - S[0], E[1] - S[1]); ub = ((E[0] - S[0]) / L, (E[1] - S[1]) / L)
    n = (-fa[1] / la, fa[0] / la)
    if n[0] * ub[0] + n[1] * ub[1] < 0: n = (-n[0], -n[1])
    sin_t = n[0] * ub[0] + n[1] * ub[1]                 # = sen(angulo de cruce)
    if sin_t < math.sin(math.radians(15)): return None  # casi paralelas: no se fuerza
    s1 = h * (1 + 2 / sin_t)                            # recorrido sobre la pista original a cada lado
    dS = math.hypot(P[0] - S[0], P[1] - S[1]); dE = math.hypot(P[0] - E[0], P[1] - E[1])
    if dS < s1 + 0.05 or dE < s1 + 0.05: return None    # no hay lugar dentro del segmento
    Q1 = (P[0] - ub[0] * s1, P[1] - ub[1] * s1); Q4 = (P[0] + ub[0] * s1, P[1] + ub[1] * s1)
    Q2 = (P[0] - n[0] * h, P[1] - n[1] * h); Q3 = (P[0] + n[0] * h, P[1] + n[1] * h)
    new = []
    for a, c in ((S, Q1), (Q1, Q2), (Q2, Q3), (Q3, Q4), (Q4, E)):
        t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1]))); t.SetEnd(pcbnew.VECTOR2I(mm(c[0]), mm(c[1])))
        t.SetWidth(mover.GetWidth()); t.SetLayer(mover.GetLayer()); t.SetNet(mover.GetNet()); b.Add(t); new.append(t)
    orig = (S, E, mover.GetWidth(), mover.GetLayer(), mover.GetNet())
    b.Delete(mover)
    return new, orig

def _undo(b, new, orig):
    for t in new: b.Delete(t)
    S, E, w, lay, net = orig
    t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(mm(S[0]), mm(S[1]))); t.SetEnd(pcbnew.VECTOR2I(mm(E[0]), mm(E[1])))
    t.SetWidth(w); t.SetLayer(lay); t.SetNet(net); b.Add(t)
    return t                                # la pista original recreada (el objeto viejo ya no existe)

def fix(b, is_hf, modo="ambas", tol=2.0, h=0.6, log=print):
    base = drc_count(b); done, pend = 0, []
    for _ in range(200):
        cs = [c for c in crossings(b, is_hf, modo, tol) if not any(math.hypot(c["P"][0] - p[0], c["P"][1] - p[1]) < 0.01 for p, _, _ in pend)]
        if not cs: break
        c = cs[0]; ok = False
        tr = {"a": c["a"], "b": c["b"]}
        for km, kf in (("b", "a"), ("a", "b")):
            for hh in (h, h * 0.7, h * 0.5, h * 1.5):
                r = _jog(b, tr[km], tr[kf], c["P"], hh)
                if not r: continue
                now = drc_count(b)
                if now <= base:
                    ok = True; base = now; break
                tr[km] = _undo(b, *r)              # seguir con la pista recreada, no con la borrada
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
