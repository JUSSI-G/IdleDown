import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import platform_utils
from monitor import Limits
from version import VERSION

DEFAULT_VALUES = {
    "idle_minutes": 10,
    "countdown": 60,
    "interval": 5,
    "average_seconds": 60,
    "cpu_limit": 10,
    "gpu_limit": 10,
    "net_limit_kb": 100,
    "disk_limit_mb": 2,
}


@dataclass
class Settings:
    limits: Limits
    required_idle_seconds: float
    countdown_seconds: int
    check_interval_seconds: float
    average_seconds: float
    dry_run: bool
    console: bool
    log_file: Path

    def saved_values(self):
        return {
            "idle_minutes": self.required_idle_seconds / 60,
            "countdown": self.countdown_seconds,
            "interval": self.check_interval_seconds,
            "average_seconds": self.average_seconds,
            "cpu_limit": self.limits.cpu_percent,
            "gpu_limit": self.limits.gpu_percent,
            "net_limit_kb": self.limits.network_bytes_per_second / 1_000,
            "disk_limit_mb": self.limits.disk_bytes_per_second / 1_000_000,
        }


def positive_number(text):
    value = float(text)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError(f"must be a number greater than 0, got {text}")
    return value


def positive_whole_number(text):
    value = int(text)
    if value <= 0:
        raise argparse.ArgumentTypeError(f"must be a whole number greater than 0, got {text}")
    return value


VALIDATORS = {name: positive_number for name in DEFAULT_VALUES}
VALIDATORS["countdown"] = positive_whole_number


def settings_file_path():
    return platform_utils.get_app_data_folder() / "settings.json"


def validate_values(raw_values):
    values = {}
    problems = []
    for name, raw_value in raw_values.items():
        if name not in VALIDATORS:
            problems.append(f"unknown setting '{name}' ignored")
            continue
        try:
            values[name] = VALIDATORS[name](str(raw_value))
        except (ValueError, argparse.ArgumentTypeError):
            problems.append(f"'{name}' has an invalid value '{raw_value}', using the default")
    return values, problems


def load_saved_values(path):
    if not path.exists():
        return {}, []
    try:
        raw_values = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {}, [f"could not read {path}: {error}"]
    if not isinstance(raw_values, dict):
        return {}, [f"{path} does not contain settings"]
    return validate_values(raw_values)


def save_values(values, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values, indent=2), encoding="utf-8")


def build_parser(saved_values):
    defaults = {**DEFAULT_VALUES, **saved_values}
    parser = argparse.ArgumentParser(
        prog="IdleDown",
        description="Shuts down the computer after it has been continuously idle for a while. "
                    "Options given here override the saved settings for this run.",
    )
    parser.add_argument("--idle-minutes", type=positive_number, default=defaults["idle_minutes"],
                        help="minutes of continuous quiet before the countdown (now: %(default)s)")
    parser.add_argument("--countdown", type=positive_whole_number, default=defaults["countdown"],
                        help="seconds you get to cancel before shutdown (now: %(default)s)")
    parser.add_argument("--interval", type=positive_number, default=defaults["interval"],
                        help="seconds between checks (now: %(default)s)")
    parser.add_argument("--average-seconds", type=positive_number, default=defaults["average_seconds"],
                        help="readings are averaged over this many seconds before comparing them to the "
                             "limits, so short background spikes don't reset the idle timer (now: %(default)s)")
    parser.add_argument("--cpu-limit", type=positive_number, default=defaults["cpu_limit"],
                        help="CPU %% that counts as idle (now: %(default)s)")
    parser.add_argument("--gpu-limit", type=positive_number, default=defaults["gpu_limit"],
                        help="GPU %% that counts as idle (now: %(default)s)")
    parser.add_argument("--net-limit-kb", type=positive_number, default=defaults["net_limit_kb"],
                        help="network KB/s that counts as idle (now: %(default)s)")
    parser.add_argument("--disk-limit-mb", type=positive_number, default=defaults["disk_limit_mb"],
                        help="disk MB/s that counts as idle (now: %(default)s)")
    parser.add_argument("--dry-run", action="store_true",
                        help="only log what would happen, never shut down")
    parser.add_argument("--console", action="store_true",
                        help="run in the terminal instead of a window")
    parser.add_argument("--log-file", type=Path,
                        default=platform_utils.get_app_data_folder() / "idledown.log",
                        help="where to write the log (default: %(default)s)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def build_settings(values, dry_run, console, log_file):
    limits = Limits(
        cpu_percent=values["cpu_limit"],
        gpu_percent=values["gpu_limit"],
        network_bytes_per_second=values["net_limit_kb"] * 1_000,
        disk_bytes_per_second=values["disk_limit_mb"] * 1_000_000,
    )
    return Settings(
        limits=limits,
        required_idle_seconds=values["idle_minutes"] * 60,
        countdown_seconds=values["countdown"],
        check_interval_seconds=values["interval"],
        average_seconds=values["average_seconds"],
        dry_run=dry_run,
        console=console,
        log_file=log_file,
    )


def readings_to_average(settings):
    return round(settings.average_seconds / settings.check_interval_seconds)


def parse_settings(arguments=None, settings_file=None):
    saved_values, problems = load_saved_values(settings_file or settings_file_path())
    args = build_parser(saved_values).parse_args(arguments)
    values = {name: getattr(args, name) for name in DEFAULT_VALUES}
    settings = build_settings(values, args.dry_run, args.console, args.log_file)
    return settings, problems
