# Reconstruye el historial de commits del proyecto (10 commits, en el orden de
# prioridad del enunciado: modelo y carga -> API -> interfaz -> ejecución).
# El detalle requisito -> commit está en TRAZABILIDAD.md.
#
# Uso:  powershell -File scripts/historial-commits.ps1

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (Test-Path .git) {
    Write-Host "Ya hay un repositorio git en $(Get-Location); no se toca."
    Write-Host "Para rehacer el historial: Remove-Item -Recurse -Force .git"
    git --no-pager log --oneline --reverse
    exit 0
}

git init -q
git symbolic-ref HEAD refs/heads/main

$email = git config user.email
if (-not $email) {
    git config user.email "dev@example.com"
    git config user.name "Desarrollador"
    Write-Host "Aviso: no habia identidad de git configurada; se uso una local a este repo."
}

function New-Commit {
    param(
        [Parameter(Mandatory = $true)][string] $Message,
        [Parameter(Mandatory = $true)][string[]] $Paths
    )
    foreach ($path in $Paths) {
        if (Test-Path $path) { git add -- $path }
    }
    git commit -q -m $Message
    git --no-pager log -1 --pretty="%h %s"
}

New-Commit "docs: enunciado de la prueba, datos de ejemplo y .gitignore" `
    @(".gitignore", "README.md", "data", "assets")

New-Commit "feat(db): esquema PostgreSQL y conexion" `
    @("backend/requirements.txt", "backend/app/__init__.py", "backend/app/config.py",
      "backend/app/db.py", "backend/app/schema.sql")

New-Commit "feat(ingesta): reglas del proveedor y descartes por motivo" `
    @("backend/app/normalize.py")

New-Commit "feat(ingesta): cargador idempotente con resumen de descartes" `
    @("backend/app/load.py")

New-Commit "feat(api): sesiones de 10 minutos y dias en America/Santiago" `
    @("backend/app/sessions.py")

New-Commit "feat(api): dispositivos, resumen diario y track GeoJSON" `
    @("backend/app/api.py")

New-Commit "feat(web): pantalla con filtros, sesiones y mapa Leaflet" `
    @("frontend")

New-Commit "feat(infra): servicio api en docker compose y Dockerfile" `
    @("docker-compose.yml", "backend/Dockerfile", ".env.example", ".dockerignore")

New-Commit "test: reglas de ingesta y cortes de sesion" `
    @("backend/tests", "backend/pytest.ini", "backend/requirements-dev.txt")

New-Commit "docs: decisiones, trazabilidad y reconstruccion del historial" `
    @("DECISIONES.md", "TRAZABILIDAD.md", "scripts")

Write-Host ""
Write-Host "Historial (mas antiguo primero):"
git --no-pager log --oneline --reverse
Write-Host ""
$pending = git status --porcelain
if ($pending) {
    Write-Host "Quedaron archivos sin trazabilidad:"
    git status --short
} else {
    Write-Host "Arbol limpio: todos los archivos del proyecto estan en algun commit."
}
