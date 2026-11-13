#!/usr/bin/env python3
"""Generador parametrico de caja (base + tapa) a partir del JSON de board_to_enclosure_json.py.
    python gen_enclosure.py placa.json carpeta_salida [config.json]
Requiere: pip install cadquery.  Salidas: base.step/.stl, tapa.step/.stl, caja_reporte.md
Modelo: la placa apoya en postes (stand-offs) con tornillo M3 en cada agujero de montaje; las paredes llevan
ventanas para conectores que quedan a <= `borde_max` mm de un borde; la tapa tiene un labio que encastra en la
base y agujeros para LEDs.  Las ALTURAS son estimadas por tipo de huella (ver ALTURAS) salvo que el JSON traiga
altura_mm: REVISAR contra datasheets antes de imprimir.  El origen del modelo es la esquina sup-izq del contorno
de la placa (X derecha, Y abajo como KiCad); el resultado se espeja en Y para que Y+ sea hacia atras (no afecta la forma)."""
import sys, os, json
import cadquery as cq

CFG = {"pared": 2.4, "piso": 2.0, "holgura": 0.8, "poste_alto": 4.0, "poste_d": 6.0, "poste_taladro": 2.6,
       "margen_sup": 3.0, "tapa_esp": 2.0, "labio": 1.6, "tol_labio": 0.25, "borde_max": 6.0,
       "ventana_margen": 1.0, "led_d": 3.6, "sin_ventana": ["J-no"], "esquina_r": 2.0}
# alturas estimadas sobre la cara superior del PCB (mm), por fragmento de nombre de huella
ALTURAS = [("DSUB", 13.0), ("BarrelJack", 11.0), ("LED_D3", 9.0), ("LED_D5", 9.5), ("DIP", 5.0), ("SOIC", 2.0),
           ("C_Disc", 5.0), ("CP_Radial", 11.0), ("Fuse", 4.0), ("D_DO-15", 5.0), ("PinHeader", 9.0),
           ("R_Axial", 2.5), ("TestPoint", 0.5), ("MountingHole", 0.0), ("MF-RG", 4.0), ("Fuse_Bourns", 4.0)]

def altura(h):
    if h.get("altura_mm") is not None: return h["altura_mm"], "dato"
    for k, v in ALTURAS:
        if k in h["huella"]: return v, "estimada"
    return 6.0, "supuesta"

