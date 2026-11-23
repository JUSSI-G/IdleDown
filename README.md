# IdleDown

Shuts down the computer once it has been continuously idle for a while. Handy for Steam downloads, overnight ML training and video renders.

Every few seconds it measures CPU %, GPU % (NVIDIA only, skipped otherwise), network speed and disk speed. When all of them stay under their limits for the whole idle time (10 minutes by default), it shows a countdown you can cancel, then shuts down. Any activity resets the idle timer, so short pauses between downloaded files or Steam unpacking to disk won't trigger a shutdown.

## Running

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
