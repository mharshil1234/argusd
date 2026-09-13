param([switch]$Force)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$server = Join-Path $repoRoot "server\main.py"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Argusd interpreter not found at $python. Create .venv and install server\requirements.txt first."
}
if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
    throw "Codex CLI was not found on PATH. Install Codex, then rerun this script."
}

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& codex mcp get argusd *> $null
$exists = $LASTEXITCODE -eq 0
$ErrorActionPreference = $previousErrorActionPreference
if ($exists -and -not $Force) {
    Write-Output "Codex MCP server 'argusd' is already registered. Use -Force to replace it."
    exit 0
}
if ($exists) {
    & codex mcp remove argusd
    if ($LASTEXITCODE -ne 0) { throw "Unable to remove the existing Codex MCP registration." }
}

& codex mcp add argusd -- $python $server
if ($LASTEXITCODE -ne 0) { throw "Codex MCP registration failed." }

Write-Output "Registered Argusd with Codex using absolute project paths."
