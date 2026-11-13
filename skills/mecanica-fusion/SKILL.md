---
name: mecanica-fusion
description: Diseña caja, soportes y montaje de una placa KiCad y los lleva a Fusion (watcher de carpeta o MCP); usar tras tener el PCB o su JSON mecánico.
---
# Mecánica y Fusion

Flujo: `board_to_enclosure_json.py` → `placa.json` → `gen_enclosure.py` (CadQuery) → `base/tapa.step|stl` → carpeta vigilada de Fusion.

1. Pedir al usuario: alturas reales de conectores/componentes altos, método de fijación (tornillos M3, encastre), conectores que deben salir, material e impresora (tolerancias).
2. Cargar `altura_mm` reales (datasheet) en el JSON; las alturas por defecto son **estimadas**.
3. Generar la caja: `python gen_enclosure.py placa.json salida/ config.json`. Leer `caja_reporte.md`.
4. **Ver en Fusion:** copiar los STEP a la carpeta que vigila el add-in `FusionWatcher` (ver `fusion-watcher/README.md` del plugin); cada STEP nuevo se importa solo como componente. Con el MCP de Fusion (cuando esté instalado y revisado) se pueden crear/ajustar operaciones en vivo; una operación por llamada.
5. Si el usuario pide un cambio (ventana más grande, otro poste), cambiar `config.json`/JSON, regenerar y re-copiar; no editar los STEP a mano.
6. Verificar: interferencia placa/caja contra el STEP de KiPilot, ventanas alineadas con los conectores, espesor mínimo imprimible (≥1,2 mm en FDM).
Límites: las cajas son rectangulares con ventanas; formas orgánicas se hacen a mano en Fusion.
