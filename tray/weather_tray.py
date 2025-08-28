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
import threading
import tempfile
import hashlib

try:
    import gi
    gi.require_version('Gtk', '3.0')
    try:
        gi.require_version('AyatanaAppIndicator3', '0.1')
        from gi.repository import AyatanaAppIndicator3 as AppIndicator3
    except (ValueError, ImportError):
        gi.require_version('AppIndicator3', '0.1')
        from gi.repository import AppIndicator3
    from gi.repository import Gtk, GLib, Gdk, Pango, PangoCairo
    import cairo
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
    # Use same UA as CLI to avoid server-side content differences
    req = urllib.request.Request(url, headers={'User-Agent': 'weather-check'})
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
        self.ind = AppIndicator3.Indicator.new(
            APP_ID, DEFAULT_ICON, AppIndicator3.IndicatorCategory.APPLICATION_STATUS
        )
        self.ind.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.ind.set_title('Weather')
        # Label support (some shells/extensions display it)
        self.ind.set_label('…', '…')

        # Menu
        self.menu = Gtk.Menu()
        self.item_title = Gtk.MenuItem(label=f"Weather — {self.city}")
        self.item_title.set_sensitive(False)
        self.menu.append(self.item_title)

        self.item_update = Gtk.MenuItem(label="Refresh now")
        self.item_update.connect('activate', self.on_refresh)
        self.menu.append(self.item_update)

        self.item_sep = Gtk.SeparatorMenuItem()
        self.menu.append(self.item_sep)

        self.item_open = Gtk.MenuItem(label="Show weather details")
        self.item_open.connect('activate', self.on_open_details)
        self.menu.append(self.item_open)

        self.item_quit = Gtk.MenuItem(label="Quit")
        self.item_quit.connect('activate', self.on_quit)
        self.menu.append(self.item_quit)

        self.menu.show_all()
        self.ind.set_menu(self.menu)

        # Data/init
        self._lat, self._lon = get_coords(self.city)
        self._last_update = None
        self._last_data = None
        # Icon cache dir for dynamic icons with text overlay (use theme-like layout)
        self._icon_cache_dir = os.path.join(tempfile.gettempdir(), 'weather-check-icons')
        # Create hicolor theme subdir so AppIndicator can find icons by name
        self._icon_theme_status_24 = os.path.join(self._icon_cache_dir, 'hicolor', '24x24', 'status')
        os.makedirs(self._icon_theme_status_24, exist_ok=True)
        self.ind.set_icon_theme_path(self._icon_cache_dir)
        self._last_icon_file = None
        GLib.idle_add(self.refresh_async)
        GLib.timeout_add_seconds(REFRESH_SECONDS, self.refresh_async)

    def _render_icon_with_text(self, base_icon_name: str, text: str, size: int = 24) -> str:
        """Render an icon by overlaying text onto the base weather icon.
        Returns the icon name (without extension) placed in the icon cache dir.
        """
        try:
            # Load base icon pixbuf from the current theme
            theme = Gtk.IconTheme.get_default()
            try:
                pixbuf = theme.load_icon(base_icon_name, size, 0)
            except Exception:
                pixbuf = theme.load_icon(DEFAULT_ICON, size, 0)

            # Create cairo surface
            width, height = size, size
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
            cr = cairo.Context(surface)

            # Paint base icon
            Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
            cr.paint()

            # Draw text bottom-right with slight outline for contrast
            layout = PangoCairo.create_layout(cr)
            # Use a compact font
            desc = Pango.FontDescription('Sans Bold 10')
            layout.set_font_description(desc)
            layout.set_text(text, -1)
            text_w, text_h = layout.get_pixel_size()
            # Prefer centered near bottom for visibility
            x = max(1, (width - text_w) // 2)
            y = max(1, height - text_h - 1)

            # Draw semi-transparent background for contrast
            bg_pad_x, bg_pad_y = 2, 1
            bg_x = max(0, x - bg_pad_x)
            bg_y = max(0, y - bg_pad_y)
            bg_w = min(width, text_w + bg_pad_x * 2)
            bg_h = min(height, text_h + bg_pad_y * 2)
            cr.save()
            cr.set_source_rgba(0, 0, 0, 0.35)
            cr.rectangle(bg_x, bg_y, bg_w, bg_h)
            cr.fill()
            cr.restore()

            # Outline (black)
            cr.set_source_rgba(0, 0, 0, 0.85)
            for dx, dy in ((-1,0),(1,0),(0,-1),(0,1)):
                cr.save()
                cr.translate(x+dx, y+dy)
                PangoCairo.show_layout(cr, layout)
                cr.restore()
            # Text (white)
            cr.set_source_rgba(1, 1, 1, 1)
            cr.save()
            cr.translate(x, y)
            PangoCairo.show_layout(cr, layout)
            cr.restore()

            # Save to a hashed filename to avoid cache issues
            h = hashlib.md5(f"{base_icon_name}|{text}|{size}".encode()).hexdigest()[:10]
            icon_basename = f"weather_temp_{h}"
            icon_path = os.path.join(self._icon_theme_status_24, icon_basename + '.png')
            surface.write_to_png(icon_path)
            return icon_path
        except Exception:
            return base_icon_name  # Fallback to base icon name

    def _set_icon_and_label(self, base_icon_name: str, label: str, temp: float | None = None):
        # Always set the indicator label (may not be shown by GNOME, but harmless)
        try:
            self.ind.set_label(label, label)
        except Exception:
            pass
        # Compose a dynamic icon with temperature text overlay for GNOME
        # Prefer a short, readable overlay like "12°"
        overlay_text = None
        if temp is not None:
            try:
                overlay_text = f"{int(round(float(temp)))}°"
            except Exception:
                overlay_text = None
        if not overlay_text:
            # Fallback: try to extract integer from label ending with °C
            try:
                if '°' in label:
                    overlay_text = label.split('°', 1)[0]
                    # Keep only the last 3 characters (handle negatives)
                    overlay_text = overlay_text[-3:] + '°'
            except Exception:
                overlay_text = None
        icon_ref = self._render_icon_with_text(base_icon_name, overlay_text or label)
        # Try setting via absolute file path first
        try:
            self.ind.set_icon_full(icon_ref, 'weather')
        except Exception:
            try:
                # Some implementations accept set_icon with path
                self.ind.set_icon(icon_ref)
            except Exception:
                # Fallback to base icon name
                self.ind.set_icon_full(base_icon_name, 'weather')

    def on_refresh(self, _=None):
        # Trigger a background refresh without blocking the UI
        self.refresh_async()

    def on_open_details(self, _=None):
        # Open or focus a simple details window without a terminal
        if getattr(self, '_details_win', None) and self._details_win.get_visible():
            self._details_win.present()
            self.update_details_view()
            return
        win = Gtk.Window(title=f"Weather — {self.city}")
        win.set_default_size(420, 520)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        win.add(box)

        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        box.pack_start(sc, True, True, 0)

        tv = Gtk.TextView()
        tv.set_editable(False)
        tv.set_cursor_visible(False)
        tv.set_monospace(True)
        sc.add(tv)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.connect('clicked', lambda *_: self.update_details_view())
        close_btn = Gtk.Button(label="Close")
        close_btn.connect('clicked', lambda *_: win.hide())
        btn_box.pack_start(refresh_btn, False, False, 6)
        btn_box.pack_end(close_btn, False, False, 6)
        box.pack_end(btn_box, False, False, 6)

        self._details_win = win
        self._details_text = tv
        self.update_details_view()
        win.show_all()

    def on_quit(self, _=None):
        Gtk.main_quit()

    def refresh_async(self, *_):
        # Start a worker thread to fetch data, then update UI via idle_add
        def _worker():
            try:
                data = fetch_weather(self._lat, self._lon)
                ts0 = data['properties']['timeseries'][0]
                details = ts0['data']['instant']['details']
                temp = safe_temp(details.get('air_temperature'))
                # Match CLI fallback: next_1_hours -> next_6_hours -> next_12_hours
                sym = (
                    ts0['data'].get('next_1_hours', {}).get('summary', {}).get('symbol_code')
                    or ts0['data'].get('next_6_hours', {}).get('summary', {}).get('symbol_code')
                    or ts0['data'].get('next_12_hours', {}).get('summary', {}).get('symbol_code')
                    or ''
                )
                icon_name = icon_name_from_symbol(sym)
                # Match CLI precision closer (keep one decimal)
                label = f"{temp:.1f}°C" if temp is not None else 'N/A'
                def _apply():
                    self._set_icon_and_label(icon_name, label, temp)
                    self._last_update = datetime.now()
                    self._last_data = data
                    self.item_title.set_label(f"Weather — {self.city} · {label}")
                    # If details window is open, refresh its contents
                    if getattr(self, '_details_win', None) and self._details_win.get_visible():
                        self.update_details_view()
                    return False
                GLib.idle_add(_apply)
            except Exception:
                def _err():
                    self.item_title.set_label(f"Weather — {self.city} · error")
                    return False
                GLib.idle_add(_err)
        threading.Thread(target=_worker, daemon=True).start()
        return True  # keep timer

    def update_details_view(self):
        # Render a readable summary in the details window
        if not getattr(self, '_details_text', None):
            return
        try:
            # Ensure we have fresh-ish data (kick off a background refresh)
            if not getattr(self, '_last_data', None) or (self._last_update and (datetime.now() - self._last_update).seconds > REFRESH_SECONDS):
                self.refresh_async()
            data = getattr(self, '_last_data', None)
            if not data:
                buf = "Weather data unavailable."
            else:
                ts = data['properties']['timeseries']
                now = ts[0]
                det = now['data']['instant']['details']
                temp = det.get('air_temperature')
                wind = det.get('wind_speed')
                hum = det.get('relative_humidity')
                pres = det.get('air_pressure_at_sea_level')
                sym = (
                    now['data'].get('next_1_hours', {}).get('summary', {}).get('symbol_code')
                    or now['data'].get('next_6_hours', {}).get('summary', {}).get('symbol_code')
                    or now['data'].get('next_12_hours', {}).get('summary', {}).get('symbol_code')
                    or ''
                )
                # Build a simple hourly preview (next 8 hours)
                lines = []
                lines.append(f"City: {self.city}")
                if self._last_update:
                    lines.append(f"Updated: {self._last_update:%Y-%m-%d %H:%M}")
                lines.append("")
                lines.append(f"Now:  {temp}°C   Wind {wind} m/s   Hum {hum}%   Pres {pres} hPa   Code {sym}")
                lines.append("")
                lines.append("Hourly (next 8h):")
                for row in ts[:8]:
                    t = datetime.fromisoformat(row['time'].replace('Z','+00:00')).strftime('%H:%M')
                    d = row['data']
                    at = d['instant']['details'].get('air_temperature')
                    p = d.get('next_1_hours', {}).get('details', {}).get('precipitation_amount', 0)
                    sc = d.get('next_1_hours', {}).get('summary', {}).get('symbol_code', '')
                    lines.append(f" {t}  {at}°C  precip {p} mm  {sc}")
                buf = "\n".join(lines)
        except Exception as e:
            buf = f"Error rendering details: {e}"
        buf_obj = self._details_text.get_buffer()
        buf_obj.set_text(buf)


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
