<#
.SYNOPSIS
    Dark Souls II: Scholar of the First Sin - make the game use XInput only.

.DESCRIPTION
    DarkSoulsII.exe binds player 1 to the first DirectInput game controller it
    finds and never falls back to XInput afterwards. Non-Xbox pads (Switch Pro,
    PowerA, generic HID) then move too slowly, or give no input at all once
    Steam Input is enabled. Phantom devices (wheels, vJoy, RGB software) can
    steal Xbox pads the same way.

    This flips one byte (file offset 0xEF5DA6, VA 0x140ef69a6: jne -> jmp) so
    the game skips its DirectInput gamepad scan. Keyboard and mouse are opened
    separately and keep working. Non-Xbox pads then need Steam Input enabled.

    Only the current Steam build is patched (verified by SHA-256). The original
    exe is kept as DarkSoulsII.exe.original.

.PARAMETER Action
    apply (default), status, or restore.

.PARAMETER GameDir
    The game's "Game" folder, the folder above it, or DarkSoulsII.exe itself.
    Leave empty to find the game through Steam's library folders.

.PARAMETER SteamPath
    Steam install folder. Only needed if Steam isn't in the registry.

.EXAMPLE
    .\ds2_xinput_patch.ps1
.EXAMPLE
    .\ds2_xinput_patch.ps1 restore "D:\SteamLibrary\steamapps\common\Dark Souls II Scholar of the First Sin\Game"
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('apply', 'status', 'restore')]
    [string]$Action = 'apply',

    [Parameter(Position = 1)]
    [string]$GameDir = '',

    [string]$SteamPath = ''
)

$ErrorActionPreference = 'Stop'

$AppId = 335300
$OriginalSha256 = '0045931b8914504531b7864a9488d396dc50cbaf524964016e1d69c3d1173131'
$PatchOffset = 0xEF5DA6
$Jne = [byte]0x75
$Jmp = [byte]0xEB

function Fail([string]$Message) {
    Write-Host $Message -ForegroundColor Red
    exit 1
}

function Get-Sha256([byte[]]$Data) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString($sha.ComputeHash($Data)).Replace('-', '').ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

# 'original', 'patched', or 'unknown'
function Get-ExeState([byte[]]$Data) {
    if ((Get-Sha256 $Data) -eq $OriginalSha256) { return 'original' }
    if ($Data.Length -gt $PatchOffset -and $Data[$PatchOffset] -eq $Jmp) {
        $copy = [byte[]]$Data.Clone()
        $copy[$PatchOffset] = $Jne
        if ((Get-Sha256 $copy) -eq $OriginalSha256) { return 'patched' }
    }
    return 'unknown'
}

function Get-StateText([string]$State) {
    switch ($State) {
        'original' { 'original (unpatched)' }
        'patched' { 'PATCHED (XInput only)' }
        default { 'unknown - not the current Steam build, or changed by another tool' }
    }
}

