#!/usr/bin/env python3
"""Tests del plugin. Correr con el Python de KiCad (pcbnew):  python tests/run_tests.py [--rapido]
Variables: FREEROUTING_JAR (si falta, se salta el test de ruteo), KICAD_CLI, KICAD_SYMBOL_DIR, KICAD_FOOTPRINT_DIR.
--rapido salta el ruteo completo de la placa RS232 (~1 min)."""
import sys, os, json, math, subprocess, tempfile, importlib.util, collections, traceback
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = os.path.join(ROOT, "skills", "kicad-kipilot-design", "scripts"); PCB = os.path.join(SK, "pcb"); EJ = os.path.join(SK, "ejemplo_rs232")
sys.path[:0] = [PCB, SK]
import pcbnew
from pcbnew import FromMM as mm
import corner45, cross90
RES = []; TMP = tempfile.mkdtemp(prefix="tests_")

def test(fn):
    try:
        r = fn(); RES.append((fn.__name__, "SALTEADO" if r == "skip" else "OK", r if isinstance(r, str) and r != "skip" else ""))
    except Exception as e:
        RES.append((fn.__name__, "FALLA", "%s: %s" % (type(e).__name__, e))); traceback.print_exc()
    return fn

def spec():
    s = importlib.util.spec_from_file_location("spec", os.path.join(EJ, "spec.py")); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

# ---------- tablero sintetico para la regla de cruces ----------
def tablero_cruces(path):
    b = pcbnew.BOARD(); nets = {}
    def net(n):
        if n not in nets: nets[n] = pcbnew.NETINFO_ITEM(b, n); b.Add(nets[n])
        return nets[n]
    pts = [(0, 0), (60, 0), (60, 40), (0, 40)]
    for i in range(4):
        s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts); a, c = pts[i], pts[(i + 1) % 4]
        s.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1]))); s.SetEnd(pcbnew.VECTOR2I(mm(c[0]), mm(c[1]))); s.SetWidth(mm(0.1)); b.Add(s)
    def tr(n, lay, a, c):
        t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1]))); t.SetEnd(pcbnew.VECTOR2I(mm(c[0]), mm(c[1])))
        t.SetWidth(mm(0.25)); t.SetLayer(lay); t.SetNet(net(n)); b.Add(t)
    tr("PWM1", pcbnew.F_Cu, (5, 20), (55, 20))      # HF horizontal
    tr("PWM2", pcbnew.B_Cu, (10, 5), (50, 35))      # HF que la cruza a ~37 grados -> fuera de regla
    tr("PWM3", pcbnew.B_Cu, (52, 15), (52, 25))     # HF que la cruza a 90 -> correcto
    tr("SIG", pcbnew.B_Cu, (5, 30), (12, 10))       # senal lenta que cruza PWM1 a ~71 grados
    b.Save(path); return path

def _camino_ok(b, net, a, c):
    S = [s for s in corner45.load(b) if str(b.FindNet(s[4]).GetNetname()).lstrip("/") == net]
    cnt = collections.Counter()
    for s in S:
        for p in (s[0], s[1]): cnt[(round(p[0], 3), round(p[1], 3))] += 1
    ext = sorted(k for k, v in cnt.items() if v == 1)
    return ext == sorted([a, c]), len(S)

@test
def cruces_detecta_y_respeta_modo():
    b = pcbnew.LoadBoard(tablero_cruces(os.path.join(TMP, "cruces.kicad_pcb")))
    hf = cross90.hf_matcher(["PWM*"])
    a = cross90.crossings(b, hf, "ambas"); g = cross90.crossings(b, hf, "alguna")
    assert len(a) == 1 and set(a[0]["nets"]) == {"PWM1", "PWM2"}, a
    assert abs(a[0]["ang"] - math.degrees(math.atan2(30, 40))) < 0.1
    assert len(g) == 2, "modo alguna debe sumar el cruce con SIG"
    return "ambas=1, alguna=2"

