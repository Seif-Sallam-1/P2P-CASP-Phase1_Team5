import logging
import os
import sys


def setup_logger(name, filename):
    """Create a logger writing to logs/<filename> and to stdout.

    Console output goes to stdout (not stderr) so shells such as PowerShell
    do not wrap log lines in NativeCommandError records. The log directory
    can be overridden with the CASP_LOG_DIR environment variable (used by
    the integration tests to avoid polluting the evidence logs).
    """
    log_dir = os.environ.get("CASP_LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    file_handler = logging.FileHandler(
        os.path.join(log_dir, filename),
        encoding="utf-8",
    )
    console_handler = logging.StreamHandler(sys.stdout)

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
