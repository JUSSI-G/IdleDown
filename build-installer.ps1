.\build.ps1

$version = python -c "from version import VERSION; print(VERSION)"

$iscc = (Get-Command iscc -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    $searchPaths = @(
        "C:\Program Files*\Inno Setup*\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup*\ISCC.exe"
    )
    $iscc = Get-ChildItem $searchPaths -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $iscc) {
    Write-Error "Inno Setup not found. Install it with: winget install --id JRSoftware.InnoSetup.7 -e"
    exit 1
}

& $iscc "/DAppVersion=$version" installer.iss
