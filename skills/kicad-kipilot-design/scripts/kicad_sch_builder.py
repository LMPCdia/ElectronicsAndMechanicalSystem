#!/usr/bin/env python3
"""
kicad_sch_builder.py  -  genera un .kicad_sch COMPLETO (simbolos con pines embebidos)
desde una lista de piezas + redes, sin pasar por la GUI de KiCad.

Pensado como complemento de KiPilot: KiPilot (API IPC) coloca simbolos "vacios" que
necesitan Herramientas > Actualizar simbolos desde biblioteca. Este modulo escribe el
archivo con las definiciones reales (cuerpo + pines) copiadas de las bibliotecas
oficiales, asigna Footprint a cada pieza y deja cada pin con su cable corto + etiqueta
de red (o marca de no-conexion). Despues basta kicad_sch_revert (KiPilot) para
recargarlo en KiCad y kicad_sch_get_netlist para verificar.

Uso:  python3 kicad_sch_builder.py   (usa gen.py -> P, y el mapa FOOT de abajo)
"""
import re, sys, uuid, math, datetime

import os, glob
def _find_libdir():
    c = [os.environ.get("KICAD_SYMBOL_DIR", "")]
    c += sorted(glob.glob(r"C:\Program Files\KiCad\*\share\kicad\symbols"), key=lambda d: [int(x) for x in re.findall(r"\d+", d.split("KiCad")[1].split("\\")[1])], reverse=True)
    c += ["/usr/share/kicad/symbols", "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols"]
    for d in c:
        if d and os.path.isdir(d): return d.rstrip("/\\") + os.sep
    raise SystemExit("No encuentro las bibliotecas de simbolos: defini KICAD_SYMBOL_DIR")
LIBDIR = _find_libdir()
S = 5.08                               # largo del cable corto pin -> etiqueta
OUT = {0: (-1, 0), 180: (1, 0), 90: (0, 1), 270: (0, -1)}   # angulo del pin -> direccion hacia afuera
LBL_ANG = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}
NS = uuid.UUID("6f1c2a52-0000-4000-8000-000000000001")

def uid(*k): return str(uuid.uuid5(NS, "/".join(map(str, k))))
def q(s): return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
def f(v): return ("%.4f" % v).rstrip("0").rstrip(".")

# ---------------------------------------------------------------- lectura de bibliotecas
_lib = {}
def _libtext(name):
    if name not in _lib: _lib[name] = open(LIBDIR + name + ".kicad_sym", encoding="utf-8").read()
    return _lib[name]

def _span(t, i):
    """indice del ')' que cierra el '(' en i (respeta cadenas)"""
    d = 0; k = i; n = len(t)
    while k < n:
        c = t[k]
        if c == '"':
            k += 1
            while t[k] != '"':
                if t[k] == "\\": k += 1
                k += 1
        elif c == "(": d += 1
        elif c == ")":
            d -= 1
            if d == 0: return k
        k += 1
    raise ValueError("parentesis sin cerrar")

def _children(t):
    """subelementos de nivel 1 de un bloque '(nombre ... )' -> lista de (texto, cabecera)"""
    out = []; k = 1; n = len(t)
    while k < n - 1:
        if t[k] == "(":
            e = _span(t, k); out.append(t[k:e + 1]); k = e + 1
        else: k += 1
    return out

def _find(libname, sym):
    t = _libtext(libname)
    m = re.search(r'\n\s*\(symbol "' + re.escape(sym) + r'"', t)
    if not m: raise KeyError(libname + ":" + sym)
    i = t.index("(", m.start())
    return t[i:_span(t, i) + 1]

