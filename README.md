# Timer

Desktop time tracker for Windows: log work sessions by name, tray background, global hotkey, dashboard, CSV import/export.

## Run from source

```powershell
cd path\to\Timer
pip install -r requirements.txt
python -m timer_app
```

Data is stored in `%LOCALAPPDATA%\TimerApp\sessions.db`.

The app icon lives at `assets/app.ico` (regenerate with `python tools\generate_icon.py` if you change the script).

## Build `Timer.exe` (PyInstaller)

From the repo root:

```powershell
pip install -r requirements.txt
pip install -r requirements-build.txt
python tools\generate_icon.py
pyinstaller --noconsole --onefile --name Timer --hidden-import PySide6.QtCharts --icon assets\app.ico --add-data "assets;assets" timer_app\__main__.py
```

- **`--icon`** embeds the icon in the `.exe` (Windows shell).
- **`--add-data`** bundles `assets/app.ico` so the tray and window title use the same icon at runtime.

Or run everything in one step:

```powershell
.\build_release.ps1
```

## Build the Windows installer (Inno Setup)

1. Install [Inno Setup 6](https://jrsoftware.org/isinfo.php) (includes the `ISCC.exe` compiler).
2. Build `dist\Timer.exe` first (see above).
3. Open `installer\Timer.iss` in Inno Setup and choose **Build → Compile**, or from a command prompt:

   ```powershell
   & "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" installer\Timer.iss
   ```

The installer is written to `output\TimerSetup-0.1.0.exe`. It installs under `%LOCALAPPDATA%\Programs\Timer` (per-user, no admin). If you use **Start with Windows** in the app, point it at the installed `Timer.exe` in that folder.

To bump the version, update `timer_app\__init__.py`, `installer\Timer.iss` (`#define MyAppVersion`), and optionally `OutputBaseFilename`.
