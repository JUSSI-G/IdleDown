import logging
import time

from monitor import IdleTimer, UsageReader, shut_down, status_line


def run_countdown(seconds):
    logging.info(f"Idle limit reached, countdown of {seconds} s started. Press Ctrl+C to cancel.")
    try:
        for remaining in range(seconds, 0, -1):
            print(f"Shutting down in {remaining:3} s", end="\r")
            time.sleep(1)
    except KeyboardInterrupt:
        print()
        logging.info("Shutdown cancelled by user.")
        return False
    print()
    return True


def run_console(settings):
    reader = UsageReader()
    timer = IdleTimer(settings.required_idle_seconds)

    try:
        while True:
            time.sleep(settings.check_interval_seconds)
            usage = reader.read()
            timer.update(usage.is_below(settings.limits))
            logging.info(status_line(usage, timer))

            if timer.is_finished():
                if run_countdown(settings.countdown_seconds):
                    succeeded = shut_down(settings.dry_run)
                    if succeeded and not settings.dry_run:
                        return
                timer.reset()
    except KeyboardInterrupt:
        print()
        logging.info("Stopped by user.")
