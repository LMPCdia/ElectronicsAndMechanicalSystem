#!/usr/bin/env python3
"""Compara las redes de un .kicad_sch con las de una spec del builder (sin GUI).
Uso: python3 netlist_check.py proyecto.kicad_sch spec.py
Usa kicad-cli (KICAD_CLI o PATH o C:\\Program Files\\KiCad\\*\\bin). Si es KiCad < 8 convierte una copia temporal.
Esto es una comprobacion de consistencia de lo generado; no reemplaza ERC/DRC (que solo se corren si el usuario los pide)."""
import sys, os, re, glob, shutil, subprocess, tempfile, importlib.util
import xml.etree.ElementTree as ET
def cli():
    for c in [os.environ.get("KICAD_CLI"), shutil.which("kicad-cli")] + sorted(glob.glob(r"C:\Program Files\KiCad\*\bin\kicad-cli.exe"), reverse=True):
        if c and os.path.exists(c): return c
    raise SystemExit("kicad-cli no encontrado: defini KICAD_CLI")
sch, spec = sys.argv[1], sys.argv[2]
k = cli(); ver = subprocess.run([k, "--version"], capture_output=True, text=True).stdout.strip()
txt = open(sch, encoding="utf-8").read(); tmp = tempfile.mkdtemp(); src = os.path.join(tmp, "t.kicad_sch")
if int(ver.split(".")[0]) < 8:   # KiCad 7: volver a la sintaxis vieja en una copia
    txt = txt.replace("(version 20231120)", "(version 20230121)").replace("(hide yes)", "hide").replace("(exclude_from_sim no)", "")
    txt = re.sub(r'\(generator_version "[^"]*"\)', "", txt).replace("(embedded_fonts no)", "")
open(src, "w", encoding="utf-8").write(txt)
xml = os.path.join(tmp, "n.xml")
r = subprocess.run([k, "sch", "export", "netlist", "--format", "kicadxml", "-o", xml, src], capture_output=True, text=True)
if r.returncode: raise SystemExit("kicad-cli no pudo leer el esquematico: " + (r.stdout + r.stderr))
sp = importlib.util.spec_from_file_location("s", spec); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
exp = {}
for (_, lib, ref, val, unit, X, Y, nets) in m.PARTS:
    for p, n in nets.items(): exp.setdefault(n, set()).add((ref, p))
got = {n.get("name").lstrip("/"): {(x.get("ref"), x.get("pin")) for x in n.findall("node")} for n in ET.parse(xml).getroot().find("nets")}
bad = [(k_, exp[k_] ^ got.get(k_, set())) for k_ in exp if got.get(k_) != exp[k_]]
print("kicad-cli", ver, "| redes esperadas:", len(exp), "| distintas:", len(bad))
for k_, d in bad: print("  DIF", k_, d)
sys.exit(1 if bad else 0)
