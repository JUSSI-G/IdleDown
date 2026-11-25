import logging
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk

from calibration import IdleMeasurement
from monitor import IdleTimer, UsageAverage, UsageReader, shut_down, status_line
from settings import readings_to_average
from settings_window import SettingsWindow
from version import VERSION

BUSY_COLOR = "#b35c00"
ERROR_COLOR = "red"
SIGNALS = ["CPU", "GPU", "Network", "Disk"]


class IdleDownWindow:
    def __init__(self, settings):
        self.settings = settings
        self.reader = UsageReader()
        self.average = UsageAverage(readings_to_average(settings))
        self.timer = IdleTimer(settings.required_idle_seconds)
        self.seconds_left = 0
        self.counting_down = False
        self.pending_job = None
        self.measurement = None
        self.settings_window = None

        self.root = tk.Tk()
        title = f"IdleDown {VERSION}"
        self.root.title(f"{title} (dry run)" if settings.dry_run else title)
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.report_callback_exception = log_unexpected_error
        self.set_window_icon()
        self.build_widgets()

    def set_window_icon(self):
        try:
            self.icon_image = tk.PhotoImage(file=asset_path("IdleDown.png"))
            self.root.iconphoto(True, self.icon_image)
        except tk.TclError:
            logging.warning("Window icon not found, using the default one.")

    def build_widgets(self):
        frame = ttk.Frame(self.root, padding=16)
        frame.grid()

        self.value_labels = {}
        self.limit_labels = {}
        for row, name in enumerate(SIGNALS):
            ttk.Label(frame, text=name).grid(row=row, column=0, sticky="w", padx=(0, 16))
            value_label = ttk.Label(frame, text="...", width=12, anchor="e")
            value_label.grid(row=row, column=1, sticky="e")
            limit_label = ttk.Label(frame, text="", foreground="gray")
            limit_label.grid(row=row, column=2, sticky="w", padx=(16, 0))
            self.value_labels[name] = value_label
            self.limit_labels[name] = limit_label

        self.idle_bar = ttk.Progressbar(frame, length=320)
        self.idle_bar.grid(row=4, column=0, columnspan=3, pady=(16, 4))
        self.idle_label = ttk.Label(frame, text="")
        self.idle_label.grid(row=5, column=0, columnspan=3)

        self.status_label = ttk.Label(frame, text="Watching...", font=("Segoe UI", 12, "bold"),
                                      width=40, anchor="center")
        self.status_label.grid(row=6, column=0, columnspan=3, pady=(12, 0))
        self.notice_label = ttk.Label(frame, text="", foreground="gray")
        self.notice_label.grid(row=7, column=0, columnspan=3, pady=(2, 8))

        buttons = ttk.Frame(frame)
        buttons.grid(row=8, column=0, columnspan=3)
        self.cancel_button = ttk.Button(buttons, text="Cancel shutdown", command=self.cancel_countdown)
        self.cancel_button.grid(row=0, column=0, padx=4)
        self.cancel_button.state(["disabled"])
        ttk.Button(buttons, text="Settings", command=self.open_settings).grid(row=0, column=1, padx=4)

        self.average_label = ttk.Label(frame, text="", foreground="gray")
        self.average_label.grid(row=9, column=0, columnspan=3, pady=(12, 0))
        ttk.Label(frame, text=f"Log: {self.settings.log_file}", foreground="gray").grid(
            row=10, column=0, columnspan=3)

        self.show_settings()

    def show_settings(self):
        limits = self.settings.limits
        self.limit_labels["CPU"].config(text=f"under {limits.cpu_percent:g} %")
        self.limit_labels["GPU"].config(text=f"under {limits.gpu_percent:g} %")
        self.limit_labels["Network"].config(text=f"under {limits.network_bytes_per_second / 1_000:g} KB/s")
        self.limit_labels["Disk"].config(text=f"under {limits.disk_bytes_per_second / 1_000_000:g} MB/s")
        self.idle_bar.config(maximum=self.settings.required_idle_seconds)
        self.average_label.config(text=f"Readings are averaged over {self.settings.average_seconds:g} s")

    def apply_settings(self, new_settings):
        self.settings = new_settings
        self.average = UsageAverage(readings_to_average(new_settings))
        self.timer = IdleTimer(new_settings.required_idle_seconds)
        self.show_settings()
        self.notice_label.config(text="Settings saved. Idle time starts over.", foreground="gray")
        logging.info(f"Settings changed: {new_settings.saved_values()}")

    def open_settings(self):
        if self.settings_window is not None:
            self.settings_window.window.lift()
            return
        self.settings_window = SettingsWindow(self)

    def start_measurement(self):
        self.measurement = IdleMeasurement()
        logging.info("Measurement started.")

    def stop_measurement(self):
        self.measurement = None

    def run(self):
        self.schedule(self.settings.check_interval_seconds, self.check_usage)
        self.root.mainloop()

    def schedule(self, seconds, callback):
        self.pending_job = self.root.after(int(seconds * 1000), callback)

    def check_usage(self):
        reading = self.reader.read()
        if self.measurement is not None:
            self.measurement.add(reading)
        usage = self.average.add(reading)

        if self.measurement is not None:
            self.timer.reset()
        else:
            self.timer.update(usage.is_below(self.settings.limits))
        logging.info(status_line(usage, self.timer, self.settings.limits))
        self.show_usage(usage)

        if self.timer.is_finished():
            self.start_countdown()
        else:
            self.schedule(self.settings.check_interval_seconds, self.check_usage)

    def show_usage(self, usage):
        texts = {"CPU": usage.cpu_text(), "GPU": usage.gpu_text(),
                 "Network": usage.network_text(), "Disk": usage.disk_text()}
        busy_signals = usage.over_limits(self.settings.limits)
        for name in SIGNALS:
            color = BUSY_COLOR if name in busy_signals else ""
            self.value_labels[name].config(text=texts[name], foreground=color)

        required = self.settings.required_idle_seconds
        idle_seconds = min(self.timer.idle_seconds(), required)
        self.idle_bar.config(value=idle_seconds)
        self.idle_label.config(text=f"Idle for {format_duration(idle_seconds)} of {format_duration(required)}")

        if self.measurement is not None:
            self.status_label.config(text="Measuring... shutdown is paused", foreground="")
        elif busy_signals:
            self.status_label.config(text=busy_text(busy_signals), foreground=BUSY_COLOR)
        else:
            remaining = format_duration(required - idle_seconds)
            self.status_label.config(text=f"Quiet. Countdown starts in {remaining}", foreground="")

    def start_countdown(self):
        logging.info(f"Idle limit reached, countdown of {self.settings.countdown_seconds} s started.")
        self.counting_down = True
        self.seconds_left = self.settings.countdown_seconds
        self.cancel_button.state(["!disabled"])
        self.bring_to_front()
        self.tick_countdown()

    def tick_countdown(self):
        if self.seconds_left > 0:
            self.status_label.config(text=f"Shutting down in {self.seconds_left} s", foreground=ERROR_COLOR)
            self.seconds_left -= 1
            self.schedule(1, self.tick_countdown)
            return

        succeeded = shut_down(self.settings.dry_run)
        if not succeeded:
            self.back_to_watching(f"Shutdown failed at {clock_time()}, see the log.", is_error=True)
        elif self.settings.dry_run:
            self.back_to_watching(f"Dry run: would have shut down at {clock_time()}.")
        else:
            self.root.destroy()

    def cancel_countdown(self):
        self.root.after_cancel(self.pending_job)
        logging.info("Shutdown cancelled by user.")
        self.back_to_watching(f"Shutdown cancelled at {clock_time()}.")

    def back_to_watching(self, notice, is_error=False):
        self.counting_down = False
        self.timer.reset()
        self.cancel_button.state(["disabled"])
        self.root.attributes("-topmost", False)
        self.status_label.config(text="Watching...", foreground="")
        self.notice_label.config(text=notice, foreground=ERROR_COLOR if is_error else "gray")
        self.schedule(self.settings.check_interval_seconds, self.check_usage)

    def bring_to_front(self):
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.bell()

    def close(self):
        logging.info("Stopped by user.")
        self.root.destroy()


def busy_text(busy_signals):
    if len(busy_signals) == 1:
        return f"Busy: {busy_signals[0]} is over its limit"
    return f"Busy: {', '.join(busy_signals[:-1])} and {busy_signals[-1]} are over their limits"


def clock_time():
    return datetime.now().strftime("%H:%M")


def asset_path(file_name):
    app_folder = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return app_folder / "assets" / file_name


def log_unexpected_error(error_type, error, traceback):
    logging.error("Unexpected error", exc_info=(error_type, error, traceback))


def format_duration(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes}:{seconds:02d}"


def run_window(settings):
    IdleDownWindow(settings).run()
