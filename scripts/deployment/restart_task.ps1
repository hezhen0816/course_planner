# Restart one Course Compass scheduled task and the python it spawned.
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\deployment\restart_task.ps1 -Task Course_Compass_Monitor -Marker backend.monitor.worker
# Stop-ScheduledTask only ends the .bat wrapper; the python child keeps running (and keeps :8000 or the
# worker alive), so it must be killed explicitly. Match on the command line marker AND on the process
# (or its parent venv launcher) living under the repo, never on every python on the machine.
param(
    [Parameter(Mandatory = $true)][string]$Task,
    [Parameter(Mandatory = $true)][string]$Marker,
    [string]$RepoMarker = 'course-compass'
)
$ErrorActionPreference = 'Stop'

Stop-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue

$all = Get-CimInstance Win32_Process -Filter "Name='python.exe'"
$candidates = $all | Where-Object { $_.CommandLine -like "*$Marker*" }
$victims = $candidates | Where-Object {
    $ppid = $_.ParentProcessId
    $parent = $all | Where-Object { $_.ProcessId -eq $ppid } | Select-Object -First 1
    ($_.ExecutablePath -like "*$RepoMarker*") -or
    ($null -ne $parent -and (($parent.ExecutablePath -like "*$RepoMarker*") -or ($parent.CommandLine -like "*$Marker*")))
}
foreach ($p in $victims) {
    Write-Output ("kill {0} {1}" -f $p.ProcessId, $p.CommandLine.Substring(0, [Math]::Min(70, $p.CommandLine.Length)))
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2
Start-ScheduledTask -TaskName $Task
Start-Sleep -Seconds 3
$state = (Get-ScheduledTask -TaskName $Task).State
$fresh = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*$Marker*" } |
    ForEach-Object { $_.CreationDate.ToString('HH:mm:ss') }
Write-Output ("{0}: {1}; python started at {2}" -f $Task, $state, ($fresh -join ', '))
