#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vertical Farming IoT — Multi ESP32 Control Dashboard
V7.3: Prominent Health Rating section, daily history, timer fix, modern UI.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import json
import urllib.request
import urllib.parse
import urllib.error
import sqlite3
import os
from datetime import datetime, date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "vertical_farm.db")
CONFIG_PATH = os.path.join(SCRIPT_DIR, "esp_config.json")

DEFAULT_CONFIG = {
    "ESP32_1": {"name": "ESP32_1 (Control)", "ip": "192.168.1.100", "color": "#e74c3c"},
    "ESP32_2": {"name": "ESP32_2 (Sensors)", "ip": "192.168.1.101", "color": "#e74c3c"},
    "ESP32_3": {"name": "ESP32_3 (Ultrasonic)", "ip": "192.168.1.102", "color": "#e74c3c"},
}

def load_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                saved = json.load(f)
                for key in DEFAULT_CONFIG:
                    if key not in saved:
                        saved[key] = DEFAULT_CONFIG[key].copy()
                    else:
                        for k, v in DEFAULT_CONFIG[key].items():
                            if k not in saved[key]:
                                saved[key][k] = v
                return saved
        except Exception:
            pass
    return {k: v.copy() for k, v in DEFAULT_CONFIG.items()}

def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)

ESP32_CONFIG = load_config()
POLL_INTERVAL = 5000

COLORS = {
    "bg_dark": "#0b0f17",
    "bg_card": "#151b27",
    "bg_card_hover": "#1e2636",
    "border": "#2a3444",
    "text_primary": "#f0f4f8",
    "text_secondary": "#94a3b8",
    "green": "#10b981",
    "green_dark": "#059669",
    "green_light": "#34d399",
    "green_glow": "#6ee7b7",
    "red": "#ef4444",
    "red_dark": "#b91c1c",
    "orange": "#f97316",
    "blue": "#3b82f6",
    "blue_dark": "#1d4ed8",
    "cyan": "#06b6d4",
    "purple": "#8b5cf6",
    "yellow": "#f59e0b",
    "white": "#ffffff",
    "gray": "#4b5563",
    "star_empty": "#4b5563",
    "star_filled": "#fbbf24",
}

LEVEL_COLORS = {
    1: {"main": "#f87171", "soft": "#fca5a5", "glow": "#fecaca"},
    2: {"main": "#60a5fa", "soft": "#93c5fd", "glow": "#bfdbfe"},
    3: {"main": "#fbbf24", "soft": "#fcd34d", "glow": "#fde68a"},
}

class Database:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_tables()

    def _init_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                level INTEGER NOT NULL,
                temp REAL,
                humidity REAL,
                light REAL,
                water REAL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tank_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                tank_level REAL,
                pump_state INTEGER
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS health_ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE NOT NULL,
                level1_rating INTEGER DEFAULT 0,
                level2_rating INTEGER DEFAULT 0,
                level3_rating INTEGER DEFAULT 0,
                notes TEXT,
                notes1 TEXT,
                notes2 TEXT,
                notes3 TEXT
            )
        """)
        for col in ["notes1", "notes2", "notes3"]:
            try:
                cursor.execute(f"ALTER TABLE health_ratings ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError:
                pass
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def insert_sensor(self, level, temp, humidity, light, water):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO sensor_history (timestamp, level, temp, humidity, light, water) VALUES (?, ?, ?, ?, ?, ?)",
            (datetime.now().isoformat(), level, temp, humidity, light, water)
        )
        self.conn.commit()

    def insert_tank(self, tank_level, pump_state):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO tank_history (timestamp, tank_level, pump_state) VALUES (?, ?, ?)",
            (datetime.now().isoformat(), tank_level, pump_state)
        )
        self.conn.commit()

    def get_sensor_history(self, limit=100):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT timestamp, level, temp, humidity, light, water FROM sensor_history ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        return cursor.fetchall()

    def get_tank_history(self, limit=100):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT timestamp, tank_level, pump_state FROM tank_history ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        return cursor.fetchall()

    def get_daily_summary(self, limit=30):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                s.day,
                s.t1, s.t2, s.t3,
                s.h1, s.h2, s.h3,
                s.l1, s.l2, s.l3,
                h.level1_rating, h.level2_rating, h.level3_rating,
                h.notes1, h.notes2, h.notes3
            FROM (
                SELECT 
                    date(timestamp) as day,
                    ROUND(AVG(CASE WHEN level=1 THEN temp END), 1) as t1,
                    ROUND(AVG(CASE WHEN level=2 THEN temp END), 1) as t2,
                    ROUND(AVG(CASE WHEN level=3 THEN temp END), 1) as t3,
                    ROUND(AVG(CASE WHEN level=1 THEN humidity END), 1) as h1,
                    ROUND(AVG(CASE WHEN level=2 THEN humidity END), 1) as h2,
                    ROUND(AVG(CASE WHEN level=3 THEN humidity END), 1) as h3,
                    ROUND(AVG(CASE WHEN level=1 THEN light END), 1) as l1,
                    ROUND(AVG(CASE WHEN level=2 THEN light END), 1) as l2,
                    ROUND(AVG(CASE WHEN level=3 THEN light END), 1) as l3
                FROM sensor_history
                GROUP BY date(timestamp)
                ORDER BY day DESC
                LIMIT ?
            ) s
            LEFT JOIN health_ratings h ON s.day = h.date
            ORDER BY s.day DESC
        """, (limit,))
        return cursor.fetchall()

    def set_health_rating(self, lvl, rating, notes=None):
        cursor = self.conn.cursor()
        today = date.today().isoformat()
        col = f"level{lvl}_rating"
        notes_col = f"notes{lvl}"
        if notes is None:
            cursor.execute(f"""
                INSERT INTO health_ratings (date, {col})
                VALUES (?, ?)
                ON CONFLICT(date) DO UPDATE SET {col} = excluded.{col}
            """, (today, rating))
        else:
            cursor.execute(f"""
                INSERT INTO health_ratings (date, {col}, {notes_col})
                VALUES (?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET {col} = excluded.{col}, {notes_col} = excluded.{notes_col}
            """, (today, rating, notes))
        self.conn.commit()

    def get_health_rating(self, lvl, for_date=None):
        cursor = self.conn.cursor()
        d = for_date or date.today().isoformat()
        col = f"level{lvl}_rating"
        cursor.execute(f"SELECT {col} FROM health_ratings WHERE date = ?", (d,))
        row = cursor.fetchone()
        return row[0] if row else 0

    def get_health_notes(self, lvl, for_date=None):
        cursor = self.conn.cursor()
        d = for_date or date.today().isoformat()
        col = f"notes{lvl}"
        cursor.execute(f"SELECT {col} FROM health_ratings WHERE date = ?", (d,))
        row = cursor.fetchone()
        return row[0] if row and row[0] else ""

    def get_all_health_ratings(self, limit=30):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT date, level1_rating, level2_rating, level3_rating, notes1, notes2, notes3 FROM health_ratings ORDER BY date DESC LIMIT ?",
            (limit,)
        )
        return cursor.fetchall()

    def add_event(self, event):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO event_log (timestamp, event) VALUES (?, ?)",
                       (datetime.now().isoformat(), event))
        self.conn.commit()

    def get_events(self, limit=100):
        cursor = self.conn.cursor()
        cursor.execute("SELECT timestamp, event FROM event_log ORDER BY timestamp DESC LIMIT ?", (limit,))
        return cursor.fetchall()

