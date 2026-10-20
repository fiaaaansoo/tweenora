param(
    [ValidateSet('fork', 'ref', 'both')][string]$Target = 'both',
    [ValidateSet('debug', 'release')][string]$Config = 'release'
)

$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$repo = (Resolve-Path (Join-Path $here '..\..\..')).Path
$trees = @{
    fork = Join-Path $repo 'runtime'
    ref  = Join-Path $repo 'tools\parity\.ref\rive-runtime'
}
$env:PATH = 'C:\Program Files (x86)\Microsoft Visual Studio\Installer;' + $env:PATH
$vcvars = 'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat'
if (-not (Test-Path $vcvars)) { throw "vcvars64.bat not found: $vcvars" }

$defines = @(
    'WITH_RIVE_TOOLS', 'WITH_RIVE_TEXT', 'RIVE_CANVAS', 'WITH_RIVE_LAYOUT', 'NOMINMAX',
    '_CRT_SECURE_NO_WARNINGS', 'RIVE_WINDOWS', 'RIVE_DESKTOP_GL', 'ORE_BACKEND_GL',
    'ORE_BACKEND_D3D11', 'ORE_BACKEND_D3D12', 'RIVE_ORE', 'YOGA_EXPORT=', '_RIVE_INTERNAL_',
    '_USE_MATH_DEFINES', '_HAS_EXCEPTIONS=0'
)
if ($Config -eq 'release') { $defines += @('RELEASE', 'NDEBUG') } else { $defines += @('DEBUG', '_DEBUG') }
$runtimeFlag = if ($Config -eq 'release') { '/MT' } else { '/MTd' }
$optimization = if ($Config -eq 'release') { '/O2' } else { '/Od' }
$commonFlags = @('/nologo', '/std:c++17', '/GR-', '/EHs-c-', $runtimeFlag, $optimization, '/W0')
$libNames = @('', '_harfbuzz', '_sheenbidi', '_yoga', '_decoders')
$extraLibs = @('libpng.lib', 'libjpeg.lib', 'libwebp.lib', 'zlib.lib', 'miniaudio.lib')

function Build-Tree([string]$label) {
    $root = $trees[$label]
    $tests = Join-Path $root 'tests'
    $outLib = Join-Path $tests "out\$Config"
    $prefix = if (Test-Path (Join-Path $outLib 'tweenora.lib')) { 'tweenora' } else { 'rive' }
    $includes = @(
        (Join-Path $root 'include'),
        (Join-Path $tests 'dependencies\rive-app_harfbuzz_rive_13.1.1\src'),
        (Join-Path $tests 'dependencies\Tehreer_SheenBidi_v2.6\Headers'),
        (Join-Path $tests 'dependencies\rive-app_miniaudio_rive_changes_5'),
        (Join-Path $tests 'dependencies\rive-app_yoga_rive_yoga_fb91f6cb0f8f'),
        (Join-Path $root 'dependencies'),
        (Join-Path $root 'renderer\include')
    )
    $libs = @($libNames | ForEach-Object { "$prefix$_.lib" }) + $extraLibs
    $outDir = Join-Path $here "out\$label"
    New-Item -ItemType Directory -Force $outDir | Out-Null
    $exe = Join-Path $outDir "sm_trace_$Config.exe"
    Remove-Item $exe -ErrorAction SilentlyContinue
    $source = Join-Path $here 'sm_trace.cpp'
    $noOp = Join-Path $root 'utils\no_op_factory.cpp'
    $clArgs = @($commonFlags) + ($defines | ForEach-Object { "/D$_" }) + ($includes | ForEach-Object { "/I`"$_`"" }) +
        @("`"$source`"", "`"$noOp`"", "/Fo$outDir\", "/Fe`"$exe`"", '/link', "/LIBPATH:`"$outLib`"") + $libs +
        @('ws2_32.lib', 'user32.lib', 'gdi32.lib', 'advapi32.lib', 'shell32.lib', 'ole32.lib')
    $commandLine = "cl $($clArgs -join ' ')"
    Set-Content -Path (Join-Path $outDir "command_$Config.txt") -Value ($commandLine -replace [regex]::Escape($root), '<TREE>')
    $log = Join-Path $env:TEMP "sm-trace-build-$label.log"
    $ErrorActionPreference = 'Continue'
    cmd /c "`"$vcvars`" >nul && $commandLine" *> $log
    $ErrorActionPreference = 'Stop'
    if (-not (Test-Path $exe)) { throw "$label build failed, see $log" }
    Write-Host "$label : $exe"
}

if ($Target -in 'fork', 'both') { Build-Tree 'fork' }
if ($Target -in 'ref', 'both') { Build-Tree 'ref' }
