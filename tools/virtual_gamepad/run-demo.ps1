$ErrorActionPreference = "Stop"

$moduleRoot = Split-Path -Parent $PSScriptRoot
$uiRoot = Join-Path $moduleRoot "ui"
$clientRoot = Join-Path $moduleRoot "client\python"
$env:PYTHONPATH = "$uiRoot;$clientRoot"

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$env:PYTHONPATH = Join-Path $repositoryRoot 'src'
python -m auto_modules.ui.virtual_gamepad.main --demo
