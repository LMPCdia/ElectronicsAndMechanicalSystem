#!/usr/bin/env python3
"""Crea el .kicad_pcb (sin rutear) a partir de la MISMA spec del esquematico + un layout.json de colocacion.
Uso (con el Python de KiCad):  python pcb_build.py spec.py layout.json salida.kicad_pcb
layout.json:
 {"board": {"w": 110, "h": 74, "chamfer": 3},
  "pos": {"J1": [x, y, rot], ...},              # cada referencia de la spec
  "holes": [[x, y], ...], "hole_fp": "MountingHole:MountingHole_3.2mm_M3",
  "texts": [["TEXTO", x, y, tamano, rot, "L"|null], ...]}
Cada huella queda con su 'path' apuntando al simbolo del esquematico (UUID estable), para que
'Actualizar PCB desde esquematico' no duplique piezas. Probado con KiCad 7.0 (pcbnew)."""
import re, sys, os, glob, json, importlib.util
import pcbnew
from pcbnew import FromMM as mm
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from kicad_sch_builder import uid

def fp_dir():
    for d in [os.environ.get("KICAD_FOOTPRINT_DIR", "")] + sorted(glob.glob(r"C:\Program Files\KiCad\*\share\kicad\footprints"), key=lambda d: [int(x) for x in re.findall(r"\d+", d.split("KiCad")[1].split("\\")[1])], reverse=True) \
            + ["/usr/share/kicad/footprints", "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"]:
        if d and os.path.isdir(d): return d.rstrip("/\\") + os.sep
    raise SystemExit("Defini KICAD_FOOTPRINT_DIR (carpeta con los .pretty)")

def load_spec(path):
    sp = importlib.util.spec_from_file_location("spec", path); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m

def build(spec, L, out):
    FP = fp_dir(); b = pcbnew.BOARD(); nets = {}
    def net(n):
        if n not in nets: nets[n] = pcbnew.NETINFO_ITEM(b, n); b.Add(nets[n])
        return nets[n]
    W, H, c = L["board"]["w"], L["board"]["h"], L["board"].get("chamfer", 0)
    pts = [(c, 0), (W - c, 0), (W, c), (W, H - c), (W - c, H), (c, H), (0, H - c), (0, c)] if c else [(0, 0), (W, 0), (W, H), (0, H)]
    for i in range(len(pts)):
        s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts)
        s.SetStart(pcbnew.VECTOR2I(mm(pts[i][0]), mm(pts[i][1]))); a = pts[(i + 1) % len(pts)]
        s.SetEnd(pcbnew.VECTOR2I(mm(a[0]), mm(a[1]))); s.SetWidth(mm(0.1)); b.Add(s)
    refs = {}                                   # ref -> [valor, {pin: red}, unidad minima]
    for (_, lib, ref, val, unit, X, Y, nets_) in spec.PARTS:
        r = refs.setdefault(ref, [val, {}, unit]); r[1].update(nets_); r[2] = min(r[2], unit)
    for ref, (val, pads, u0) in refs.items():
        if ref not in spec.FOOT: raise SystemExit("Falta footprint para " + ref)
        if ref not in L["pos"]: raise SystemExit("Falta posicion en layout para " + ref)
        lib, name = spec.FOOT[ref].split(":")
        f = pcbnew.FootprintLoad(FP + lib + ".pretty", name)
        if f is None: raise SystemExit("Huella no encontrada: " + spec.FOOT[ref])
        x, y, rot = (L["pos"][ref] + [0])[:3]
        f.SetReference(ref); f.SetValue(val); f.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y))); f.SetOrientationDegrees(rot)
        b.Add(f)
        for p in f.Pads():
            n = pads.get(p.GetNumber())
            if n: p.SetNet(net(n))
        f.SetPath(pcbnew.KIID_PATH("/" + uid("sym", ref, u0)))
        f.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8))); f.Reference().SetTextThickness(mm(0.12)); f.Value().SetVisible(False)
    for i, (hx, hy) in enumerate(L.get("holes", [])):
        f = pcbnew.FootprintLoad(FP + L.get("hole_fp", "MountingHole:MountingHole_3.2mm_M3").split(":")[0] + ".pretty",
                                 L.get("hole_fp", "MountingHole:MountingHole_3.2mm_M3").split(":")[1])
        f.SetReference("H%d" % (i + 1)); f.SetValue("M3"); f.SetPosition(pcbnew.VECTOR2I(mm(hx), mm(hy))); b.Add(f)
        f.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8))); f.Value().SetVisible(False)
    for (s_, x, y, size, rot, just) in L.get("texts", []):
        t = pcbnew.PCB_TEXT(b); t.SetText(s_); t.SetLayer(pcbnew.F_SilkS); t.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size))); t.SetTextThickness(mm(0.15)); t.SetTextAngleDegrees(rot)
        if just == "L": t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
        b.Add(t)
    b.Save(out)
    print("guardado", out, "| huellas:", len(b.GetFootprints()), "| redes:", len(nets))

if __name__ == "__main__":
    build(load_spec(sys.argv[1]), json.load(open(sys.argv[2])), sys.argv[3])
