# Downloads the Kotlin/JVM compiler into tools/kotlin (dashboard root = parent of scripts/).
# Requires PowerShell 5+ (Expand-Archive). kotlinc still needs a JDK on PATH at runtime.
$ErrorActionPreference = "Stop"
$version = "2.1.10"
$dashboardRoot = Split-Path -Parent $PSScriptRoot
$dest = Join-Path $dashboardRoot "tools\kotlin"
$marker = Join-Path $dest "bin\kotlinc.bat"
if (Test-Path $marker) {
    Write-Host "Kotlin compiler already present: $dest"
    exit 0
}
$url = "https://github.com/JetBrains/kotlin/releases/download/v$version/kotlin-compiler-$version.zip"
$zip = Join-Path $env:TEMP "kotlin-compiler-$version.zip"
$extract = Join-Path $env:TEMP "kotlin-extract-$version"
Write-Host "Downloading Kotlin compiler $version ..."
Invoke-WebRequest -Uri $url -OutFile $zip
if (Test-Path $extract) {
    Remove-Item $extract -Recurse -Force
}
Expand-Archive -LiteralPath $zip -DestinationPath $extract -Force
$inner = Get-ChildItem $extract -Directory | Select-Object -First 1
if (-not $inner) {
    throw "Unexpected Kotlin zip layout (no root directory)."
}
$kotlinc = Join-Path $inner.FullName "bin\kotlinc.bat"
if (-not (Test-Path $kotlinc)) {
    throw "Unexpected Kotlin zip layout (missing bin\kotlinc.bat)."
}
if (Test-Path $dest) {
    Remove-Item $dest -Recurse -Force
}
$toolsDir = Join-Path $dashboardRoot "tools"
if (-not (Test-Path $toolsDir)) {
    New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
}
Move-Item $inner.FullName $dest
Write-Host "Kotlin compiler installed: $dest"
