param(
    [string]$PythonCommand = "python"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $ScriptDir ".."))
$BuildRoot = Join-Path $ProjectRoot ".build\windows"
$VenvDir = Join-Path $BuildRoot "venv"
$WorkDir = Join-Path $BuildRoot "pyinstaller"
$DistDir = Join-Path $ProjectRoot "dist\windows"
$Jar = Join-Path $ProjectRoot "release\banhelper-bridge-2.0.0.jar"

if (-not (Test-Path -LiteralPath $Jar -PathType Leaf)) { throw "Fabric JAR not found: $Jar" }
if (Test-Path -LiteralPath $BuildRoot) { Remove-Item -LiteralPath $BuildRoot -Recurse -Force }
if (Test-Path -LiteralPath $DistDir) { Remove-Item -LiteralPath $DistDir -Recurse -Force }
New-Item -ItemType Directory -Path $BuildRoot, $DistDir -Force | Out-Null

& $PythonCommand -m venv $VenvDir
if ($LASTEXITCODE -ne 0) { throw "Unable to create build venv" }
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
& $VenvPython -m pip install --disable-pip-version-check --requirement (Join-Path $ProjectRoot "requirements-build.txt")
if ($LASTEXITCODE -ne 0) { throw "Unable to install pinned build dependencies" }

$env:BANHELPER_OUTPUT_NAME = "BanHelper"
$env:PYINSTALLER_CONFIG_DIR = Join-Path $BuildRoot "pyinstaller-config"
& $VenvPython -m PyInstaller --noconfirm --workpath $WorkDir --distpath $DistDir (Join-Path $ProjectRoot "packaging\banhelper.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

$Exe = Join-Path $DistDir "BanHelper.exe"
if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) { throw "Expected EXE was not created: $Exe" }
$SmokeRoot = Join-Path $BuildRoot "smoke path кириллица"
$MovedDir = Join-Path $BuildRoot "moved artifact"
New-Item -ItemType Directory -Path $SmokeRoot, $MovedDir -Force | Out-Null
$MovedExe = Join-Path $MovedDir "BanHelper.exe"
Copy-Item -LiteralPath $Exe -Destination $MovedExe
$OldAppData = $env:APPDATA
$OldLocalAppData = $env:LOCALAPPDATA
try {
    $env:APPDATA = Join-Path $SmokeRoot "AppData\Roaming"
    $env:LOCALAPPDATA = Join-Path $SmokeRoot "AppData\Local"
    & $MovedExe --packaging-smoke
    if ($LASTEXITCODE -ne 0) { throw "Frozen EXE smoke test failed with exit code $LASTEXITCODE" }
    $Database = Join-Path $env:APPDATA "BanHelper\banhelper.sqlite3"
    if (-not (Test-Path -LiteralPath $Database -PathType Leaf)) { throw "Smoke database was not written to AppData" }
    if (Test-Path -LiteralPath (Join-Path $MovedDir "banhelper.sqlite3")) { throw "Application wrote data next to EXE" }
}
finally {
    $env:APPDATA = $OldAppData
    $env:LOCALAPPDATA = $OldLocalAppData
}

$Hash = (Get-FileHash -LiteralPath $Exe -Algorithm SHA256).Hash.ToLowerInvariant()
"$Hash  BanHelper.exe" | Set-Content -LiteralPath (Join-Path $DistDir "SHA256SUMS.txt") -Encoding ascii
Write-Host "Windows release created: $Exe"
