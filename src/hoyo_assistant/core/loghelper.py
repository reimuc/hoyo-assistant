import logging
import os
import sys
from types import FrameType

from loguru import logger

VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


class InterceptHandler(logging.Handler):
    """
    Logs to loguru from Python standard logging module.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)

        # Find caller from where originated the logged message
        # logging.currentframe() may return None in some environments; type accordingly
        frame: FrameType | None = logging.currentframe()
        depth = 2
        while (
            frame is not None
            and getattr(frame, "f_code", None) is not None
            and frame.f_code.co_filename == logging.__file__
        ):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logger(log_level: str = "INFO") -> None:
    normalized_level = str(log_level or "INFO").upper()
    if normalized_level not in VALID_LOG_LEVELS:
        sys.stderr.write(
            f"Invalid HOYO_ASSISTANT_SYSTEM__LOG_LEVEL={normalized_level}, fallback to INFO\n"
        )
        normalized_level = "INFO"

    # Remove default handler
    logger.remove()

    # Determine Log Directory
    # Default to CWD/logs, not src/hoyo_assistant/logs
    default_log_dir = os.path.join(os.getcwd(), "logs")
    log_dir = os.environ.get("HOYO_ASSISTANT_LOG_DIR", default_log_dir)

    # Log Retention and Rotation Configs
    rotation = os.environ.get("HOYO_ASSISTANT_LOG_ROTATION", "10 MB")
    retention = os.environ.get("HOYO_ASSISTANT_LOG_RETENTION", "1 week")

    # Environment flags to control outputs
    console_enable = (
        os.environ.get("HOYO_ASSISTANT_LOG_CONSOLE_ENABLE", "true").lower() == "true"
    )
    file_enable = (
        os.environ.get("HOYO_ASSISTANT_LOG_FILE_ENABLE", "true").lower() == "true"
    )

    # Add console handler with improved format
    # Business Logic logs (INFO+) shown to user. Runtime logs (DEBUG) hidden unless requested.
    if console_enable:
        console_format = "<green>{time:HH:mm:ss}</green> | <level>{message}</level>"
        if normalized_level == "DEBUG":
            console_format = (
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level>"
            )
        logger.add(
            sys.stderr,
            format=console_format,
            level=normalized_level,
        )

    # Add file handler - captures everything (DEBUG+) for troubleshooting
    if file_enable:
        try:
            os.makedirs(log_dir, exist_ok=True)
            log_file_path = os.path.join(log_dir, "hoyo_assistant.log")
            logger.add(
                log_file_path,
                rotation=rotation,
                retention=retention,
                level="DEBUG",  # Always capture DEBUG in file unless disk space is concern?
                encoding="utf-8",
                enqueue=True,  # Async safe
                backtrace=True,
                diagnose=True,
            )
        except Exception as e:
            # Fallback to console if file logging fails (e.g. permission error)
            sys.stderr.write(f"Failed to setup file logging: {e}\n")

    # Intercept standard logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # Quiet specific loggers
    for logger_name in ["httpx", "urllib3", "asyncio"]:
        logging_logger = logging.getLogger(logger_name)
        # Avoid double handling if possible, but force propagation to False and handle strictly
        logging_logger.handlers = [InterceptHandler()]
        logging_logger.propagate = False

        if normalized_level == "DEBUG":
            logging_logger.setLevel(logging.INFO)
        else:
            logging_logger.setLevel(logging.WARNING)


_env_log_level = os.environ.get("HOYO_ASSISTANT_SYSTEM__LOG_LEVEL", "INFO").upper()
setup_logger(_env_log_level)

log = logger
