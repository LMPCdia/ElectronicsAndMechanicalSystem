#!/usr/bin/env python3
"""Colocacion automatica de piezas: spec.py + reglas.json -> layout.json (para make_pcb.py).
    python autoplace.py spec.py reglas.json layout.json [--semilla N] [--png vista.png]
Se corre con el Python de KiCad (lee las huellas reales: pads y courtyard).

reglas.json (todo opcional salvo board):
 {"board": {"w": 110, "h": 74, "chamfer": 3},
  "agujeros": {"inset": 4},                       # M3 en las 4 esquinas (o "holes": [[x,y],...])
  "bordes": {"J1": "izq", "J2": "der", "JK1": "abajo"},   # conectores al borde (se orientan solos: DSUB, BarrelJack)
  "rot_borde": {"J5": {"izq": 90, ...}},           # orientacion a mano para familias no conocidas
  "fijos": {"U9": [x, y, rot]},
  "barrera": {"x": 55, "ancho": 4.8, "izq": "iso", "der": "hf"},   # aislacion: bloque de la spec -> lado
  "gnd": {"iso": "GND_ISO", "hf": "GND_HF"},       # planos de masa por lado (o "gnd_net": "GND" sin barrera)
  "route": {...}, "hf_nets": [...], "texts": [...]}  # se copian tal cual al layout
Lado de cada pieza: por sus redes. Una pieza cuyas redes tocan los dos lados va SOBRE la barrera (opto, DC-DC),
orientada para que cada pad quede del lado de su red. El resto se ubica con recocido simulado minimizando la
longitud de las conexiones (masa con poco peso: va al plano) sin solapar courtyards ni salir de su zona."""
import sys, os, re, json, math, random, glob, importlib.util, collections
import pcbnew
from pcbnew import ToMM

GAP = 0.6           # separacion minima entre courtyards (mm)
MARGEN = 1.0        # al borde de la placa
GRID = 0.5
FAMILIAS = {        # direccion hacia donde "mira" el conector con rot 0
    "DSUB": (0, 1), "BarrelJack": (-1, 0), "USB_B": (0, 1), "RJ45": (0, 1)}
DIRS = {"izq": (-1, 0), "der": (1, 0), "arriba": (0, -1), "abajo": (0, 1)}

def fp_dir():
    for d in [os.environ.get("KICAD_FOOTPRINT_DIR", "")] + sorted(glob.glob(r"C:\Program Files\KiCad\*\share\kicad\footprints"), key=lambda d: [int(x) for x in re.findall(r"\d+", d.split("KiCad")[1].split("\\")[1])], reverse=True) \
            + ["/usr/share/kicad/footprints", "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"]:
        if d and os.path.isdir(d): return d.rstrip("/\\") + os.sep
    raise SystemExit("Defini KICAD_FOOTPRINT_DIR")

def rot_vec(v, deg):  # rotacion de KiCad (antihoraria en pantalla, Y hacia abajo)
    r = math.radians(deg); c, s = round(math.cos(r), 9), round(math.sin(r), 9)
    return (v[0] * c + v[1] * s, -v[0] * s + v[1] * c)

class Pieza:
    def __init__(s, ref, fpid, pads):
        lib, name = fpid.split(":"); f = pcbnew.FootprintLoad(fp_dir() + lib + ".pretty", name)
        if f is None: raise SystemExit("Huella no encontrada: " + fpid)
        s.ref, s.fpid, s.name, s.nets = ref, fpid, name, pads   # pads: {num: red}
        s.geo = {}
        for rot in (0, 90, 180, 270):
            f.SetPosition(pcbnew.VECTOR2I(0, 0)); f.SetOrientationDegrees(rot)
            cy = f.GetCourtyard(pcbnew.F_CrtYd)
            bb = cy.BBox() if cy.OutlineCount() else f.GetBoundingBox(False, False)
            box = (ToMM(bb.GetLeft()), ToMM(bb.GetTop()), ToMM(bb.GetRight()), ToMM(bb.GetBottom()))
            pp = [(p.GetNumber(), ToMM(p.GetPosition().x), ToMM(p.GetPosition().y)) for p in f.Pads()]
            s.geo[rot] = (box, pp)
        s.x = s.y = 0.0; s.rot = 0; s.lado = None; s.modo = "libre"; s.rots = (0, 90, 180, 270)
    def box(s, x=None, y=None, rot=None):
        x = s.x if x is None else x; y = s.y if y is None else y; b = s.geo[s.rot if rot is None else rot][0]
        return (x + b[0], y + b[1], x + b[2], y + b[3])
    def pads(s):
        return [(n, s.x + px, s.y + py) for (n, px, py) in s.geo[s.rot][1]]

