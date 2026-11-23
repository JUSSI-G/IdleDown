import logging
import sys

from settings import parse_settings
from version import VERSION


def setup_logging(log_file):
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handlers = [logging.FileHandler(log_file, encoding="utf-8")]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def main():
    settings = parse_settings()
    setup_logging(settings.log_file)
    logging.info(f"IdleDown {VERSION} started. Settings: {settings}")

    if settings.console:
        from console_app import run_console
        run_console(settings)
    else:
        from gui_app import run_window
        run_window(settings)


if __name__ == "__main__":
    main()
