# One-click test runner for Windows (ASCII only on purpose).
# Creates .venv, installs requirements, runs pytest and smoke_test.py,
# and writes everything to test_log.txt in the project folder.

$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

$root = $PSScriptRoot
if (Test-Path (Join-Path $root 'main.py')) {
    $proj = $root
} else {
    $proj = Join-Path $root 'x402-indicator-api'
    $zip = Join-Path $root 'x402-indicator-api.zip'
    # Only unzip the first time, so later runs never overwrite your edits or .env
    if ((Test-Path $zip) -and -not (Test-Path (Join-Path $proj 'main.py'))) {
        Expand-Archive -Path $zip -DestinationPath $root
    }
}
if (-not (Test-Path (Join-Path $proj 'main.py'))) {
    Write-Host "Project files not found next to this script." -ForegroundColor Red
    exit 1
}
Set-Location $proj

$log = Join-Path $proj 'test_log.txt'
Set-Content -Path $log -Value "=== run started $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" -Encoding UTF8

function Write-Log([string]$Text) {
    Write-Host $Text
    Add-Content -Path $log -Value $Text -Encoding UTF8
}

function Invoke-Step([string]$Title, [string]$Exe, [string[]]$ArgList) {
    Write-Log ''
    Write-Log "===== $Title ====="
    Write-Log ("> " + $Exe + ' ' + ($ArgList -join ' '))
    & $Exe @ArgList 2>&1 | ForEach-Object { Write-Log ($_.ToString()) }
    $code = $LASTEXITCODE
    Write-Log "(exit code: $code)"
    return $code
}

$summary = [ordered]@{}

# 1. Find Python 3.10+
$pyExe = $null
$pyArgs = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pyExe = 'py'; $pyArgs = @('-3')
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pyExe = 'python'
}
$pyOk = $false
if ($pyExe) {
    $ver = (& $pyExe @pyArgs -c "import sys; print(sys.version.split()[0], sys.version_info[:2] >= (3, 10))" 2>&1 | Out-String).Trim()
    Write-Log "Python: $pyExe $($pyArgs -join ' ') -> $ver"
    $pyOk = $ver -match 'True$'
}
if (-not $pyOk) {
    Write-Log 'ERROR: Python 3.10+ not found. Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH") and run again.'
    Write-Log 'RUN FINISHED'
    exit 1
}

# 2. Virtual environment + dependencies
$vpy = Join-Path $proj '.venv\Scripts\python.exe'
if (-not (Test-Path $vpy)) {
    $summary['venv'] = Invoke-Step 'create .venv' $pyExe ($pyArgs + @('-m', 'venv', '.venv'))
}
$summary['pip install'] = Invoke-Step 'pip install -r requirements.txt' $vpy @('-m', 'pip', 'install', '--disable-pip-version-check', '--progress-bar', 'off', '-r', 'requirements.txt')
Invoke-Step 'installed versions' $vpy @('-c', "import importlib.metadata as m; [print(p, m.version(p)) for p in ('x402', 'fastapi', 'uvicorn', 'httpx', 'eth-account', 'pydantic')]") | Out-Null

# 3. Unit + API tests
$summary['pytest'] = Invoke-Step 'pytest' $vpy @('-m', 'pytest', '-q', '-p', 'no:cacheprovider')

# 4. End-to-end smoke test with x402 payments enabled (Base Sepolia testnet)
$summary['smoke test'] = Invoke-Step 'smoke test (x402 on testnet)' $vpy @('smoke_test.py')

Write-Log ''
Write-Log '===== SUMMARY ====='
foreach ($k in $summary.Keys) {
    $status = if ($summary[$k] -eq 0) { 'OK' } else { "FAILED (exit $($summary[$k]))" }
    Write-Log ("{0,-12} {1}" -f $k, $status)
}
Write-Log "Log saved to: $log"
Write-Log 'RUN FINISHED'
