#!/usr/bin/env python3
# GNOME Tray widget (AppIndicator) for Weather Check
# Dependencies: python3-gi, gir1.2-gtk-3.0, gir1.2-ayatanaappindicator3-0.1 (or gir1.2-appindicator3-0.1)

import os
import sys
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime

try:
    import gi
    gi.require_version('Gtk', '3.0')
    try:
        gi.require_version('AyatanaAppIndicator3', '0.1')
        from gi.repository import AyatanaAppIndicator3 as AppIndicator3
    except (ValueError, ImportError):
        gi.require_version('AppIndicator3', '0.1')
        from gi.repository import AppIndicator3
    from gi.repository import Gtk, GLib
except Exception as e:
    sys.stderr.write("PyGObject (Gtk/AppIndicator) is required: apt install python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1\n")
    raise

APP_ID = 'weather-check-tray'
REFRESH_SECONDS = int(os.getenv('WEATHER_TRAY_REFRESH', '600'))
CITY = None

# Basic mapping from MET Norway symbol codes to common theme icon names
SYMBOL_ICON_MAP = [
    (('thunder', 'thunderstorm'), 'weather-storm-symbolic'),
    (('heavysnow', 'snow', 'lightsnow'), 'weather-snow-symbolic'),
    (('heavyrain', 'lightrain', 'rain', 'showers'), 'weather-showers-symbolic'),
    (('partlycloudy', 'fair'), 'weather-few-clouds-symbolic'),
    (('cloudy',), 'weather-overcast-symbolic'),
    (('clearsky',), 'weather-clear-symbolic'),
]
DEFAULT_ICON = 'weather-severe-alert-symbolic'


def http_get_json(url, timeout=10):
    req = urllib.request.Request(url, headers={'User-Agent': 'weather-check-tray'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def detect_city():
    try:
        city = urllib.request.urlopen('https://ipinfo.io/city', timeout=5).read().decode('utf-8').strip()
        return city or 'Sofia'
    except Exception:
        return 'Sofia'


def get_coords(city):
    q = urllib.parse.quote(city)
    url = f"https://nominatim.openstreetmap.org/search?city={q}&format=json&limit=1"
    try:
        arr = http_get_json(url)
        if arr:
            return float(arr[0]['lat']), float(arr[0]['lon'])
    except Exception:
        pass
    return 42.6977, 23.3219  # Sofia fallback


def fetch_weather(lat, lon):
    url = f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={lat}&lon={lon}"
    return http_get_json(url)


def icon_name_from_symbol(symbol_code):
    if not symbol_code:
        return DEFAULT_ICON
    s = symbol_code.lower()
    for keys, icon in SYMBOL_ICON_MAP:
        if any(k in s for k in keys):
            return icon
    return DEFAULT_ICON


def safe_temp(v):
    try:
        return float(v)
    except Exception:
        return None


class WeatherTray:
    def __init__(self, city=None):
        self.city = city or detect_city()
        self.ind = AppIndicator3.Indicator.new(APP_ID, DEFAULT_ICON, AppIndicator3.IndicatorCategory.APPLICATION_STATUS)
        self.ind.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.ind.set_title('Weather')
        # Label support (some shells/extensions display it)
        self.ind.set_label('…', '…')
        self.menu = Gtk.Menu()

        self.item_title = Gtk.MenuItem(label=f"Weather — {self.city}")
        self.item_title.set_sensitive(False)
        self.menu.append(self.item_title)

        self.item_update = Gtk.MenuItem(label="Refresh now")
        self.item_update.connect('activate', self.on_refresh)
        self.menu.append(self.item_update)

        self.item_sep = Gtk.SeparatorMenuItem()
        self.menu.append(self.item_sep)

        self.item_open = Gtk.MenuItem(label="Open weather-check")
        self.item_open.connect('activate', self.on_open_cli)
        self.menu.append(self.item_open)

        self.item_quit = Gtk.MenuItem(label="Quit")
        self.item_quit.connect('activate', self.on_quit)
        self.menu.append(self.item_quit)

        self.menu.show_all()
        self.ind.set_menu(self.menu)

        self._lat, self._lon = get_coords(self.city)
        self._last_update = None
        GLib.idle_add(self.refresh)
        GLib.timeout_add_seconds(REFRESH_SECONDS, self.refresh)

    def on_refresh(self, _=None):
        self.refresh()

    def on_open_cli(self, _=None):
        # Try to launch the CLI in a terminal
        cmd = os.getenv('WEATHER_TRAY_CLI', 'weather-check')
        try:
            # Use system default terminal if available
            term = os.getenv('TERMINAL') or 'gnome-terminal'
            os.spawnlp(os.P_NOWAIT, term, term, '--', cmd)
        except Exception:
            # Fallback: run in background without terminal
            os.spawnlp(os.P_NOWAIT, cmd, cmd)

    def on_quit(self, _=None):
        Gtk.main_quit()

    def refresh(self):
        try:
            data = fetch_weather(self._lat, self._lon)
            ts0 = data['properties']['timeseries'][0]
            details = ts0['data']['instant']['details']
            temp = safe_temp(details.get('air_temperature'))
            sym = ts0['data'].get('next_1_hours', {}).get('summary', {}).get('symbol_code') or ''
            icon_name = icon_name_from_symbol(sym)
            label = f"{int(round(temp))}°C" if temp is not None else 'N/A'
            self.ind.set_icon_full(icon_name, 'weather')
            # Some shells show the label, others ignore it
            self.ind.set_label(label, label)
            self._last_update = datetime.now()
            self.item_title.set_label(f"Weather — {self.city} · {label}")
        except Exception as e:
            # Keep previous icon/label; show error in title
            self.item_title.set_label(f"Weather — {self.city} · error")
        return True  # keep timer


def main():
    city = None
    if len(sys.argv) > 1:
        city = ' '.join(sys.argv[1:]).strip()
    global CITY
    CITY = city or os.getenv('CITY')
    app = WeatherTray(city=CITY)
    Gtk.main()


if __name__ == '__main__':
    main()
