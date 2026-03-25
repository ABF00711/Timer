$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Installing dependencies..."
pip install -r requirements.txt
pip install -r requirements-build.txt

Write-Host "Generating icon..."
python tools\generate_icon.py

Write-Host "Building Timer.exe with PyInstaller..."
$addData = "assets" + [char]0x3B + "assets"
pyinstaller `
  --noconsole `
  --onefile `
  --name Timer `
  --hidden-import PySide6.QtCharts `
  --icon assets\app.ico `
  --add-data $addData `
  timer_app\__main__.py

Write-Host ""
Write-Host "Done: dist\Timer.exe"
Write-Host "Next: open installer\Timer.iss in Inno Setup and Build to create output\TimerSetup-0.1.0.exe"