def flat_symbol(libid):
    """devuelve (texto_simbolo_embebido, props{nombre:(valor,x,y,ang)}) resolviendo 'extends'"""
    lib, name = libid.split(":")
    der = _find(lib, name)
    mext = re.match(r'\(symbol "[^"]+"\s*\(extends "([^"]+)"\)', der)
    base_name = mext.group(1) if mext else name
    base = _find(lib, base_name) if mext else der
    der_kids = _children(der); base_kids = _children(base)
    props = [k for k in der_kids if k.startswith("(property ")]
    keep = [k for k in base_kids if not k.startswith("(property ") and not k.startswith("(extends")]
    # atributos propios del derivado (in_bom, etc.) ya vienen en base
    keep = [re.sub(r'\(symbol "' + re.escape(base_name) + r'_', '(symbol "' + name + '_', k) if k.startswith("(symbol ") else k
            for k in keep]
    body = "(symbol " + q(libid) + "\n\t" + "\n\t".join(props + keep) + "\n)"
    pr = {}
    for p in props:
        m = re.match(r'\(property "([^"]+)" "((?:[^"\\]|\\.)*)"\s*\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)', p)
        if m: pr[m.group(1)] = (m.group(2), float(m.group(3)), float(m.group(4)), float(m.group(5)))
    return body, pr

def _tokens(t):
    return re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', t)

def sym_pins(body):
    """[(unit, numero, nombre, tipo, x, y, ang)] del simbolo aplanado"""
    out = []
    for sub in re.finditer(r'\(symbol "[^"]*?_(\d+)_(\d+)"', body):
        u = int(sub.group(1)); i = body.index("(", sub.start())
        blk = body[i:_span(body, i) + 1]
        for m in re.finditer(r'\(pin (\w+) (\w+)\s*\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)\s*\(length ([-\d.]+)\)(.*?)\(name "((?:[^"\\]|\\.)*)".*?\(number "((?:[^"\\]|\\.)*)"', blk, re.S):
            out.append((u, m.group(9), m.group(8), m.group(1), float(m.group(3)), float(m.group(4)), int(float(m.group(5)))))
    return out

