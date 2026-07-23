import logging
import sys

import structlog


def configure_logging(log_level: str = "info") -> None:
    """
    Structured JSON logging, per ARCHITECTURE.md §25.3 — every service emits
    logs in the same shape so they can be correlated across service boundaries
    by a single log store (ELK/Loki) using a shared correlation ID convention.
    """
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level.upper(),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
