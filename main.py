import logging
import subprocess
import time
from pathlib import Path

import psutil

import platform_utils

CPU_LIMIT_PERCENT = 10.0
GPU_LIMIT_PERCENT = 10.0
NETWORK_LIMIT_BYTES_PER_SECOND = 100_000
DISK_LIMIT_BYTES_PER_SECOND = 2_000_000

CHECK_INTERVAL_SECONDS = 5
REQUIRED_IDLE_SECONDS = 10 * 60
COUNTDOWN_SECONDS = 60
DRY_RUN = False

LOG_FILE = Path(__file__).with_name("idledown.log")


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def read_byte_totals():
    network = psutil.net_io_counters()
    disk = psutil.disk_io_counters()
    network_total = network.bytes_sent + network.bytes_recv
    disk_total = disk.read_bytes + disk.write_bytes if disk else 0
    return network_total, disk_total


def read_usage(gpus, previous_totals, previous_time):
    cpu_percent = psutil.cpu_percent(interval=1)
    gpu_percent = platform_utils.get_gpu_usage(gpus)

    network_total, disk_total = read_byte_totals()
    previous_network_total, previous_disk_total = previous_totals
    current_time = time.monotonic()
    elapsed_seconds = current_time - previous_time

    network_speed = (network_total - previous_network_total) / elapsed_seconds
    disk_speed = (disk_total - previous_disk_total) / elapsed_seconds

    usage = (cpu_percent, gpu_percent, network_speed, disk_speed)
    return usage, (network_total, disk_total), current_time


def is_idle(usage):
    cpu_percent, gpu_percent, network_speed, disk_speed = usage
    return (cpu_percent < CPU_LIMIT_PERCENT
            and (gpu_percent is None or gpu_percent < GPU_LIMIT_PERCENT)
            and network_speed < NETWORK_LIMIT_BYTES_PER_SECOND
            and disk_speed < DISK_LIMIT_BYTES_PER_SECOND)


def format_status(usage, idle_seconds):
    cpu_percent, gpu_percent, network_speed, disk_speed = usage
    gpu_text = "n/a" if gpu_percent is None else f"{gpu_percent}%"
    return (f"CPU {cpu_percent:5.1f}%  GPU {gpu_text:>4}  "
            f"NET {network_speed / 1_000:8.1f} KB/s  "
            f"DISK {disk_speed / 1_000_000:6.2f} MB/s  "
            f"idle {idle_seconds:4.0f}/{REQUIRED_IDLE_SECONDS} s")


def run_countdown():
    logging.info(f"Idle limit reached, countdown of {COUNTDOWN_SECONDS} s started. Press Ctrl+C to cancel.")
    try:
        for remaining in range(COUNTDOWN_SECONDS, 0, -1):
            print(f"Shutting down in {remaining:3} s", end="\r")
            time.sleep(1)
    except KeyboardInterrupt:
        print()
        logging.info("Shutdown cancelled by user.")
        return False
    print()
    return True


def shut_down():
    command = " ".join(platform_utils.get_shutdown_command())
    if DRY_RUN:
        logging.info(f"Dry run, would run: {command}")
        return
    logging.info(f"Shutting down now: {command}")
    try:
        platform_utils.shutdown_computer()
    except (OSError, subprocess.CalledProcessError) as error:
        logging.error(f"Shutdown failed: {error}")


def main():
    gpus = platform_utils.find_nvidia_gpus()
    logging.info(f"Started. NVIDIA GPUs found: {len(gpus)}. Dry run: {DRY_RUN}. "
                 f"Required idle time: {REQUIRED_IDLE_SECONDS} s.")

    previous_totals = read_byte_totals()
    previous_time = time.monotonic()
    idle_start_time = None

    while True:
        time.sleep(CHECK_INTERVAL_SECONDS)
        usage, previous_totals, previous_time = read_usage(gpus, previous_totals, previous_time)

        if is_idle(usage):
            if idle_start_time is None:
                idle_start_time = time.monotonic()
            idle_seconds = time.monotonic() - idle_start_time
        else:
            idle_start_time = None
            idle_seconds = 0

        logging.info(format_status(usage, idle_seconds))

        if idle_seconds >= REQUIRED_IDLE_SECONDS:
            if run_countdown():
                shut_down()
                return
            idle_start_time = None


if __name__ == "__main__":
    setup_logging()
    try:
        main()
    except KeyboardInterrupt:
        print()
        logging.info("Stopped by user.")