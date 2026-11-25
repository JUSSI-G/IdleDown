import unittest

from calibration import CLOSE, RELIABLE, SOMETIMES, UNUSED, check_job, suggest_limits
from monitor import Usage
from settings import DEFAULT_VALUES

WINDOW = 12


def steady(cpu=0.0, gpu=None, network_kb=0.0, disk_mb=0.0, count=24):
    return [Usage(cpu, gpu, network_kb * 1_000, disk_mb * 1_000_000)] * count


class SuggestLimitsTests(unittest.TestCase):
    def test_quiet_pc_keeps_the_defaults(self):
        suggestion = suggest_limits(steady(cpu=1.5, gpu=2, network_kb=20, disk_mb=0.3), WINDOW)
        self.assertEqual(suggestion.not_quiet, [])
        self.assertEqual(suggestion.values, {"cpu_limit": 10, "gpu_limit": 10, "net_limit_kb": 100, "disk_limit_mb": 2})

    def test_limit_is_twice_the_quiet_level_rounded_up(self):
        suggestion = suggest_limits(steady(cpu=7.2, disk_mb=1.69), WINDOW)
        self.assertEqual(suggestion.values["cpu_limit"], 15)
        self.assertEqual(suggestion.values["disk_limit_mb"], 3.5)

    def test_busy_pc_is_reported_instead_of_suggested(self):
        suggestion = suggest_limits(steady(cpu=30, network_kb=900, disk_mb=9), WINDOW)
        self.assertEqual(suggestion.values, {})
        self.assertEqual(len(suggestion.not_quiet), 3)

    def test_no_gpu_means_no_gpu_suggestion(self):
        self.assertNotIn("gpu_limit", suggest_limits(steady(cpu=1), WINDOW).values)

    def test_one_spike_counts_as_part_of_the_average(self):
        readings = steady(cpu=1, count=23) + steady(cpu=60, count=1)
        # (11 * 1 + 60) / 12 = 5.9 %, doubled and rounded up: 12 %, not the 120 % a raw peak would give
        self.assertEqual(suggest_limits(readings, WINDOW).values["cpu_limit"], 12)


class CheckJobTests(unittest.TestCase):
    def verdicts(self, readings):
        result = check_job(readings, WINDOW, DEFAULT_VALUES)
        return result.verdict(), {signal.rule.label: signal.verdict for signal in result.signals}

    def test_heavy_job_is_reliable(self):
        verdict, signals = self.verdicts(steady(cpu=30, gpu=95, network_kb=5, disk_mb=0.5))
        self.assertEqual(verdict, RELIABLE)
        self.assertEqual(signals, {"CPU": RELIABLE, "GPU": RELIABLE, "Network": UNUSED, "Disk": UNUSED})

    def test_job_just_above_a_limit_is_close(self):
        self.assertEqual(self.verdicts(steady(cpu=12))[0], CLOSE)

    def test_job_that_dips_below_is_sometimes(self):
        readings = steady(cpu=50, count=12) + steady(cpu=2, count=12)
        self.assertEqual(self.verdicts(readings)[0], SOMETIMES)

    def test_nothing_running_is_unused(self):
        self.assertEqual(self.verdicts(steady(cpu=2, gpu=0, network_kb=3, disk_mb=0.3))[0], UNUSED)

    def test_one_reliable_signal_is_enough(self):
        verdict, signals = self.verdicts(steady(cpu=2, network_kb=20_000))
        self.assertEqual(verdict, RELIABLE)
        self.assertEqual(signals["CPU"], UNUSED)


if __name__ == "__main__":
    unittest.main()
