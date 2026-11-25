import unittest
from unittest.mock import patch

from monitor import IdleTimer, Limits, Usage, UsageAverage, status_line

LIMITS = Limits(cpu_percent=10, gpu_percent=10, network_bytes_per_second=100_000, disk_bytes_per_second=2_000_000)


def usage(cpu=0, gpu=None, network=0, disk=0):
    return Usage(cpu, gpu, network, disk)


class UsageTests(unittest.TestCase):
    def test_quiet_usage_is_below_limits(self):
        self.assertEqual(usage(cpu=3, gpu=2, network=5_000, disk=300_000).over_limits(LIMITS), [])
        self.assertTrue(usage(cpu=3).is_below(LIMITS))

    def test_names_every_signal_over_its_limit(self):
        busy = usage(cpu=50, gpu=90, network=1_000_000, disk=9_000_000)
        self.assertEqual(busy.over_limits(LIMITS), ["CPU", "GPU", "Network", "Disk"])

    def test_reaching_the_limit_counts_as_busy(self):
        self.assertEqual(usage(cpu=10).over_limits(LIMITS), ["CPU"])

    def test_missing_gpu_is_never_busy(self):
        self.assertEqual(usage(gpu=None).over_limits(LIMITS), [])
        self.assertEqual(usage(gpu=None).gpu_text(), "n/a")

    def test_texts(self):
        reading = usage(cpu=3.14, gpu=35.4, network=12_345, disk=1_500_000)
        self.assertEqual(reading.cpu_text(), "3.1 %")
        self.assertEqual(reading.gpu_text(), "35 %")
        self.assertEqual(reading.network_text(), "12.3 KB/s")
        self.assertEqual(reading.disk_text(), "1.50 MB/s")


class UsageAverageTests(unittest.TestCase):
    def test_averages_only_the_most_recent_readings(self):
        average = UsageAverage(3)
        for cpu in [90, 0, 0, 3]:
            result = average.add(usage(cpu=cpu, network=300, disk=600))
        self.assertAlmostEqual(result.cpu_percent, 1.0)
        self.assertAlmostEqual(result.network_bytes_per_second, 300)

    def test_short_spike_does_not_make_the_average_busy(self):
        average = UsageAverage(12)
        for _ in range(11):
            average.add(usage(cpu=2))
        self.assertTrue(average.add(usage(cpu=60)).is_below(LIMITS))

    def test_gpu_average_skips_missing_readings(self):
        average = UsageAverage(3)
        average.add(usage(gpu=50))
        average.add(usage(gpu=None))
        self.assertAlmostEqual(average.add(usage(gpu=20)).gpu_percent, 35)

    def test_gpu_is_none_when_never_read(self):
        self.assertIsNone(UsageAverage(3).add(usage(gpu=None)).gpu_percent)

    def test_window_of_zero_still_keeps_one_reading(self):
        average = UsageAverage(0)
        average.add(usage(cpu=80))
        self.assertEqual(average.add(usage(cpu=4)).cpu_percent, 4)


class IdleTimerTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("monitor.time.monotonic", return_value=1000.0)
        self.clock = patcher.start()
        self.addCleanup(patcher.stop)
        self.timer = IdleTimer(required_seconds=600)

    def test_counts_continuous_idle_time(self):
        self.timer.update(True)
        self.clock.return_value = 1599.0
        self.timer.update(True)
        self.assertFalse(self.timer.is_finished())
        self.clock.return_value = 1600.0
        self.assertTrue(self.timer.is_finished())

    def test_activity_starts_the_count_over(self):
        self.timer.update(True)
        self.clock.return_value = 1500.0
        self.timer.update(False)
        self.assertEqual(self.timer.idle_seconds(), 0)
        self.timer.update(True)
        self.clock.return_value = 1550.0
        self.assertEqual(self.timer.idle_seconds(), 50)

    def test_reset(self):
        self.timer.update(True)
        self.clock.return_value = 2000.0
        self.timer.reset()
        self.assertEqual(self.timer.idle_seconds(), 0)


class StatusLineTests(unittest.TestCase):
    def test_mentions_busy_signals(self):
        line = status_line(usage(cpu=50, disk=5_000_000), IdleTimer(600), LIMITS)
        self.assertTrue(line.endswith("busy: CPU, Disk"))

    def test_quiet_line_has_no_busy_part(self):
        self.assertNotIn("busy", status_line(usage(cpu=1), IdleTimer(600), LIMITS))


if __name__ == "__main__":
    unittest.main()
