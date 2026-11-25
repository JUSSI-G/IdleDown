import argparse
import logging
import tkinter as tk
from tkinter import ttk

from calibration import CLOSE, RELIABLE, SOMETIMES, check_job, suggest_limits
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
WARNING_COLOR = "#b35c00"
ERROR_COLOR = "red"

IDLE = "idle"
JOB = "job"


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
        self.measure_button = ttk.Button(helper_buttons, text="Measure my idle PC",
                                         command=lambda: self.start_measuring(IDLE))
        self.measure_button.grid(row=0, column=0, padx=4)
        self.job_button = ttk.Button(helper_buttons, text="Check my running job",
                                     command=lambda: self.start_measuring(JOB))
        self.job_button.grid(row=0, column=1, padx=4)
        ttk.Button(helper_buttons, text="Reset to defaults", command=self.reset_to_defaults).grid(
            row=1, column=0, columnspan=2, pady=(6, 0))

        self.message_label = ttk.Label(frame, text="", wraplength=360, justify="left")
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

    def start_measuring(self, kind):
        self.main.start_measurement()
        self.measure_button.state(["disabled"])
        self.job_button.state(["disabled"])
        self.update_measuring(kind)

    def update_measuring(self, kind):
        measurement = self.main.measurement
        if measurement is None:
            return
        if not measurement.is_done():
            minutes, seconds = divmod(int(measurement.seconds_left()), 60)
            if kind == IDLE:
                advice = ("Leave the PC alone, and close programs that normally aren't running "
                          "when you leave it.")
            else:
                advice = "Keep your job running as it normally does, and leave the PC alone otherwise."
            self.show_message(f"Measuring for {minutes}:{seconds:02d} more. {advice} "
                              f"Shutdown is paused while measuring.")
            self.window.after(1000, lambda: self.update_measuring(kind))
            return

        self.main.stop_measurement()
        self.measure_button.state(["!disabled"])
        self.job_button.state(["!disabled"])
        if kind == IDLE:
            self.finish_idle_measurement(measurement)
        else:
            self.finish_job_check(measurement)

    def finish_idle_measurement(self, measurement):
        suggestion = suggest_limits(measurement.readings, readings_to_average(self.main.settings))
        logging.info(f"Idle measurement finished: suggested {suggestion.values}, not quiet: {suggestion.not_quiet}")

        if suggestion.not_quiet:
            self.show_message("Your PC wasn't quiet enough to measure: " + ", ".join(suggestion.not_quiet)
                              + ". Close running programs and measure again.", ERROR_COLOR)
            return
        self.fill(suggestion.values)
        self.show_message("Suggested limits filled in from your PC's quiet levels. "
                          "Press Save to use them.", GOOD_COLOR)

    def finish_job_check(self, measurement):
        current_values = self.main.settings.saved_values()
        result = check_job(measurement.readings, readings_to_average(self.main.settings), current_values)
        logging.info(f"Job check finished: {result.verdict()}, "
                     + ", ".join(f"{s.rule.label} {s.verdict} {s.rule.format(s.lowest)}-{s.rule.format(s.highest)}"
                                 for s in result.signals))

        idle_minutes = f"{current_values['idle_minutes']:g}"
        headlines = {
            RELIABLE: ("IdleDown sees this job as busy.", GOOD_COLOR),
            CLOSE: ("This job is only just above the limits, so a dip could look like idle. "
                    "Measure your idle PC, then try lower limits.", WARNING_COLOR),
            SOMETIMES: (f"This job is sometimes below the limits. If it stays below them for "
                        f"{idle_minutes} minutes, the countdown starts while the job is still running.",
                        WARNING_COLOR),
        }
        headline, color = headlines.get(result.verdict(), (
            "IdleDown doesn't see this job as busy, so it could shut down while the job runs. "
            "Don't rely on IdleDown for this job.", ERROR_COLOR))

        lines = [headline, ""]
        for signal in result.signals:
            lines.append(describe_signal(signal))
        self.show_message("\n".join(lines), color)

    def close(self):
        if self.main.measurement is not None:
            self.main.stop_measurement()
            logging.info("Measurement cancelled.")
        self.main.settings_window = None
        self.window.destroy()



def describe_signal(signal):
    rule = signal.rule
    lowest, highest = rule.format(signal.lowest), rule.format(signal.highest)
    job_range = f"{lowest} {rule.unit}" if lowest == highest else f"{lowest}–{highest} {rule.unit}"
    limit = f"{signal.limit:g} {rule.unit}"
    if signal.verdict == RELIABLE:
        return f"✓ {rule.label}: job at {job_range}, well above the {limit} limit."
    if signal.verdict == CLOSE:
        return f"! {rule.label}: job at {job_range}, only just above the {limit} limit."
    if signal.verdict == SOMETIMES:
        return f"! {rule.label}: job at {job_range}, sometimes below the {limit} limit."
    return f"– {rule.label}: not used by this job ({job_range})."
