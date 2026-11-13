# Esquemático generado por archivo (símbolos con pines reales)

Leer cuando haya que construir un esquemático completo (decenas de piezas) o cuando `kicad_sch_create_items` deje símbolos sin pines.

## Por qué existe
- `kicad_sch_create_items` coloca símbolos como **cáscaras vacías**: en el archivo guardado `lib_symbols` no trae pines ni cuerpo. Los cables y etiquetas quedan sin pin que tocar y el netlist sale vacío. Solución manual: *Herramientas → Actualizar símbolos desde biblioteca…* y repetirla cada vez que se agregan piezas nuevas.
- KiPilot no expone posiciones de pines, no puede asignar `Footprint`, y `kicad_sch_revert` / `open_document` no sirven para recargar un archivo reescrito (timeout o "no saved file on disk").
- Por eso, para esquemas grandes: **generar el `.kicad_sch` completo** con `scripts/kicad_sch_builder.py`, y usar KiPilot para leer, ajustar y exportar.

## Flujo
1. Escribir una spec Python (ver `scripts/ejemplo_rs232/spec.py`): `PARTS` = `(bloque, lib_id, ref, valor, unidad, X, Y, {pin: red})`, `FOOT` = `{ref: "Lib:Huella"}`, más `TITLE`, `PAPER`, `ROOT_UUID`, `HEADERS`, `NOTES`.
2. `python scripts/kicad_sch_builder.py spec.py salida.kicad_sch`. Define `KICAD_SYMBOL_DIR` si no encuentra las bibliotecas (en Windows las busca en `C:\Program Files\KiCad\*\share\kicad\symbols`).
3. `python scripts/netlist_check.py salida.kicad_sch spec.py` compara las redes del archivo con la spec usando `kicad-cli`. Es una comprobación de consistencia de lo generado, no ERC.
4. Hacer copia del esquemático anterior, copiar el archivo al proyecto **con el editor de esquemático cerrado** (o cerrarlo sin guardar y reabrir). Un editor con un documento vacío o viejo, al guardar, pisa el archivo bueno.
5. Reabrir y confirmar con `kicad_sch_get_symbols` (cantidad esperada) y, si hace falta, `kicad_sch_get_netlist`.

## Qué hace el builder
- Copia de la biblioteca oficial la definición completa de cada símbolo (resuelve `extends`: 74HC04→74LS04, MAX3232→MAX232, 6N137→HCPL-261A) y la embebe con el nombre `Lib:Nombre`.
- Cada pin conectado recibe un cable corto (5,08 mm hacia afuera) y una etiqueta con el nombre de red; cada pin sin conectar recibe una marca de no-conexión.
- Asigna `Footprint`, UUID estables (uuid5 por ref/unidad/pin) y la instancia de proyecto. Formato `version 20231120`, que KiCad 8+ lee y reescribe al guardar.

## Trampas encontradas
- Un salto de línea real dentro de un texto del esquemático hace que KiCad abra el archivo vacío: escapar como `\n`. (`q()` del builder ya lo hace.)
- Compuertas sin usar de un integrado multiunidad: no ponerlas en la misma coordenada que otra etiqueta; si el cable de una entrada termina en el mismo punto que el de otra señal, las redes se unen.
- Los nombres de red de etiquetas locales salen con prefijo `/` en el netlist y en el PCB (`/EQ_TX`). Mantenerlo en la PCB para que "Actualizar PCB desde esquemático" no renombre.
- Para que la actualización no duplique piezas, fijar el `path` de cada huella de la PCB a `/<uuid del símbolo>` (unidad más baja en multiunidad).
- `spin_style` de KiPilot admite `bottom|left|right|unknown|up`; `down` se rechaza.
- Si una escritura hace timeout, volver a leer antes de repetirla: puede haberse aplicado.
- No usar `Device:R` para algo que no sea resistencia; para módulos sin símbolo oficial (p. ej. DC-DC) usar un símbolo genérico (`Connector_Generic:Conn_01x04`) cuyo pinout coincida con el footprint, y verificar el pinout con el datasheet.
