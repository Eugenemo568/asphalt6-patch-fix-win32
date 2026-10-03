# Asphalt 6 Win32 port fixer - Windows PowerShell 5.1+ / PowerShell 7
#   .\patch.ps1 [-GameDir <folder>] [-DebugLog] [-Restore]
# The original exe is kept as "Asphalt 6.exe.orig"; -Restore puts it back.
[CmdletBinding()]
param(
    [string]$GameDir,
    [switch]$DebugLog,
    [switch]$Restore
)
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExeName = 'Asphalt 6.exe'
$BakName = 'Asphalt 6.exe.orig'

function Fail([string]$msg) { Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }

function Get-Sha256([byte[]]$data) {
    $h = [System.Security.Cryptography.SHA256]::Create()
    try { return (-join ($h.ComputeHash($data) | ForEach-Object { $_.ToString('x2') })) } finally { $h.Dispose() }
}

function ConvertFrom-Hex([string]$hex) {
    $b = New-Object byte[] ($hex.Length / 2)
    for ($i = 0; $i -lt $b.Length; $i++) { $b[$i] = [Convert]::ToByte($hex.Substring($i * 2, 2), 16) }
    return ,$b
}

function Test-Bytes([byte[]]$buf, [int]$offset, [byte[]]$expect) {
    for ($i = 0; $i -lt $expect.Length; $i++) { if ($buf[$offset + $i] -ne $expect[$i]) { return $false } }
    return $true
}

function Find-GameDir {
    $candidates = @()
    if ($GameDir) { $candidates += $GameDir }
    $candidates += $Here, (Split-Path -Parent $Here), (Get-Location).Path
    foreach ($d in $candidates) {
        if ($d -and ((Test-Path -LiteralPath (Join-Path $d $ExeName)) -or (Test-Path -LiteralPath (Join-Path $d $BakName)))) {
            return (Resolve-Path -LiteralPath $d).Path
        }
    }
    if ($GameDir) { Fail "`"$ExeName`" not found in $GameDir" }
    if ($env:OS -eq 'Windows_NT') {
        Add-Type -AssemblyName System.Windows.Forms
        $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
        $dlg.Description = "Select the Asphalt 6 folder (the one with `"$ExeName`")"
        if ($dlg.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
            if (Test-Path -LiteralPath (Join-Path $dlg.SelectedPath $ExeName)) { return $dlg.SelectedPath }
        }
    }
    Fail "`"$ExeName`" not found. Put this patcher into the game folder or pass -GameDir."
}

$dir = Find-GameDir
$exe = Join-Path $dir $ExeName
$bak = Join-Path $dir $BakName
Write-Host "Game folder: $dir"

if ($Restore) {
    if (-not (Test-Path -LiteralPath $bak)) { Fail "no backup `"$BakName`" to restore" }
    Copy-Item -LiteralPath $bak -Destination $exe -Force
    Write-Host 'Restored the original exe.' -ForegroundColor Green
    exit 0
}

$spec = Get-Content -LiteralPath (Join-Path (Join-Path $Here 'patches') 'asphalt6-win32.json') -Raw | ConvertFrom-Json

# Select groups: all default ones (+ debug-log on request); skip duplicate offsets.
$names = @()
foreach ($p in $spec.groups.PSObject.Properties) { if ($p.Value.default) { $names += $p.Name } }
if ($DebugLog) { $names += 'debug-log' }
$patches = @(); $seen = @{}
foreach ($n in $names) {
    foreach ($p in $spec.groups.$n.patches) {
        if (-not $seen.ContainsKey([string]$p.offset)) { $seen[[string]$p.offset] = $true; $patches += $p }
    }
}

# Always patch from the pristine original (the backup if one exists).
$src = $exe
if (Test-Path -LiteralPath $bak) { $src = $bak }
[byte[]]$buf = [System.IO.File]::ReadAllBytes($src)
$sha = Get-Sha256 $buf

if ($sha -ne $spec.original_sha256) {
    if ($src -eq $exe) {
        $applied = $true
        foreach ($p in $patches) { if (-not (Test-Bytes $buf ([int]$p.offset) (ConvertFrom-Hex $p.patched))) { $applied = $false; break } }
        if ($applied) { Write-Host 'Already patched - nothing to do.' -ForegroundColor Green; exit 0 }
    }
    Fail ("unknown version of the exe (sha256 $sha).`n" +
          "This patch is for Asphalt6-Win32.zip from archive.org/details/asphalt-6-win-32 (sha256 $($spec.original_sha256)).")
}

foreach ($p in $patches) {
    $o = [int]$p.offset
    $old = ConvertFrom-Hex $p.original
    $new = ConvertFrom-Hex $p.patched
    if (-not (Test-Bytes $buf $o $old)) { Fail ("unexpected bytes at 0x{0:x} - aborting, nothing was written" -f $o) }
    [Array]::Copy($new, 0, $buf, $o, $new.Length)
}

if (-not (Test-Path -LiteralPath $bak)) {
    Copy-Item -LiteralPath $exe -Destination $bak
    Write-Host "Backup: `"$BakName`""
}
[System.IO.File]::WriteAllBytes($exe, $buf)
Write-Host ("Applied: {0} ({1} patches)" -f ($names -join ', '), $patches.Count) -ForegroundColor Green
Write-Host "sha256: $(Get-Sha256 $buf)"

# Convenience launchers next to the game
$launchers = Join-Path $Here 'launchers'
if (Test-Path -LiteralPath $launchers) {
    Get-ChildItem -LiteralPath $launchers -Filter *.bat | ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $dir -Force }
    Write-Host 'Copied launchers: windowed / diagnostic log.'
}
exit 0
