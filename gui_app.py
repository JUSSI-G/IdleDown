import logging
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from monitor import IdleTimer, UsageReader, shut_down, status_line
from version import VERSION


class IdleDownWindow:
    def __init__(self, settings):
        self.settings = settings
        self.reader = UsageReader()
        self.timer = IdleTimer(settings.required_idle_seconds)
        self.seconds_left = 0
        self.pending_job = None

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

        limits = self.settings.limits
        rows = [
            ("CPU", f"under {limits.cpu_percent:g} %"),
            ("GPU", f"under {limits.gpu_percent:g} %"),
            ("Network", f"under {limits.network_bytes_per_second / 1_000:g} KB/s"),
            ("Disk", f"under {limits.disk_bytes_per_second / 1_000_000:g} MB/s"),
        ]
        self.value_labels = {}
        for row, (name, limit_text) in enumerate(rows):
            ttk.Label(frame, text=name).grid(row=row, column=0, sticky="w", padx=(0, 16))
            value_label = ttk.Label(frame, text="...", width=12, anchor="e")
            value_label.grid(row=row, column=1, sticky="e")
            ttk.Label(frame, text=limit_text, foreground="gray").grid(row=row, column=2, sticky="w", padx=(16, 0))
            self.value_labels[name] = value_label

        self.idle_bar = ttk.Progressbar(frame, length=320, maximum=self.settings.required_idle_seconds)
        self.idle_bar.grid(row=4, column=0, columnspan=3, pady=(16, 4))
        self.idle_label = ttk.Label(frame, text="")
        self.idle_label.grid(row=5, column=0, columnspan=3)

        self.status_label = ttk.Label(frame, text="Watching...", font=("Segoe UI", 12, "bold"),
                                      width=40, anchor="center")
        self.status_label.grid(row=6, column=0, columnspan=3, pady=(12, 8))

        self.cancel_button = ttk.Button(frame, text="Cancel shutdown", command=self.cancel_countdown)
        self.cancel_button.grid(row=7, column=0, columnspan=3)
        self.cancel_button.state(["disabled"])

        ttk.Label(frame, text=f"Log: {self.settings.log_file}", foreground="gray").grid(
            row=8, column=0, columnspan=3, pady=(12, 0))

    def run(self):
        self.schedule(self.settings.check_interval_seconds, self.check_usage)
        self.root.mainloop()

    def schedule(self, seconds, callback):
        self.pending_job = self.root.after(int(seconds * 1000), callback)

    def check_usage(self):
        usage = self.reader.read()
        self.timer.update(usage.is_below(self.settings.limits))
        logging.info(status_line(usage, self.timer))
        self.show_usage(usage)

        if self.timer.is_finished():
            self.start_countdown()
        else:
            self.schedule(self.settings.check_interval_seconds, self.check_usage)

    def show_usage(self, usage):
        self.value_labels["CPU"].config(text=usage.cpu_text())
        self.value_labels["GPU"].config(text=usage.gpu_text())
        self.value_labels["Network"].config(text=usage.network_text())
        self.value_labels["Disk"].config(text=usage.disk_text())

        idle_seconds = min(self.timer.idle_seconds(), self.settings.required_idle_seconds)
        self.idle_bar.config(value=idle_seconds)
        self.idle_label.config(
            text=f"Idle for {format_duration(idle_seconds)} of {format_duration(self.settings.required_idle_seconds)}"
        )

    def start_countdown(self):
        logging.info(f"Idle limit reached, countdown of {self.settings.countdown_seconds} s started.")
        self.seconds_left = self.settings.countdown_seconds
        self.cancel_button.state(["!disabled"])
        self.bring_to_front()
        self.tick_countdown()

    def tick_countdown(self):
        if self.seconds_left > 0:
            self.status_label.config(text=f"Shutting down in {self.seconds_left} s", foreground="red")
            self.seconds_left -= 1
            self.schedule(1, self.tick_countdown)
            return

        succeeded = shut_down(self.settings.dry_run)
        if not succeeded:
            self.back_to_watching("Shutdown failed, see the log. Watching...", is_error=True)
        elif self.settings.dry_run:
            self.back_to_watching("Dry run: would have shut down now. Watching...")
        else:
            self.root.destroy()

    def cancel_countdown(self):
        self.root.after_cancel(self.pending_job)
        logging.info("Shutdown cancelled by user.")
        self.back_to_watching("Shutdown cancelled. Watching...")

    def back_to_watching(self, message, is_error=False):
        self.timer.reset()
        self.cancel_button.state(["disabled"])
        self.root.attributes("-topmost", False)
        self.status_label.config(text=message, foreground="red" if is_error else "")
        self.schedule(self.settings.check_interval_seconds, self.check_usage)

    def bring_to_front(self):
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.bell()

    def close(self):
        logging.info("Stopped by user.")
        self.root.destroy()


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