function Get-SteamRoots {
    $roots = New-Object System.Collections.Generic.List[string]
    if ($SteamPath) { $roots.Add($SteamPath) }
    foreach ($key in 'HKCU:\Software\Valve\Steam', 'HKLM:\SOFTWARE\WOW6432Node\Valve\Steam', 'HKLM:\SOFTWARE\Valve\Steam') {
        $props = Get-ItemProperty -Path $key -ErrorAction SilentlyContinue
        if (-not $props) { continue }
        foreach ($name in 'SteamPath', 'InstallPath') {
            if ($props.$name) { $roots.Add([string]$props.$name) }
        }
    }
    if (${env:ProgramFiles(x86)}) { $roots.Add((Join-Path ${env:ProgramFiles(x86)} 'Steam')) }
    return $roots | ForEach-Object { $_.Replace('/', '\') } | Select-Object -Unique
}

function Find-GameDir {
    $libraries = New-Object System.Collections.Generic.List[string]
    foreach ($root in Get-SteamRoots) {
        $libraries.Add($root)
        $vdf = Join-Path $root 'steamapps\libraryfolders.vdf'
        if (-not (Test-Path -LiteralPath $vdf)) { continue }
        foreach ($m in [regex]::Matches([IO.File]::ReadAllText($vdf), '"path"\s+"([^"]+)"')) {
            $libraries.Add($m.Groups[1].Value.Replace('\\', '\'))
        }
    }
    foreach ($lib in ($libraries | Select-Object -Unique)) {
        $acf = Join-Path $lib "steamapps\appmanifest_$AppId.acf"
        if (-not (Test-Path -LiteralPath $acf)) { continue }
        $m = [regex]::Match([IO.File]::ReadAllText($acf), '"installdir"\s+"([^"]+)"')
        if (-not $m.Success) { continue }
        $dir = Join-Path (Join-Path (Join-Path $lib 'steamapps\common') $m.Groups[1].Value) 'Game'
        if (Test-Path -LiteralPath (Join-Path $dir 'DarkSoulsII.exe')) { return $dir }
    }
    return $null
}

function Resolve-GameDir {
    if (-not $GameDir) { return Find-GameDir }
    $p = $GameDir.Trim().Trim('"').TrimEnd('\')
    if (Test-Path -LiteralPath $p -PathType Leaf) { $p = Split-Path -Parent $p }
    if (-not (Test-Path -LiteralPath (Join-Path $p 'DarkSoulsII.exe')) -and
        (Test-Path -LiteralPath (Join-Path $p 'Game\DarkSoulsII.exe'))) {
        $p = Join-Path $p 'Game'
    }
    return $p
}

$dir = Resolve-GameDir
if (-not $dir) {
    Fail ("Couldn't find Dark Souls II: Scholar of the First Sin in your Steam libraries.`n" +
        "Drag the game's 'Game' folder onto the .bat file, or run:`n" +
        "  .\ds2_xinput_patch.ps1 $Action `"<path to ...\Dark Souls II Scholar of the First Sin\Game>`"")
}
$exe = Join-Path $dir 'DarkSoulsII.exe'
$backup = Join-Path $dir 'DarkSoulsII.exe.original'
if (-not (Test-Path -LiteralPath $exe)) { Fail "DarkSoulsII.exe not found in: $dir" }

Write-Host "Game folder: $dir"
$current = [IO.File]::ReadAllBytes($exe)
$state = Get-ExeState $current
Write-Host "DarkSoulsII.exe: $(Get-StateText $state)"
if ($Action -eq 'status') { exit 0 }

$want = 'patched'
if ($Action -eq 'restore') { $want = 'original' }
if ($state -eq $want) {
    Write-Host 'Nothing to do.' -ForegroundColor Green
    exit 0
}

# Get an untouched copy of the exe to work from.
if ($state -eq 'original') {
    $original = $current
    if (-not (Test-Path -LiteralPath $backup)) {
        Copy-Item -LiteralPath $exe -Destination $backup
        Write-Host 'Backed up the original exe -> DarkSoulsII.exe.original'
    }
} elseif ($state -eq 'patched') {
    $original = [byte[]]$current.Clone()
    $original[$PatchOffset] = $Jne
} elseif ((Test-Path -LiteralPath $backup) -and
          (Get-ExeState ([IO.File]::ReadAllBytes($backup))) -eq 'original') {
    $original = [IO.File]::ReadAllBytes($backup)
} else {
    Fail ("This DarkSoulsII.exe isn't the current Steam build of Scholar of the First Sin, and no clean backup was found.`n" +
        "In Steam: right-click the game > Properties > Installed Files > Verify integrity of game files, then run this again.")
}

$target = [byte[]]$original.Clone()
if ($want -eq 'patched') { $target[$PatchOffset] = $Jmp }

if ($state -eq 'unknown') {
    # Keep whatever another tool put there instead of silently discarding it.
    $keep = "DarkSoulsII.exe.replaced-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Copy-Item -LiteralPath $exe -Destination (Join-Path $dir $keep)
    Write-Host "Saved the previously modified exe -> $keep"
}

try {
    [IO.File]::WriteAllBytes($exe, $target)
} catch [UnauthorizedAccessException] {
    Fail ('Access denied writing DarkSoulsII.exe. Make sure the file is not read-only (right-click > Properties),' +
        "`nor right-click the .bat file and choose `"Run as administrator`".")
} catch [IO.IOException] {
    Fail 'DarkSoulsII.exe is in use. Close Dark Souls II and try again.'
}

$after = Get-ExeState ([IO.File]::ReadAllBytes($exe))
if ($after -ne $want) { Fail "Write did not stick (exe is now: $(Get-StateText $after))." }
Write-Host "DarkSoulsII.exe: $(Get-StateText $after)" -ForegroundColor Green
if ($want -eq 'patched') {
    Write-Host 'Non-Xbox controller? In Steam: Dark Souls II > Properties > Controller > "Enable Steam Input".'
}
