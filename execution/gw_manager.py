# ============================================================
# PROJECT      : EDGECORE_V1 — Pairs Trading Bot
# FILE         : execution/gw_manager.py
# DESCRIPTION  : IB Gateway health checker — detect, launch, login, validate
# PYTHON       : 3.11+
# LAST UPDATED : 2026-04-11
# ============================================================
"""IB Gateway health checker with auto-launch and auto-login.

Ensures IB Gateway is running, authenticated, and its API is reachable
before the bot starts trading.  Handles the daily 05:30 restart cycle
by polling with backoff, filling the login form when credentials are
configured.

Capabilities:
- **Auto-detect**: checks process presence and API port.
- **Auto-launch**: starts ``ibgateway.exe`` if not running and
  ``execution.gateway_path`` is set.
- **Auto-login**: fills the IB Gateway login form (username + password)
  and clicks "Connexion" by simulating physical mouse clicks and
  keystrokes via ``pywinauto.mouse`` / ``pywinauto.keyboard``.
  Works with Java Swing without requiring the Java Access Bridge.
- **Daily restart (05:30)**: the poll loop retries the login fill
  whenever the port is closed and credentials are configured.

Usage::

    from execution.gw_manager import ensure_gateway_ready

    if not await ensure_gateway_ready(settings.execution):
        logger.critical("gateway_unavailable_aborting_session")
        return
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import socket
import subprocess
from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, cast

from structlog import get_logger

if TYPE_CHECKING:
    from config.settings import ExecutionConfig

logger = get_logger(__name__)

# ------------------------------------------------------------------
# Module-level constants (mirror of AlphaEdge IB_GATEWAY_* constants)
# ------------------------------------------------------------------
_HEALTH_RETRIES: int = 8
_HEALTH_RETRY_DELAY_SECONDS: int = 10
_STARTUP_TIMEOUT_SECONDS: int = 120  # max wait after auto-launching gateway
_API_TIMEOUT_SECONDS: float = 15.0  # validation probe timeout

# Regex patterns for locating the IB Gateway login window.
# IB Gateway shows "Portail IBKR" (FR), "IBKR Portal" (EN), or "IB Gateway".
_GW_WINDOW_TITLE_RE = r"Portail IBKR|IBKR Portal|IB Gateway"
# Login button label varies by language.
_GW_LOGIN_BTN_RE = r"Connexion|Login|Log In|Se connecter"

# Win32 constant: SW_RESTORE = 9 (show and restore window).
# Stable in the Windows API since Windows 3.1.
_SW_RESTORE: int = 9

# Windows-only: detach child process so it survives bot restarts.
_DETACHED_PROCESS = 0x00000008


# ------------------------------------------------------------------
# Win32 / pywinauto Protocol shims (for type checking without stubs)
# ------------------------------------------------------------------
class _Win32Gui(Protocol):
    """Subset of win32gui used by gateway detection and login fill."""

    def EnumWindows(  # noqa: N802
        self,
        func: Callable[..., object],
        extra: object,
        /,
    ) -> None: ...

    def IsWindowVisible(self, hwnd: int, /) -> int: ...  # noqa: N802

    def GetWindowText(self, hwnd: int, /) -> str: ...  # noqa: N802

    def ShowWindow(self, hwnd: int, ncmd: int, /) -> int: ...  # noqa: N802

    def SetForegroundWindow(self, hwnd: int, /) -> None: ...  # noqa: N802

    def GetWindowRect(self, hwnd: int, /) -> tuple[int, int, int, int]: ...  # noqa: N802


class _PwKeyboard(Protocol):
    """Subset of pywinauto.keyboard used for key injection."""

    def send_keys(
        self,
        keys: str,
        pause: float = ...,
        with_spaces: bool = ...,
    ) -> None: ...


class _PwMouse(Protocol):
    """Subset of pywinauto.mouse used for click injection."""

    def click(
        self,
        button: str = ...,
        coords: tuple[int, int] = ...,
    ) -> None: ...


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------
async def ensure_gateway_ready(config: ExecutionConfig) -> bool:
    """Ensure IB Gateway is running and the API is reachable.

    Strategy:
    1. If port open + API responds → return True immediately.
    2. If process not running + ``gateway_path`` configured → launch it.
    3. Poll until the API becomes reachable.  On each cycle where the port
       is still closed and ``username``/``password`` are configured, try to
       fill the login form (handles fresh launch + daily 05:30 restart).
    4. After all retries exhausted → return False.

    Parameters
    ----------
    config : ExecutionConfig
        Execution configuration carrying ``gateway_path``, ``username``,
        and ``password``.  ``IBKR_HOST``/``IBKR_PORT``/``IBKR_CLIENT_ID``
        are read from environment variables (consistent with IBGatewaySync).

    Returns
    -------
    bool
        True if gateway is healthy and API is reachable.
    """
    host = os.getenv("IBKR_HOST", "127.0.0.1")
    port = int(os.getenv("IBKR_PORT", "4002"))
    client_id = int(os.getenv("IBKR_CLIENT_ID", "1"))

    # Fast path: already healthy
    if _is_api_port_open(host, port):
        if await _validate_api_connection(host, port, client_id):
            logger.info("edgecore_gw_healthy", host=host, port=port)
            return True
        logger.warning(
            "edgecore_gw_port_open_validation_failed",
            note="gateway may be restarting",
        )

    has_credentials = bool(
        getattr(config, "username", "") and getattr(config, "password", "")
    )

    # Auto-launch or wait for external startup
    launched = False
    gateway_path: str = getattr(config, "gateway_path", "")
    if not _is_gateway_process_running():
        if gateway_path:
            launched = _start_gateway_process(gateway_path)
            if not launched:
                return False
        else:
            logger.warning(
                "edgecore_gw_process_not_detected",
                note="waiting for external startup (Task Scheduler / manual)",
            )
    else:
        logger.info(
            "edgecore_gw_process_detected",
            note="waiting for API to become available",
        )

    if has_credentials:
        logger.info(
            "edgecore_gw_credentials_configured", note="will auto-fill login form"
        )
    else:
        logger.info(
            "edgecore_gw_no_credentials",
            note="set IB_USERNAME / IB_PASSWORD in .env for auto-login",
        )

    # More retries after a fresh launch (gateway needs time to start Java + auth)
    max_retries = (
        _STARTUP_TIMEOUT_SECONDS // _HEALTH_RETRY_DELAY_SECONDS
        if launched
        else _HEALTH_RETRIES
    )

    # Poll until API becomes reachable
    for attempt in range(1, max_retries + 1):
        logger.info(
            "edgecore_gw_waiting_api",
            attempt=attempt,
            max_retries=max_retries,
        )
        await asyncio.sleep(_HEALTH_RETRY_DELAY_SECONDS)

        if not _is_api_port_open(host, port):
            # Login form may be visible — try to fill it
            if has_credentials:
                await _fill_gateway_login_if_needed(
                    config.username,
                    config.password,  # type: ignore[attr-defined]  # added in settings.py
                )
            continue

        if await _validate_api_connection(host, port, client_id):
            logger.info(
                "edgecore_gw_ready",
                attempts=attempt,
            )
            return True

    logger.critical(
        "edgecore_gw_unreachable",
        max_retries=max_retries,
        note="manual intervention required",
    )
    return False


# ------------------------------------------------------------------
# Gateway launcher (native — no IBC)
# ------------------------------------------------------------------
def _start_gateway_process(gateway_path: str) -> bool:
    """Launch ``ibgateway.exe`` from *gateway_path*.

    IB Gateway remembers credentials when **Store settings on server**
    is enabled in the gateway configuration.  Subsequent launches
    auto-authenticate without manual intervention.

    Parameters
    ----------
    gateway_path : str
        Directory containing ``ibgateway.exe``
        (e.g. ``C:\\Jts\\ibgateway\\1044``).

    Returns
    -------
    bool
        True if the process was launched successfully.
    """
    exe = pathlib.Path(gateway_path) / "ibgateway.exe"
    if not exe.exists():
        logger.error("edgecore_gw_executable_not_found", path=str(exe))
        return False

    try:
        subprocess.Popen(
            [str(exe)],
            cwd=str(exe.parent),
            creationflags=_DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
        logger.info("edgecore_gw_launched", path=str(exe))
        return True
    except OSError as exc:
        logger.error("edgecore_gw_launch_failed", error=str(exc))
        return False


def _try_enable_java_access_bridge(gateway_dir: pathlib.Path) -> None:
    """Enable the Java Accessibility Bridge once (best-effort).

    ``jabswitch -enable`` makes Java Swing controls visible to Windows
    UIA.  IB Gateway bundles its own JRE; ``jabswitch.exe`` is typically
    found in ``<gateway_dir>/jre/bin/`` or directly in ``<gateway_dir>``.
    """
    candidates = [
        gateway_dir / "jre" / "bin" / "jabswitch.exe",
        gateway_dir / "bin" / "jabswitch.exe",
        gateway_dir / "jabswitch.exe",
    ]
    for jabswitch in candidates:
        if jabswitch.exists():
            try:
                subprocess.run(
                    [str(jabswitch), "-enable"],
                    timeout=10,
                    check=False,
                    capture_output=True,
                )
                logger.info("edgecore_gw_jab_enabled", path=str(jabswitch))
                return
            except OSError:
                pass
    logger.debug(
        "edgecore_gw_jabswitch_not_found",
        note="run 'jabswitch -enable' manually if auto-login fails",
    )


# ------------------------------------------------------------------
# Login form automation (win32gui + SendInput — no JAB, no UIA)
# ------------------------------------------------------------------
async def _fill_gateway_login_if_needed(username: str, password: str) -> bool:
    """Async wrapper — fills the IB Gateway login form if the window is visible.

    Runs the blocking call in a thread pool so it does not block the
    event loop.
    """
    return await asyncio.to_thread(_fill_gateway_login_sync, username, password)


def _fill_gateway_login_sync(username: str, password: str) -> bool:
    """Fill the IB Gateway login window (blocking).

    Finds the window by title via ``win32gui``, brings it to the
    foreground, then simulates physical mouse clicks on the username and
    password fields (located by their proportional position inside the
    window) and types the credentials using ``pywinauto.keyboard``
    SendInput.  Clicks the login button to submit.

    This approach does **not** require the Java Access Bridge or UIA —
    it works at the Win32 ``SendInput`` level and is compatible with
    Java Swing, Electron, and any other GUI framework.

    Returns
    -------
    bool
        True if credentials were submitted.  False if the window was not
        visible yet — will be retried on the next poll cycle.
    """
    try:
        import pywinauto.keyboard as pw_keyboard
        import pywinauto.mouse as pw_mouse
        import win32gui
    except ImportError:
        logger.warning(
            "edgecore_gw_pywinauto_not_installed",
            note="pip install pywinauto to enable auto-login",
        )
        return False

    return _do_login_fill(
        username,
        password,
        cast(_Win32Gui, win32gui),
        cast(_PwKeyboard, pw_keyboard),
        cast(_PwMouse, pw_mouse),
    )


def _do_login_fill(
    username: str,
    password: str,
    win32gui: _Win32Gui,
    pw_keyboard: _PwKeyboard,
    pw_mouse: _PwMouse,
) -> bool:
    """Execute the actual GUI fill once all modules are available.

    Separated from :func:`_fill_gateway_login_sync` so that unit tests
    can pass mock modules directly without fighting Python's import
    machinery.
    """
    import time

    hwnd = _find_gateway_hwnd(cast(_Win32Gui, win32gui))
    if not hwnd:
        return False

    # Bring window to foreground
    try:
        win32gui.ShowWindow(hwnd, _SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
    except Exception as exc:
        logger.debug("edgecore_gw_focus_failed", error=str(exc))
        return False

    time.sleep(0.8)  # wait for focus

    rect = win32gui.GetWindowRect(hwnd)
    cx = (rect[0] + rect[2]) // 2
    win_top = rect[1]
    win_h = rect[3] - rect[1]

    # Field positions — relative to window height (IB Gateway fixed layout).
    # Calibrated from the IB Gateway 10.44 login window:
    #   username field ~43%, password field ~53%, connexion button ~67%.
    user_y = win_top + int(win_h * 0.43)
    pass_y = win_top + int(win_h * 0.53)
    btn_y = win_top + int(win_h * 0.67)

    try:
        # Username field
        pw_mouse.click(coords=(cx, user_y))
        time.sleep(0.3)
        pw_keyboard.send_keys("^a")  # select all (clear existing)
        pw_keyboard.send_keys(_escape_sendkeys(username), with_spaces=True, pause=0.02)

        # Password field
        pw_mouse.click(coords=(cx, pass_y))
        time.sleep(0.3)
        pw_keyboard.send_keys("^a")
        pw_keyboard.send_keys(_escape_sendkeys(password), with_spaces=True, pause=0.02)

        time.sleep(0.2)

        # Connexion button
        pw_mouse.click(coords=(cx, btn_y))

        logger.info("edgecore_gw_login_submitted")
        return True

    except Exception as exc:
        logger.debug("edgecore_gw_login_fill_failed", error=str(exc))
        return False


def _find_gateway_hwnd(win32gui: _Win32Gui) -> int:
    """Return the HWND of the IB Gateway login window, or 0 if not found."""
    import re

    pattern = re.compile(_GW_WINDOW_TITLE_RE, re.IGNORECASE)
    found = [0]

    def _cb(hwnd: int, _: object) -> bool:
        if win32gui.IsWindowVisible(hwnd):
            title: str = win32gui.GetWindowText(hwnd)
            if pattern.search(title):
                found[0] = hwnd
                return False  # stop enumeration
        return True

    try:
        win32gui.EnumWindows(_cb, None)
    except Exception:
        pass

    return found[0]


def _escape_sendkeys(text: str) -> str:
    """Escape pywinauto send_keys special characters.

    Characters ``+``, ``^``, ``%``, ``~``, ``(``, ``)``, ``{``, ``}``
    have special meaning in ``pywinauto.keyboard.send_keys`` — wrap each
    in braces to send them literally.
    """
    _special = frozenset("+^%~(){}")
    return "".join(f"{{{c}}}" if c in _special else c for c in text)


# ------------------------------------------------------------------
# Process detection (tasklist.exe — no psutil dependency)
# ------------------------------------------------------------------
def _is_gateway_process_running() -> bool:
    """Check if an IB Gateway process is running (Windows)."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq ibgateway.exe", "/NH"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # tasklist returns "INFO: No tasks are running..." when not found
        return "ibgateway.exe" in result.stdout.lower()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        logger.warning("edgecore_gw_process_query_failed")
        return False


