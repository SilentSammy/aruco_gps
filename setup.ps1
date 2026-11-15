param([switch]$Yes)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not $Yes) {
    $answer = Read-Host 'Create .venv and install vision dependencies? [Y/n]'
    if ($answer -and $answer -notmatch '^(y|yes)$') { return }
}
python -m venv .venv
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& .venv/Scripts/python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE) { exit $LASTEXITCODE }
