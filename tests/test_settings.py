import argparse
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

from settings import (DEFAULT_VALUES, parse_settings, positive_number, positive_whole_number,
                      readings_to_average, save_values)


class ValidatorTests(unittest.TestCase):
    def test_accepts_positive_numbers(self):
        self.assertEqual(positive_number("2.5"), 2.5)
        self.assertEqual(positive_whole_number("60"), 60)

    def test_rejects_zero_negative_and_non_finite(self):
        for text in ["0", "-1", "nan", "inf", "-inf"]:
            with self.subTest(text=text), self.assertRaises(argparse.ArgumentTypeError):
                positive_number(text)

    def test_whole_number_rejects_fractions_and_text(self):
        for text in ["2.5", "nan", "abc"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                positive_whole_number(text)


class SettingsFileTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "settings.json"

    def parse(self, *arguments):
        return parse_settings(list(arguments), self.path)

    def test_defaults_without_a_file(self):
        settings, problems = self.parse()
        self.assertEqual(problems, [])
        self.assertEqual(settings.saved_values(), DEFAULT_VALUES)

    def test_saved_values_are_loaded(self):
        save_values({**DEFAULT_VALUES, "cpu_limit": 15, "idle_minutes": 20}, self.path)
        settings, problems = self.parse()
        self.assertEqual(problems, [])
        self.assertEqual(settings.limits.cpu_percent, 15)
        self.assertEqual(settings.required_idle_seconds, 1200)

    def test_command_line_overrides_saved_values(self):
        save_values({**DEFAULT_VALUES, "cpu_limit": 15}, self.path)
        settings, _ = self.parse("--cpu-limit", "30")
        self.assertEqual(settings.limits.cpu_percent, 30)

    def test_units_are_converted(self):
        settings, _ = self.parse("--net-limit-kb", "250", "--disk-limit-mb", "3.5")
        self.assertEqual(settings.limits.network_bytes_per_second, 250_000)
        self.assertEqual(settings.limits.disk_bytes_per_second, 3_500_000)

    def test_bad_values_fall_back_to_defaults_with_a_warning(self):
        self.path.write_text(json.dumps({"cpu_limit": "abc", "countdown": 2.5, "interval": "nan", "foo": 1}))
        settings, problems = self.parse()
        self.assertEqual(settings.limits.cpu_percent, DEFAULT_VALUES["cpu_limit"])
        self.assertEqual(settings.countdown_seconds, DEFAULT_VALUES["countdown"])
        self.assertEqual(settings.check_interval_seconds, DEFAULT_VALUES["interval"])
        self.assertEqual(len(problems), 4)

    def test_broken_file_is_reported_not_fatal(self):
        for content in ["{not json", "[1, 2]"]:
            with self.subTest(content=content):
                self.path.write_text(content)
                settings, problems = self.parse()
                self.assertEqual(settings.saved_values(), DEFAULT_VALUES)
                self.assertEqual(len(problems), 1)

    def test_saved_values_round_trip(self):
        settings, _ = self.parse("--idle-minutes", "15", "--gpu-limit", "20")
        save_values(settings.saved_values(), self.path)
        reloaded, _ = self.parse()
        self.assertEqual(reloaded.saved_values(), settings.saved_values())

    def test_invalid_command_line_value_exits(self):
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            self.parse("--interval", "nan")


class ReadingsToAverageTests(unittest.TestCase):
    def test_number_of_readings_in_the_window(self):
        settings, _ = parse_settings(["--interval", "5", "--average-seconds", "60"], Path("missing.json"))
        self.assertEqual(readings_to_average(settings), 12)
        settings, _ = parse_settings(["--interval", "2", "--average-seconds", "30"], Path("missing.json"))
        self.assertEqual(readings_to_average(settings), 15)


if __name__ == "__main__":
    unittest.main()