# ---------------------------------------------------------------- generador
def build(parts, footprints, title="", rev="A", company="", paper="A3", project="PlacaV1.1",
          root_uuid=None, notes=(), headers=()):
    """parts: [(blk, libid, ref, value, unit, X, Y, {pin:red})]; footprints: {ref: 'Lib:Footprint'}"""
    root = root_uuid or "5b238fdd-67aa-4526-ac19-944940be3fe6"   # uuid raiz del proyecto PlacaV1.1
    libs = {}; propsmap = {}
    for p in parts:
        if p[1] not in libs: libs[p[1]], propsmap[p[1]] = flat_symbol(p[1])
    pinsmap = {k: sym_pins(v) for k, v in libs.items()}
    o = []
    o.append("(kicad_sch\n\t(version 20231120)\n\t(generator \"kicad_sch_builder\")\n\t(generator_version \"1.0\")")
    o.append("\t(uuid %s)\n\t(paper %s)" % (q(root), q(paper)))
    o.append("\t(title_block\n\t\t(title %s)\n\t\t(date %s)\n\t\t(rev %s)\n\t\t(company %s)\n\t)" %
             (q(title), q(datetime.date.today().isoformat()), q(rev), q(company)))
    o.append("\t(lib_symbols")
    for k in libs: o.append("\t\t" + libs[k].replace("\n", "\n\t\t"))
    o.append("\t)")
    nwires = nlabels = nnc = 0
    body = []
    for (blk, lib, ref, val, unit, X, Y, nets) in parts:
        props = propsmap[lib]
        s = ["\t(symbol", "\t\t(lib_id %s)" % q(lib), "\t\t(at %s %s 0)" % (f(X), f(Y)), "\t\t(unit %d)" % unit,
             "\t\t(exclude_from_sim no)", "\t\t(in_bom yes)", "\t\t(on_board yes)", "\t\t(dnp no)",
             "\t\t(uuid %s)" % q(uid("sym", ref, unit))]
        def prop(name, value, hide=False):
            _, ax, ay, ang = props.get(name, ("", 0, 0, 0))
            e = "(effects (font (size 1.27 1.27))%s)" % (" (hide yes)" if hide else "")
            return "\t\t(property %s %s (at %s %s %s) %s)" % (q(name), q(value), f(X + ax), f(Y - ay), f(ang), e)
        s.append(prop("Reference", ref))
        s.append(prop("Value", val))
        s.append(prop("Footprint", footprints.get(ref, ""), True))
        s.append(prop("Datasheet", props.get("Datasheet", ("", 0, 0, 0))[0], True))
        used = []
        for (u, num, nm, typ, px, py, ang) in pinsmap[lib]:
            if u not in (0, unit): continue
            used.append(num)
            s.append("\t\t(pin %s (uuid %s))" % (q(num), q(uid("pin", ref, unit, num))))
        s.append("\t\t(instances (project %s (path %s (reference %s) (unit %d))))" % (q(project), q("/" + root), q(ref), unit))
        s.append("\t)")
        body.append("\n".join(s))
        for (u, num, nm, typ, px, py, ang) in pinsmap[lib]:
            if u not in (0, unit): continue
            x, y = round(X + px, 2), round(Y - py, 2)
            if num in nets:
                d = OUT[ang]; ex, ey = round(x + d[0] * S, 2), round(y + d[1] * S, 2)
                body.append("\t(wire (pts (xy %s %s) (xy %s %s)) (stroke (width 0) (type default)) (uuid %s))" %
                            (f(x), f(y), f(ex), f(ey), q(uid("w", ref, unit, num))))
                just = "right" if LBL_ANG[d] in (180, 270) else "left"
                body.append("\t(label %s (at %s %s %d) (effects (font (size 1.27 1.27)) (justify %s bottom)) (uuid %s))" %
                            (q(nets[num]), f(ex), f(ey), LBL_ANG[d], just, q(uid("l", ref, unit, num))))
                nwires += 1; nlabels += 1
            elif typ != "no_connect":
                body.append("\t(no_connect (at %s %s) (uuid %s))" % (f(x), f(y), q(uid("nc", ref, unit, num)))); nnc += 1
    for k, (txt, x, y, sz) in enumerate(headers):
        body.append("\t(text %s (exclude_from_sim no) (at %s %s 0) (effects (font (size %s %s) bold) (justify left bottom)) (uuid %s))" %
                    (q(txt), f(x), f(y), sz, sz, q(uid("hdr", k))))
    for k, (txt, x, y) in enumerate(notes):
        body.append("\t(text %s (exclude_from_sim no) (at %s %s 0) (effects (font (size 1.27 1.27)) (justify left top)) (uuid %s))" %
                    (q(txt), f(x), f(y), q(uid("note", k))))
    o += body
    o.append("\t(sheet_instances (path \"/\" (page \"1\")))\n\t(embedded_fonts no)\n)")
    return "\n".join(o) + "\n", dict(wires=nwires, labels=nlabels, no_connect=nnc, symbols=len(parts), libs=len(libs))

if __name__ == "__main__":
    import importlib.util, argparse
    ap = argparse.ArgumentParser(description="Genera un .kicad_sch completo desde una spec Python")
    ap.add_argument("spec", help="archivo .py con PARTS, FOOT y opcionales TITLE, REV, COMPANY, PAPER, PROJECT, ROOT_UUID, HEADERS, NOTES")
    ap.add_argument("out", help="ruta del .kicad_sch a escribir (con KiCad cerrado o sin ese documento abierto)")
    a = ap.parse_args()
    sp = importlib.util.spec_from_file_location("spec", a.spec); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    g = lambda k, d=None: getattr(m, k, d)
    txt, st = build(m.PARTS, m.FOOT, title=g("TITLE", ""), rev=g("REV", "A"), company=g("COMPANY", ""), paper=g("PAPER", "A3"),
                    project=g("PROJECT", "proyecto"), root_uuid=g("ROOT_UUID"), notes=g("NOTES", ()), headers=g("HEADERS", ()))
    open(a.out, "w", encoding="utf-8").write(txt)
    print(a.out, st)
