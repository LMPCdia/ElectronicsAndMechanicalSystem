#!/usr/bin/env python3
"""Extrae de un .kicad_pcb los datos que necesita un CAD mecanico (Fusion, Inventor, FreeCAD) para disenar
caja y soportes: contorno, espesor, agujeros de montaje, y cada huella con posicion, rotacion, lado,
caja envolvente (courtyard o pads) y borde mas cercano. Unidades: mm; origen = esquina superior izquierda
del contorno (X a la derecha, Y hacia abajo, como KiCad). Correr con el Python de KiCad:
    python board_to_enclosure_json.py placa.kicad_pcb salida.json
No inventa alturas: las toma del modelo 3D si hubiera una tabla en ALTURAS_MM, si no queda null (completar a mano)."""
import sys, json, pcbnew
ALTURAS_MM = {}   # {"DIP-16": 6.0, ...} completar con datasheets/modelos reales
mm = lambda v: round(pcbnew.ToMM(v), 3)
b = pcbnew.LoadBoard(sys.argv[1])
bb = b.GetBoardEdgesBoundingBox(); x0, y0 = bb.GetX(), bb.GetY()
rel = lambda p: [mm(p.x - x0), mm(p.y - y0)]
out = {"unidades": "mm", "origen": "esquina sup-izq del contorno", "espesor_pcb": mm(b.GetDesignSettings().GetBoardThickness()),
       "contorno": {"ancho": mm(bb.GetWidth()), "alto": mm(bb.GetHeight())}, "huellas": [], "agujeros_montaje": []}
for fp in b.GetFootprints():
    c = fp.GetBoundingBox(False, False)
    fid = str(fp.GetFPID().GetLibItemName())
    d = {"ref": fp.GetReference(), "valor": fp.GetValue(), "huella": fid, "centro": rel(fp.GetPosition()),
         "rot": round(fp.GetOrientationDegrees(), 1), "lado": "B" if fp.IsFlipped() else "F",
         "caja": {"x": mm(c.GetX() - x0), "y": mm(c.GetY() - y0), "ancho": mm(c.GetWidth()), "alto": mm(c.GetHeight())},
         "altura_mm": next((h for k, h in ALTURAS_MM.items() if k in fid), None),
         "modelo_3d": [m.m_Filename for m in fp.Models()]}
    d["dist_borde"] = {"izq": d["caja"]["x"], "arriba": d["caja"]["y"],
                       "der": round(out["contorno"]["ancho"] - d["caja"]["x"] - d["caja"]["ancho"], 3),
                       "abajo": round(out["contorno"]["alto"] - d["caja"]["y"] - d["caja"]["alto"], 3)}
    out["huellas"].append(d)
    if fid.startswith("MountingHole"):
        for p in fp.Pads(): out["agujeros_montaje"].append({"ref": fp.GetReference(), "centro": rel(p.GetPosition()), "diam_taladro": mm(p.GetDrillSize().x)})
json.dump(out, open(sys.argv[2], "w"), indent=1, ensure_ascii=False)
print(sys.argv[2], "| huellas:", len(out["huellas"]), "| agujeros:", len(out["agujeros_montaje"]), "| contorno:", out["contorno"])
