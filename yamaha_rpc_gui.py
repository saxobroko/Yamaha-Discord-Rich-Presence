#!/usr/bin/env python3
"""
Yamaha RX-V6A / Navidrome → Discord RPC (GUI)
Features:
- Tray icon support, minimize to tray
- Restore GUI on double-click tray icon
- Album art caching via Last.fm
- Yamaha MusicCast and/or Navidrome (Subsonic) now-playing
- User inputs Yamaha IP, Navidrome URL/creds, Discord Client ID, Last.fm key
- No console logging
- Requires: Python 3.10+, requests, pypresence, pystray, pillow, tkinter
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import requests
import json
import time
import hashlib
import secrets
from pypresence import Presence
try:
    from pypresence.types import ActivityType, StatusDisplayType
except ImportError:  # pypresence < 4.6
    ActivityType = None
    StatusDisplayType = None
import os
import pystray
from PIL import Image
import sys

GENERIC_IMAGE = "3844724"
SUBSONIC_API_VERSION = "1.16.1"
SUBSONIC_CLIENT = "YamahaRPC"
SOURCE_MODES = ("auto", "yamaha", "navidrome")


def app_dir():
    """Writable directory next to the exe when frozen; otherwise cwd."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(".")


CONFIG_FILE = os.path.join(app_dir(), "yamaha_rpc_config.json")
CACHE_FILE = os.path.join(app_dir(), "cache.json")


