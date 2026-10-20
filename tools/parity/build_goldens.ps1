param(
    [ValidateSet('fork', 'ref', 'both')][string]$Target = 'both',
    [int]$Mp = 4,
    [ValidateSet('debug', 'release')][string]$Config = 'debug',
    [switch]$NoLto
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$refRoot = Join-Path $PSScriptRoot '.ref\rive-runtime'
$vendor = Join-Path $repo 'vendor\rive-runtime'
if (-not (Test-Path $vendor)) {
    $common = (git -C $repo rev-parse --path-format=absolute --git-common-dir).Trim()
    $vendor = Join-Path (Split-Path $common -Parent) 'vendor\rive-runtime'
}

$env:GIT_CONFIG_COUNT = '1'
$env:GIT_CONFIG_KEY_0 = 'core.longpaths'
$env:GIT_CONFIG_VALUE_0 = 'true'
$env:CL = "-MP$Mp"
$env:MSYS2_ENV_CONV_EXCL = 'CL'
$env:PATH = 'C:\Program Files\Git\bin;' + $env:PATH

function Build-Goldens([string]$testsDir, [string]$label) {
    $log = Join-Path $env:TEMP "parity-build-$label.log"
    $exe = Join-Path $testsDir "out\$Config\goldens.exe"
    Remove-Item $exe -ErrorAction SilentlyContinue
    Push-Location $testsDir
    $ErrorActionPreference = 'Continue'
    try {
        $buildArgs = @('--toolset=msc')
        if ($NoLto) { $buildArgs += '--no-lto' }
        powershell -ExecutionPolicy Bypass -File ..\build\build_rive.ps1 @buildArgs $Config -- goldens *> $log
    } finally {
        Pop-Location
        $ErrorActionPreference = 'Stop'
    }
    $text = (Get-Content $log -Raw) -replace "`0", ''
    $summaries = [regex]::Matches($text, '(\d+)\s+(?:Erreur|Error)\(s\)')
    if ($summaries.Count -eq 0) { throw "$label build summary not found, see $log" }
    foreach ($summary in $summaries) {
        if ([int]$summary.Groups[1].Value -ne 0) { throw "$label build failed, see $log" }
    }
    if (-not (Test-Path $exe)) { throw "$exe missing, see $log" }
    Write-Host "$label : $exe"
}

if ($Target -in 'ref', 'both') {
    if (-not (Test-Path (Join-Path $refRoot '.git'))) {
        git -c core.longpaths=true clone $vendor $refRoot
        if ($LASTEXITCODE -ne 0) { throw 'clone of the reference runtime failed' }
    }
    $expected = (git -C $vendor rev-parse HEAD).Trim()
    $actual = (git -C $refRoot rev-parse HEAD).Trim()
    if ($expected -ne $actual) { throw "reference clone is at ${actual}, vendor is at ${expected}; delete ${refRoot}" }
    Build-Goldens (Join-Path $refRoot 'tests') 'ref'
}
if ($Target -in 'fork', 'both') {
    Build-Goldens (Join-Path $repo 'runtime\tests') 'fork'
}
