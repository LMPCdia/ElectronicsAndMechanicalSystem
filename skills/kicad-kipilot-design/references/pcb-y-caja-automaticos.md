# PCB y caja automáticos (spec → esquema → PCB → caja)

Cadena probada con la interfaz RS232 aislada (46 huellas, 27 redes). Todo corre con el Python de KiCad (`pcbnew`), salvo la caja (CadQuery, `pip install cadquery`).

## Pasos
1. **spec.py** (PARTS, FOOT, HEADERS, NOTES): fuente única. `kicad_sch_builder.py spec.py PlacaX.kicad_sch` → esquema. `netlist_check.py` → redes coherentes.
2. **layout.json** (ver `ejemplo_rs232/layout.json`): contorno (`w,h,chamfer`), `pos` `[x,y,rot]` por referencia (todas las de la spec), `holes`, `texts`, `route` (ancho, separación, clase de potencia, vía), `keepouts` (franja sin cobre, p. ej. barrera de aislación) y `zones` (planos de masa).
3. `pcb/make_pcb.py spec.py layout.json salida/ --jar freerouting.jar` → `placa.kicad_pcb`: huellas con `path` al símbolo (no duplica al "Actualizar PCB desde esquemático"), ruteo Freerouting, planos, y **todas las esquinas/T a 90° convertidas en chaflán de 45°**. Redes con prefijo `/` como el esquema.
4. `board_to_enclosure_json.py placa.kicad_pcb placa.json` → datos mecánicos.
5. `gen_enclosure.py placa.json carpeta [config.json]` → `base`/`tapa` en STEP y STL + `caja_reporte.md`. Parámetros en `config.json` (pared, piso, holgura, poste_alto, tapa_esp, borde_max, led_d, sin_ventana…).

## Regla de cruces PWM / alta frecuencia (90° entre capas)
Si dos pistas de redes PWM o de alta frecuencia pasan una sobre la otra (en capas distintas), el cruce tiene que ser a **90°** para minimizar el acoplamiento. Es complementaria a la regla de esquinas: dentro de una misma pista nunca 90° (chaflán 45°); entre pistas que se cruzan en capas distintas, siempre 90°.
- Declarar en `layout.json`: `"hf_nets": ["PWM*", "CLK", ...]` y opcional `"hf_cross": {"modo": "ambas"|"alguna", "tol_grados": 2, "h": 0.6}`. `ambas` (por defecto) = solo cruces entre dos redes HF; `alguna` = cualquier cruce que involucre una red HF.
- `make_pcb.py` la aplica sola después del ruteo: desvío local en S (sin esquinas de 90°) que cruza en perpendicular a lo largo de 2·h mm; cada desvío se valida con el DRC y se deshace si empeora.
- Chequeo independiente: `python pcb/cross90.py placa.kicad_pcb layout.json` (sale 1 si hay cruces fuera de regla).
- Límite: si el cruce cae sobre un chaflán o a menos de ~2 mm del extremo de un tramo no hay lugar para el desvío; queda listado como "sin resolver" para corregir a mano (o mover piezas y re-rutear).

## Resultado de la prueba (RS232)
- PCB regenerada desde la spec: 0 pistas sin conectar, 0 esquinas a 90°, redes idénticas a la spec (27/27), DRC igual que la placa hecha a mano (solo avisos de serigrafía y de biblioteca).
- Caja: 116.5 × 80.5 × 25.6 mm, ventanas en J1, J2, JK1, JK2, 3 agujeros de LED, 4 postes M3. STEP válidos (1 sólido cada uno).

## Límites conocidos (decirlos al usuario)
- Colocación: la hace el usuario o Claude a mano en `layout.json`; no hay autocolocación. El ruteo es automático pero no reemplaza revisar.
- Alturas de componentes de la caja son **estimadas por tipo de huella** (tabla ALTURAS); cargar `altura_mm` real (datasheet/modelo 3D) antes de imprimir.
- Las ventanas son rectángulos al ancho de la caja de la huella + 1 mm; verificar el conector real. La tapa encastra por fricción (labio, tolerancia 0.25): ajustar a la impresora.
- Los 3D del PCB no se usan para la caja (solo cajas envolventes): el STEP de KiPilot sirve para verificar interferencias a mano.
- Fusion: el MCP de Fusion permite importar/ejecutar scripts, pero la caja aquí se genera fuera; Fusion solo recibe el STEP. Fusion no crea PCB.
- Sin DRC/ERC de KiCad 10 hasta que el usuario lo pida; `drc.py` de KiCad 7 es solo orientativo.
