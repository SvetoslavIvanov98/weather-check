
# Weather Check

Lightweight CLI weather viewer with a polished, app-like output.

## Features

- Auto-detect city (via ipinfo) or accept a city name
- Current conditions, 3-day forecast and 24-hour hourly view
- Portable, single-shell script (bash) that uses `curl` + `jq`
- Optional desktop packaging: `.deb` included in the repo
- Color themes and boxed layouts for an "app" feel in terminal

## Requirements

- Linux (untested on other OSes)
- bash, curl, jq, tput

## Quick install (DEB)

1. Build or use the included package:

```bash
# If you already have the package (built or included)
sudo dpkg -i ~/weather-check/weather-check-1.0.deb
# fix missing deps if dpkg reports them
sudo apt-get install -f
```

2. Or install the script manually (no package):

```bash
sudo cp weather-check /usr/local/bin/weather-check
sudo chmod +x /usr/local/bin/weather-check
hash -r
```

## Run

```bash
# use detected city
weather-check
# or specify a city
weather-check <City Name>
```

## Flags (common)

- `-r <duration>` or `--refresh <duration>` — auto-refresh interval (e.g. 30s, 5m, 1h)
- `-k` or `--keep` — keep previous output (don't clear terminal)
- `--no-color` — disable colors (set `NO_COLOR=1` in env to force)

## Troubleshooting

- No colors visible: ensure you run the installed script (check `which weather-check`) and that your terminal supports ANSI colors. If you see literal sequences like `\\033[1m`, the installed script contains literal backslashes; reinstall from the workspace script or copy it manually as shown above.
- Wrong copy being executed: run `command -v weather-check` and inspect that file. Remove or overwrite older copies in `/usr/local/bin` or `/usr/bin` as needed.
- Dependency errors while installing the .deb: run `sudo apt-get install -f` to resolve missing packages.

## Developer notes

- Main script: `weather-check` (root of the repo)
- Package tree: `weather-check-1.0/` (DEBIAN control, `usr/bin/weather-check`, etc.)
- Rebuild .deb:

```bash
# from repo root
fakeroot dpkg-deb --build weather-check-1.0 ./weather-check-1.0.deb
```

## Contributing

- Bug reports and PRs welcome. Keep changes small and add tests where practical (script smoke tests).

## License

- See `weather-check-1.0/usr/share/doc/weather-check/copyright` for packaging metadata.

## Systemd service (alerts)

This repository includes a simple alert script and example systemd user units that trigger notifications when the weather changes.

Files included:

- `scripts/weather-alert` — checks current weather and stores state under `${XDG_STATE_HOME:-~/.local/state}/weather-check` by default; sends a desktop notification via `notify-send` when relevant changes occur.
- `systemd/user/weather-alert.service` — user service that runs the script.
- `systemd/user/weather-alert.timer` — timer that runs the service every 10 minutes.

Enable as a user service (recommended):

```bash
# copy files to a persistent location under your home, or adjust ExecStart in the .service file
mkdir -p ~/.config/systemd/user
cp systemd/user/weather-alert.service ~/.config/systemd/user/weather-alert.service
cp systemd/user/weather-alert.timer ~/.config/systemd/user/weather-alert.timer
mkdir -p ~/.local/bin
cp scripts/weather-alert ~/.local/bin/weather-alert
chmod +x ~/.local/bin/weather-alert

# reload and enable timer
systemctl --user daemon-reload
systemctl --user enable --now weather-alert.timer

# Check status
systemctl --user status weather-alert.timer
journalctl --user -u weather-alert.service -f
```

Notes:

- By default, the script stores state in `${XDG_STATE_HOME:-~/.local/state}/weather-check` (user-writable). Override with `Environment=STATE_DIR=/path` in the service if desired.
- The script uses `notify-send` for desktop notifications; install `libnotify-bin` on Debian/Ubuntu if you want GUI notifications.
- The unit uses `ExecStart=%h/.local/bin/weather-alert`; systemd does not expand `~` in ExecStart.
- Adjust `CITY`, `THRESHOLD_TEMP`, or `STATE_DIR` via `Environment=` lines in the systemd unit or by editing the script.
- Verify state file after first run: `ls -l ~/.local/state/weather-check/last_state.json`.

## GNOME tray widget (optional)

Files:

- `tray/weather_tray.py` — AppIndicator-based tray icon that shows current temperature and menu.
- `tray/weather-check-tray` — small launcher script you can place on PATH.
- `tray/weather-tray.desktop` — Example autostart entry using `Exec=weather-check-tray`.

Dependencies (Debian/Ubuntu):

```bash
sudo apt-get install -y python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
```

Run:

```bash
# option A: run directly
python3 tray/weather_tray.py  # optional: CITY via args or env

# option B: install shim to PATH for portability
install -Dm755 tray/weather-check-tray ~/.local/bin/weather-check-tray
weather-check-tray
```

Autostart:

```bash
mkdir -p ~/.config/autostart
cp tray/weather-tray.desktop ~/.config/autostart/
# edit ~/.config/autostart/weather-tray.desktop to point Exec= to the correct path if needed
# If you installed the shim to PATH, Exec=weather-check-tray will work as-is.
```


