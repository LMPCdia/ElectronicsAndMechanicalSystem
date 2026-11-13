# Fusion Watcher (add-in)
Importa a Fusion cada `.step` que aparezca en una carpeta. Es lo que usa el agente mecánico para que veas la caja aparecer.
Seguridad: solo lee archivos de la carpeta; no abre puertos ni ejecuta código externo.
## Instalar (Windows)
1. Copiá la carpeta `FusionWatcher` a `%AppData%\Autodesk\Autodesk Fusion 360\API\AddIns\`.
2. En Fusion: `Utilidades` → `Scripts y complementos` → pestaña *Complementos* → `FusionWatcher` → *Ejecutar* (tildá *Ejecutar al iniciar* si querés).
3. Carpeta vigilada: `Documentos\FusionWatcher` (o variable `FUSION_WATCH_DIR`). Abrí un diseño antes de copiar STEP.
## Uso
El agente deja `base.step`/`tapa.step` en esa carpeta y aparecen como componentes. Si regenera el mismo archivo, se importa otra copia: borrá la vieja.
**No probado en Fusion real todavía**: primera prueba pendiente en tu máquina.
