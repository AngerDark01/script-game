$ErrorActionPreference = "Stop"

$moduleRoot = Split-Path -Parent $PSScriptRoot
$uiRoot = Join-Path $moduleRoot "ui"
$clientRoot = Join-Path $moduleRoot "client\python"
$env:PYTHONPATH = "$uiRoot;$clientRoot"

python -m virtual_gamepad_ui.main --demo
