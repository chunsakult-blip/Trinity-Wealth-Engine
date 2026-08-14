import logging
import logging.handlers
import os
import sys
from pathlib import Path


_SETUP_DONE = False


def _get_log_file() -> Path:
    """Return the canonical application log path."""
    log_dir = Path(__file__).resolve().parents[1] / "logs"
    log_dir.mkdir(exist_ok=True)
    return log_dir / "system.log"


def _find_file_handler(log_file: Path) -> logging.Handler | None:
    """
    Find an existing TimedRotatingFileHandler for the same log file.

    This is important on Windows because creating multiple handlers that
    point to the same file can cause rollover races and WinError 32.
    """
    root_logger = logging.getLogger()

    target = os.path.normcase(os.path.abspath(str(log_file)))

    for handler in root_logger.handlers:
        if not isinstance(handler, logging.handlers.TimedRotatingFileHandler):
            continue

        handler_file = getattr(handler, "baseFilename", None)
        if not handler_file:
            continue

        current = os.path.normcase(os.path.abspath(str(handler_file)))

        if current == target:
            return handler

    return None


def setup_logging(level: str | None = None) -> None:
    """
    Configure the root logger.

    Level is taken from LOG_LEVEL (default: INFO) unless explicitly
    overridden through the function argument.

    The setup is idempotent both through the module-level guard and by
    detecting an already-existing file handler. The second protection is
    necessary because tests may reset _SETUP_DONE while the root logger
    itself still retains its handlers.
    """
    global _SETUP_DONE

    if _SETUP_DONE:
        return

    log_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()

    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s:%(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

    root_logger = logging.getLogger()

    # Keep noisy third-party libraries under control.
    for noisy in ("httpx", "httpcore", "urllib3", "chromadb"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # yfinance can emit HTTP 404 errors during endpoint fallback even when
    # the overall data retrieval succeeds.
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)

    log_file = _get_log_file()

    # ---------------------------------------------------------------
    # IMPORTANT:
    # Reuse an existing handler if one already points to system.log.
    #
    # This prevents duplicate TimedRotatingFileHandler instances from
    # opening the same file and competing during midnight rollover.
    # ---------------------------------------------------------------
    file_handler = _find_file_handler(log_file)

    if file_handler is None:
        file_handler = logging.handlers.TimedRotatingFileHandler(
            log_file,
            when="midnight",
            interval=1,
            backupCount=7,
            encoding="utf-8",
        )

        file_handler.setLevel(logging.WARNING)

        formatter = logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
        )
        file_handler.setFormatter(formatter)

        root_logger.addHandler(file_handler)

    else:
        # Ensure an existing handler still has the expected configuration.
        file_handler.setLevel(logging.WARNING)

    _SETUP_DONE = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)
