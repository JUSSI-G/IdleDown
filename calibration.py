import math
import time
from dataclasses import dataclass, field

from monitor import UsageAverage
from settings import DEFAULT_VALUES

MEASURE_SECONDS = 120
SAFETY_FACTOR = 2

RELIABLE = "reliable"
CLOSE = "close"
SOMETIMES = "sometimes"
UNUSED = "unused"


@dataclass
class LimitRule:
    setting: str
    label: str
    unit: str
    minimum: float
    maximum: float
    step: float

    def format(self, value):
        return f"{value:.1f}" if self.step < 1 else f"{value:.0f}"


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


@dataclass
class SignalCheck:
    rule: LimitRule
    lowest: float
    highest: float
    limit: float
    verdict: str


@dataclass
class JobCheck:
    signals: list = field(default_factory=list)

    def verdict(self):
        verdicts = {signal.verdict for signal in self.signals}
        for verdict in (RELIABLE, CLOSE, SOMETIMES):
            if verdict in verdicts:
                return verdict
        return UNUSED


def round_up(value, step):
    return math.ceil(value / step) * step


def averaged_levels(readings, reading_count):
    average = UsageAverage(reading_count)
    window = min(reading_count, len(readings))
    levels = {"cpu": [], "gpu": [], "network": [], "disk": []}
    for count, reading in enumerate(readings, start=1):
        usage = average.add(reading)
        if count < window:
            continue
        levels["cpu"].append(usage.cpu_percent)
        if usage.gpu_percent is not None:
            levels["gpu"].append(usage.gpu_percent)
        levels["network"].append(usage.network_bytes_per_second / 1_000)
        levels["disk"].append(usage.disk_bytes_per_second / 1_000_000)
    return levels


def suggest_limits(readings, reading_count):
    suggestion = Suggestion()
    for signal, values in averaged_levels(readings, reading_count).items():
        if not values:
            continue
        rule = RULES[signal]
        level = max(values)
        wanted = level * SAFETY_FACTOR
        if wanted > rule.maximum:
            suggestion.not_quiet.append(f"{rule.label} was at {rule.format(level)} {rule.unit}")
            continue
        suggestion.values[rule.setting] = max(rule.minimum, round_up(wanted, rule.step))
    return suggestion


def check_signal(rule, values, limit):
    lowest, highest = min(values), max(values)
    if lowest >= limit * 1.5:
        verdict = RELIABLE
    elif lowest >= limit:
        verdict = CLOSE
    elif highest >= limit:
        verdict = SOMETIMES
    else:
        verdict = UNUSED
    return SignalCheck(rule, lowest, highest, limit, verdict)


def check_job(readings, reading_count, current_values):
    job_check = JobCheck()
    for signal, values in averaged_levels(readings, reading_count).items():
        if not values:
            continue
        rule = RULES[signal]
        job_check.signals.append(check_signal(rule, values, current_values[rule.setting]))
    return job_check


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
