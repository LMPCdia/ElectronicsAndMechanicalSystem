#!/usr/bin/env python3
"""Lista que huellas de un .kicad_pcb tienen modelo 3D asignado y cuales no.
Correr con el Python de KiCad (el que trae pcbnew):  python audit_3d_models.py placa.kicad_pcb
Informa: sin modelo, y modelos genericos/inferidos que conviene reemplazar por el real (ver GENERICOS)."""
import sys, collections, pcbnew
GENERICOS = {"PinHeader": "modulo real (DC-DC, etc.) mas grande que un header", "Fuse_Bourns": "huella provisoria",
             "BarrelJack": "jack generico: medidas reales segun el modelo comprado", "Socket": "zocalo sin el circuito integrado"}
b = pcbnew.LoadBoard(sys.argv[1]); sin = []; con = collections.OrderedDict()
for fp in b.GetFootprints():
    ms = [m.m_Filename for m in fp.Models()]
    fid = str(fp.GetFPID().GetUniStringLibId())
    if ms: con.setdefault((fid, ms[0]), []).append(fp.GetReference())
    else: sin.append((fp.GetReference(), fid))
print("huellas:", len(b.GetFootprints()), "| sin modelo:", len(sin))
for r, f in sin: print("  SIN MODELO", r, f)
for (fid, mf), refs in con.items():
    nota = [v for k, v in GENERICOS.items() if k in fid]
    print("  ", ",".join(refs), fid, "->", mf, ("  [REVISAR: " + nota[0] + "]") if nota else "")
print("Verificar en el visor 3D que las variables ${KICADn_3DMODEL_DIR} resuelvan en la version instalada.")
