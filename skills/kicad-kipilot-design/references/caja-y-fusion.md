# De la placa a la caja: modelos 3D y traspaso a Fusion

Leer cuando el usuario pida modelos 3D, STEP, caja, soportes o integración con un CAD mecánico.

## Qué hace y qué no hace KiPilot
- Exporta la placa con `kicad_export_3d` (STEP) y vistas con `kicad_export_render`. **No se conecta a Fusion** ni diseña cajas. La skill de KiPilot solo pide mantener origen, unidades y revisión comunes con la aplicación que reciba el STEP.
- Un STEP exportado no prueba ajuste mecánico: solo se puede afirmar lo que se haya medido o revisado.

## Flujo
1. **Auditar modelos**: `python scripts/audit_3d_models.py placa.kicad_pcb` (Python de KiCad). Informa huellas sin modelo (puntos de prueba y agujeros de montaje no lo necesitan) y modelos genéricos a reemplazar (header en lugar de módulo DC-DC, jack genérico, zócalo sin el integrado, huella provisoria). Confirmar en el visor 3D que `${KICADn_3DMODEL_DIR}` resuelva en la versión instalada.
2. **Modelos faltantes o genéricos**: buscar el STEP del fabricante (datasheet, SnapEDA, Ultra Librarian) y asociarlo a la huella (propiedades de la huella, `${KIPRJMOD}/modelos/...`). Si no hay modelo, modelar un bloque con las medidas del datasheet y marcarlo como **inferido**. No deformar la huella para que calce con un STEP incorrecto.
3. **Exportar**: STEP con `kicad_export_3d`; datos para el CAD con `python scripts/board_to_enclosure_json.py placa.kicad_pcb datos.json` (contorno, espesor, agujeros de montaje, posición/rotación/lado/caja de cada huella, distancia a los bordes; un valor negativo significa que la pieza sobresale, p. ej. un DB9). Las alturas (`altura_mm`) quedan en `null` hasta cargarlas desde datasheet o modelo.
4. **Diseñar en Fusion** (ver abajo) a partir de ese JSON y del STEP: ventanas para conectores y LEDs, bases con tornillos en los agujeros de montaje, tapa, holgura de impresión o corte.

## Servidor MCP de Fusion (candidato, sin instalar)
- `faust-machines/fusion360-mcp-server` (PyPI `fusion360-mcp-server`, MIT, beta, un solo mantenedor, versión 0.1.0): servidor MCP por stdio + add-in de Fusion que escucha en `localhost:9876`. Expone ~80–93 herramientas (bocetos, extrusión, shell, agujeros, booleanas, parámetros, exportar STEP/STL/F3D). Importa mallas (`import_mesh`); **no lista importación de STEP** (hacerla con la interfaz de Fusion o con `execute_code`).
- Riesgos: el socket **no tiene autenticación**; `execute_code` ejecuta Python arbitrario dentro de Fusion; una operación por llamada y timeout de 30 s; tras un timeout revisar el estado antes de reintentar.
- Antes de instalar: leer el código de `addon/` y del servidor, confirmar que el bind es `127.0.0.1`, no definir `FUSION_MCP_HOST=0.0.0.0`, fijar la versión. La instalación y registro en Claude Desktop los ejecuta el usuario.
- Alternativas si no se instala nada: generar la caja en un entorno de script (CadQuery/OpenSCAD) y entregar STEP/STL, o usar el CAD que el usuario ya tenga automatizado.

## Qué informar
Piezas sin modelo, piezas con modelo genérico o inferido, medidas que faltan (alturas, jack real, módulo DC-DC), y que el ajuste mecánico no fue verificado salvo que se haya medido o revisado.