@test
def cruces_corrige_a_90():
    b = pcbnew.LoadBoard(tablero_cruces(os.path.join(TMP, "cruces2.kicad_pcb")))
    hf = cross90.hf_matcher(["/PWM*"])                       # el prefijo "/" de KiCad se ignora
    d0 = cross90.drc_count(b)
    done, pend = cross90.fix(b, hf, "ambas", log=lambda *x: None)
    assert done == 1 and not pend, (done, pend)
    assert cross90.crossings(b, hf, "ambas") == [], "quedan cruces fuera de regla"
    # el unico cruce entre PWM1 y PWM2 ahora es a 90 grados
    ang = [cross90._ang(*x) for x in [(s1[1], s1[2], s2[1], s2[2]) for s1 in cross90._segs(b) for s2 in cross90._segs(b)
           if str(s1[0].GetNetname()) == "PWM1" and str(s2[0].GetNetname()) == "PWM2" and cross90._inter(s1[1], s1[2], s2[1], s2[2])]]
    assert len(ang) == 1 and abs(ang[0] - 90) < 0.5, ang
    ok, n = _camino_ok(b, "PWM2", (10.0, 5.0), (50.0, 35.0)); assert ok, "PWM2 quedo cortada"
    assert corner45.issues(corner45.load(b)) == [], "el desvio genero esquinas a 90"
    assert cross90.drc_count(b) <= d0, "el desvio empeoro el DRC"
    return "1 cruce corregido, PWM2 continua en %d tramos, sin esquinas a 90" % n

