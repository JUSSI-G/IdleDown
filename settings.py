import argparse
from dataclasses import dataclass
from pathlib import Path

import platform_utils
from monitor import Limits
from version import VERSION


@dataclass
class Settings:
    limits: Limits
    required_idle_seconds: float
    countdown_seconds: int
    check_interval_seconds: float
    dry_run: bool
    console: bool
    log_file: Path


def build_parser():
    parser = argparse.ArgumentParser(
        prog="IdleDown",
        description="Shuts down the computer after it has been continuously idle for a while.",
    )
    parser.add_argument("--idle-minutes", type=float, default=10,
                        help="minutes of continuous quiet before the countdown (default: 10)")
    parser.add_argument("--countdown", type=int, default=60,
                        help="seconds you get to cancel before shutdown (default: 60)")
    parser.add_argument("--interval", type=float, default=5,
                        help="seconds between checks (default: 5)")
    parser.add_argument("--cpu-limit", type=float, default=10,
                        help="CPU %% that counts as idle (default: 10)")
    parser.add_argument("--gpu-limit", type=float, default=10,
                        help="GPU %% that counts as idle (default: 10)")
    parser.add_argument("--net-limit-kb", type=float, default=100,
                        help="network KB/s that counts as idle (default: 100)")
    parser.add_argument("--disk-limit-mb", type=float, default=2,
                        help="disk MB/s that counts as idle (default: 2)")
    parser.add_argument("--dry-run", action="store_true",
                        help="only log what would happen, never shut down")
    parser.add_argument("--console", action="store_true",
                        help="run in the terminal instead of a window")
    parser.add_argument("--log-file", type=Path,
                        default=platform_utils.get_app_data_folder() / "idledown.log",
                        help="where to write the log (default: %(default)s)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def parse_settings(arguments=None):
    args = build_parser().parse_args(arguments)
    limits = Limits(
        cpu_percent=args.cpu_limit,
        gpu_percent=args.gpu_limit,
        network_bytes_per_second=args.net_limit_kb * 1_000,
        disk_bytes_per_second=args.disk_limit_mb * 1_000_000,
    )
    return Settings(
        limits=limits,
        required_idle_seconds=args.idle_minutes * 60,
        countdown_seconds=args.countdown,
        check_interval_seconds=args.interval,
        dry_run=args.dry_run,
        console=args.console,
        log_file=args.log_file,
    )
