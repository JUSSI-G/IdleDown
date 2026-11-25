import logging
import subprocess
import time
from collections import deque
from dataclasses import dataclass

import psutil

import platform_utils


@dataclass
class Limits:
    cpu_percent: float
    gpu_percent: float
    network_bytes_per_second: float
    disk_bytes_per_second: float


@dataclass
class Usage:
    cpu_percent: float
    gpu_percent: float | None
    network_bytes_per_second: float
    disk_bytes_per_second: float

    def over_limits(self, limits):
        busy_signals = []
        if self.cpu_percent >= limits.cpu_percent:
            busy_signals.append("CPU")
        if self.gpu_percent is not None and self.gpu_percent >= limits.gpu_percent:
            busy_signals.append("GPU")
        if self.network_bytes_per_second >= limits.network_bytes_per_second:
            busy_signals.append("Network")
        if self.disk_bytes_per_second >= limits.disk_bytes_per_second:
            busy_signals.append("Disk")
        return busy_signals

    def is_below(self, limits):
        return not self.over_limits(limits)

    def cpu_text(self):
        return f"{self.cpu_percent:.1f} %"

    def gpu_text(self):
        return "n/a" if self.gpu_percent is None else f"{self.gpu_percent:.0f} %"

    def network_text(self):
        return f"{self.network_bytes_per_second / 1_000:.1f} KB/s"

    def disk_text(self):
        return f"{self.disk_bytes_per_second / 1_000_000:.2f} MB/s"


def read_byte_totals():
    network = psutil.net_io_counters()
    disk = psutil.disk_io_counters()
    network_total = network.bytes_sent + network.bytes_recv
    disk_total = disk.read_bytes + disk.write_bytes if disk else 0
    return network_total, disk_total


class UsageReader:
    def __init__(self):
        self.gpus = platform_utils.find_nvidia_gpus()
        logging.info(f"NVIDIA GPUs found: {len(self.gpus)}")
        psutil.cpu_percent(interval=None)
        self.previous_totals = read_byte_totals()
        self.previous_time = time.monotonic()

    def read(self):
        cpu_percent = psutil.cpu_percent(interval=None)
        gpu_percent = platform_utils.get_gpu_usage(self.gpus)

        network_total, disk_total = read_byte_totals()
        previous_network_total, previous_disk_total = self.previous_totals
        current_time = time.monotonic()
        elapsed_seconds = current_time - self.previous_time

        network_speed = (network_total - previous_network_total) / elapsed_seconds
        disk_speed = (disk_total - previous_disk_total) / elapsed_seconds

        self.previous_totals = (network_total, disk_total)
        self.previous_time = current_time
        return Usage(cpu_percent, gpu_percent, network_speed, disk_speed)


class UsageAverage:
    def __init__(self, reading_count):
        self.recent_readings = deque(maxlen=max(1, reading_count))

    def add(self, usage):
        self.recent_readings.append(usage)
        return self.average()

    def average(self):
        readings = self.recent_readings
        gpu_values = [usage.gpu_percent for usage in readings if usage.gpu_percent is not None]
        return Usage(
            cpu_percent=sum(usage.cpu_percent for usage in readings) / len(readings),
            gpu_percent=sum(gpu_values) / len(gpu_values) if gpu_values else None,
            network_bytes_per_second=sum(usage.network_bytes_per_second for usage in readings) / len(readings),
            disk_bytes_per_second=sum(usage.disk_bytes_per_second for usage in readings) / len(readings),
        )


class IdleTimer:
    def __init__(self, required_seconds):
        self.required_seconds = required_seconds
        self.idle_since = None

    def update(self, is_idle):
        if not is_idle:
            self.idle_since = None
        elif self.idle_since is None:
            self.idle_since = time.monotonic()

    def idle_seconds(self):
        if self.idle_since is None:
            return 0
        return time.monotonic() - self.idle_since

    def is_finished(self):
        return self.idle_seconds() >= self.required_seconds

    def reset(self):
        self.idle_since = None


def status_line(usage, timer, limits):
    line = (f"CPU {usage.cpu_text():>8}  GPU {usage.gpu_text():>5}  "
            f"NET {usage.network_text():>12}  DISK {usage.disk_text():>11}  "
            f"idle {timer.idle_seconds():4.0f}/{timer.required_seconds:.0f} s")
    busy_signals = usage.over_limits(limits)
    if busy_signals:
        line += f"  busy: {', '.join(busy_signals)}"
    return line


def shut_down(dry_run):
    command = " ".join(platform_utils.get_shutdown_command())
    if dry_run:
        logging.info(f"Dry run, would run: {command}")
        return True
    logging.info(f"Shutting down now: {command}")
    try:
        platform_utils.shutdown_computer()
    except (OSError, subprocess.CalledProcessError) as error:
        logging.error(f"Shutdown failed: {error}")
        return False
    return True
