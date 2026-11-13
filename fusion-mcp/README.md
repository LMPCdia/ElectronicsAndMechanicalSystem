# MCP de Fusion (revisado y parcheado)

Copia del add-in de [faust-machines/fusion360-mcp-server](https://github.com/faust-machines/fusion360-mcp-server) (MIT, commit `19b9f1e`, oct-2026) con un parche de seguridad.

## Revisión (13-11-2026)
- **Arquitectura:** add-in dentro de Fusion que escucha en `localhost:9876` (TCP, JSON por línea, **sin autenticación**) + servidor MCP en Python (stdio) que lo llama. Dependencias del servidor: `mcp`, `anyio`, `click`. No hace llamadas a internet.
- **Capacidades:** bocetos, extrusiones, agujeros, parámetros, export STEP/STL/F3D, import de mallas y `execute_code` (Python arbitrario dentro de Fusion, con los permisos de tu usuario).
- **Riesgo encontrado:** el socket acepta un JSON suelto al final de cualquier conexión. Una **página web** puede hacer `fetch("http://localhost:9876", {method:"POST", body:'{"command":"execute_code",...}'})`, y el cuerpo del pedido HTTP se ejecutaba. Lo comprobamos con la versión original: el comando se despachaba.
- **Parche** (`Fusion360MCP/server/socket_server.py`, `_looks_like_http`): si lo recibido empieza como un pedido HTTP, se corta la conexión sin despachar nada. Verificado: HTTP → 0 comandos ejecutados; JSON normal → funciona igual.
- **Riesgo que queda:** cualquier programa que ya corra en tu PC puede conectarse al puerto (igual ya tendría tus permisos). No pongas `FUSION_MCP_HOST=0.0.0.0` y detené el add-in cuando no lo uses.

## Instalar (Windows)
1. Copiá la carpeta `Fusion360MCP` a `%AppData%\Autodesk\Autodesk Fusion 360\API\AddIns\`.
2. En Fusion: Utilidades → Scripts y complementos → Complementos → `Fusion360MCP` → Ejecutar.
3. Instalá `uv` (una vez): `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`.
4. Registrá el servidor MCP **de la misma versión que el add-in**:
   - Claude Code: `claude mcp add fusion360 -- uvx --from git+https://github.com/faust-machines/fusion360-mcp-server@19b9f1e fusion360-mcp-server --mode socket`
   - App de escritorio (config de MCP):
     ```json
     {"mcpServers": {"fusion360": {"command": "uvx", "args": ["--from", "git+https://github.com/faust-machines/fusion360-mcp-server@19b9f1e", "fusion360-mcp-server", "--mode", "socket"]}}}
     ```
5. Probá con un diseño abierto: pedile a Claude "listá los cuerpos del diseño de Fusion".

Límites: una operación por llamada, 30 s de tiempo máximo por operación. Para importar los STEP de la caja sigue siendo más simple el `fusion-watcher`.