def enable_windows_dpi_awareness():
    """Tell Windows this process is DPI-aware so Tk is not bitmap-upscaled (blurry).

    Must run before the first Tk() / tk.Tk() is created.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        # Per-monitor DPI awareness V2 (Windows 10 1703+)
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 == -4
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except Exception:
        pass
    try:
        import ctypes
        # PROCESS_PER_MONITOR_DPI_AWARE == 2
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


# ---------------- Cache ----------------
class Cache:
    def __init__(self, filename=CACHE_FILE):
        self.filename = filename
        self.data = {}
        self.load()

    def load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r") as f:
                    self.data = json.load(f)
            except:
                self.data = {}

    def save(self):
        try:
            with open(self.filename, "w") as f:
                json.dump(self.data, f, indent=2)
        except:
            pass

    def get_album_art(self, artist, album):
        return self.data.get("album_art", {}).get(f"{artist}|{album}")

    def set_album_art(self, artist, album, url):
        if "album_art" not in self.data:
            self.data["album_art"] = {}
        self.data["album_art"][f"{artist}|{album}"] = url
        self.save()

# ---------------- Helpers ----------------
def env_or_config(config, key, env_name):
    env_val = os.environ.get(env_name, "").strip()
    if env_val:
        return env_val
    return (config.get(key) or "").strip()


def normalize_base_url(url):
    url = (url or "").strip().rstrip("/")
    if url.endswith("/rest"):
        url = url[:-5]
    return url


# ---------------- Yamaha RPC Bridge ----------------
class YamahaRPCBridge(threading.Thread):
    def __init__(self, config, status_callback=None):
        super().__init__(daemon=True)
        self.config = config
        self.status_callback = status_callback
        self._stop = threading.Event()
        self.rpc = None
        self.last_track = None
        self.cache = Cache()

    def stop(self):
        self._stop.set()

    def running(self):
        return not self._stop.is_set()

    def _set_status(self, s):
        if self.status_callback:
            try:
                self.status_callback(s)
            except:
                pass

    def connect_rpc(self):
        try:
            client_id = self.config.get("discord_client_id") or None
            self.rpc = Presence(client_id) if client_id else None
            if self.rpc:
                self.rpc.connect()
            return True, None
        except Exception as e:
            return False, str(e)

    def get_yamaha_info(self):
        try:
            ip = self.config.get("yamaha_ip")
            if not ip:
                return None
            url = f"http://{ip}/YamahaExtendedControl/v1/netusb/getPlayInfo"
            r = requests.get(url, timeout=3)
            r.raise_for_status()
            js = r.json()
            if js.get("playback", "").lower() != "play":
                return None
            return {
                "track": js.get("track"),
                "artist": js.get("artist"),
                "album": js.get("album"),
                "play_time": js.get("play_time", 0),
                "source": "yamaha",
            }
        except:
            return None

    def _navidrome_auth_params(self):
        base = normalize_base_url(
            env_or_config(self.config, "navidrome_url", "NAVIDROME_URL")
        )
        user = env_or_config(self.config, "navidrome_user", "NAVIDROME_USER")
        password = env_or_config(
            self.config, "navidrome_password", "NAVIDROME_PASSWORD"
        )
        if not base or not user or not password:
            return None, None
        salt = secrets.token_hex(8)
        token = hashlib.md5((password + salt).encode("utf-8")).hexdigest()
        params = {
            "u": user,
            "t": token,
            "s": salt,
            "v": SUBSONIC_API_VERSION,
            "c": SUBSONIC_CLIENT,
            "f": "json",
        }
        return base, params

    def _subsonic_get(self, endpoint, extra=None):
        base, params = self._navidrome_auth_params()
        if not base:
            return None
        query = dict(params)
        if extra:
            query.update(extra)
        url = f"{base}/rest/{endpoint}.view"
        r = requests.get(url, params=query, timeout=5)
        r.raise_for_status()
        js = r.json()
        resp = js.get("subsonic-response") or {}
        if resp.get("status") != "ok":
            return None
        return resp

    def _navidrome_entry_to_info(self, entry, player_name=None):
        if not entry:
            return None
        title = entry.get("title") or entry.get("name")
        artist = entry.get("displayArtist") or entry.get("artist") or ""
        album = entry.get("album") or ""
        if not title:
            return None
        play_time = 0
        if entry.get("positionMs") is not None:
            try:
                play_time = max(0, int(entry["positionMs"]) // 1000)
            except (TypeError, ValueError):
                play_time = 0
        info = {
            "track": title,
            "artist": artist,
            "album": album,
            "play_time": play_time,
            "source": "navidrome",
            "player": player_name or entry.get("playerName") or "",
            "cover_art_id": entry.get("coverArt") or entry.get("id"),
        }
        return info

    def get_navidrome_info(self):
        """Return currently playing track from any of the user's Navidrome devices."""
        try:
            base, params = self._navidrome_auth_params()
            if not base:
                return None
            configured_user = params["u"]
            resp = self._subsonic_get("getNowPlaying")
            if not resp:
                return None
            entries = (resp.get("nowPlaying") or {}).get("entry") or []
            if isinstance(entries, dict):
                entries = [entries]

            candidates = []
            for entry in entries:
                username = entry.get("username") or ""
                if username and username != configured_user:
                    continue
                state = (entry.get("state") or "").lower()
                try:
                    minutes_ago = int(entry.get("minutesAgo", 9999))
                except (TypeError, ValueError):
                    minutes_ago = 9999
                # Prefer explicit OpenSubsonic playing state; otherwise recent scrobble.
                if state == "playing":
                    score = 0
                elif state in ("paused", "stopped"):
                    continue
                elif minutes_ago <= 2:
                    score = 1 + minutes_ago
                else:
                    continue
                candidates.append((score, minutes_ago, entry))

            if not candidates:
                return None
            candidates.sort(key=lambda item: (item[0], item[1]))
            return self._navidrome_entry_to_info(candidates[0][2])
        except:
            return None

    def resolve_now_playing(self):
        mode = (self.config.get("source_mode") or "auto").strip().lower()
        if mode not in SOURCE_MODES:
            mode = "auto"

        if mode == "yamaha":
            return self.get_yamaha_info()
        if mode == "navidrome":
            return self.get_navidrome_info()

        # auto: prefer Navidrome when it reports an active play, else Yamaha
        navidrome = self.get_navidrome_info()
        if navidrome:
            return navidrome
        return self.get_yamaha_info()

    def get_album_art(self, artist, album):
        cached = self.cache.get_album_art(artist, album)
        if cached:
            return cached
        try:
            api_key = self.config.get("lastfm_api_key")
            if not api_key:
                return None
            url = (
                f"http://ws.audioscrobbler.com/2.0/"
                f"?method=album.getinfo&api_key={api_key}"
                f"&artist={requests.utils.quote(artist)}&album={requests.utils.quote(album)}&format=json"
            )
            r = requests.get(url, timeout=3).json()
            if "album" in r and "image" in r["album"]:
                images = r["album"]["image"]
                if images:
                    album_art_url = images[-1].get("#text") or None
                    if album_art_url:
                        self.cache.set_album_art(artist, album, album_art_url)
                        return album_art_url
            return None
        except:
            return None

    def run(self):
        self._set_status("Connecting to Discord...")
        ok, err = self.connect_rpc()
        if not ok:
            self._set_status(f"Discord connect error: {err}")
            return

        mode = (self.config.get("source_mode") or "auto").strip().lower()
        self._set_status(f"Connected. Polling ({mode})...")
        poll = float(self.config.get("poll_interval", 2))
        while not self._stop.is_set():
            info = self.resolve_now_playing()
            if info:
                track_id = f"{info.get('source')}|{info['artist']}|{info['album']}|{info['track']}"
                if track_id != self.last_track:
                    self.last_track = track_id
                    album_art_url = self.get_album_art(info["artist"], info["album"])
                    source_label = "Navidrome" if info.get("source") == "navidrome" else "Yamaha"
                    player = info.get("player") or ""
                    artist = info["artist"] or "Unknown artist"
                    album = info["album"] or ""
                    # Spotify-style: "Listening to {artist}" (needs pypresence 4.6+)
                    large_text = f"via {source_label}"
                    if player:
                        large_text = f"{source_label}: {player}"
                    elif album:
                        large_text = album
                    kwargs = {
                        "details": info["track"] or "Unknown track",
                        "state": artist,
                        "large_image": album_art_url if album_art_url else GENERIC_IMAGE,
                        "large_text": large_text,
                        "start": int(time.time()) - int(info.get("play_time", 0)),
                    }
                    if ActivityType is not None:
                        kwargs["activity_type"] = ActivityType.LISTENING
                    if StatusDisplayType is not None:
                        kwargs["status_display_type"] = StatusDisplayType.STATE
                    try:
                        if self.rpc:
                            self.rpc.update(**kwargs)
                        self._set_status(
                            f'Listening: {artist} — {info["track"]} ({source_label})'
                        )
                    except:
                        self._set_status("RPC update error")
            else:
                try:
                    if self.rpc:
                        self.rpc.clear()
                    self._set_status("No track playing")
                    self.last_track = None
                except:
                    pass
            time.sleep(poll)
        try:
            if self.rpc:
                self.rpc.clear()
        except:
            pass
        self._set_status("Stopped")