class DataStore:
    def __init__(self, db):
        self.db = db
        self.levels = {
            1: {"temp": "--", "hum": "--", "light": "--", "water": "--"},
            2: {"temp": "--", "hum": "--", "light": "--", "water": "--"},
            3: {"temp": "--", "hum": "--", "light": "--", "water": "--"},
        }
        self.tank = {"level": "--", "pump": "--"}
        self.esp_status = {"ESP32_1": False, "ESP32_2": False, "ESP32_3": False}
        self.controls = {
            "l1_power": False, "l2_power": False, "l3_power": False,
            "l1_white": False, "l2_white": False, "l3_white": False,
            "l1_rb": False, "l2_rb": False, "l3_rb": False,
            "pump": False,
        }
        self.timers = {
            1: {"on": "08:00", "off": "20:00", "active": False},
            2: {"on": "08:00", "off": "20:00", "active": False},
            3: {"on": "08:00", "off": "20:00", "active": False},
        }
        self.safety_lock = False
        self.control_mode = "AUTO"
        self._callbacks = []

    def subscribe(self, callback):
        self._callbacks.append(callback)

    def notify(self):
        for cb in self._callbacks:
            try:
                cb()
            except Exception:
                pass

    def add_history(self, event):
        self.db.add_event(event)
        self.notify()

    def set_control_mode(self, mode):
        self.control_mode = mode
        self.notify()

store = None

class ESPClient:
    @staticmethod
    def fetch(url, timeout=3):
        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "VerticalFarmApp/1.0")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except Exception:
            return None

    @staticmethod
    def post(url, data=None, timeout=3, form_encoded=False):
        try:
            if form_encoded and data:
                payload = urllib.parse.urlencode(data).encode("utf-8")
                req = urllib.request.Request(url, data=payload, method="POST")
                req.add_header("Content-Type", "application/x-www-form-urlencoded")
            elif data:
                payload = json.dumps(data).encode("utf-8")
                req = urllib.request.Request(url, data=payload, method="POST")
                req.add_header("Content-Type", "application/json")
            else:
                req = urllib.request.Request(url, method="POST")
            req.add_header("User-Agent", "VerticalFarmApp/1.0")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except Exception:
            return None

class PollingThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.running = True
        self._demo_mode = False

    def run(self):
        while self.running:
            if self._demo_mode:
                import random
                for lvl in [1, 2, 3]:
                    store.levels[lvl]["temp"] = f"{random.uniform(24.0, 30.0):.1f}"
                    store.levels[lvl]["hum"] = f"{random.uniform(55.0, 75.0):.1f}"
                    store.levels[lvl]["light"] = f"{random.uniform(200.0, 800.0):.1f}"
                    store.levels[lvl]["water"] = f"{random.uniform(40.0, 90.0):.1f}"
                store.tank["level"] = f"{random.uniform(50.0, 95.0):.1f}"
                store.tank["pump"] = "ON" if store.controls["pump"] else "OFF"
                store.esp_status = {k: True for k in store.esp_status}
                for lvl in [1, 2, 3]:
                    try:
                        store.db.insert_sensor(lvl,
                            float(store.levels[lvl]["temp"]),
                            float(store.levels[lvl]["hum"]),
                            float(store.levels[lvl]["light"]),
                            float(store.levels[lvl]["water"]))
                    except Exception:
                        pass
                try:
                    store.db.insert_tank(float(store.tank["level"]), 1 if store.tank["pump"] == "ON" else 0)
                except Exception:
                    pass
            else:
                for key, cfg in ESP32_CONFIG.items():
                    ip = cfg["ip"]
                    resp = ESPClient.fetch(f"http://{ip}/status")
                    store.esp_status[key] = resp is not None
                    if resp:
                        try:
                            data = json.loads(resp)
                            if key == "ESP32_2":
                                for i, lvl in enumerate([1, 2, 3], 1):
                                    t = data.get(f"temp_l{i}", "--")
                                    h = data.get(f"hum_l{i}", "--")
                                    l = data.get(f"lux_l{i}", "--")
                                    store.levels[lvl]["temp"] = str(t)
                                    store.levels[lvl]["hum"] = str(h)
                                    store.levels[lvl]["light"] = str(l)
                                    try:
                                        store.db.insert_sensor(lvl, float(t), float(h), float(l), 0.0)
                                    except Exception:
                                        pass
                            elif key == "ESP32_3":
                                store.tank["level"] = str(data.get("tank_pct", "--"))
                                for i, lvl in enumerate([1, 2, 3], 1):
                                    store.levels[lvl]["water"] = str(data.get(f"l{i}_pct", "--"))
                                try:
                                    store.db.insert_tank(float(data.get("tank_pct", 0)), 0)
                                except Exception:
                                    pass
                            elif key == "ESP32_1":
                                store.tank["pump"] = "ON" if data.get("pump", 0) else "OFF"
                                store.controls["pump"] = bool(data.get("pump", 0))
                                store.controls["l1_power"] = bool(data.get("l1_pwr", 0))
                                store.controls["l2_power"] = bool(data.get("l2_pwr", 0))
                                store.controls["l3_power"] = bool(data.get("l3_pwr", 0))
                        except Exception:
                            pass
            store.notify()
            time.sleep(POLL_INTERVAL / 1000)

    def stop(self):
        self.running = False

    def set_demo(self, val):
        self._demo_mode = val

class SmoothToggle(tk.Canvas):
    def __init__(self, parent, command=None, on_color=COLORS["green"], off_color=COLORS["gray"],
                 width=60, height=32, animation_ms=120):
        super().__init__(parent, width=width, height=height, bg=COLORS["bg_dark"], highlightthickness=0, cursor="hand2")
        self.command = command
        self.on_color = on_color
        self.off_color = off_color
        self.width = width
        self.height = height
        self.r = height // 2
        self.knob_r = self.r - 4
        self._state = False
        self._animating = False
        self._current_knob_x = self.r + 4
        self._target_knob_x = self._current_knob_x
        self.animation_ms = animation_ms
        self._draw()
        self.bind("<Button-1>", self._toggle)

    def _draw(self):
        self.delete("all")
        progress = (self._current_knob_x - (self.r + 4)) / ((self.width - self.r - 4) - (self.r + 4))
        progress = max(0.0, min(1.0, progress))
        bg = self._interpolate_color(self.off_color, self.on_color, progress)
        self._create_rounded_rect(0, 0, self.width, self.height, self.r, fill=bg, outline="")
        self.create_oval(
            self._current_knob_x - self.knob_r, self.height//2 - self.knob_r,
            self._current_knob_x + self.knob_r, self.height//2 + self.knob_r,
            fill=COLORS["white"], outline="#e5e7eb", width=1
        )
        self.create_oval(
            self._current_knob_x - self.knob_r + 1, self.height//2 - self.knob_r + 2,
            self._current_knob_x + self.knob_r + 1, self.height//2 + self.knob_r + 2,
            fill="", outline="#000000", width=1, stipple="gray50"
        )

    def _create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2, x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _interpolate_color(self, c1, c2, t):
        def hex_to_rgb(h):
            h = h.lstrip("#")
            return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        def rgb_to_hex(r, g, b):
            return f"#{r:02x}{g:02x}{b:02x}"
        r1, g1, b1 = hex_to_rgb(c1)
        r2, g2, b2 = hex_to_rgb(c2)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        return rgb_to_hex(r, g, b)

    def _toggle(self, event=None):
        self.set_state(not self._state)

    def set_state(self, state):
        if self._state == state:
            return
        self._state = state
        self._target_knob_x = (self.width - self.r - 4) if state else (self.r + 4)
        self._animate()
        if self.command:
            self.command(state)

    def _animate(self):
        if self._animating:
            return
        self._animating = True
        self._step_animation()

    def _step_animation(self):
        dx = self._target_knob_x - self._current_knob_x
        if abs(dx) < 0.5:
            self._current_knob_x = self._target_knob_x
            self._draw()
            self._animating = False
            return
        step = dx * 0.25
        if abs(step) < 1:
            step = 1 if dx > 0 else -1
        self._current_knob_x += step
        self._draw()
        self.after(16, self._step_animation)

    def get_state(self):
        return self._state

