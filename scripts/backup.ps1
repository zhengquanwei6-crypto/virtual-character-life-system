param(
  [string]$Version = (Get-Content "$PSScriptRoot\..\VERSION" -ErrorAction SilentlyContinue),
  [string]$OutputDir = "$PSScriptRoot\..\backups"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\.."
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$safeVersion = if ($Version) { $Version.Trim() } else { "manual" }
$targetDir = Join-Path $OutputDir "$stamp-$safeVersion"

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

if (Test-Path "$root\backend\data") {
  Copy-Item "$root\backend\data" "$targetDir\data" -Recurse -Force
}

if (Test-Path "$root\backend\.env") {
  Copy-Item "$root\backend\.env" "$targetDir\backend.env" -Force
}

@{
  version = $safeVersion
  createdAt = (Get-Date).ToString("o")
  source = "$root"
} | ConvertTo-Json | Set-Content -Encoding UTF8 "$targetDir\metadata.json"

Compress-Archive -Path "$targetDir\*" -DestinationPath "$targetDir.zip" -Force
Write-Output "$targetDir.zip"