# ---------------- GUI ----------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Yamaha / Navidrome → Discord RPC")
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self._last_dpi = None
        self._dpi_check_after = None
        self._apply_dpi_scaling(force=True)

        self.config_data = self.load_config()
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        row = 0

        # Source mode
        ttk.Label(frm, text="Source mode:").grid(row=row, column=0, sticky="w")
        self.source_var = tk.StringVar(
            value=self.config_data.get("source_mode", "auto")
        )
        self.source_combo = ttk.Combobox(
            frm,
            textvariable=self.source_var,
            values=list(SOURCE_MODES),
            state="readonly",
            width=28,
        )
        self.source_combo.grid(row=row, column=1, padx=6, pady=6, sticky="w")
        row += 1

        # Yamaha IP
        ttk.Label(frm, text="Yamaha IP:").grid(row=row, column=0, sticky="w")
        self.ip_var = tk.StringVar(value=self.config_data.get("yamaha_ip", ""))
        ttk.Entry(frm, textvariable=self.ip_var, width=30).grid(
            row=row, column=1, padx=6, pady=6, sticky="w"
        )
        row += 1

        # Navidrome URL
        ttk.Label(frm, text="Navidrome URL:").grid(row=row, column=0, sticky="w")
        self.nd_url_var = tk.StringVar(
            value=self.config_data.get("navidrome_url", "")
        )
        ttk.Entry(frm, textvariable=self.nd_url_var, width=30).grid(
            row=row, column=1, padx=6, pady=6, sticky="w"
        )
        row += 1

        # Navidrome username
        ttk.Label(frm, text="Navidrome Username:").grid(row=row, column=0, sticky="w")
        self.nd_user_var = tk.StringVar(
            value=self.config_data.get("navidrome_user", "")
        )
        ttk.Entry(frm, textvariable=self.nd_user_var, width=30).grid(
            row=row, column=1, padx=6, pady=6, sticky="w"
        )
        row += 1

        # Navidrome password
        ttk.Label(frm, text="Navidrome Password:").grid(row=row, column=0, sticky="w")
        self.nd_pass_var = tk.StringVar(
            value=self.config_data.get("navidrome_password", "")
        )
        ttk.Entry(frm, textvariable=self.nd_pass_var, width=30, show="*").grid(
            row=row, column=1, padx=6, pady=6, sticky="w"
        )
        row += 1

        # Discord Client ID
        ttk.Label(frm, text="Discord Client ID:").grid(row=row, column=0, sticky="w")
        self.cid_var = tk.StringVar(
            value=self.config_data.get("discord_client_id", "")
        )
        ttk.Entry(frm, textvariable=self.cid_var, width=30).grid(
            row=row, column=1, padx=6, pady=6, sticky="w"
        )
        row += 1

        # Last.fm API Key
        ttk.Label(frm, text="Last.fm API Key:").grid(row=row, column=0, sticky="w")
        self.lfm_var = tk.StringVar(
            value=self.config_data.get("lastfm_api_key", "")
        )
        ttk.Entry(frm, textvariable=self.lfm_var, width=30).grid(
            row=row, column=1, padx=6, pady=6, sticky="w"
        )
        row += 1

        # Poll interval
        ttk.Label(frm, text="Poll Interval (seconds):").grid(
            row=row, column=0, sticky="w"
        )
        self.poll_var = tk.StringVar(
            value=str(self.config_data.get("poll_interval", 2))
        )
        ttk.Entry(frm, textvariable=self.poll_var, width=10).grid(
            row=row, column=1, padx=6, pady=6, sticky="w"
        )
        row += 1

        # Start/Stop buttons
        self.start_btn = ttk.Button(
            frm, text="Start", command=self.start_bridge, width=12
        )
        self.start_btn.grid(row=row, column=0, pady=6)
        self.stop_btn = ttk.Button(
            frm, text="Stop", command=self.stop_bridge, width=12, state="disabled"
        )
        self.stop_btn.grid(row=row, column=1, pady=6, sticky="w")
        row += 1

        # Status
        self.status_var = tk.StringVar(value="Stopped")
        ttk.Label(frm, text="Status:").grid(row=row, column=0, sticky="w")
        self.status_lbl = ttk.Label(frm, textvariable=self.status_var)
        self.status_lbl.grid(row=row, column=1, sticky="w")

        # Size to content; keep resizable with a sensible minimum
        self._apply_dpi_scaling(force=True)
        self._fit_to_content()

        # Tray icon setup — minimize and close both hide to tray
        self.tray_icon = None
        self._tray_hiding = False
        self.bind("<Unmap>", self._on_unmap)
        # Re-scale when the window moves to a monitor with a different DPI
        self.bind("<Configure>", self._on_configure)

    # ---------------- Helper Methods ----------------
    def _get_window_dpi(self):
        """Current monitor DPI for this window (Windows GetDpiForWindow when available)."""
        if sys.platform == "win32":
            try:
                import ctypes
                hwnd = int(self.winfo_id())
                # Prefer top-level HWND — Tk's winfo_id may be a child frame
                GA_ROOT = 2
                root = ctypes.windll.user32.GetAncestor(hwnd, GA_ROOT)
                if root:
                    hwnd = root
                dpi = int(ctypes.windll.user32.GetDpiForWindow(hwnd))
                if dpi > 0:
                    return float(dpi)
            except Exception:
                pass
        try:
            dpi = float(self.winfo_fpixels("1i"))
            if dpi > 0:
                return dpi
        except Exception:
            pass
        return 96.0

    def _apply_dpi_scaling(self, force=False):
        """Align Tk scaling with the display DPI for this window.

        Returns True if scaling changed.
        """
        try:
            dpi = self._get_window_dpi()
            if not force and self._last_dpi is not None and abs(dpi - self._last_dpi) < 0.5:
                return False
            self._last_dpi = dpi
            self.tk.call("tk", "scaling", dpi / 72.0)
            return True
        except Exception:
            return False

    def _on_configure(self, event):
        if event.widget is not self:
            return
        # Debounce rapid Configure events while dragging between monitors
        if self._dpi_check_after is not None:
            try:
                self.after_cancel(self._dpi_check_after)
            except Exception:
                pass
        self._dpi_check_after = self.after(120, self._maybe_update_monitor_dpi)

    def _maybe_update_monitor_dpi(self):
        self._dpi_check_after = None
        try:
            if self.state() != "normal":
                return
        except tk.TclError:
            return
        if self._apply_dpi_scaling():
            # Refit minsize/content so 1440p→1080p (and reverse) stays proportional
            self._fit_to_content(resize=True)

    def _fit_to_content(self, resize=True):
        """Default geometry = required content size; window stays resizable."""
        self.update_idletasks()
        width = max(self.winfo_reqwidth(), 1)
        height = max(self.winfo_reqheight(), 1)
        # Small padding so borders/status aren't clipped on some themes
        width += 8
        height += 8
        self.minsize(width, height)
        if resize:
            # Keep current top-left when only size changes after a DPI switch
            try:
                x = self.winfo_x()
                y = self.winfo_y()
                self.geometry(f"{width}x{height}+{x}+{y}")
            except tk.TclError:
                self.geometry(f"{width}x{height}")
        self.resizable(True, True)

    def resource_path(self, relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def _on_unmap(self, event):
        """Minimize button → tray (not a taskbar-iconified window)."""
        if event.widget is not self or self._tray_hiding:
            return
        try:
            if self.state() != "iconic":
                return
        except tk.TclError:
            return
        # Defer so Windows finishes the iconify before we withdraw (less flicker)
        self._tray_hiding = True
        self.after(0, self._minimize_to_tray)

    def _minimize_to_tray(self):
        try:
            self.hide_to_tray()
        finally:
            self._tray_hiding = False

    def create_tray_icon(self):
        try:
            icon_path = self.resource_path("3844724.png")
            if os.path.exists(icon_path):
                icon_image = Image.open(icon_path)
            else:
                icon_image = Image.new("RGB", (64, 64), color=(32, 40, 52))
            self.tray_icon = pystray.Icon(
                "YamahaRPC",
                icon_image,
                "Yamaha Discord RPC",
                menu=pystray.Menu(
                    pystray.MenuItem(
                        "Show",
                        self._tray_show,
                        default=True,
                    ),
                    pystray.MenuItem("Quit", self._tray_quit),
                ),
            )
            self.tray_icon.run_detached()
            self.tray_icon.visible = True
        except Exception:
            self.tray_icon = None

    def _tray_show(self, icon=None, item=None):
        # pystray callbacks run off the Tk thread
        self.after(0, self.restore_from_tray)

    def _tray_quit(self, icon=None, item=None):
        self.after(0, self.quit_app)

    def hide_to_tray(self):
        try:
            # withdraw removes taskbar button; preferred over staying iconic
            self.withdraw()
        except tk.TclError:
            pass
        if not self.tray_icon:
            self.create_tray_icon()
        elif self.tray_icon:
            try:
                self.tray_icon.visible = True
            except Exception:
                pass

    def restore_from_tray(self):
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except tk.TclError:
            pass
        # Monitor may have changed while in tray — refresh DPI
        self.after(50, self._maybe_update_monitor_dpi)
        if self.tray_icon:
            try:
                self.tray_icon.visible = False
            except Exception:
                pass

    def quit_app(self, icon=None):
        if hasattr(self, "bridge") and self.bridge.running():
            self.bridge.stop()
            time.sleep(0.2)
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None
        self.destroy()

    def save_config(self):
        mode = (self.source_var.get() or "auto").strip().lower()
        if mode not in SOURCE_MODES:
            mode = "auto"
        data = {
            "source_mode": mode,
            "yamaha_ip": self.ip_var.get().strip(),
            "navidrome_url": self.nd_url_var.get().strip(),
            "navidrome_user": self.nd_user_var.get().strip(),
            "navidrome_password": self.nd_pass_var.get().strip(),
            "discord_client_id": self.cid_var.get().strip(),
            "lastfm_api_key": self.lfm_var.get().strip(),
            "poll_interval": float(self.poll_var.get().strip() or 2),
        }
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(data, f, indent=2)
            self.config_data = data
        except Exception as e:
            messagebox.showerror("Save error", str(e))

    def load_config(self):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            return {}

    def start_bridge(self):
        try:
            float(self.poll_var.get())
        except:
            messagebox.showerror("Invalid", "Poll interval must be a number")
            return
        self.save_config()
        self.bridge = YamahaRPCBridge(self.config_data, status_callback=self.set_status)
        self.bridge.start()
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.set_status("Starting...")

    def stop_bridge(self):
        try:
            if hasattr(self, "bridge"):
                self.bridge.stop()
                time.sleep(0.2)
        except:
            pass
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.set_status("Stopped")

    def set_status(self, s):
        self.status_var.set(s)

# ---------------- Main ----------------
if __name__ == "__main__":
    enable_windows_dpi_awareness()
    app = App()
    app.mainloop()
