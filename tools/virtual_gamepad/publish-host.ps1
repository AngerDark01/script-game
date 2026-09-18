$ErrorActionPreference = "Stop"

$moduleRoot = Split-Path -Parent $PSScriptRoot
$project = Join-Path $moduleRoot "host\src\VirtualGamepadHost\VirtualGamepadHost.csproj"
$output = Join-Path $moduleRoot "dist\host"

New-Item -ItemType Directory -Force $output | Out-Null
dotnet publish $project -c Release -r win-x64 --self-contained true -o $output
Write-Output "Published host to $output"
