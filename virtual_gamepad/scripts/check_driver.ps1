$ErrorActionPreference = "Stop"

$devices = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
    Where-Object { $_.FriendlyName -match "ViGEm|Virtual Gamepad Emulation" }

if ($devices) {
    $devices | Select-Object Status,Class,FriendlyName,InstanceId | Format-Table -AutoSize
    Write-Output "ViGEmBus appears to be installed."
    exit 0
}

Write-Output "ViGEmBus was not found. Install the signed ViGEmBus driver before using a real virtual controller."
exit 1
