import math
import time
from dataclasses import dataclass, field

from monitor import UsageAverage
from settings import DEFAULT_VALUES

MEASURE_SECONDS = 120
SAFETY_FACTOR = 2


@dataclass
class LimitRule:
    setting: str
    label: str
    unit: str
    minimum: float
    maximum: float
    step: float


RULES = {
    "cpu": LimitRule("cpu_limit", "CPU", "%", DEFAULT_VALUES["cpu_limit"], maximum=25, step=1),
    "gpu": LimitRule("gpu_limit", "GPU", "%", DEFAULT_VALUES["gpu_limit"], maximum=25, step=1),
    "network": LimitRule("net_limit_kb", "Network", "KB/s", DEFAULT_VALUES["net_limit_kb"], maximum=1000, step=10),
    "disk": LimitRule("disk_limit_mb", "Disk", "MB/s", DEFAULT_VALUES["disk_limit_mb"], maximum=10, step=0.5),
}


@dataclass
class Suggestion:
    values: dict = field(default_factory=dict)
    not_quiet: list = field(default_factory=list)


def round_up(value, step):
    return math.ceil(value / step) * step


def quiet_levels(readings, reading_count):
    average = UsageAverage(reading_count)
    window = min(reading_count, len(readings))
    peaks = {"cpu": 0.0, "gpu": None, "network": 0.0, "disk": 0.0}
    for count, reading in enumerate(readings, start=1):
        usage = average.add(reading)
        if count < window:
            continue
        peaks["cpu"] = max(peaks["cpu"], usage.cpu_percent)
        if usage.gpu_percent is not None:
            peaks["gpu"] = max(peaks["gpu"] or 0.0, usage.gpu_percent)
        peaks["network"] = max(peaks["network"], usage.network_bytes_per_second / 1_000)
        peaks["disk"] = max(peaks["disk"], usage.disk_bytes_per_second / 1_000_000)
    return peaks


def suggest_limits(readings, reading_count):
    suggestion = Suggestion()
    for signal, level in quiet_levels(readings, reading_count).items():
        if level is None:
            continue
        rule = RULES[signal]
        wanted = level * SAFETY_FACTOR
        if wanted > rule.maximum:
            suggestion.not_quiet.append(f"{rule.label} was at {level:.1f} {rule.unit}")
            continue
        suggestion.values[rule.setting] = max(rule.minimum, round_up(wanted, rule.step))
    return suggestion


class IdleMeasurement:
    def __init__(self, duration_seconds=MEASURE_SECONDS):
        self.duration_seconds = duration_seconds
        self.started = time.monotonic()
        self.readings = []

    def add(self, usage):
        self.readings.append(usage)

    def seconds_left(self):
        return max(0.0, self.duration_seconds - (time.monotonic() - self.started))

    def is_done(self):
        return self.seconds_left() == 0 and len(self.readings) >= 2
