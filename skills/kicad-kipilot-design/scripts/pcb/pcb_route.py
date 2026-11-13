#!/usr/bin/env python3
"""Ruteo con Freerouting: DSN (con clases y franjas sin cobre) -> motor -> SES -> pistas + zonas de masa -> chaflanes 45.
Uso (Python de KiCad):  python pcb_route.py placa.kicad_pcb layout.json salida.kicad_pcb [--jar freerouting.jar] [--java java]
layout.json (ademas de lo de pcb_build):
 "route": {"width": 0.25, "clearance": 0.25, "power_width": 0.4, "power_nets": ["5V_HF", ...], "via": [0.6, 0.3]},
 "keepouts": [[x1, y1, x2, y2], ...],                 # sin cobre en ambas capas (p. ej. franja de aislacion)
 "zones": [{"net": "GND_ISO", "x1": .., "y1": .., "x2": .., "y2": ..}, ...]   # planos en F.Cu y B.Cu
 "hf_nets": ["PWM*", ...], "hf_cross": {"modo": "ambas"}   # cruces PWM/HF a 90 grados (ver cross90.py)
Variables: FREEROUTING_JAR, JAVA. En Linux sin pantalla se usa xvfb-run si existe. No hace DRC: eso solo si el usuario lo pide."""
import sys, os, re, json, shutil, subprocess, math
import pcbnew
from pcbnew import FromMM as mm
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import corner45, cross90

def export_dsn(src, dst, L):
    R = L.get("route", {}); w = int(R.get("width", 0.25) * 1000); cl = int(R.get("clearance", 0.25) * 1000)
    pw = R.get("power_nets", []); pww = int(R.get("power_width", 0.4) * 1000); via = R.get("via", [0.6, 0.3])
    b = pcbnew.LoadBoard(src); pcbnew.ExportSpecctraDSN(b, dst); t = open(dst).read()
    t = re.sub(r"\(width 200\)", "(width %d)" % w, t); t = re.sub(r"\(clearance 200\.1\)", "(clearance %d)" % cl, t)
    m = re.search(r"\(class kicad_default \"\"(.*?)\n      \(circuit", t, re.S)
    allnets = m.group(1).split(); rest = [n for n in allnets if n not in pw]; pwn = [n for n in pw if n in allnets]
    vn = "Via[0-1]_%d:%d_um" % (int(via[0] * 1000), int(via[1] * 1000))
    cls = '(class kicad_default ""\n      %s\n      (circuit\n        (use_via %s)\n      )\n      (rule\n        (width %d)\n        (clearance %d)\n      )\n    )' % (" ".join(rest), vn, w, cl)
    if pwn: cls += '\n    (class power ""\n      %s\n      (circuit\n        (use_via %s)\n      )\n      (rule\n        (width %d)\n        (clearance %d)\n      )\n    )' % (" ".join(pwn), vn, pww, cl)
    s = t.index("(class kicad_default"); e = t.index("\n    )\n  )\n  (wiring", s) + len("\n    )")
    t = t[:s] + cls + t[e:]
    ko = "".join("    (keepout \"\" (rect %s %d %d %d %d))\n" % (ly, x1 * 1000, -y1 * 1000, x2 * 1000, -y2 * 1000)
                 for (x1, y1, x2, y2) in L.get("keepouts", []) for ly in ("F.Cu", "B.Cu"))
    t = t.replace("    (boundary", ko + "    (boundary", 1)
    open(dst, "w").write(t); print("DSN ok:", dst)

def run_freerouting(dsn, ses, jar, java, log):
    cmd = [java, "-jar", jar, "-de", dsn, "-do", ses, "-mp", "40", "-mt", "1", "-oit", "0.1"]
    if sys.platform.startswith("linux") and shutil.which("xvfb-run"): cmd = ["xvfb-run", "-a"] + cmd
    with open(log, "w") as f: subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, check=False)
    txt = open(log, errors="ignore").read()
    ok = os.path.exists(ses) and os.path.getsize(ses) > 0
    print("Freerouting:", "SES generado" if ok else "SIN SES", "|", [l for l in txt.splitlines() if "completed" in l][-1:])
    if not ok: raise SystemExit("Freerouting no produjo SES; ver " + log)

def blocks(txt, key):
    i = 0
    while True:
        m = re.compile(r"\(" + key + r"[\s]").search(txt, i)
        if not m: return
        i = m.start(); d = 0; j = i
        while True:
            if txt[j] == "(": d += 1
            elif txt[j] == ")":
                d -= 1
                if d == 0: break
            j += 1
        yield txt[i:j + 1]; i = j + 1

