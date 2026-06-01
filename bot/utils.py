"""
Utility helpers — banner, formatting, and configuration.

Provides a polished startup experience and reusable formatting
functions used across the CLI and dashboard.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

# ------------------------------------------------------------------ #
#  ASCII Banner                                                        #
# ------------------------------------------------------------------ #

BANNER = r"""
  _____ ____      _    ____  ___ _   _  ____   ____   ___ _____
 |_   _|  _ \    / \  |  _ \|_ _| \ | |/ ___| | __ ) / _ \_   _|
   | | | |_) |  / _ \ | | | || ||  \| | |  _  |  _ \| | | || |
   | | |  _ <  / ___ \| |_| || || |\  | |_| | | |_) | |_| || |
   |_| |_| \_\/_/   \_\____/___|_| \_|\____| |____/ \___/ |_|
"""

VERSION = "2.0.0"
SUBTITLE = "Binance Futures Testnet | USDT-M"


def print_banner() -> None:
    """Print the startup banner with version info."""
    banner_text = Text(BANNER, style="bold cyan")
    console.print(
        Panel(
            banner_text,
            subtitle=f"v{VERSION} | {SUBTITLE}",
            border_style="cyan",
            padding=(0, 2),
        )
    )


# ------------------------------------------------------------------ #
#  Formatting helpers                                                  #
# ------------------------------------------------------------------ #


def fmt_price(price: float | str, decimals: int = 2) -> str:
    """Format a price with commas and fixed decimals."""
    try:
        val = float(price)
        return f"{val:,.{decimals}f}"
    except (ValueError, TypeError):
        return str(price)


def fmt_quantity(qty: float | str, decimals: int = 4) -> str:
    """Format a quantity with fixed decimals."""
    try:
        val = float(qty)
        return f"{val:.{decimals}f}"
    except (ValueError, TypeError):
        return str(qty)


def fmt_pnl(pnl: float | str) -> str:
    """Format PnL with colour: green for profit, red for loss."""
    try:
        val = float(pnl)
        colour = "green" if val >= 0 else "red"
        sign = "+" if val > 0 else ""
        return f"[{colour}]{sign}{val:,.2f} USDT[/{colour}]"
    except (ValueError, TypeError):
        return str(pnl)


def fmt_percent(pct: float | str) -> str:
    """Format a percentage with colour coding."""
    try:
        val = float(pct)
        colour = "green" if val >= 0 else "red"
        sign = "+" if val > 0 else ""
        return f"[{colour}]{sign}{val:.2f}%[/{colour}]"
    except (ValueError, TypeError):
        return str(pct)


def fmt_side(side: str) -> str:
    """Colour-code BUY/SELL."""
    s = side.upper()
    colour = "green" if s == "BUY" else "red"
    return f"[bold {colour}]{s}[/bold {colour}]"


def fmt_status(status: str) -> str:
    """Colour-code order status."""
    colours = {
        "FILLED": "bold green",
        "NEW": "bold yellow",
        "PARTIALLY_FILLED": "bold yellow",
        "CANCELED": "dim",
        "EXPIRED": "dim red",
        "REJECTED": "bold red",
    }
    style = colours.get(status.upper(), "white")
    return f"[{style}]{status}[/{style}]"


def fmt_timestamp(ts_ms: int | str | None) -> str:
    """Convert Binance millisecond timestamp to readable string."""
    if ts_ms is None:
        return "-"
    try:
        ts = int(ts_ms) / 1000
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, TypeError, OSError):
        return str(ts_ms)


# ------------------------------------------------------------------ #
#  Config helpers                                                      #
# ------------------------------------------------------------------ #


def get_api_credentials() -> tuple[str, str]:
    """Load API key and secret from environment."""
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    return api_key, api_secret


def validate_credentials(api_key: str, api_secret: str) -> bool:
    """Check that credentials are not empty."""
    return bool(api_key and api_secret)
