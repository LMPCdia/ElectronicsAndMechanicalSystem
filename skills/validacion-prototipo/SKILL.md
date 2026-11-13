---
name: validacion-prototipo
description: Revisión cruzada de electrónica y mecánica, lista de compra y plan de pruebas para el prototipo; usar antes de imprimir o armar.
---
# Validación y prototipo
Checklist (marcar OK / FALTA / NO APLICA, nunca omitir):
- Redes del PCB == spec (`netlist_check.py`); 0 pistas sin conectar; 0 esquinas a 90°; cruces entre capas de redes PWM/HF a 90° (`cross90.py`), sin resolver listados.
- Alimentación: consumo total vs. capacidad; mínimo de carga del DC-DC; polaridad y protecciones.
- Aislación: distancias de fuga/aire según la tensión; franja sin cobre; huecos de tornillos.
- Huellas con modelo 3D (`audit_3d_models.py`) y alturas reales cargadas.
- Caja: ventanas vs. conectores, holgura de la placa, postes en agujeros de montaje, ventilación si hay calor.
- BOM: referencias, valores, huella, proveedor posible, cantidad + 10 % repuesto; marcar piezas sin stock local.
- Plan de pruebas: medir tensiones en puntos de prueba sin conectar la carga, luego con carga; prueba funcional paso a paso con valores esperados.
- Impresión: orientación, soportes, material, orden de ensamble, tornillería (M3 x largo).
Entregar: `bom.csv`, `plan_pruebas.md`, `pendientes.md` (qué no pudo verificarse y por qué: ERC/DRC de KiCad 10 no corridos, etc.).
