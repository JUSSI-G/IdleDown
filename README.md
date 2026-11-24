# IdleDown

Shuts down the computer once it has been continuously idle for a while. Handy for Steam downloads, overnight ML training and video renders.

Every few seconds it measures CPU %, GPU % (NVIDIA only, skipped otherwise), network speed and disk speed. When all of them stay under their limits for the whole idle time (10 minutes by default), it shows a countdown you can cancel, then shuts down. Any activity resets the idle timer, so short pauses between downloaded files or Steam unpacking to disk won't trigger a shutdown.

On Windows the shutdown is forced (`shutdown /s /f`), because Windows refuses a normal shutdown while the screen is locked. Open apps are closed without asking, so save your work before leaving IdleDown running.

## Download (Windows)

Get `IdleDown-Setup-<version>.exe` from the [Releases page](https://github.com/JUSSI-G/IdleDown/releases/latest) and run it. It installs for your user only, so no admin rights are needed, and adds a Start menu shortcut (a desktop shortcut is optional). Uninstall it from Settings → Apps → Installed apps.

The installer isn't digitally signed, so Windows may show "Windows protected your PC". Click **More info → Run anyway**.

## Running from source

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Useful options:

```powershell
python main.py --help
python main.py --dry-run                       # never shuts down, only logs
python main.py --console                       # no window, prints to the terminal
python main.py --idle-minutes 20 --cpu-limit 15
```

Everything is logged with timestamps to `idledown.log` in a per-user folder:

| OS | Log folder |
|---|---|
| Windows | `%LOCALAPPDATA%\IdleDown` |
| macOS | `~/Library/Application Support/IdleDown` |
| Linux | `~/.local/state/IdleDown` |

The window shows the exact path, and `--log-file` changes it.

## Building the exe

```powershell
.\build.ps1
```

The result is `dist\IdleDown.exe`. Build on each OS separately, since PyInstaller can't cross-compile.

## Building the installer

Install Inno Setup once with `winget install --id JRSoftware.InnoSetup.7 -e`, then:

```powershell
.\build-installer.ps1
```

This builds the exe and then `installer-output\IdleDown-Setup-<version>.exe`.

## Releasing a new version

1. Change the number in `version.py`, for example to `0.4.0`, and commit it.
2. Tag the commit and push the tag:
   ```powershell
   git tag v0.4.0
   git push origin v0.4.0
   ```
3. GitHub Actions (`.github/workflows/release.yml`) builds the installer and publishes it as a new release. The tag must match `version.py`, or the build stops.

## Files

| File | What it does |
|---|---|
| `main.py` | Starts the app: reads settings, sets up logging, opens the window or console mode |
| `settings.py` | Command-line options |
| `monitor.py` | Reads usage, tracks idle time, shuts down |
| `gui_app.py` | The window |
| `console_app.py` | Terminal mode |
| `platform_utils.py` | Everything OS-specific: the shutdown command, the GPU and the log folder |
| `version.py` | The version number |
| `installer.iss` | The Inno Setup installer script |
| `build.ps1`, `build-installer.ps1` | Build the exe, and the exe plus the installer |
| `.github/workflows/release.yml` | Builds and publishes the installer when a version tag is pushed |