def load_spec(p):
    sp = importlib.util.spec_from_file_location("spec", p); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m

def solape(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0]) + GAP; h = min(a[3], b[3]) - max(a[1], b[1]) + GAP
    return w * h if w > 0 and h > 0 else 0.0

def colocar(spec, R, seed=1, log=print):
    random.seed(seed)
    W, H = R["board"]["w"], R["board"]["h"]
    # piezas y redes (uniendo unidades)
    pads, bloque = collections.defaultdict(dict), {}
    for (blk, lib, ref, val, unit, X, Y, nets) in spec.PARTS:
        pads[ref].update(nets); bloque.setdefault(ref, blk)
    P = {ref: Pieza(ref, spec.FOOT[ref], pads[ref]) for ref in pads}
    # agujeros = obstaculos
    holes = R.get("holes") or ([[i, j] for j in (R["agujeros"]["inset"], H - R["agujeros"]["inset"])
                                for i in (R["agujeros"]["inset"], W - R["agujeros"]["inset"])] if "agujeros" in R else [])
    obst = [(hx - 3.6, hy - 3.6, hx + 3.6, hy + 3.6) for hx, hy in holes]
    # lados por redes
    bar = R.get("barrera"); lado_de_bloque = {}
    if bar: lado_de_bloque = {bar["izq"]: "izq", bar["der"]: "der"}
    red_lados = collections.defaultdict(set)
    for ref, pz in P.items():
        l = lado_de_bloque.get(bloque[ref])
        if l:
            for n in pz.nets.values(): red_lados[n].add(l)
    for pz in P.values():
        ls = set().union(*[red_lados.get(n, set()) for n in pz.nets.values()]) if pz.nets else set()
        pz.lado = "puente" if len(ls) > 1 else (ls.pop() if ls else None)
    XB = bar["x"] if bar else None; half = bar.get("ancho", 4.8) / 2 if bar else 0
    def zona(pz):
        x0, y0, x1, y1 = MARGEN, MARGEN, W - MARGEN, H - MARGEN
        if pz.lado == "izq": x1 = XB - half - 0.3
        elif pz.lado == "der": x0 = XB + half + 0.3
        return x0, y0, x1, y1
    # fijos
    for ref, (x, y, r) in R.get("fijos", {}).items():
        P[ref].x, P[ref].y, P[ref].rot, P[ref].modo = x, y, r, "fijo"
    # conectores de borde: rotacion por familia y distancia al borde
    for ref, lado in R.get("bordes", {}).items():
        pz = P[ref]; d = DIRS[lado]
        rot = R.get("rot_borde", {}).get(ref, {}).get(lado)
        if rot is None:
            fam = next((k for k in FAMILIAS if k in pz.name), None)
            if fam is None: raise SystemExit("No se como orientar %s (%s): agregalo en rot_borde" % (ref, pz.name))
            rot = next(r for r in (0, 90, 180, 270) if max(abs(a - b) for a, b in zip(rot_vec(FAMILIAS[fam], r), d)) < 1e-6)
        pz.rot = rot; pz.rots = (rot,); pz.modo = lado
        b = pz.geo[rot][0]; m = re.search(r"EdgePinOffset([\d.]+)mm", pz.name)
        # el ancla queda a EdgePinOffset del borde (DSUB) o el frente del courtyard al ras del borde
        if lado == "izq": pz.x = float(m.group(1)) if m else -b[0]
        elif lado == "der": pz.x = W - float(m.group(1)) if m else W - b[2]
        elif lado == "arriba": pz.y = float(m.group(1)) if m else -b[1]
        else: pz.y = H - float(m.group(1)) if m else H - b[3]
    # piezas puente: sobre la barrera, cada pad del lado de su red
    for pz in P.values():
        if pz.lado != "puente" or pz.modo != "libre": continue
        best = None
        for rot in (0, 90, 180, 270):
            pp = pz.geo[rot][1]; xs = [px for _, px, _ in pp]; cx = (min(xs) + max(xs)) / 2
            mal = sum(1 for n, px, _ in pp if pz.nets.get(n) and red_lados.get(pz.nets[n]) and
                      len(red_lados[pz.nets[n]]) == 1 and (("izq" in red_lados[pz.nets[n]]) != (px < cx)))
            dentro = sum(1 for _, px, _ in pp if abs(px - cx) < half)      # pads dentro de la franja
            key = (mal, dentro, -(max(xs) - min(xs)))
            if best is None or key < best[0]: best = (key, rot, cx)
        pz.rot, pz.rots, pz.modo = best[1], (best[1],), "puente"; pz.x = XB - best[2]
    # nets: pesos
    gnds = set(R.get("gnd", {}).values()) | ({R["gnd_net"]} if R.get("gnd_net") else set())
    potencia = set(R.get("route", {}).get("power_nets", []))
    redes = collections.defaultdict(list)
    for ref, pz in P.items():
        for num, n in pz.nets.items(): redes[n].append((ref, num))
    peso = {n: (0.08 if n in gnds else 0.4 if n in potencia else 1.0) for n in redes if len(redes[n]) > 1}
    def pad_xy(ref, num):
        pz = P[ref]
        for n, px, py in pz.geo[pz.rot][1]:
            if n == num: return pz.x + px, pz.y + py
        return pz.x, pz.y
    def hpwl(n):
        pts = [pad_xy(r, num) for r, num in redes[n]]; xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        return peso[n] * ((max(xs) - min(xs)) + (max(ys) - min(ys)))
    movibles = [pz for pz in P.values() if pz.modo != "fijo"]
    libres = [pz for pz in P.values() if pz.modo == "libre"]
    # posicion inicial: al azar en su zona
    for pz in movibles:
        x0, y0, x1, y1 = zona(pz); b = pz.geo[pz.rot][0]
        if pz.modo in ("libre", "izq", "der"): pz.y = random.uniform(y0 - b[1], max(y0 - b[1], y1 - b[3]))
        if pz.modo in ("libre", "arriba", "abajo"): pz.x = random.uniform(x0 - b[0], max(x0 - b[0], x1 - b[2]))
        if pz.modo == "puente": pz.y = random.uniform(y0 - b[1], max(y0 - b[1], y1 - b[3]))
    nets_de = {ref: [n for n in set(P[ref].nets.values()) if n in peso] for ref in P}
    lista = list(P.values())
    def fuera(pz):
        x0, y0, x1, y1 = zona(pz) if pz.modo == "libre" else (-50, MARGEN, W + 50, H - MARGEN) if pz.modo in ("izq", "der") \
            else (MARGEN, -50, W - MARGEN, H + 50) if pz.modo in ("arriba", "abajo") else (-50, MARGEN, W + 50, H - MARGEN)
        b = pz.box(); return max(0, x0 - b[0]) + max(0, y0 - b[1]) + max(0, b[2] - x1) + max(0, b[3] - y1)
    def choques(pz):
        b = pz.box(); s = sum(solape(b, o.box()) for o in lista if o is not pz) + sum(solape(b, o) for o in obst)
        if XB is not None and pz.modo != "puente" and b[0] < XB + half and b[2] > XB - half: s += 5 * (min(b[2], XB + half) - max(b[0], XB - half))
        return s
    def costo_pieza(pz, k):
        return sum(hpwl(n) for n in nets_de[pz.ref]) + k * (choques(pz) + 3 * fuera(pz))
    def total(k):
        return sum(hpwl(n) for n in peso) + k * (sum(choques(p) for p in lista) / 2 + 3 * sum(fuera(p) for p in lista))
    it = 60000; T0, T1 = 8.0, 0.02; k = 2.0
    for i in range(it):
        T = T0 * (T1 / T0) ** (i / it); k = 2.0 + 60.0 * i / it
        pz = random.choice(movibles); old = (pz.x, pz.y, pz.rot)
        c0 = costo_pieza(pz, k); r = random.random(); otro = None
        if r < 0.1 and len(pz.rots) > 1:
            pz.rot = random.choice(pz.rots)
        elif r < 0.18 and pz.modo == "libre":
            otro = random.choice(libres)
            if otro is pz or otro.lado != pz.lado: otro = None
            else:
                c0 += costo_pieza(otro, k); o_old = (otro.x, otro.y)
                pz.x, pz.y, otro.x, otro.y = otro.x, otro.y, pz.x, pz.y
        else:
            st = max(0.3, 6 * T / T0 * 10)
            if pz.modo in ("libre", "abajo", "arriba"): pz.x += random.gauss(0, st)
            if pz.modo in ("libre", "izq", "der", "puente"): pz.y += random.gauss(0, st)
        c1 = costo_pieza(pz, k) + (costo_pieza(otro, k) if otro else 0)
        if c1 > c0 and random.random() > math.exp(-(c1 - c0) / T):
            pz.x, pz.y, pz.rot = old
            if otro: otro.x, otro.y = o_old
    # ajuste a grilla y limpieza final de choques (solo empujar)
    for pz in movibles:
        if pz.modo in ("libre", "abajo", "arriba"): pz.x = round(pz.x / GRID) * GRID
        if pz.modo in ("libre", "izq", "der", "puente"): pz.y = round(pz.y / GRID) * GRID
    for _ in range(4000):
        malos = [p for p in movibles if choques(p) > 1e-6 or fuera(p) > 1e-6]
        if not malos: break
        pz = random.choice(malos); best = (choques(pz) + 3 * fuera(pz), pz.x, pz.y)
        for dx, dy in ((GRID, 0), (-GRID, 0), (0, GRID), (0, -GRID), (2 * GRID, 0), (-2 * GRID, 0), (0, 2 * GRID), (0, -2 * GRID)):
            if pz.modo in ("izq", "der", "puente"): dx = 0
            if pz.modo in ("arriba", "abajo"): dy = 0
            pz.x += dx; pz.y += dy; c = choques(pz) + 3 * fuera(pz)
            if c < best[0] - 1e-9: best = (c, pz.x, pz.y)
            pz.x -= dx; pz.y -= dy
        if best[1:] == (pz.x, pz.y): pz.x += random.choice((-GRID, GRID)) * (pz.modo not in ("izq", "der", "puente")); pz.y += random.choice((-GRID, GRID)) * (pz.modo not in ("arriba", "abajo"))
        else: pz.x, pz.y = best[1], best[2]
    malos = [p.ref for p in lista if choques(p) > 1e-6 or fuera(p) > 1e-6]
    largo = sum(hpwl(n) / peso[n] for n in peso if n not in gnds)
    log("colocadas %d piezas | longitud estimada de senales %.0f mm | con choques: %s" % (len(P), largo, malos or "ninguna"))
    L = {"board": R["board"], "pos": {p.ref: [round(p.x, 3), round(p.y, 3), p.rot] for p in lista}, "holes": holes}
    for k_ in ("route", "hf_nets", "hf_cross", "texts", "hole_fp"):
        if k_ in R: L[k_] = R[k_]
    if bar:   # franja sin cobre con huecos donde hay pads de piezas puente, y planos de masa por lado
        cortes = sorted((p.box()[1] - 0.4, p.box()[3] + 0.4) for p in lista if p.modo == "puente" and
                        any(abs(px - XB) < half for _, px, _ in p.pads()))
        ko, y = [], 0.0
        for a, b in cortes:
            if a > y: ko.append([XB - half, y, XB + half, a])
            y = max(y, b)
        if y < H: ko.append([XB - half, y, XB + half, H])
        L["keepouts"] = [[round(v, 2) for v in k] for k in ko]
        g = R.get("gnd", {})
        L["zones"] = [z for z in ({"net": g.get(bar["izq"]), "x1": 0.6, "y1": 0.6, "x2": XB - half - 0.2, "y2": H - 0.6},
                                  {"net": g.get(bar["der"]), "x1": XB + half + 0.2, "y1": 0.6, "x2": W - 0.6, "y2": H - 0.6}) if z["net"]]
    elif R.get("gnd_net"):
        L["zones"] = [{"net": R["gnd_net"], "x1": 0.6, "y1": 0.6, "x2": W - 0.6, "y2": H - 0.6}]
    return L, P, malos

