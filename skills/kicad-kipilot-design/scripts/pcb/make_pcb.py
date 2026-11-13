#!/usr/bin/env python3
"""Orquestador: spec + layout (o reglas) -> placa ruteada con chaflanes a 45 grados.
python make_pcb.py spec.py layout.json carpeta_salida [--jar freerouting.jar] [--java java] [--semillas 3]
Si el JSON no trae "pos" se toma como reglas de colocacion automatica (autoplace.py): se coloca, se rutea y,
si quedan pads sin conectar, se reintenta con otra semilla. Ejecutar con el Python de KiCad.
Salidas: <carpeta>/layout_usado.json, vista_colocacion.png (si es automatica), placa_sin_rutear.kicad_pcb, placa.kicad_pcb"""
import sys, os, json, subprocess
H = os.path.dirname(os.path.abspath(__file__)); spec, lay, out = sys.argv[1:4]; rest = sys.argv[4:]
n_sem = int(rest[rest.index("--semillas") + 1]) if "--semillas" in rest else 3
if "--semillas" in rest: i = rest.index("--semillas"); rest = rest[:i] + rest[i + 2:]
os.makedirs(out, exist_ok=True); raw = os.path.join(out, "placa_sin_rutear.kicad_pcb"); fin = os.path.join(out, "placa.kicad_pcb")
used = os.path.join(out, "layout_usado.json"); auto = "pos" not in json.load(open(lay))

def sin_conectar(path):
    code = ("import sys, pcbnew\nb = pcbnew.LoadBoard(sys.argv[1]); b.BuildConnectivity()\n"
            "print(b.GetConnectivity().GetUnconnectedCount(True))")
    r = subprocess.run([sys.executable, "-c", code, path], capture_output=True, text=True, check=True)
    return int(r.stdout.strip().splitlines()[-1])

for sem in range(1, (n_sem if auto else 1) + 1):
    if auto:
        r = subprocess.run([sys.executable, os.path.join(H, "autoplace.py"), spec, lay, used, "--semilla", str(sem),
                            "--png", os.path.join(out, "vista_colocacion.png")])
        if r.returncode: print("semilla %d: colocacion con choques, pruebo otra" % sem); continue
    else:
        json.dump(json.load(open(lay)), open(used, "w"), indent=1)
    subprocess.run([sys.executable, os.path.join(H, "pcb_build.py"), spec, used, raw], check=True)
    subprocess.run([sys.executable, os.path.join(H, "pcb_route.py"), raw, used, fin] + rest, check=True)
    n = sin_conectar(fin)
    print("pads/conexiones sin rutear:", n)
    if n == 0 or not auto: break
    print("semilla %d no cerro el ruteo; pruebo otra colocacion" % sem)
sys.exit(0 if os.path.exists(fin) and sin_conectar(fin) == 0 else 1)