class ModeToggle(tk.Frame):
    def __init__(self, parent, command=None, **kwargs):
        super().__init__(parent, bg=COLORS["bg_dark"], **kwargs)
        self.command = command
        self._mode = "AUTO"

        self.manual_btn = tk.Label(self, text="MANUAL", font=("Segoe UI", 13, "bold"),
                                   bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
                                   padx=24, pady=10, cursor="hand2")
        self.manual_btn.pack(side="left")
        self.manual_btn.bind("<Button-1>", lambda e: self.set_mode("MANUAL"))

        self.auto_btn = tk.Label(self, text="AUTO (Cloud)", font=("Segoe UI", 13, "bold"),
                                 bg=COLORS["blue"], fg=COLORS["white"],
                                 padx=24, pady=10, cursor="hand2")
        self.auto_btn.pack(side="left")
        self.auto_btn.bind("<Button-1>", lambda e: self.set_mode("AUTO"))

    def set_mode(self, mode):
        if self._mode == mode:
            return
        self._mode = mode
        if mode == "MANUAL":
            self.manual_btn.config(bg=COLORS["green"], fg=COLORS["white"])
            self.auto_btn.config(bg=COLORS["bg_card"], fg=COLORS["text_secondary"])
        else:
            self.manual_btn.config(bg=COLORS["bg_card"], fg=COLORS["text_secondary"])
            self.auto_btn.config(bg=COLORS["blue"], fg=COLORS["white"])
        if self.command:
            self.command(mode)

    def get_mode(self):
        return self._mode

class StatusDot(tk.Canvas):
    def __init__(self, parent, color, size=12):
        super().__init__(parent, width=size, height=size, bg=COLORS["bg_dark"], highlightthickness=0)
        self.color = color
        self.size = size
        self._draw()

    def _draw(self):
        self.delete("all")
        pad = 2
        self.create_oval(pad, pad, self.size-pad, self.size-pad, fill=self.color, outline="")

    def set_color(self, color):
        self.color = color
        self._draw()

class GreenButton(tk.Canvas):
    def __init__(self, parent, text, command=None, color=COLORS["green"], hover_color=COLORS["green_light"],
                 text_color=COLORS["white"], width=120, height=42):
        super().__init__(parent, width=width, height=height, bg=COLORS["bg_dark"], highlightthickness=0, cursor="hand2")
        self.text = text
        self.command = command
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.current_color = color
        self.width = width
        self.height = height
        self._draw()
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _draw(self):
        self.delete("all")
        r = 10
        self.create_rounded_rect(0, 0, self.width, self.height, r, fill=self.current_color, outline="")
        self.create_text(self.width//2, self.height//2, text=self.text, fill=self.text_color,
                         font=("Segoe UI", 12, "bold"))

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2, x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _on_enter(self, e):
        self.current_color = self.hover_color
        self._draw()

    def _on_leave(self, e):
        self.current_color = self.color
        self._draw()

    def _on_click(self, e):
        if self.command:
            self.command()

