#!/usr/bin/env python3
"""Orquestador: spec + layout -> placa ruteada con chaflanes a 45 grados.
python make_pcb.py spec.py layout.json carpeta_salida [--jar freerouting.jar] [--java java]
Ejecutar con el Python de KiCad. Salidas: <carpeta>/placa_sin_rutear.kicad_pcb, placa.kicad_pcb (+ .dsn/.ses/log)."""
import sys, os, subprocess
H = os.path.dirname(os.path.abspath(__file__)); spec, lay, out = sys.argv[1:4]; rest = sys.argv[4:]
os.makedirs(out, exist_ok=True); raw = os.path.join(out, "placa_sin_rutear.kicad_pcb"); fin = os.path.join(out, "placa.kicad_pcb")
subprocess.run([sys.executable, os.path.join(H, "pcb_build.py"), spec, lay, raw], check=True)
subprocess.run([sys.executable, os.path.join(H, "pcb_route.py"), raw, lay, fin] + rest, check=True)