def vista(L, P, png, R):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    W, H = L["board"]["w"], L["board"]["h"]; fig, ax = plt.subplots(figsize=(W / 12, H / 12), dpi=110)
    ax.add_patch(plt.Rectangle((0, 0), W, H, fill=False, lw=1.5))
    for k in L.get("keepouts", []): ax.add_patch(plt.Rectangle((k[0], k[1]), k[2] - k[0], k[3] - k[1], color="#f4cccc"))
    col = {"izq": "#cfe2f3", "der": "#d9ead3", "puente": "#fce5cd", None: "#eeeeee"}
    for p in P.values():
        b = p.box(); ax.add_patch(plt.Rectangle((b[0], b[1]), b[2] - b[0], b[3] - b[1], fc=col.get(p.lado, "#eee"), ec="k", lw=0.5))
        for _, px, py in p.pads(): ax.plot(px, py, ".", color="#b45f06", ms=2)
        ax.text((b[0] + b[2]) / 2, (b[1] + b[3]) / 2, p.ref, ha="center", va="center", fontsize=6)
    for hx, hy in L.get("holes", []): ax.add_patch(plt.Circle((hx, hy), 1.6, fill=False))
    ax.set_xlim(-12, W + 12); ax.set_ylim(H + 12, -12); ax.set_aspect("equal"); ax.axis("off"); fig.tight_layout(); fig.savefig(png)

if __name__ == "__main__":
    a = sys.argv; spec, R, out = load_spec(a[1]), json.load(open(a[2])), a[3]
    seed = int(a[a.index("--semilla") + 1]) if "--semilla" in a else 1
    L, P, malos = colocar(spec, R, seed)
    json.dump(L, open(out, "w"), indent=1); print("layout:", out)
    if "--png" in a: vista(L, P, a[a.index("--png") + 1], R); print("vista:", a[a.index("--png") + 1])
    sys.exit(1 if malos else 0)