def build(data, out, cfg):
    c = dict(CFG); c.update(cfg)
    W, H = data["contorno"]["ancho"], data["contorno"]["alto"]; t = data["espesor_pcb"]
    hs = data["huellas"]; rep = []
    hmax = 0
    for h in hs:
        v, how = altura(h); h["_h"], h["_how"] = v, how; hmax = max(hmax, v)
    hmax_noled = max([h["_h"] for h in hs if "LED" not in h["huella"]] + [0])
    ih = c["poste_alto"] + t + hmax + c["margen_sup"]      # altura interior de la base hasta el plano de la tapa
    cw, ch = W + 2 * c["holgura"], H + 2 * c["holgura"]
    ow, oh = cw + 2 * c["pared"], ch + 2 * c["pared"]
    ox = -c["holgura"] - c["pared"]; oy = ox               # esquina del exterior respecto al origen de la placa
    def rbox(w, h, z0, z1, r):
        return (cq.Workplane("XY").workplane(offset=z0).center(ox + w / 2, oy + h / 2).rect(w, h).extrude(z1 - z0)
                .edges("|Z").fillet(min(r, w / 4, h / 4)))
    base = rbox(ow, oh, 0, c["piso"] + ih, c["esquina_r"])
    cav = (cq.Workplane("XY").workplane(offset=c["piso"]).center(ox + c["pared"] + cw / 2, oy + c["pared"] + ch / 2)
           .rect(cw, ch).extrude(ih + 1))
    base = base.cut(cav)
    zp = c["piso"] + c["poste_alto"]                       # cara inferior del PCB
    for m in data["agujeros_montaje"]:
        x, y = m["centro"]
        post = cq.Workplane("XY").workplane(offset=c["piso"]).center(x, y).circle(c["poste_d"] / 2).extrude(c["poste_alto"])
        post = post.cut(cq.Workplane("XY").workplane(offset=c["piso"] + 0.5).center(x, y).circle(c["poste_taladro"] / 2).extrude(c["poste_alto"]))
        base = base.union(post)
    ztop = c["piso"] + ih                                  # borde superior de la pared
    zpcb_top = zp + t
    win = []
    for h in hs:
        if not (h["ref"].startswith("J") or h["ref"].startswith("JK")) or h["ref"] in c["sin_ventana"]: continue
        d = h["dist_borde"]; side, dist = min(d.items(), key=lambda kv: kv[1])
        if dist > c["borde_max"]: continue
        b = h["caja"]; m = c["ventana_margen"]; hh = h["_h"]
        z0 = zpcb_top - 0.5; zh = hh + 1.0 + 0.5
        if side in ("izq", "der"):
            ww, cy = b["alto"] + 2 * m, b["y"] + b["alto"] / 2
            x0 = ox - 1 if side == "izq" else W + c["holgura"] - 0.01
            w = (cq.Workplane("XY").workplane(offset=z0).center(x0 + (c["pared"] + c["holgura"] + 2) / 2, cy)
                 .rect(c["pared"] + c["holgura"] + 2, ww).extrude(zh))
        else:
            ww, cx = b["ancho"] + 2 * m, b["x"] + b["ancho"] / 2
            y0 = oy - 1 if side == "arriba" else H + c["holgura"] - 0.01
            w = (cq.Workplane("XY").workplane(offset=z0).center(cx, y0 + (c["pared"] + c["holgura"] + 2) / 2)
                 .rect(ww, c["pared"] + c["holgura"] + 2).extrude(zh))
        # si la ventana pasaria del borde superior de la pared, se corta igual (queda abierta arriba)
        base = base.cut(w); win.append((h["ref"], side, round(ww, 1), round(zh, 1)))
    # tapa
    lid = rbox(ow, oh, ztop, ztop + c["tapa_esp"], c["esquina_r"])
    lw, lh = cw - 2 * c["tol_labio"], ch - 2 * c["tol_labio"]
    lip = (cq.Workplane("XY").workplane(offset=ztop - c["labio"]).center(ox + c["pared"] + cw / 2, oy + c["pared"] + ch / 2)
           .rect(lw, lh).rect(lw - 2 * 1.6, lh - 2 * 1.6).extrude(c["labio"]))
    lid = lid.union(lip)
    leds = [h for h in hs if "LED" in h["huella"]]
    for h in leds:
        cx, cy = h["centro"]
        lid = lid.cut(cq.Workplane("XY").workplane(offset=ztop - 0.1).center(cx, cy).circle(c["led_d"] / 2).extrude(c["tapa_esp"] + 0.2))
    lid = lid.translate((0, 0, -ztop))                      # tapa apoyada en z=0 para imprimir boca arriba
    os.makedirs(out, exist_ok=True)
    for name, solid in (("base", base), ("tapa", lid)):
        cq.exporters.export(solid, os.path.join(out, name + ".step")); cq.exporters.export(solid, os.path.join(out, name + ".stl"))
    L = ["# Reporte de caja", "", "Placa %.1f x %.1f mm, espesor %.2f mm." % (W, H, t),
         "Exterior: %.1f x %.1f x %.1f mm (base %.1f + tapa %.1f)." % (ow, oh, ztop + c["tapa_esp"], ztop, c["tapa_esp"]),
         "Altura interior sobre el piso: %.1f mm; componente mas alto: %.1f mm." % (ih, hmax), "",
         "## Ventanas de conectores"] + ["- %s: pared %s, ancho %.1f mm, alto %.1f mm" % w for w in win] + \
        ["", "## Agujeros de LED en la tapa", ", ".join(h["ref"] for h in leds) or "ninguno", "",
         "## Alturas usadas (REVISAR)"] + ["- %s (%s): %.1f mm [%s]" % (h["ref"], h["huella"], h["_h"], h["_how"])
                                           for h in hs if h["_how"] != "dato" and h["_h"] > 2.6]
    open(os.path.join(out, "caja_reporte.md"), "w").write("\n".join(L))
    print("\n".join(L[:6])); print("ventanas:", [w[0] for w in win], "| LEDs:", len(leds))

if __name__ == "__main__":
    cfg = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else {}
    build(json.load(open(sys.argv[1])), sys.argv[2], cfg)
