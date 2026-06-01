"""
Rich Live TUI dashboard for the trading bot.

Displays a multi-panel terminal dashboard with:
- Account balance & margin info
- Live price ticker (via WebSocket)
- Recent orders table
- Open positions

Uses Rich's Live display for smooth, flicker-free updates.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from rich.columns import Columns
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from bot.client import BinanceClient
from bot.utils import (
    fmt_percent,
    fmt_pnl,
    fmt_price,
    fmt_quantity,
    fmt_side,
    fmt_status,
    fmt_timestamp,
)
from bot.websocket_feed import PriceFeed

logger = logging.getLogger(__name__)
console = Console()


class Dashboard:
    """Interactive terminal dashboard with live data.

    Parameters
    ----------
    client:
        Authenticated ``BinanceClient`` instance.
    watch_symbols:
        Symbols to track in the price ticker panel.
    """

    def __init__(
        self,
        client: BinanceClient,
        watch_symbols: Optional[List[str]] = None,
    ) -> None:
        self._client = client
        self._symbols = watch_symbols or ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        self._price_feed: Optional[PriceFeed] = None
        self._account_data: Dict[str, Any] = {}
        self._balances: List[Dict[str, Any]] = []
        self._positions: List[Dict[str, Any]] = []
        self._recent_orders: List[Dict[str, Any]] = []

    # ---- Data fetching -------------------------------------------- #

    def _refresh_account(self) -> None:
        """Fetch account info, balances, and positions."""
        try:
            self._account_data = self._client.get_account()
            self._balances = [
                a for a in self._account_data.get("assets", [])
                if float(a.get("walletBalance", 0)) > 0
            ]
            self._positions = [
                p for p in self._account_data.get("positions", [])
                if float(p.get("positionAmt", 0)) != 0
            ]
        except Exception as exc:
            logger.error("Failed to fetch account data: %s", exc)

    def _refresh_orders(self) -> None:
        """Fetch recent orders for watched symbols."""
        try:
            all_orders = []
            for sym in self._symbols[:3]:  # Top 3 to avoid rate limits
                orders = self._client.get_all_orders(symbol=sym, limit=5)
                all_orders.extend(orders)
            # Sort by time descending
            self._recent_orders = sorted(
                all_orders,
                key=lambda o: o.get("time", 0),
                reverse=True,
            )[:10]
        except Exception as exc:
            logger.error("Failed to fetch orders: %s", exc)

    # ---- Panel builders ------------------------------------------- #

    def _build_account_panel(self) -> Panel:
        """Build the account overview panel."""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="bold cyan")
        table.add_column("Value", justify="right")

        total_balance = self._account_data.get("totalWalletBalance", "0")
        available = self._account_data.get("availableBalance", "0")
        unrealized = self._account_data.get("totalUnrealizedProfit", "0")
        margin_balance = self._account_data.get("totalMarginBalance", "0")

        table.add_row("Total Balance", f"{fmt_price(total_balance)} USDT")
        table.add_row("Available", f"{fmt_price(available)} USDT")
        table.add_row("Margin Balance", f"{fmt_price(margin_balance)} USDT")
        table.add_row("Unrealized PnL", fmt_pnl(unrealized))

        return Panel(table, title="Account", border_style="cyan", padding=(1, 1))

    def _build_prices_panel(self) -> Panel:
        """Build the live prices panel from WebSocket data."""
        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("Symbol", style="bold")
        table.add_column("Price", justify="right")
        table.add_column("24h %", justify="right")
        table.add_column("24h High", justify="right")
        table.add_column("24h Low", justify="right")

        tickers = self._price_feed.tickers if self._price_feed else {}

        for sym in self._symbols:
            ticker = tickers.get(sym.upper())
            if ticker:
                table.add_row(
                    sym,
                    fmt_price(ticker.price),
                    fmt_percent(ticker.price_change_pct),
                    fmt_price(ticker.high_24h),
                    fmt_price(ticker.low_24h),
                )
            else:
                table.add_row(sym, "[dim]loading...[/dim]", "-", "-", "-")

        return Panel(table, title="Live Prices", border_style="magenta", padding=(1, 1))

    def _build_positions_panel(self) -> Panel:
        """Build the open positions panel."""
        if not self._positions:
            content = Text("No open positions", style="dim")
            return Panel(content, title="Positions", border_style="yellow", padding=(1, 1))

        table = Table(show_header=True, header_style="bold yellow", box=None)
        table.add_column("Symbol", style="bold")
        table.add_column("Side")
        table.add_column("Size", justify="right")
        table.add_column("Entry Price", justify="right")
        table.add_column("Unrealized PnL", justify="right")

        for pos in self._positions[:5]:
            amt = float(pos.get("positionAmt", 0))
            side = "LONG" if amt > 0 else "SHORT"
            side_style = "green" if amt > 0 else "red"
            table.add_row(
                pos.get("symbol", ""),
                f"[{side_style}]{side}[/{side_style}]",
                fmt_quantity(abs(amt)),
                fmt_price(pos.get("entryPrice", "0")),
                fmt_pnl(pos.get("unrealizedProfit", "0")),
            )

        return Panel(table, title="Positions", border_style="yellow", padding=(1, 1))

    def _build_orders_panel(self) -> Panel:
        """Build the recent orders panel."""
        if not self._recent_orders:
            content = Text("No recent orders", style="dim")
            return Panel(content, title="Recent Orders", border_style="green", padding=(1, 1))

        table = Table(show_header=True, header_style="bold green", box=None)
        table.add_column("ID", style="dim")
        table.add_column("Symbol")
        table.add_column("Side")
        table.add_column("Type")
        table.add_column("Qty", justify="right")
        table.add_column("Price", justify="right")
        table.add_column("Status")
        table.add_column("Time")

        for o in self._recent_orders[:8]:
            table.add_row(
                str(o.get("orderId", ""))[-8:],  # Last 8 chars for readability
                o.get("symbol", ""),
                fmt_side(o.get("side", "")),
                o.get("type", ""),
                fmt_quantity(o.get("origQty", "0")),
                fmt_price(o.get("price", "0")),
                fmt_status(o.get("status", "")),
                fmt_timestamp(o.get("time")),
            )

        return Panel(table, title="Recent Orders", border_style="green", padding=(1, 1))

    def _build_layout(self) -> Group:
        """Assemble all panels into the dashboard layout."""
        # Top row: Account + Prices side by side
        top_row = Columns(
            [self._build_account_panel(), self._build_prices_panel()],
            equal=True,
            expand=True,
        )
        # Bottom row: Positions + Orders
        bottom_row = Columns(
            [self._build_positions_panel(), self._build_orders_panel()],
            equal=True,
            expand=True,
        )

        footer = Text(
            "  Press Ctrl+C to exit  |  Data refreshes every 5 seconds  |  Prices update in real-time",
            style="dim",
        )

        return Group(top_row, bottom_row, footer)

    # ---- Main loop ------------------------------------------------ #

    def run(self) -> None:
        """Start the dashboard with live updates."""
        console.print("[bold cyan]Starting dashboard...[/bold cyan]\n")

        # Start WebSocket price feed
        self._price_feed = PriceFeed(symbols=self._symbols)
        self._price_feed.start()

        # Initial data load
        self._refresh_account()
        self._refresh_orders()

        try:
            with Live(
                self._build_layout(),
                console=console,
                refresh_per_second=2,
                screen=False,
            ) as live:
                last_refresh = time.time()
                while True:
                    # Refresh REST data every 5 seconds
                    if time.time() - last_refresh > 5:
                        self._refresh_account()
                        self._refresh_orders()
                        last_refresh = time.time()

                    live.update(self._build_layout())
                    time.sleep(0.5)

        except KeyboardInterrupt:
            console.print("\n[dim]Dashboard stopped.[/dim]")
        finally:
            if self._price_feed:
                self._price_feed.stop()
