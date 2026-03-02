import structlog
import logging
from pathlib import Path
from datetime import datetime

def setup_logger(name: str, log_level: str = "INFO", log_dir: str = "logs") -> structlog.BoundLogger:
    """
    Configure structured logging for the trading system.
    
    Args:
        name: Logger name (typically module name)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_dir: Directory for log files
    
    Returns:
        Configured structlog logger instance
    """
    Path(log_dir).mkdir(exist_ok=True)
    
    # Standard library logging config
    handler = logging.FileHandler(
        f"{log_dir}/{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    handler.setFormatter(
        logging.Formatter("%(message)s")
    )
    
    root_logger = logging.getLogger()
    # Prevent handler accumulation on repeated calls
    if not any(
        isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', '').endswith('.log')
        for h in root_logger.handlers
    ):
        root_logger.addHandler(handler)
    root_logger.setLevel(log_level)
    
    # Structlog config
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    return structlog.get_logger(name)