# ------------------------------------------------------------------
# TCP port probe
# ------------------------------------------------------------------
def _is_api_port_open(host: str, port: int) -> bool:
    """Test whether the IB Gateway API port accepts TCP connections."""
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except (ConnectionRefusedError, TimeoutError, OSError):
        return False


# ------------------------------------------------------------------
# API validation (lightweight ib_insync connect + disconnect)
# ------------------------------------------------------------------
async def _validate_api_connection(host: str, port: int, client_id: int) -> bool:
    """Perform a lightweight IB API handshake to confirm authentication.

    Connects with a dedicated client ID (client_id + 99) to avoid
    colliding with the main trading connection, then disconnects
    immediately.
    """
    try:
        from ib_insync import IB
    except ImportError:
        logger.error("edgecore_gw_ib_insync_not_installed")
        return False

    ib = IB()
    probe_client_id = client_id + 99
    try:
        await asyncio.wait_for(
            ib.connectAsync(
                host=host,
                port=port,
                clientId=probe_client_id,
                readonly=True,
            ),
            timeout=_API_TIMEOUT_SECONDS,
        )
        ib.disconnect()
        return True
    except (TimeoutError, ConnectionError, OSError):
        return False
    except Exception:
        logger.debug("edgecore_gw_api_validation_failed", exc_info=True)
        return False
    finally:
        if ib.isConnected():
            ib.disconnect()
