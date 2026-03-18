"""
Global shutdown coordination for EDGECORE trading system.

Provides:
- Signal-based shutdown (SIGINT, SIGTERM, SIGUSR1)
- File-based shutdown trigger (data/trading_enabled)
- Thread-safe state management
- Graceful position closure coordination
"""

import signal
import os
import threading
from pathlib import Path
from datetime import datetime
from typing import Any, Optional
from structlog import get_logger

logger = get_logger(__name__)


class ShutdownManager:
    """
    Graceful shutdown coordinator with multiple trigger mechanisms.
    
    Features:
    - OS signal handlers (SIGINT, SIGTERM, SIGUSR1)
    - File-based shutdown trigger (data/trading_enabled)
    - Thread-safe state management
    - Non-blocking signal handling
    """
    
    # Class-level lock for thread safety (shared is OK for the lock itself)
    _global_lock = threading.Lock()
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize shutdown manager.
        
        Args:
            data_dir: Directory for trading_enabled file
        """
        # Instance-level state (not shared across instances)
        self._shutdown_flag: bool = False
        self._shutdown_reason: Optional[str] = None
        
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.trading_enabled_file = self.data_dir / "trading_enabled"
        
        # Create trading_enabled file on startup
        self._create_trading_enabled_file()
        
        # Register OS signal handlers
        self._register_signal_handlers()
        
        logger.info(
            "shutdown_manager_initialized",
            trading_enabled_file=str(self.trading_enabled_file),
            signals_registered=["SIGINT", "SIGTERM", "SIGUSR1"]
        )
    
    def _create_trading_enabled_file(self) -> None:
        """Create trading_enabled marker file on startup."""
        try:
            self.trading_enabled_file.touch()
            logger.debug("trading_enabled_file_created", file=str(self.trading_enabled_file))
        except Exception as e:
            logger.error("trading_enabled_file_creation_failed", error=str(e))
            raise
    
    def _register_signal_handlers(self) -> None:
        """Register OS signal handlers for graceful shutdown."""
        def _sigint_handler(signum: int, frame: Any) -> None:
            self.request_shutdown(f"SIGINT (Ctrl+C) - pid={os.getpid()}")
        
        def _sigterm_handler(signum: int, frame: Any) -> None:
            self.request_shutdown(f"SIGTERM (system kill) - pid={os.getpid()}")
        
        def _sigusr1_handler(signum: int, frame: Any) -> None:
            self.request_shutdown(f"SIGUSR1 (user signal) - pid={os.getpid()}")
        
        try:
            signal.signal(signal.SIGINT, _sigint_handler)
            signal.signal(signal.SIGTERM, _sigterm_handler)
            if hasattr(signal, 'SIGUSR1'):
                signal.signal(signal.SIGUSR1, _sigusr1_handler)
            else:
                logger.info("sigusr1_not_available", reason="not supported on this platform")
            logger.debug("signal_handlers_registered")
        except Exception as e:
            logger.error("signal_handler_registration_failed", error=str(e))
            # Don't raise - continue without signals on some platforms
    
    def request_shutdown(self, reason: str) -> None:
        """
        Request graceful shutdown with reason logging.
        
        Thread-safe. Can be called multiple times (idempotent).
        
        Args:
            reason: Description of why shutdown was requested
        """
        with ShutdownManager._global_lock:
            if not self._shutdown_flag:
                self._shutdown_flag = True
                self._shutdown_reason = reason
                logger.warning(
                    "shutdown_requested",
                    reason=reason,
                    timestamp=datetime.now().isoformat()
                )
    
    def is_shutdown_requested(self) -> bool:
        """
        Check if shutdown has been requested (by any mechanism).
        
        Returns:
            True if shutdown requested via signal, file, or code
        
        Note:
            - Checks signal-based flag first (fastest)
            - Falls back to file-based check if flag not set
        """
        with ShutdownManager._global_lock:
            if self._shutdown_flag:
                return True
        
        # Check file-based trigger
        if not self.trading_enabled_file.exists():
            # File was deleted - trigger shutdown
            reason = "trading_enabled file deleted"
            self.request_shutdown(reason)
            return True
        
        return False
    
    def get_shutdown_reason(self) -> Optional[str]:
        """
        Get reason for shutdown request.
        
        Returns:
            Reason string if shutdown requested, else None
        """
        with ShutdownManager._global_lock:
            return self._shutdown_reason
    
    def cleanup(self) -> None:
        """
        Cleanup on shutdown.
        
        Removes trading_enabled file to prevent restart confusion.
        """
        try:
            if self.trading_enabled_file.exists():
                self.trading_enabled_file.unlink()
                logger.info("trading_enabled_file_removed")
        except Exception as e:
            logger.error("cleanup_failed", error=str(e))


def create_trading_enabled_marker() -> None:
    """
    Create trading_enabled marker file.
    
    This allows external scripts to trigger shutdown by deleting this file:
    
    Example:
        rm data/trading_enabled  # Triggers graceful shutdown
    """
    mgr = ShutdownManager()
    mgr._create_trading_enabled_file()


def request_external_shutdown(reason: str = "external_shutdown") -> None:
    """
    Request shutdown from external script.
    
    Args:
        reason: Description of why shutdown was requested
    
    Example:
        from execution.shutdown_manager import request_external_shutdown
        request_external_shutdown("Market circuit breaker triggered")
    """
    mgr = ShutdownManager()
    mgr.request_shutdown(reason)
