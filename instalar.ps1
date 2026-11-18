# Instalador de equipo-ingenieria en Windows.
# Uso (PowerShell, NO hace falta administrador):
#   powershell -ExecutionPolicy Bypass -File .\instalar.ps1
# Que hace (cada paso se salta si ya esta hecho):
#   1. uv (para correr el servidor MCP de Fusion y CadQuery sin tocar el Python de KiCad)
#   2. Java 21 (para Freerouting) con winget
#   3. Freerouting 1.9.0 en %LOCALAPPDATA%\equipo-ingenieria\ y variable FREEROUTING_JAR
#   4. Registra el MCP de Fusion en la app de escritorio de Claude (con copia de seguridad del config)
#   5. Si esta Claude Code (comando "claude"): agrega el marketplace, instala el plugin y registra el MCP
#   6. Copia los complementos de Fusion si no estan
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$Tools = Join-Path $env:LOCALAPPDATA "equipo-ingenieria"
$McpFrom = "git+https://github.com/faust-machines/fusion360-mcp-server@19b9f1e"
New-Item -ItemType Directory -Force -Path $Tools | Out-Null
function Paso($t) { Write-Host "`n== $t" -ForegroundColor Cyan }
function Ok($t) { Write-Host "   OK  $t" -ForegroundColor Green }
function Aviso($t) { Write-Host "   !!  $t" -ForegroundColor Yellow }
function Refrescar-Path { $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User") }

Paso "1/6 uv"
if (Get-Command uvx -ErrorAction SilentlyContinue) { Ok "uv ya instalado" }
else {
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    Refrescar-Path
    if (Get-Command uvx -ErrorAction SilentlyContinue) { Ok "uv instalado" } else { Aviso "uv no quedo en el PATH: cerra y abri PowerShell y volve a correr el script" }
}
$Uvx = (Get-Command uvx -ErrorAction SilentlyContinue).Source

Paso "2/6 Java"
$java = Get-Command java -ErrorAction SilentlyContinue
if ($java) { Ok ("java ya instalado: " + $java.Source) }
else {
    winget install --id Microsoft.OpenJDK.21 -e --accept-source-agreements --accept-package-agreements --silent
    Refrescar-Path
    if (Get-Command java -ErrorAction SilentlyContinue) { Ok "Java 21 instalado" } else { Aviso "Java instalado pero falta reabrir PowerShell para que aparezca en el PATH" }
}

Paso "3/6 Freerouting"
$Jar = Join-Path $Tools "freerouting-1.9.0.jar"
if (Test-Path $Jar) { Ok "ya descargado" }
else {
    Invoke-WebRequest "https://github.com/freerouting/freerouting/releases/download/v1.9.0/freerouting-1.9.0.jar" -OutFile $Jar
    Ok "descargado en $Jar"
}
[Environment]::SetEnvironmentVariable("FREEROUTING_JAR", $Jar, "User"); $env:FREEROUTING_JAR = $Jar
Ok "FREEROUTING_JAR=$Jar"

Paso "4/6 MCP de Fusion en la app de escritorio de Claude"
$Cfg = Join-Path $env:APPDATA "Claude\claude_desktop_config.json"
if (-not $Uvx) { Aviso "sin uv no se puede registrar (paso 1)" }
else {
    if (Test-Path $Cfg) {
        Copy-Item $Cfg "$Cfg.backup-$(Get-Date -Format yyyyMMdd-HHmmss)"
        $json = Get-Content $Cfg -Raw | ConvertFrom-Json
    } else { New-Item -ItemType Directory -Force -Path (Split-Path $Cfg) | Out-Null; $json = [pscustomobject]@{} }
    if (-not $json.PSObject.Properties["mcpServers"]) { $json | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) }
    $srv = [pscustomobject]@{ command = $Uvx; args = @("--from", $McpFrom, "fusion360-mcp-server", "--mode", "socket") }
    if ($json.mcpServers.PSObject.Properties["fusion360"]) { $json.mcpServers.fusion360 = $srv } else { $json.mcpServers | Add-Member -NotePropertyName fusion360 -NotePropertyValue $srv }
    $json | ConvertTo-Json -Depth 20 | Set-Content -Path $Cfg -Encoding UTF8
    Ok "fusion360 agregado a $Cfg (copia de seguridad al lado). Reinicia la app de Claude."
}

Paso "5/6 Claude Code (plugin + MCP)"
if (Get-Command claude -ErrorAction SilentlyContinue) {
    claude plugin marketplace add LMPCdia/ElectronicsAndMechanicalSystem
    claude plugin install equipo-ingenieria@lmpc-ingenieria
    if ($Uvx) { claude mcp add fusion360 -s user -- $Uvx --from $McpFrom fusion360-mcp-server --mode socket }
    Ok "plugin y MCP registrados en Claude Code"
} else { Aviso "Claude Code (comando 'claude') no esta instalado: se salta. En la app de escritorio el plugin se agrega desde la seccion de plugins." }

Paso "6/6 Complementos de Fusion"
$AddIns = Join-Path $env:APPDATA "Autodesk\Autodesk Fusion 360\API\AddIns"
foreach ($d in @(@("fusion-watcher\FusionWatcher", "FusionWatcher"), @("fusion-mcp\Fusion360MCP", "Fusion360MCP"))) {
    $dst = Join-Path $AddIns $d[1]
    if (Test-Path (Join-Path $dst ($d[1] + ".py"))) { Ok "$($d[1]) ya esta en AddIns" }
    else { Copy-Item -Recurse -Force (Join-Path $Repo $d[0]) $dst; Ok "$($d[1]) copiado" }
}
$kicad = Get-ChildItem "C:\Program Files\KiCad\*\bin\python.exe" -ErrorAction SilentlyContinue |
    Sort-Object { $v = ($_.Directory.Parent.Name -split '\.') + @('0', '0'); [int]($v[0] -replace '\D', '') * 1000 + [int]($v[1] -replace '\D', '') } -Descending |
    Select-Object -First 1
if ($kicad) { Ok "Python de KiCad: $($kicad.FullName)" } else { Aviso "no encontre el Python de KiCad en C:\Program Files\KiCad" }

Write-Host "`nListo. Falta solo en Fusion: Utilidades > Scripts y complementos > Complementos > ejecutar FusionWatcher y Fusion360MCP (tilda 'Ejecutar al iniciar')." -ForegroundColor Cyan
