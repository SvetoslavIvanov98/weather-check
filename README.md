
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


