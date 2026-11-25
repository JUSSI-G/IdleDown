import argparse
import logging
import tkinter as tk
from tkinter import ttk

from calibration import suggest_limits
from settings import (DEFAULT_VALUES, VALIDATORS, build_settings, readings_to_average,
                      save_values, settings_file_path)

FIELDS = [
    ("idle_minutes", "Idle time before countdown", "minutes"),
    ("countdown", "Countdown", "seconds"),
    ("interval", "Check every", "seconds"),
    ("average_seconds", "Average readings over", "seconds"),
    ("cpu_limit", "CPU limit", "%"),
    ("gpu_limit", "GPU limit", "%"),
    ("net_limit_kb", "Network limit", "KB/s"),
    ("disk_limit_mb", "Disk limit", "MB/s"),
]

GOOD_COLOR = "#2e7d32"
ERROR_COLOR = "red"


class SettingsWindow:
    def __init__(self, main_window):
        self.main = main_window
        self.window = tk.Toplevel(main_window.root)
        self.window.title("IdleDown settings")
        self.window.resizable(False, False)
        self.window.transient(main_window.root)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.entries = {}
        self.build_widgets()
        self.fill(main_window.settings.saved_values())

    def build_widgets(self):
        frame = ttk.Frame(self.window, padding=16)
        frame.grid()

        for row, (name, label, unit) in enumerate(FIELDS):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=2)
            entry = ttk.Entry(frame, width=10, justify="right")
            entry.grid(row=row, column=1, pady=2)
            ttk.Label(frame, text=unit, foreground="gray").grid(row=row, column=2, sticky="w", padx=(6, 0))
            self.entries[name] = entry

        helper_buttons = ttk.Frame(frame)
        helper_buttons.grid(row=len(FIELDS), column=0, columnspan=3, pady=(14, 0))
        self.measure_button = ttk.Button(helper_buttons, text="Measure my idle PC", command=self.start_measuring)
        self.measure_button.grid(row=0, column=0, padx=4)
        ttk.Button(helper_buttons, text="Reset to defaults", command=self.reset_to_defaults).grid(row=0, column=1, padx=4)

        self.message_label = ttk.Label(frame, text="", wraplength=330, justify="left")
        self.message_label.grid(row=len(FIELDS) + 1, column=0, columnspan=3, pady=(10, 0), sticky="w")

        main_buttons = ttk.Frame(frame)
        main_buttons.grid(row=len(FIELDS) + 2, column=0, columnspan=3, pady=(14, 0), sticky="e")
        ttk.Button(main_buttons, text="Save", command=self.save).grid(row=0, column=0, padx=4)
        ttk.Button(main_buttons, text="Cancel", command=self.close).grid(row=0, column=1, padx=4)

    def fill(self, values):
        for name, value in values.items():
            entry = self.entries[name]
            entry.delete(0, "end")
            entry.insert(0, f"{value:g}")

    def show_message(self, text, color=""):
        self.message_label.config(text=text, foreground=color)

    def read_entries(self):
        values = {}
        problems = []
        for name, label, unit in FIELDS:
            text = self.entries[name].get().strip()
            try:
                values[name] = VALIDATORS[name](text)
            except (ValueError, argparse.ArgumentTypeError):
                kind = "a whole number" if name == "countdown" else "a number"
                problems.append(f"{label} must be {kind} greater than 0.")
        return values, problems

    def save(self):
        values, problems = self.read_entries()
        if problems:
            self.show_message("\n".join(problems), ERROR_COLOR)
            return
        if self.main.counting_down:
            self.show_message("Cancel the shutdown countdown before saving.", ERROR_COLOR)
            return

        path = settings_file_path()
        save_values(values, path)
        current = self.main.settings
        new_settings = build_settings(values, current.dry_run, current.console, current.log_file)
        self.main.apply_settings(new_settings)
        logging.info(f"Settings saved to {path}")
        self.close()

    def reset_to_defaults(self):
        self.fill(DEFAULT_VALUES)
        self.show_message("Defaults filled in. Press Save to use them.")

    def start_measuring(self):
        self.main.start_measurement()
        self.measure_button.state(["disabled"])
        self.update_measuring()

    def update_measuring(self):
        measurement = self.main.measurement
        if measurement is None:
            return
        if not measurement.is_done():
            minutes, seconds = divmod(int(measurement.seconds_left()), 60)
            self.show_message(f"Measuring for {minutes}:{seconds:02d} more. Leave the PC alone, "
                              f"and close programs that normally aren't running when you leave it. "
                              f"Shutdown is paused while measuring.")
            self.window.after(1000, self.update_measuring)
            return

        self.main.stop_measurement()
        self.measure_button.state(["!disabled"])
        suggestion = suggest_limits(measurement.readings, readings_to_average(self.main.settings))
        logging.info(f"Idle measurement finished: suggested {suggestion.values}, not quiet: {suggestion.not_quiet}")

        if suggestion.not_quiet:
            self.show_message("Your PC wasn't quiet enough to measure: " + ", ".join(suggestion.not_quiet)
                              + ". Close running programs and measure again.", ERROR_COLOR)
            return
        self.fill(suggestion.values)
        self.show_message("Suggested limits filled in from your PC's quiet levels. "
                          "Press Save to use them.", GOOD_COLOR)

    def close(self):
        if self.main.measurement is not None:
            self.main.stop_measurement()
            logging.info("Idle measurement cancelled.")
        self.main.settings_window = None
        self.window.destroy()