def import_ses(b, ses_path, L):
    ses = open(ses_path).read(); ses = ses[ses.index("(network_out"):]; nets0 = b.GetNetsByName()
    LAY = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}; U = 1e-4; nw = nv = 0
    via = L.get("route", {}).get("via", [0.6, 0.3])
    for nb in blocks(ses, "net"):
        n = nets0[nb.split()[1]]
        for wb in blocks(nb, "wire"):
            m = re.search(r"\(path (\S+) (\d+)([^)]*)\)", wb); lay, w = LAY[m.group(1)], int(m.group(2)) * U
            v = [int(x) for x in m.group(3).split()]; pts = [(v[k] * U, -v[k + 1] * U) for k in range(0, len(v), 2)]
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1))); t.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
                t.SetWidth(mm(w)); t.SetLayer(lay); t.SetNet(n); b.Add(t); nw += 1
        for vb in blocks(nb, "via"):
            m = re.search(r"\(via \S+ (-?\d+) (-?\d+)\)", vb); v = pcbnew.PCB_VIA(b)
            v.SetPosition(pcbnew.VECTOR2I(mm(int(m.group(1)) * U), mm(-int(m.group(2)) * U)))
            v.SetWidth(mm(via[0])); v.SetDrill(mm(via[1])); v.SetNet(n); b.Add(v); nv += 1
    print("segmentos", nw, "vias", nv)
    nets = b.GetNetsByName()
    for zd in L.get("zones", []):
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            z = pcbnew.ZONE(b); z.SetLayer(layer); z.SetNet(nets[zd["net"]]); z.SetMinThickness(mm(0.25)); z.SetLocalClearance(mm(0.3))
            z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL); z.SetThermalReliefGap(mm(0.3)); z.SetThermalReliefSpokeWidth(mm(0.4))
            o = z.Outline(); o.NewOutline()
            for (x, y) in [(zd["x1"], zd["y1"]), (zd["x2"], zd["y1"]), (zd["x2"], zd["y2"]), (zd["x1"], zd["y2"])]: o.Append(mm(x), mm(y))
            b.Add(z)
    if L.get("zones"): pcbnew.ZONE_FILLER(b).Fill(b.Zones())

def chamfer(b):
    S = corner45.load(b); S = corner45.merge_collinear(corner45.cleanup(S)); S, sk = corner45.fix(S)
    S = corner45.merge_collinear(corner45.cleanup(S)); S, sk = corner45.fix(S); S = corner45.merge_collinear(corner45.cleanup(S))
    for t in [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"]: b.Delete(t)
    nets = {n.GetNetCode(): n for n in b.GetNetInfo().NetsByNetcode().values()}
    for a, c, w, lay, nc in S:
        if math.hypot(c[0] - a[0], c[1] - a[1]) < 0.001: continue
        t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1]))); t.SetEnd(pcbnew.VECTOR2I(mm(c[0]), mm(c[1])))
        t.SetWidth(mm(w)); t.SetLayer(lay); t.SetNet(nets[nc]); b.Add(t)
    if len(list(b.Zones())): pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    iss = corner45.issues(corner45.load(b))
    print("chaflanes 45: esquinas/T a 90 grados restantes:", len(iss), "| sin resolver:", len(sk))
    return len(iss)

if __name__ == "__main__":
    a = sys.argv; src, lay, out = a[1], json.load(open(a[2])), a[3]
    opt = lambda k, d: a[a.index(k) + 1] if k in a else d
    jar = opt("--jar", os.environ.get("FREEROUTING_JAR", "freerouting.jar")); java = opt("--java", os.environ.get("JAVA", "java"))
    base = os.path.splitext(out)[0]
    export_dsn(src, base + ".dsn", lay); run_freerouting(base + ".dsn", base + ".ses", jar, java, base + "_freerouting.log")
    b = pcbnew.LoadBoard(src); import_ses(b, base + ".ses", lay); n90 = chamfer(b)
    if lay.get("hf_nets"):                                    # regla: cruces de redes PWM/HF a 90 grados entre capas
        is_hf, modo, tol, h = cross90.cfg_from_layout(lay); cross90.fix(b, is_hf, modo, tol, h)
        print("esquinas a 90 tras desvios:", len(corner45.issues(corner45.load(b))))
    for n in b.GetNetsByName().values():                       # mismo nombre que el netlist del esquematico (etiquetas locales: "/RED")
        s = str(n.GetNetname())
        if s and not s.startswith("/") and not s.startswith("unconnected"): n.SetNetname("/" + s)
    b.Save(out); print("guardado", out, "| pistas/vias:", len(list(b.GetTracks())), "| zonas:", len(list(b.Zones())))
