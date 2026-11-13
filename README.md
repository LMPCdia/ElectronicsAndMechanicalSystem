# equipo-ingenieria
Plugin de Claude: equipo de agentes (director, electrónica, mecánica, revisor, prototipado) para llevar un producto de la idea al prototipo impreso.
- `/nuevo-producto` arranca con una entrevista y un `brief.md`.
- Skills: `proyecto-producto`, `kicad-kipilot-design`, `mecanica-fusion`, `validacion-prototipo`.
- `fusion-watcher/`: add-in de Fusion que importa los STEP que genera el equipo (ver su README).
## Instalar
- **Windows, todo junto:** `powershell -ExecutionPolicy Bypass -File .\instalar.ps1` (uv, Java, Freerouting, MCP de Fusion en la app de Claude y en Claude Code, plugin y complementos de Fusion).
- **Claude Code:** `/plugin marketplace add LMPCdia/ElectronicsAndMechanicalSystem` y después `/plugin install equipo-ingenieria@lmpc-ingenieria`.
- **Fusion:** `fusion-watcher/` (importa STEP solo) y `fusion-mcp/` (MCP revisado y parcheado; ver su README).
- Tests: `FREEROUTING_JAR=ruta/freerouting.jar python tests/run_tests.py` (con el Python de KiCad; `--rapido` saltea el ruteo completo).
- Requisitos: KiCad (Python con pcbnew), KiPilot MCP (opcional), Freerouting (jar), `pip install cadquery`, Java.
Estado: v0.1 — pipeline KiCad y caja probados con la interfaz RS232; watcher sin probar en Fusion; MCP de Fusion pendiente de revisión.