class HealthRatingWidget(tk.Frame):
    def __init__(self, parent, level, db, on_change=None, **kwargs):
        super().__init__(parent, bg=COLORS["bg_card"], **kwargs)
        self.level = level
        self.db = db
        self.on_change = on_change
        self.rating = db.get_health_rating(level)
        self.notes = db.get_health_notes(level)
        self.stars = []
        self._build()

    def _build(self):
        colors = LEVEL_COLORS[self.level]

        hdr = tk.Frame(self, bg=COLORS["bg_card"])
        hdr.pack(fill="x", pady=(0, 4))
        tk.Label(hdr, text=f"LEVEL {self.level}", font=("Segoe UI", 12, "bold"),
                 bg=COLORS["bg_card"], fg=colors["main"]).pack(side="left")
        tk.Label(hdr, text=date.today().strftime("%d/%m/%Y"), font=("Segoe UI", 9),
                 bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack(side="right")

        stars_row = tk.Frame(self, bg="#1e2636")
        stars_row.pack(fill="x", pady=(4, 4))

        for i in range(1, 4):
            star = tk.Label(stars_row, text="★", font=("Segoe UI", 22),
                            bg="#1e2636",
                            fg=COLORS["star_filled"] if i <= self.rating else COLORS["star_empty"],
                            cursor="hand2")
            star.pack(side="left", padx=6)
            star.bind("<Button-1>", lambda e, idx=i: self._set_rating(idx))
            self.stars.append(star)

        self.val_lbl = tk.Label(stars_row, text=f"{self.rating}/3", font=("Segoe UI", 11, "bold"),
                                bg="#1e2636", fg=COLORS["yellow"])
        self.val_lbl.pack(side="right", padx=(8, 4))

        tk.Label(self, text="Catatan:", font=("Segoe UI", 10),
                 bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack(anchor="w", pady=(4, 0))

        entry_row = tk.Frame(self, bg=COLORS["bg_card"])
        entry_row.pack(fill="x", pady=(2, 0))

        self.notes_entry = tk.Entry(entry_row, font=("Segoe UI", 10),
                                    bg=COLORS["bg_dark"], fg=COLORS["text_primary"],
                                    highlightbackground=COLORS["border"], highlightthickness=1,
                                    insertbackground=COLORS["green"])
        self.notes_entry.insert(0, self.notes or "")
        self.notes_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.notes_entry.bind("<Return>", lambda e: self._save_notes())
        self.notes_entry.bind("<FocusOut>", lambda e: self._save_notes())

        save_lbl = tk.Label(entry_row, text="💾", font=("Segoe UI", 12),
                            bg=COLORS["bg_card"], fg=COLORS["green_light"], cursor="hand2")
        save_lbl.pack(side="right")
        save_lbl.bind("<Button-1>", lambda e: self._save_notes())

        self.status_lbl = tk.Label(self, text="", font=("Segoe UI", 8),
                                     bg=COLORS["bg_card"], fg=COLORS["green_light"])
        self.status_lbl.pack(anchor="w", pady=(2, 0))

    def _set_rating(self, value):
        self.rating = value
        for i, star in enumerate(self.stars, 1):
            star.config(fg=COLORS["star_filled"] if i <= value else COLORS["star_empty"])
        self.val_lbl.config(text=f"{value}/3")
        self.db.set_health_rating(self.level, value)
        self.status_lbl.config(text="✅ Rating disimpan", fg=COLORS["green_light"])
        self.after(2000, lambda: self.status_lbl.config(text=""))
        if self.on_change:
            self.on_change(self.level, value)

    def _save_notes(self):
        text = self.notes_entry.get().strip()
        if text != self.notes:
            self.notes = text
            self.db.set_health_rating(self.level, self.rating, notes=text)
            self.status_lbl.config(text="✅ Catatan disimpan", fg=COLORS["green_light"])
            self.after(2000, lambda: self.status_lbl.config(text=""))
            if self.on_change:
                self.on_change(self.level, self.rating)

    def refresh(self):
        new_rating = self.db.get_health_rating(self.level)
        new_notes = self.db.get_health_notes(self.level)
        if new_rating != self.rating:
            self.rating = new_rating
            for i, star in enumerate(self.stars, 1):
                star.config(fg=COLORS["star_filled"] if i <= self.rating else COLORS["star_empty"])
            self.val_lbl.config(text=f"{self.rating}/3")
        if new_notes != self.notes:
            self.notes = new_notes
            self.notes_entry.delete(0, tk.END)
            self.notes_entry.insert(0, self.notes or "")

class VerticalFarmingApp:
    def __init__(self, root, db):
        self.root = root
        self.db = db
        self.root.title("Vertical Farming IoT — Multi ESP32 Control")
        self.root.geometry("1500x980")
        self.root.configure(bg=COLORS["bg_dark"])
        self.root.minsize(1350, 850)

        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TNotebook", background=COLORS["bg_dark"], borderwidth=0)
        self.style.configure("TNotebook.Tab", background=COLORS["bg_card"], foreground=COLORS["text_secondary"],
                             padding=[24, 10], font=("Segoe UI", 12, "bold"))
        self.style.map("TNotebook.Tab", background=[("selected", COLORS["green"])],
                       foreground=[("selected", COLORS["white"])])
        self.style.configure("TFrame", background=COLORS["bg_dark"])
        self.style.configure("TLabel", background=COLORS["bg_dark"], foreground=COLORS["text_primary"])

        self._build_ui()
        store.subscribe(self._on_data_update)

        self.poll_thread = PollingThread()
        self.poll_thread.start()
        self._schedule_refresh()

    def _build_ui(self):
        top = tk.Frame(self.root, bg=COLORS["bg_dark"])
        top.pack(fill="x", padx=24, pady=(18, 8))

        title_frame = tk.Frame(top, bg=COLORS["bg_dark"])
        title_frame.pack(side="left")
        tk.Label(title_frame, text="VERTICAL FARMING", font=("Segoe UI", 28, "bold"),
                 bg=COLORS["bg_dark"], fg=COLORS["green"]).pack(anchor="w")
        tk.Label(title_frame, text="Multi-ESP32 IoT Control Dashboard", font=("Segoe UI", 13),
                 bg=COLORS["bg_dark"], fg=COLORS["text_secondary"]).pack(anchor="w")

        mode_frame = tk.Frame(top, bg=COLORS["bg_dark"])
        mode_frame.pack(side="right", padx=(0, 24))
        tk.Label(mode_frame, text="Control Mode:", font=("Segoe UI", 12),
                 bg=COLORS["bg_dark"], fg=COLORS["text_secondary"]).pack(side="left", padx=(0, 12))
        self.mode_toggle = ModeToggle(mode_frame, command=self._on_mode_change)
        self.mode_toggle.pack(side="left")

        status_frame = tk.Frame(top, bg=COLORS["bg_dark"])
        status_frame.pack(side="right", padx=(0, 30))
        self.esp_dots = {}
        for key, cfg in ESP32_CONFIG.items():
            f = tk.Frame(status_frame, bg=COLORS["bg_dark"])
            f.pack(side="left", padx=14)
            dot = StatusDot(f, COLORS["red"], size=14)
            dot.pack(side="left", padx=(0, 8))
            tk.Label(f, text=cfg["name"], font=("Segoe UI", 12),
                     bg=COLORS["bg_dark"], fg=COLORS["text_secondary"]).pack(side="left")
            self.esp_dots[key] = dot

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=24, pady=12)

        self.settings_tab = tk.Frame(self.notebook, bg=COLORS["bg_dark"])
        self.notebook.add(self.settings_tab, text="  SETTINGS  ")
        self._build_settings_tab()

        self.monitor_tab = tk.Frame(self.notebook, bg=COLORS["bg_dark"])
        self.notebook.add(self.monitor_tab, text="  MONITOR  ")
        self._build_monitor_tab()

        self.history_tab = tk.Frame(self.notebook, bg=COLORS["bg_dark"])
        self.notebook.add(self.history_tab, text="  HISTORY  ")
        self._build_history_tab()

    def _on_mode_change(self, mode):
        store.set_control_mode(mode)
        store.add_history(f"Control mode changed to: {mode}")
        ip = ESP32_CONFIG["ESP32_1"]["ip"]
        url = f"http://{ip}/command?cmd={mode}"
        resp = ESPClient.fetch(url, timeout=2)
        if resp:
            store.add_history(f"[OK] ESP32_1 mode set to {mode}")
        else:
            store.add_history(f"[WARN] ESP32_1 not responding for mode change")

    def _build_settings_tab(self):
        container = tk.Frame(self.settings_tab, bg=COLORS["bg_dark"])
        container.pack(fill="both", expand=True, padx=30, pady=20)

        tk.Label(container, text="⚙️ ESP32 Configuration", font=("Segoe UI", 20, "bold"),
                 bg=COLORS["bg_dark"], fg=COLORS["green"]).pack(anchor="w", pady=(0, 6))
        tk.Label(container, text="Set the IP address for each ESP32 board. Changes are saved automatically.",
                 font=("Segoe UI", 13), bg=COLORS["bg_dark"], fg=COLORS["text_secondary"]).pack(anchor="w", pady=(0, 20))

        self.ip_entries = {}
        for key, cfg in ESP32_CONFIG.items():
            card = tk.Frame(container, bg=COLORS["bg_card"], highlightbackground=COLORS["border"], highlightthickness=1)
            card.pack(fill="x", pady=8, ipady=12)

            strip = tk.Frame(card, bg=cfg["color"], width=6)
            strip.pack(side="left", fill="y", padx=(0, 15))
            strip.pack_propagate(False)

            info = tk.Frame(card, bg=COLORS["bg_card"])
            info.pack(side="left", fill="y", expand=True)

            tk.Label(info, text=cfg["name"], font=("Segoe UI", 16, "bold"),
                     bg=COLORS["bg_card"], fg=COLORS["text_primary"]).pack(anchor="w", padx=15, pady=(10, 2))
            tk.Label(info, text=f"Gateway Node ID: {key.replace('_', '')}", font=("Segoe UI", 12),
                     bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack(anchor="w", padx=15)

            ip_frame = tk.Frame(card, bg=COLORS["bg_card"])
            ip_frame.pack(side="right", padx=20)
            tk.Label(ip_frame, text="IP Address:", font=("Segoe UI", 12, "bold"),
                     bg=COLORS["bg_card"], fg=COLORS["text_secondary"]).pack(side="left", padx=(0, 10))
            entry = tk.Entry(ip_frame, width=18, font=("Segoe UI", 13), justify="center",
                             bg=COLORS["bg_dark"], fg=COLORS["text_primary"],
                             highlightbackground=COLORS["border"], highlightthickness=1,
                             insertbackground=COLORS["green"])
            entry.insert(0, cfg["ip"])
            entry.pack(side="left")
            self.ip_entries[key] = entry

        btn_frame = tk.Frame(container, bg=COLORS["bg_dark"])
        btn_frame.pack(fill="x", pady=(20, 10))

        save_btn = GreenButton(btn_frame, "Save & Apply", command=self._save_ip_settings,
                               color=COLORS["green"], hover_color=COLORS["green_light"], width=150, height=44)
        save_btn.pack(side="left", padx=(0, 15))

        test_btn = GreenButton(btn_frame, "Test Connection", command=self._test_connections,
                               color=COLORS["blue"], hover_color=COLORS["cyan"], width=150, height=44)
        test_btn.pack(side="left", padx=(0, 15))

        reset_btn = GreenButton(btn_frame, "Reset to Default", command=self._reset_ip_defaults,
                                color=COLORS["gray"], hover_color=COLORS["text_secondary"], width=150, height=44)
        reset_btn.pack(side="left")

        self.settings_status = tk.Label(container, text="", font=("Segoe UI", 13),
                                        bg=COLORS["bg_dark"], fg=COLORS["green_light"])
        self.settings_status.pack(anchor="w", pady=(15, 0))

    def _save_ip_settings(self):
        global ESP32_CONFIG
        for key, entry in self.ip_entries.items():
            ip = entry.get().strip()
            parts = ip.split(".")
            if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                ESP32_CONFIG[key]["ip"] = ip
            else:
                messagebox.showerror("Invalid IP", f"IP address for {key} is not valid.\nFormat: xxx.xxx.xxx.xxx")
                return
        save_config(ESP32_CONFIG)
        self.settings_status.config(text="✅ IP addresses saved successfully!", fg=COLORS["green_light"])
        store.add_history("IP configuration updated via Settings")

    def _test_connections(self):
        self.settings_status.config(text="🔄 Testing connections...", fg=COLORS["yellow"])
        self.root.update_idletasks()
        results = []
        for key, cfg in ESP32_CONFIG.items():
            ip = cfg["ip"]
            resp = ESPClient.fetch(f"http://{ip}/status", timeout=2)
            if resp:
                results.append(f"{key}: ✅ Connected")
                store.esp_status[key] = True
            else:
                results.append(f"{key}: ❌ Offline")
                store.esp_status[key] = False
        store.notify()
        self.settings_status.config(text="  |  ".join(results), fg=COLORS["green_light"])

    def _reset_ip_defaults(self):
        global ESP32_CONFIG
        ESP32_CONFIG = {k: v.copy() for k, v in DEFAULT_CONFIG.items()}
        for key, entry in self.ip_entries.items():
            entry.delete(0, tk.END)
            entry.insert(0, DEFAULT_CONFIG[key]["ip"])
        save_config(ESP32_CONFIG)
        self.settings_status.config(text="✅ Reset to default IPs.", fg=COLORS["green_light"])

    def _build_monitor_tab(self):
        top_bar = tk.Frame(self.monitor_tab, bg=COLORS["bg_dark"])
        top_bar.pack(fill="x", pady=(0, 12))

        self.mode_indicator = tk.Label(top_bar, text="MODE: AUTO (Cloud)", font=("Segoe UI", 13, "bold"),
                                       bg=COLORS["bg_dark"], fg=COLORS["blue"])
        self.mode_indicator.pack(side="left")

        self.connect_btn = GreenButton(top_bar, "Connect All", command=self._connect_all,
                                       color=COLORS["green"], hover_color=COLORS["green_light"],
                                       width=130, height=40)
        self.connect_btn.pack(side="right")

        content = tk.Frame(self.monitor_tab, bg=COLORS["bg_dark"])
        content.pack(fill="both", expand=True)
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=2)
        content.grid_rowconfigure(0, weight=1)

        left_panel = tk.Frame(content, bg=COLORS["bg_dark"])
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 15))
        left_panel.grid_rowconfigure(0, weight=1)
        left_panel.grid_rowconfigure(1, weight=0)
        left_panel.grid_rowconfigure(2, weight=0)
        left_panel.grid_columnconfigure(0, weight=1)
        left_panel.grid_columnconfigure(1, weight=1)
        left_panel.grid_columnconfigure(2, weight=1)

        self.level_cards = {}
        self.level_widgets = {}
        for i, lvl in enumerate([1, 2, 3]):
            card = self._create_level_card(left_panel, lvl)
            card.grid(row=0, column=i, sticky="nsew", padx=(0, 10 if i < 2 else 0), pady=(0, 10))
            self.level_cards[lvl] = card

        tank_card = self._create_tank_card(left_panel)
        tank_card.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10))

        timer_card = self._create_timer_card(left_panel)
        timer_card.grid(row=2, column=0, columnspan=3, sticky="ew")

        right_panel = tk.Frame(content, bg=COLORS["bg_dark"])
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.grid_rowconfigure(0, weight=0)
        right_panel.grid_rowconfigure(1, weight=0)
        right_panel.grid_rowconfigure(2, weight=1)
        right_panel.grid_rowconfigure(3, weight=0)

        power_card = self._create_power_control_card(right_panel)
        power_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        pump_card = self._create_pump_control_card(right_panel)
        pump_card.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        health_card = self._create_health_card(right_panel)
        health_card.grid(row=2, column=0, sticky="nsew", pady=(0, 10))

        safety = tk.Frame(right_panel, bg=COLORS["red_dark"], highlightbackground=COLORS["red"], highlightthickness=2)
        safety.grid(row=3, column=0, sticky="ew")
        tk.Label(safety, text="RESET SAFETY LOCK", font=("Segoe UI", 14, "bold"),
                 bg=COLORS["red_dark"], fg=COLORS["white"], cursor="hand2").pack(expand=True, pady=12)
        safety.bind("<Button-1>", lambda e: self._reset_safety())

    def _create_level_card(self, parent, level):
        colors = LEVEL_COLORS[level]
        card = tk.Frame(parent, bg=COLORS["bg_card"], highlightbackground=COLORS["border"], highlightthickness=1)

        header = tk.Frame(card, bg=colors["main"], height=5)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(card, text=f"LEVEL {level}", font=("Segoe UI", 16, "bold"),
                 bg=COLORS["bg_card"], fg=colors["main"]).pack(anchor="w", padx=12, pady=(10, 4))

        sep = tk.Frame(card, bg=COLORS["border"], height=1)
        sep.pack(fill="x", padx=12, pady=(0, 8))

        self.level_widgets[level] = {}
        fields = [
            ("temp", "Temp", "°C", colors["soft"]),
            ("hum", "Hum", "%", colors["soft"]),
            ("light", "Light", "lux", colors["soft"]),
            ("water", "Water", "%", colors["soft"]),
        ]
        for key, label, unit, color in fields:
            row = tk.Frame(card, bg=COLORS["bg_card"])
            row.pack(fill="x", padx=12, pady=5)
            tk.Label(row, text=label, font=("Segoe UI", 13), bg=COLORS["bg_card"],
                     fg=COLORS["text_secondary"], width=8, anchor="w").pack(side="left")
            val_lbl = tk.Label(row, text="--", font=("Segoe UI", 14, "bold"),
                               bg=COLORS["bg_card"], fg=color, width=8, anchor="e")
            val_lbl.pack(side="left", padx=(6, 0))
            tk.Label(row, text=unit, font=("Segoe UI", 12), bg=COLORS["bg_card"],
                     fg=COLORS["text_secondary"]).pack(side="left", padx=(4, 0))
            self.level_widgets[level][key] = val_lbl

        return card

    def _create_tank_card(self, parent):
        card = tk.Frame(parent, bg=COLORS["bg_card"], highlightbackground=COLORS["border"], highlightthickness=1)
        header = tk.Frame(card, bg=COLORS["cyan"], height=5)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(card, text="TANGKI NUTRIEN", font=("Segoe UI", 16, "bold"),
                 bg=COLORS["bg_card"], fg=COLORS["cyan"]).pack(anchor="w", padx=12, pady=(10, 4))
        sep = tk.Frame(card, bg=COLORS["border"], height=1)
        sep.pack(fill="x", padx=12, pady=(0, 8))
        body = tk.Frame(card, bg=COLORS["bg_card"])
        body.pack(fill="x", padx=12, pady=10)
        self.tank_level_lbl = tk.Label(body, text="--%", font=("Segoe UI", 26, "bold"),
                                       bg=COLORS["bg_card"], fg=COLORS["cyan"])
        self.tank_level_lbl.pack(side="left")
        pump_frame = tk.Frame(body, bg=COLORS["bg_card"])
        pump_frame.pack(side="right")
        tk.Label(pump_frame, text="Pump:", font=("Segoe UI", 13), bg=COLORS["bg_card"],
                 fg=COLORS["text_secondary"]).pack(anchor="e")
        self.pump_status_lbl = tk.Label(pump_frame, text="--", font=("Segoe UI", 16, "bold"),
                                        bg=COLORS["bg_card"], fg=COLORS["text_secondary"])
        self.pump_status_lbl.pack(anchor="e")
        return card

    def _create_timer_card(self, parent):
        card = tk.Frame(parent, bg=COLORS["bg_card"], highlightbackground=COLORS["border"], highlightthickness=1)
        header = tk.Frame(card, bg=COLORS["yellow"], height=5)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(card, text="LED TIMER SCHEDULE", font=("Segoe UI", 16, "bold"),
                 bg=COLORS["bg_card"], fg=COLORS["yellow"]).pack(anchor="w", padx=12, pady=(10, 4))
        sep = tk.Frame(card, bg=COLORS["border"], height=1)
        sep.pack(fill="x", padx=12, pady=(0, 8))
        self.timer_widgets = {}
        for lvl in [1, 2, 3]:
            row = tk.Frame(card, bg=COLORS["bg_card"])
            row.pack(fill="x", padx=12, pady=6)
            tk.Label(row, text=f"L{lvl}", font=("Segoe UI", 13, "bold"),
                     bg=COLORS["bg_card"], fg=LEVEL_COLORS[lvl]["main"], width=4).pack(side="left")
            tk.Label(row, text="ON:", font=("Segoe UI", 12), bg=COLORS["bg_card"],
                     fg=COLORS["text_secondary"]).pack(side="left", padx=(10, 4))
            on_entry = tk.Entry(row, width=8, font=("Segoe UI", 12), justify="center",
                                bg=COLORS["bg_dark"], fg=COLORS["text_primary"],
                                highlightbackground=COLORS["border"], highlightthickness=1,
                                insertbackground=COLORS["green"])
            on_entry.insert(0, store.timers[lvl]["on"])
            on_entry.pack(side="left", padx=2)
            tk.Label(row, text="OFF:", font=("Segoe UI", 12), bg=COLORS["bg_card"],
                     fg=COLORS["text_secondary"]).pack(side="left", padx=(10, 4))
            off_entry = tk.Entry(row, width=8, font=("Segoe UI", 12), justify="center",
                                 bg=COLORS["bg_dark"], fg=COLORS["text_primary"],
                                 highlightbackground=COLORS["border"], highlightthickness=1,
                                 insertbackground=COLORS["green"])
            off_entry.insert(0, store.timers[lvl]["off"])
            off_entry.pack(side="left", padx=2)
            var = tk.BooleanVar(value=store.timers[lvl]["active"])
            chk = tk.Checkbutton(row, text="Aktif", variable=var,
                                 bg=COLORS["bg_card"], fg=COLORS["text_secondary"],
                                 selectcolor=COLORS["bg_dark"], activebackground=COLORS["bg_card"],
                                 font=("Segoe UI", 12))
            chk.pack(side="left", padx=(10, 0))
            def make_save(lvl_num, on_e, off_e, v):
                return lambda: self._save_timer(lvl_num, on_e.get(), off_e.get(), v.get())
            save_btn = GreenButton(row, "Simpan", command=make_save(lvl, on_entry, off_entry, var),
                                   color=COLORS["green"], hover_color=COLORS["green_light"], width=90, height=32)
            save_btn.pack(side="left", padx=(10, 0))
            self.timer_widgets[lvl] = {"on": on_entry, "off": off_entry, "active": var}
        return card

    def _create_power_control_card(self, parent):
        card = tk.Frame(parent, bg=COLORS["bg_card"], highlightbackground=COLORS["border"], highlightthickness=1)
        header = tk.Frame(card, bg=COLORS["green"], height=5)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(card, text="POWER CONTROL", font=("Segoe UI", 16, "bold"),
                 bg=COLORS["bg_card"], fg=COLORS["green"]).pack(anchor="w", padx=12, pady=(10, 4))
        sep = tk.Frame(card, bg=COLORS["border"], height=1)
        sep.pack(fill="x", padx=12, pady=(0, 8))
        self.power_switches = {}
        levels = [
            ("Level 1 Power", "l1_power"),
            ("Level 2 Power", "l2_power"),
            ("Level 3 Power", "l3_power"),
        ]
        for label, key in levels:
            row = tk.Frame(card, bg=COLORS["bg_card"])
            row.pack(fill="x", padx=12, pady=10)
            tk.Label(row, text=label, font=("Segoe UI", 13, "bold"),
                     bg=COLORS["bg_card"], fg=COLORS["text_primary"]).pack(side="left")
            def make_cmd(k):
                return lambda st: self._send_control(k, st)
            sw = SmoothToggle(row, command=make_cmd(key), on_color=COLORS["green"], off_color=COLORS["gray"])
            sw.pack(side="right")
            self.power_switches[key] = sw
        return card

    def _create_pump_control_card(self, parent):
        card = tk.Frame(parent, bg=COLORS["bg_card"], highlightbackground=COLORS["border"], highlightthickness=1)
        header = tk.Frame(card, bg=COLORS["purple"], height=5)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(card, text="PUMP CONTROL", font=("Segoe UI", 16, "bold"),
                 bg=COLORS["bg_card"], fg=COLORS["purple"]).pack(anchor="w", padx=12, pady=(10, 4))
        sep = tk.Frame(card, bg=COLORS["border"], height=1)
        sep.pack(fill="x", padx=12, pady=(0, 8))
        row = tk.Frame(card, bg=COLORS["bg_card"])
        row.pack(fill="x", padx=12, pady=10)
        tk.Label(row, text="Pump", font=("Segoe UI", 14, "bold"),
                 bg=COLORS["bg_card"], fg=COLORS["text_primary"]).pack(side="left")
        self.pump_switch = SmoothToggle(row, command=lambda st: self._send_control("pump", st),
                                        on_color=COLORS["purple"], off_color=COLORS["gray"])
        self.pump_switch.pack(side="right")
        return card

    def _create_health_card(self, parent):
        card = tk.Frame(parent, bg=COLORS["bg_card"], highlightbackground=COLORS["border"], highlightthickness=1)
        header = tk.Frame(card, bg=COLORS["green_light"], height=5)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(card, text="🌱 PLANT HEALTH RATING", font=("Segoe UI", 16, "bold"),
                 bg=COLORS["bg_card"], fg=COLORS["green_light"]).pack(anchor="w", padx=12, pady=(10, 4))
        sep = tk.Frame(card, bg=COLORS["border"], height=1)
        sep.pack(fill="x", padx=12, pady=(0, 8))

        self.health_widgets = {}
        body = tk.Frame(card, bg=COLORS["bg_card"])
        body.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(2, weight=1)

        for i, lvl in enumerate([1, 2, 3]):
            hw = HealthRatingWidget(body, lvl, self.db, on_change=self._on_health_change)
            hw.grid(row=0, column=i, sticky="nsew", padx=(0, 8 if i < 2 else 0))
            self.health_widgets[lvl] = hw

        return card

    def _on_health_change(self, level, rating):
        store.add_history(f"Health rating Level {level}: {rating} star(s) on {date.today().strftime('%d/%m/%Y')}")

    def _build_history_tab(self):
        container = tk.Frame(self.history_tab, bg=COLORS["bg_dark"])
        container.pack(fill="both", expand=True, padx=10, pady=10)
        hist_notebook = ttk.Notebook(container)
        hist_notebook.pack(fill="both", expand=True)

        daily_tab = tk.Frame(hist_notebook, bg=COLORS["bg_dark"])
        hist_notebook.add(daily_tab, text="  Daily Summary  ")
        self._build_daily_summary(daily_tab)

        health_tab = tk.Frame(hist_notebook, bg=COLORS["bg_dark"])
        hist_notebook.add(health_tab, text="  Health Ratings  ")
        self._build_health_history(health_tab)

        event_tab = tk.Frame(hist_notebook, bg=COLORS["bg_dark"])
        hist_notebook.add(event_tab, text="  Event Log  ")
        self._build_event_log(event_tab)

    def _build_daily_summary(self, parent):
        tk.Label(parent, text="📊 Daily Sensor Summary (Average per Day)", font=("Segoe UI", 16, "bold"),
                 bg=COLORS["bg_dark"], fg=COLORS["green"]).pack(anchor="w", pady=(0, 10))
        style = ttk.Style()
        style.configure("Daily.Treeview", background=COLORS["bg_card"], foreground=COLORS["text_primary"],
                        fieldbackground=COLORS["bg_card"], rowheight=30)
        style.configure("Daily.Treeview.Heading", background=COLORS["bg_card"], foreground=COLORS["green"],
                        font=("Segoe UI", 11, "bold"))
        style.map("Daily.Treeview", background=[("selected", COLORS["green_dark"])])
        columns = ("date", "t1", "t2", "t3", "h1", "h2", "h3", "l1", "l2", "l3", "hr1", "hr2", "hr3", "n1", "n2", "n3")
        self.daily_tree = ttk.Treeview(parent, columns=columns, show="headings", style="Daily.Treeview", height=18)
        self.daily_tree.heading("date", text="Date")
        self.daily_tree.heading("t1", text="Temp L1")
        self.daily_tree.heading("t2", text="Temp L2")
        self.daily_tree.heading("t3", text="Temp L3")
        self.daily_tree.heading("h1", text="Hum L1")
        self.daily_tree.heading("h2", text="Hum L2")
        self.daily_tree.heading("h3", text="Hum L3")
        self.daily_tree.heading("l1", text="Light L1")
        self.daily_tree.heading("l2", text="Light L2")
        self.daily_tree.heading("l3", text="Light L3")
        self.daily_tree.heading("hr1", text="Health L1")
        self.daily_tree.heading("hr2", text="Health L2")
        self.daily_tree.heading("hr3", text="Health L3")
        self.daily_tree.heading("n1", text="Catatan L1")
        self.daily_tree.heading("n2", text="Catatan L2")
        self.daily_tree.heading("n3", text="Catatan L3")
        widths = [90, 60, 60, 60, 60, 60, 60, 70, 70, 70, 80, 80, 80, 150, 150, 150]
        for c, w in zip(columns, widths):
            self.daily_tree.column(c, width=w, anchor="center")
        for c in ["n1", "n2", "n3"]:
            self.daily_tree.column(c, anchor="w")
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.daily_tree.yview)
        self.daily_tree.configure(yscrollcommand=scrollbar.set)
        self.daily_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _build_health_history(self, parent):
        tk.Label(parent, text="Daily Health Ratings", font=("Segoe UI", 16, "bold"),
                 bg=COLORS["bg_dark"], fg=COLORS["yellow"]).pack(anchor="w", pady=(0, 10))
        style = ttk.Style()
        style.configure("Health.Treeview", background=COLORS["bg_card"], foreground=COLORS["text_primary"],
                        fieldbackground=COLORS["bg_card"], rowheight=30)
        style.configure("Health.Treeview.Heading", background=COLORS["bg_card"], foreground=COLORS["yellow"],
                        font=("Segoe UI", 11, "bold"))
        style.map("Health.Treeview", background=[("selected", "#3f3f25")])
        columns = ("date", "l1", "l2", "l3", "n1", "n2", "n3")
        self.health_tree = ttk.Treeview(parent, columns=columns, show="headings", style="Health.Treeview", height=18)
        self.health_tree.heading("date", text="Date")
        self.health_tree.heading("l1", text="Level 1 ★")
        self.health_tree.heading("l2", text="Level 2 ★")
        self.health_tree.heading("l3", text="Level 3 ★")
        self.health_tree.heading("n1", text="Catatan L1")
        self.health_tree.heading("n2", text="Catatan L2")
        self.health_tree.heading("n3", text="Catatan L3")
        for c, w in zip(columns, [100, 90, 90, 90, 200, 200, 200]):
            self.health_tree.column(c, width=w, anchor="center")
        for c in ["n1", "n2", "n3"]:
            self.health_tree.column(c, anchor="w")
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.health_tree.yview)
        self.health_tree.configure(yscrollcommand=scrollbar.set)
        self.health_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _build_event_log(self, parent):
        tk.Label(parent, text="System Event Log", font=("Segoe UI", 16, "bold"),
                 bg=COLORS["bg_dark"], fg=COLORS["cyan"]).pack(anchor="w", pady=(0, 10))
        style = ttk.Style()
        style.configure("Event.Treeview", background=COLORS["bg_card"], foreground=COLORS["text_primary"],
                        fieldbackground=COLORS["bg_card"], rowheight=28)
        style.configure("Event.Treeview.Heading", background=COLORS["bg_card"], foreground=COLORS["cyan"],
                        font=("Segoe UI", 11, "bold"))
        style.map("Event.Treeview", background=[("selected", COLORS["green_dark"])])
        columns = ("time", "event")
        self.event_tree = ttk.Treeview(parent, columns=columns, show="headings", style="Event.Treeview", height=18)
        self.event_tree.heading("time", text="Time")
        self.event_tree.heading("event", text="Event")
        self.event_tree.column("time", width=180, anchor="center")
        self.event_tree.column("event", width=900, anchor="w")
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.event_tree.yview)
        self.event_tree.configure(yscrollcommand=scrollbar.set)
        self.event_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _on_data_update(self):
        pass

    def _schedule_refresh(self):
        self._refresh_ui()
        self.root.after(1000, self._schedule_refresh)

    def _refresh_ui(self):
        for key, connected in store.esp_status.items():
            color = COLORS["green"] if connected else COLORS["red"]
            self.esp_dots[key].set_color(color)
        for lvl in [1, 2, 3]:
            data = store.levels[lvl]
            widgets = self.level_widgets.get(lvl, {})
            for key, val in data.items():
                if key in widgets:
                    widgets[key].config(text=str(val))
            if lvl in self.health_widgets:
                self.health_widgets[lvl].refresh()
        self.tank_level_lbl.config(text=f"{store.tank.get('level', '--')}%")
        pump_st = store.tank.get("pump", "--")
        self.pump_status_lbl.config(text=pump_st,
                                     fg=COLORS["green"] if pump_st == "ON" else COLORS["text_secondary"])
        for key, sw in self.power_switches.items():
            sw.set_state(store.controls.get(key, False))
        self.pump_switch.set_state(store.controls.get("pump", False))

        mode = store.control_mode
        if mode == "MANUAL":
            self.mode_indicator.config(text="MODE: MANUAL (App Control)", fg=COLORS["green"])
        else:
            self.mode_indicator.config(text="MODE: AUTO (Cloud)", fg=COLORS["blue"])

        self._refresh_daily_summary()
        self._refresh_health_history()
        self._refresh_event_log()

    def _refresh_daily_summary(self):
        for item in self.daily_tree.get_children():
            self.daily_tree.delete(item)
        rows = self.db.get_daily_summary(limit=30)
        for row in rows:
            day, t1, t2, t3, h1, h2, h3, l1, l2, l3, hr1, hr2, hr3, n1, n2, n3 = row
            hr1_s = "★"*(hr1 or 0) + "☆"*(3-(hr1 or 0)) if hr1 is not None else "—"
            hr2_s = "★"*(hr2 or 0) + "☆"*(3-(hr2 or 0)) if hr2 is not None else "—"
            hr3_s = "★"*(hr3 or 0) + "☆"*(3-(hr3 or 0)) if hr3 is not None else "—"
            self.daily_tree.insert("", "end", values=(
                day, f"{t1 or '--'}", f"{t2 or '--'}", f"{t3 or '--'}",
                f"{h1 or '--'}", f"{h2 or '--'}", f"{h3 or '--'}",
                f"{l1 or '--'}", f"{l2 or '--'}", f"{l3 or '--'}",
                hr1_s, hr2_s, hr3_s,
                n1 or "—", n2 or "—", n3 or "—"
            ))

    def _refresh_health_history(self):
        for item in self.health_tree.get_children():
            self.health_tree.delete(item)
        rows = self.db.get_all_health_ratings(limit=30)
        for row in rows:
            d, l1, l2, l3, n1, n2, n3 = row
            self.health_tree.insert("", "end", values=(
                d, 
                "★"*l1 + "☆"*(3-l1), 
                "★"*l2 + "☆"*(3-l2), 
                "★"*l3 + "☆"*(3-l3),
                n1 or "—", n2 or "—", n3 or "—"
            ))

    def _refresh_event_log(self):
        for item in self.event_tree.get_children():
            self.event_tree.delete(item)
        rows = self.db.get_events(limit=50)
        for row in rows:
            ts, ev = row
            self.event_tree.insert("", "end", values=(ts[:19], ev))

    def _connect_all(self):
        store.add_history("Attempting to connect to all ESP32 devices...")
        for key, cfg in ESP32_CONFIG.items():
            ip = cfg["ip"]
            resp = ESPClient.fetch(f"http://{ip}/status", timeout=2)
            if resp:
                store.esp_status[key] = True
                store.add_history(f"Connected to {key} at {ip}")
            else:
                store.esp_status[key] = False
                store.add_history(f"Failed to connect to {key} at {ip}")
        store.notify()

    def _send_control(self, control_key, state):
        if store.safety_lock:
            store.add_history(f"[BLOCKED] Safety lock active — cannot toggle {control_key}")
            return
        if store.control_mode == "AUTO" and control_key != "pump":
            store.add_history(f"[WARN] In AUTO mode — ThingsSentral may override {control_key}")
        store.controls[control_key] = state
        action = "ON" if state else "OFF"
        store.add_history(f"Command: {control_key} -> {action}")
        cmd_map = {
            "pump": "PUMP",
            "l1_power": "L1_PWR", "l1_white": "L1_WHT", "l1_rb": "L1_RB",
            "l2_power": "L2_PWR", "l2_white": "L2_WHT", "l2_rb": "L2_RB",
            "l3_power": "L3_PWR", "l3_white": "L3_WHT", "l3_rb": "L3_RB",
        }
        esp_cmd = cmd_map.get(control_key, control_key.upper())
        esp_cmd += f"_{action}"
        ip = ESP32_CONFIG["ESP32_1"]["ip"]
        url = f"http://{ip}/command?cmd={esp_cmd}"
        resp = ESPClient.fetch(url, timeout=2)
        if resp:
            store.add_history(f"[OK] ESP32_1 responded: {resp.strip()}")
        else:
            store.add_history(f"[WARN] No response from ESP32_1. Queued: {esp_cmd}")

    def _save_timer(self, level, on_time, off_time, active):
        store.timers[level] = {"on": on_time, "off": off_time, "active": active}
        status = "Activated" if active else "Deactivated"
        store.add_history(f"Timer L{level} saved: ON {on_time}, OFF {off_time} ({status})")
        ip = ESP32_CONFIG["ESP32_1"]["ip"]
        data = {
            "level": str(level),
            "on": on_time,
            "off": off_time,
            "active": "1" if active else "0"
        }
        resp = ESPClient.post(f"http://{ip}/timer", data=data, timeout=3, form_encoded=True)
        if resp:
            store.add_history("[OK] Timer config sent to ESP32_1")
        else:
            store.add_history("[WARN] Timer config could not reach ESP32_1")

    def _reset_safety(self):
        store.safety_lock = False
        store.add_history("SAFETY LOCK RESET — All controls enabled")

    def on_close(self):
        self.poll_thread.stop()
        self.root.destroy()

if __name__ == "__main__":
    db = Database(DB_PATH)
    store = DataStore(db)
    root = tk.Tk()
    app = VerticalFarmingApp(root, db)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
