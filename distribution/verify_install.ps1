param(
    [Parameter(Mandatory=$true)][string]$Setup,
    [Parameter(Mandatory=$true)][string]$Payload,
    [Parameter(Mandatory=$true)][string]$TestRoot
)
$ErrorActionPreference = 'Stop'
if (-not [Environment]::Is64BitProcess) { throw 'Verification requires 64-bit PowerShell for the correct installation registry view.' }
$testLocation = [IO.Path]::GetFullPath($TestRoot)
$workspaceBuild = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../build')) + '\'
if (-not $testLocation.StartsWith($workspaceBuild, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'TestRoot must be a new folder under this workspace build directory.'
}
if (Test-Path -LiteralPath $testLocation) { throw 'TestRoot must not already exist.' }
$registration = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{6D7B4AA5-2AB1-4A57-A063-2F3D822D6F91}_is1'
if (Test-Path -LiteralPath $registration) { throw 'An installed workbench already exists; refusing to replace its registration.' }
New-Item -ItemType Directory -Path $testLocation | Out-Null
$env:AUTO_MODULES_DATA_DIR = Join-Path $testLocation 'user-data'
$installLocation = Join-Path $testLocation 'installed'
$report = [ordered]@{ success = $false; install = $null; upgrade = $null; uninstall = $null }
function Run-Checked([string]$Executable, [string[]]$Arguments) {
    $process = Start-Process -FilePath $Executable -ArgumentList $Arguments -WindowStyle Hidden -PassThru -Wait
    if ($process.ExitCode -ne 0) { throw ('Command failed: ' + $Executable + ', code ' + $process.ExitCode) }
}
try {
    # Tests an existing driver only: never install/remove a driver for validation.
    Run-Checked (Join-Path $Payload 'AutoModules.exe') @('--check-driver')
    $installArgs = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOICONS', '/TASKS=maps', ('/DIR="' + $installLocation + '"'))
    Run-Checked $Setup ($installArgs + ('/LOG="' + (Join-Path $testLocation 'install.log') + '"'))
    $report.install = 'passed'
    $launcher = Join-Path $installLocation 'AutoModules.exe'
    Run-Checked $launcher @('--self-test')
    $config = Join-Path $env:AUTO_MODULES_DATA_DIR 'config.json'
    $beforeHash = (Get-FileHash -LiteralPath $config -Algorithm SHA256).Hash
    $mapRoot = Join-Path $env:AUTO_MODULES_DATA_DIR 'map_data'
    $mapBefore = @(Get-ChildItem -LiteralPath $mapRoot -File -Recurse | Get-FileHash -Algorithm SHA256)
    $marker = Join-Path $mapRoot 'installer-preservation-marker.txt'
    'Keep this user-created map marker through upgrade and uninstall.' | Set-Content -LiteralPath $marker
    $env:PYTHONPATH = ''
    $env:PYTHONHOME = ''
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    & (Join-Path $installLocation 'python/python.exe') -I -B (Join-Path $installLocation 'app/smoke_check.py') *> (Join-Path $testLocation 'installed-smoke.log')
    if ($LASTEXITCODE -ne 0) { throw 'Installed Python smoke failed.' }
    Run-Checked $Setup ($installArgs + ('/LOG="' + (Join-Path $testLocation 'upgrade.log') + '"'))
    Run-Checked $launcher @('--self-test')
    if ((Get-FileHash -LiteralPath $config -Algorithm SHA256).Hash -ne $beforeHash) { throw 'Upgrade changed user configuration.' }
    foreach ($file in $mapBefore) {
        if ((Get-FileHash -LiteralPath $file.Path -Algorithm SHA256).Hash -ne $file.Hash) { throw ('Upgrade changed map: ' + $file.Path) }
    }
    if (-not (Test-Path -LiteralPath $marker)) { throw 'Upgrade removed user marker.' }
    $report.upgrade = 'passed, configuration and maps preserved'
    Run-Checked (Join-Path $installLocation 'unins000.exe') @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', ('/LOG="' + (Join-Path $testLocation 'uninstall.log') + '"'))
    if (-not (Test-Path -LiteralPath $config) -or -not (Test-Path -LiteralPath $marker)) { throw 'Uninstall removed user data.' }
    if (Test-Path -LiteralPath $launcher) { throw 'Uninstall left launcher behind.' }
    $report.uninstall = 'passed, user data retained'
    $report.success = $true
} catch {
    $report.error = $_.Exception.ToString()
} finally {
    $report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $testLocation 'result.json') -Encoding UTF8
}
if (-not $report.success) { exit 1 }
