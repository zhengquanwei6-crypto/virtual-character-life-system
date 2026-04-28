param(
  [Parameter(Mandatory = $true)]
  [string]$Version
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path "$PSScriptRoot\.."
$git = (Get-Command git -ErrorAction SilentlyContinue).Source
if (-not $git -and (Test-Path "$root\.tools\PortableGit\cmd\git.exe")) {
  $git = "$root\.tools\PortableGit\cmd\git.exe"
}
if (-not $git) {
  throw "Git not found. Install Git or keep the portable Git under .tools."
}

Set-Content -Encoding ASCII "$root\VERSION" $Version

$backup = & "$PSScriptRoot\backup.ps1" -Version $Version
Write-Output "Backup created: $backup"

& $git -C $root add VERSION CHANGELOG.md README.md backend frontend deploy mobile scripts .github .gitignore .dockerignore
& $git -C $root commit -m "Release v$Version"
& $git -C $root tag "v$Version"

Write-Output "Created release tag v$Version. Push with:"
Write-Output "git -C $root push origin main --tags"