@test
def esquema_desde_spec():
    out = os.path.join(TMP, "t.kicad_sch")
    subprocess.run([sys.executable, os.path.join(SK, "kicad_sch_builder.py"), os.path.join(EJ, "spec.py"), out], check=True, capture_output=True)
    r = subprocess.run([sys.executable, os.path.join(SK, "netlist_check.py"), out, os.path.join(EJ, "spec.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-600:] + r.stderr[-600:]
    return r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "ok"

@test
def pcb_ruteada_rs232():
    if "--rapido" in sys.argv: return "skip"
    jar = os.environ.get("FREEROUTING_JAR", "")
    if not os.path.exists(jar): return "skip"
    L = json.load(open(os.path.join(EJ, "layout.json")))
    L["hf_nets"] = ["EQ_TX", "HC_OUT", "OPTO_OUT", "HF_RXD", "RX_TTL"]; L["hf_cross"] = {"modo": "alguna"}   # ejercita la regla
    lay = os.path.join(TMP, "layout_hf.json"); json.dump(L, open(lay, "w")); out = os.path.join(TMP, "rs232")
    r = subprocess.run([sys.executable, os.path.join(PCB, "make_pcb.py"), os.path.join(EJ, "spec.py"), lay, out, "--jar", jar], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-800:] + r.stderr[-800:]
    b = pcbnew.LoadBoard(os.path.join(out, "placa.kicad_pcb"))
    assert corner45.issues(corner45.load(b)) == [], "hay esquinas a 90"
    m = spec(); exp = collections.defaultdict(set); got = collections.defaultdict(set)
    for (_, lib, ref, val, u, X, Y, n) in m.PARTS:
        for p, net in n.items(): exp["/" + net].add((ref, p))
    for f in b.GetFootprints():
        for p in f.Pads():
            n = str(p.GetNetname())
            if n and not n.startswith("unconn"): got[n].add((f.GetReference(), p.GetNumber()))
    assert dict(exp) == dict(got), "redes PCB distintas a la spec"
    f = os.path.join(TMP, "drc.rpt"); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); pcbnew.WriteDRCReport(b, f, pcbnew.EDA_UNITS_MILLIMETRES, True)
    txt = open(f).read(); assert "Found 0 unconnected pads" in txt, "pads sin conectar"
    for k in ("[clearance]", "[shorting_items]", "[tracks_crossing]"): assert k not in txt, k
    rest = cross90.crossings(b, cross90.hf_matcher(L["hf_nets"]), "alguna")
    linea = [l for l in r.stdout.splitlines() if "cruces HF" in l]
    return "redes %d/%d, 0 sin conectar, 0 esquinas 90, %s, cruces HF restantes %d" % (len(got), len(exp), linea[-1] if linea else "", len(rest))

@test
def caja_desde_json():
    try: import cadquery as cq
    except ImportError: return "skip"
    out = os.path.join(TMP, "caja")
    subprocess.run([sys.executable, os.path.join(SK, "gen_enclosure.py"), os.path.join(EJ, "placa_ejemplo.json"), out], check=True, capture_output=True)
    for n in ("base", "tapa"):
        s = cq.importers.importStep(os.path.join(out, n + ".step")).val()
        assert s.isValid() and len(s.Solids()) == 1, n
    rep = open(os.path.join(out, "caja_reporte.md")).read()
    for r in ("J1", "J2", "JK1", "JK2"): assert r + ":" in rep, "falta ventana " + r
    return "base y tapa validas, 4 ventanas"

@test
def colocacion_automatica():
    import autoplace
    R = json.load(open(os.path.join(EJ, "reglas.json")))
    L, P, malos = autoplace.colocar(spec(), R, seed=1, log=lambda *x: None)
    assert not malos, "piezas con choques: %s" % malos
    assert set(L["pos"]) == set(P) and len(P) == 42
    W, H = R["board"]["w"], R["board"]["h"]
    assert abs(L["pos"]["J1"][0] - 7.7) < 0.01 and abs(L["pos"]["J2"][0] - (W - 7.7)) < 0.01, "DB9 no quedaron al borde"
    for r in ("JK1", "JK2"): assert abs(P[r].box()[3] - H) < 0.01, r + " no quedo al borde inferior"
    XB = R["barrera"]["x"]
    for p in P.values():                                     # cada pieza en su lado, nada pisa la franja salvo puentes
        b = p.box()
        if p.lado == "izq": assert b[2] <= XB - 2.4, p.ref
        if p.lado == "der": assert b[0] >= XB + 2.4, p.ref
    assert P["U4"].lado == P["DC1"].lado == "puente"
    for num, x, y in P["U4"].pads():                         # opto: LED (iso) a la izquierda, salida (hf) a la derecha
        n = P["U4"].nets.get(num)
        if n in ("LED_A", "GND_ISO"): assert x < XB, (num, n)
        if n in ("5V_HF", "GND_HF", "OPTO_OUT"): assert x > XB, (num, n)
    return "42 piezas sin choques, conectores al borde, U4/DC1 sobre la barrera bien orientados"

@test
def colocacion_y_ruteo_automaticos():
    if "--rapido" in sys.argv: return "skip"
    jar = os.environ.get("FREEROUTING_JAR", "")
    if not os.path.exists(jar): return "skip"
    out = os.path.join(TMP, "auto")
    r = subprocess.run([sys.executable, os.path.join(PCB, "make_pcb.py"), os.path.join(EJ, "spec.py"), os.path.join(EJ, "reglas.json"), out, "--jar", jar],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-800:] + r.stderr[-800:]
    b = pcbnew.LoadBoard(os.path.join(out, "placa.kicad_pcb"))
    assert corner45.issues(corner45.load(b)) == []
    f = os.path.join(TMP, "drc_auto.rpt"); pcbnew.ZONE_FILLER(b).Fill(b.Zones()); pcbnew.WriteDRCReport(b, f, pcbnew.EDA_UNITS_MILLIMETRES, True)
    txt = open(f).read(); assert "Found 0 unconnected pads" in txt
    for k in ("[clearance]", "[shorting_items]", "[tracks_crossing]", "[copper_edge_clearance]"): assert k not in txt, k
    return "placa sin posiciones manuales: 0 sin conectar, 0 errores de cobre, 0 esquinas 90"

print("\n=== Resultados ===")
for n, st, d in RES: print("%-32s %-9s %s" % (n, st, d))
sys.exit(1 if any(st == "FALLA" for _, st, _ in RES) else 0)
