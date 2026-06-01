#!/usr/bin/env python3
"""
CLI entry point for the Binance Futures Testnet Trading Bot.

Uses Typer for argument parsing and Rich for coloured, tabular output.
Provides multiple commands for a complete trading experience:

  order        Place an order (MARKET / LIMIT / STOP_LIMIT)
  interactive  Guided order placement with prompts and live prices
  account      View account balance, margin, and positions
  prices       Live price ticker via WebSocket
  history      View recent order history
  cancel       Cancel an open order
  dashboard    Full TUI dashboard with live data

Usage examples
--------------
  python cli.py order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01
  python cli.py interactive
  python cli.py account
  python cli.py prices --symbols BTCUSDT ETHUSDT
  python cli.py history --symbol BTCUSDT
  python cli.py cancel --symbol BTCUSDT --order-id 123456
  python cli.py dashboard
"""

from __future__ import annotations

import os
import sys
import time
from typing import List, Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, FloatPrompt, Prompt
from rich.table import Table

from bot.client import BinanceAPIError, BinanceClient, BinanceNetworkError
from bot.logging_config import setup_logging
from bot.orders import OrderManager
from bot.utils import (
    fmt_percent,
    fmt_pnl,
    fmt_price,
    fmt_quantity,
    fmt_side,
    fmt_status,
    fmt_timestamp,
    print_banner,
    validate_credentials,
    get_api_credentials,
)
from bot.validators import ValidationError

# ------------------------------------------------------------------ #
#  Bootstrap                                                           #
# ------------------------------------------------------------------ #

load_dotenv()
setup_logging()

console = Console()
app = typer.Typer(
    name="trading-bot",
    help="Binance Futures Testnet Trading Bot -- MARKET, LIMIT, STOP_LIMIT orders with live data.",
    add_completion=False,
    rich_markup_mode="rich",
    no_args_is_help=True,
)


def _get_client() -> BinanceClient:
    """Build a ``BinanceClient`` from environment variables."""
    api_key, api_secret = get_api_credentials()
    if not validate_credentials(api_key, api_secret):
        console.print(
            "[bold red]Error:[/bold red] BINANCE_API_KEY and BINANCE_API_SECRET "
            "must be set in the environment or in a .env file.\n"
            "[dim]Copy .env.example to .env and add your testnet credentials.[/dim]"
        )
        raise typer.Exit(code=1)
    return BinanceClient(api_key=api_key, api_secret=api_secret)


# ------------------------------------------------------------------ #
#  Display helpers                                                     #
# ------------------------------------------------------------------ #


def _print_request_summary(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: float | None,
    stop_price: float | None,
) -> None:
    """Render a coloured summary table before sending the order."""
    table = Table(
        title="Order Request",
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
    )
    table.add_column("Parameter", style="bold")
    table.add_column("Value")

    table.add_row("Symbol", symbol.upper())
    table.add_row("Side", fmt_side(side))
    table.add_row("Type", order_type.upper())
    table.add_row("Quantity", fmt_quantity(quantity))
    if price is not None:
        table.add_row("Price", fmt_price(price))
    if stop_price is not None:
        table.add_row("Stop Price", fmt_price(stop_price))

    console.print()
    console.print(table)


def _print_response(result) -> None:  # noqa: ANN001
    """Render the API response in a rich table."""
    table = Table(
        title="Order Response",
        show_header=True,
        header_style="bold green",
        border_style="green",
    )
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("Order ID", str(result.order_id))
    table.add_row("Symbol", result.symbol)
    table.add_row("Side", fmt_side(result.side))
    table.add_row("Type", result.order_type)
    table.add_row("Status", fmt_status(result.status))
    table.add_row("Original Qty", result.orig_qty)
    table.add_row("Executed Qty", result.executed_qty)
    table.add_row("Avg Price", result.avg_price)
    if result.price and result.price != "0":
        table.add_row("Price", result.price)
    if result.stop_price and result.stop_price != "0":
        table.add_row("Stop Price", result.stop_price)
    if result.time_in_force:
        table.add_row("Time in Force", result.time_in_force)

    console.print()
    console.print(table)
    console.print()
    console.print(
        Panel(
            f"[bold green]Order {result.order_id} placed successfully![/bold green]",
            title="Success",
            border_style="green",
        )
    )


def _handle_error(exc: Exception) -> None:
    """Print a formatted error and exit."""
    if isinstance(exc, ValidationError):
        console.print(f"\n[bold red]Validation Error:[/bold red] {exc}")
    elif isinstance(exc, BinanceAPIError):
        console.print(f"\n[bold red]API Error ({exc.code}):[/bold red] {exc.message}")
    elif isinstance(exc, BinanceNetworkError):
        console.print(f"\n[bold red]Network Error:[/bold red] {exc}")
    else:
        console.print(f"\n[bold red]Error:[/bold red] {exc}")
    raise typer.Exit(code=1)


# ------------------------------------------------------------------ #
#  Command: order                                                      #
# ------------------------------------------------------------------ #


@app.command()
def order(
    symbol: str = typer.Option(..., "--symbol", "-s", help="Trading pair, e.g. BTCUSDT"),
    side: str = typer.Option(..., "--side", help="Order side: BUY or SELL"),
    order_type: str = typer.Option(..., "--type", "-t", help="Order type: MARKET, LIMIT, or STOP_LIMIT"),
    quantity: float = typer.Option(..., "--quantity", "-q", help="Order quantity"),
    price: float | None = typer.Option(None, "--price", "-p", help="Limit price (required for LIMIT and STOP_LIMIT)"),
    stop_price: float | None = typer.Option(None, "--stop-price", help="Stop price (required for STOP_LIMIT)"),
) -> None:
    """Place an order on Binance Futures Testnet."""
    print_banner()
    _print_request_summary(symbol, side, order_type, quantity, price, stop_price)

    client = _get_client()
    manager = OrderManager(client)

    try:
        with console.status("[bold cyan]Placing order on Binance Futures Testnet...[/bold cyan]"):
            result = manager.place_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                stop_price=stop_price,
            )
        _print_response(result)
    except (ValidationError, BinanceAPIError, BinanceNetworkError) as exc:
        _handle_error(exc)


# ------------------------------------------------------------------ #
#  Command: interactive                                                #
# ------------------------------------------------------------------ #


@app.command()
def interactive() -> None:
    """Guided interactive order placement with prompts and live prices."""
    print_banner()
    console.print(
        Panel(
            "[bold]Interactive Order Placement[/bold]\n"
            "[dim]Answer each prompt to build your order. Press Ctrl+C to cancel.[/dim]",
            border_style="cyan",
        )
    )

    client = _get_client()

    try:
        # Step 1: Symbol
        console.print("\n[bold cyan]Step 1/5:[/bold cyan] Trading Pair")
        symbol = Prompt.ask(
            "  Enter symbol",
            default="BTCUSDT",
        ).upper()

        # Fetch and show current price for context
        try:
            with console.status("[dim]Fetching current price...[/dim]"):
                ticker = client.get_ticker_price(symbol=symbol)
            current_price = float(ticker.get("price", 0))
            console.print(f"  [dim]Current price: [bold]{fmt_price(current_price)}[/bold] USDT[/dim]")
        except Exception:
            current_price = None
            console.print("  [dim]Could not fetch current price[/dim]")

        # Step 2: Side
        console.print("\n[bold cyan]Step 2/5:[/bold cyan] Order Side")
        side = Prompt.ask(
            "  Select side",
            choices=["BUY", "SELL"],
            default="BUY",
        )

        # Step 3: Order Type
        console.print("\n[bold cyan]Step 3/5:[/bold cyan] Order Type")
        order_type = Prompt.ask(
            "  Select type",
            choices=["MARKET", "LIMIT", "STOP_LIMIT"],
            default="MARKET",
        )

        # Step 4: Quantity
        console.print("\n[bold cyan]Step 4/5:[/bold cyan] Quantity")
        quantity = FloatPrompt.ask("  Enter quantity")

        # Step 5: Price (conditional)
        price = None
        stop_price_val = None

        if order_type in ("LIMIT", "STOP_LIMIT"):
            console.print("\n[bold cyan]Step 5/5:[/bold cyan] Price")
            if current_price:
                console.print(f"  [dim]Reference price: {fmt_price(current_price)} USDT[/dim]")
            price = FloatPrompt.ask("  Enter limit price")

        if order_type == "STOP_LIMIT":
            stop_price_val = FloatPrompt.ask("  Enter stop/trigger price")

        # Show summary and confirm
        console.print()
        _print_request_summary(symbol, side, order_type, quantity, price, stop_price_val)

        if not Confirm.ask("\n  [bold yellow]Confirm order?[/bold yellow]"):
            console.print("\n  [dim]Order cancelled.[/dim]")
            raise typer.Exit()

        # Place order
        manager = OrderManager(client)
        with console.status("[bold cyan]Placing order...[/bold cyan]"):
            result = manager.place_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                stop_price=stop_price_val,
            )
        _print_response(result)

    except KeyboardInterrupt:
        console.print("\n\n  [dim]Cancelled.[/dim]")
        raise typer.Exit()
    except (ValidationError, BinanceAPIError, BinanceNetworkError) as exc:
        _handle_error(exc)


# ------------------------------------------------------------------ #
#  Command: account                                                    #
# ------------------------------------------------------------------ #


@app.command()
def account() -> None:
    """View account balance, margin, and open positions."""
    print_banner()
    client = _get_client()

    try:
        with console.status("[bold cyan]Fetching account data...[/bold cyan]"):
            acct = client.get_account()

        # Account summary
        summary = Table(title="Account Summary", header_style="bold cyan", border_style="cyan")
        summary.add_column("Metric", style="bold")
        summary.add_column("Value", justify="right")

        summary.add_row("Total Balance", f"{fmt_price(acct.get('totalWalletBalance', '0'))} USDT")
        summary.add_row("Available Balance", f"{fmt_price(acct.get('availableBalance', '0'))} USDT")
        summary.add_row("Total Margin Balance", f"{fmt_price(acct.get('totalMarginBalance', '0'))} USDT")
        summary.add_row("Unrealized PnL", fmt_pnl(acct.get("totalUnrealizedProfit", "0")))
        summary.add_row("Total Maint. Margin", f"{fmt_price(acct.get('totalMaintMargin', '0'))} USDT")

        console.print()
        console.print(summary)

        # Non-zero balances
        assets = [a for a in acct.get("assets", []) if float(a.get("walletBalance", 0)) > 0]
        if assets:
            bal_table = Table(title="Asset Balances", header_style="bold green", border_style="green")
            bal_table.add_column("Asset", style="bold")
            bal_table.add_column("Wallet Balance", justify="right")
            bal_table.add_column("Available", justify="right")
            bal_table.add_column("Unrealized PnL", justify="right")

            for a in assets:
                bal_table.add_row(
                    a.get("asset", ""),
                    fmt_price(a.get("walletBalance", "0")),
                    fmt_price(a.get("availableBalance", "0")),
                    fmt_pnl(a.get("unrealizedProfit", "0")),
                )

            console.print()
            console.print(bal_table)

        # Open positions
        positions = [p for p in acct.get("positions", []) if float(p.get("positionAmt", 0)) != 0]
        if positions:
            pos_table = Table(title="Open Positions", header_style="bold yellow", border_style="yellow")
            pos_table.add_column("Symbol", style="bold")
            pos_table.add_column("Side")
            pos_table.add_column("Size", justify="right")
            pos_table.add_column("Entry Price", justify="right")
            pos_table.add_column("Mark Price", justify="right")
            pos_table.add_column("Unrealized PnL", justify="right")
            pos_table.add_column("Leverage")

            for p in positions:
                amt = float(p.get("positionAmt", 0))
                side_str = "LONG" if amt > 0 else "SHORT"
                side_colour = "green" if amt > 0 else "red"
                pos_table.add_row(
                    p.get("symbol", ""),
                    f"[bold {side_colour}]{side_str}[/bold {side_colour}]",
                    fmt_quantity(abs(amt)),
                    fmt_price(p.get("entryPrice", "0")),
                    fmt_price(p.get("markPrice", "0")),
                    fmt_pnl(p.get("unrealizedProfit", "0")),
                    f"{p.get('leverage', '1')}x",
                )

            console.print()
            console.print(pos_table)
        else:
            console.print("\n[dim]No open positions.[/dim]")

    except (BinanceAPIError, BinanceNetworkError) as exc:
        _handle_error(exc)


# ------------------------------------------------------------------ #
#  Command: prices                                                     #
# ------------------------------------------------------------------ #


@app.command()
def prices(
    symbols: Optional[List[str]] = typer.Option(
        ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"],
        "--symbols",
        help="Symbols to track (space-separated)",
    ),
    live: bool = typer.Option(False, "--live", "-l", help="Stream live prices via WebSocket"),
) -> None:
    """View current prices or stream live updates via WebSocket."""
    print_banner()

    if live:
        _live_price_stream(symbols)
    else:
        _snapshot_prices(symbols)


def _snapshot_prices(symbols: List[str]) -> None:
    """Fetch and display current prices (one-shot)."""
    client = _get_client()

    try:
        with console.status("[bold cyan]Fetching prices...[/bold cyan]"):
            all_tickers = client.get_ticker_24h()

        # Filter to requested symbols
        symbol_set = {s.upper() for s in symbols}
        tickers = [t for t in all_tickers if t.get("symbol") in symbol_set]

        table = Table(title="Market Prices (24h)", header_style="bold magenta", border_style="magenta")
        table.add_column("Symbol", style="bold")
        table.add_column("Price", justify="right")
        table.add_column("24h Change", justify="right")
        table.add_column("24h %", justify="right")
        table.add_column("24h High", justify="right")
        table.add_column("24h Low", justify="right")
        table.add_column("Volume", justify="right")

        for t in tickers:
            table.add_row(
                t.get("symbol", ""),
                fmt_price(t.get("lastPrice", "0")),
                fmt_pnl(t.get("priceChange", "0")),
                fmt_percent(t.get("priceChangePercent", "0")),
                fmt_price(t.get("highPrice", "0")),
                fmt_price(t.get("lowPrice", "0")),
                fmt_price(float(t.get("quoteVolume", 0)), decimals=0),
            )

        console.print()
        console.print(table)

    except (BinanceAPIError, BinanceNetworkError) as exc:
        _handle_error(exc)


def _live_price_stream(symbols: List[str]) -> None:
    """Stream live prices via WebSocket."""
    from rich.live import Live
    from bot.websocket_feed import PriceFeed

    console.print("[bold cyan]Starting live price stream...[/bold cyan]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    feed = PriceFeed(symbols=symbols)
    feed.start()

    # Wait a moment for initial data
    time.sleep(2)

    try:
        with Live(console=console, refresh_per_second=2, screen=False) as live:
            while True:
                table = Table(
                    title="Live Prices (WebSocket)",
                    header_style="bold magenta",
                    border_style="magenta",
                )
                table.add_column("Symbol", style="bold")
                table.add_column("Price", justify="right")
                table.add_column("24h %", justify="right")
                table.add_column("24h High", justify="right")
                table.add_column("24h Low", justify="right")

                tickers = feed.tickers
                for sym in symbols:
                    ticker = tickers.get(sym.upper())
                    if ticker:
                        table.add_row(
                            sym.upper(),
                            fmt_price(ticker.price),
                            fmt_percent(ticker.price_change_pct),
                            fmt_price(ticker.high_24h),
                            fmt_price(ticker.low_24h),
                        )
                    else:
                        table.add_row(sym.upper(), "[dim]connecting...[/dim]", "-", "-", "-")

                live.update(table)
                time.sleep(0.5)

    except KeyboardInterrupt:
        console.print("\n[dim]Stream stopped.[/dim]")
    finally:
        feed.stop()


# ------------------------------------------------------------------ #
#  Command: history                                                    #
# ------------------------------------------------------------------ #


@app.command()
def history(
    symbol: str = typer.Option("BTCUSDT", "--symbol", "-s", help="Trading pair"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of orders to show"),
) -> None:
    """View recent order history for a symbol."""
    print_banner()
    client = _get_client()

    try:
        with console.status(f"[bold cyan]Fetching order history for {symbol.upper()}...[/bold cyan]"):
            orders = client.get_all_orders(symbol=symbol.upper(), limit=limit)

        if not orders:
            console.print(f"\n[dim]No orders found for {symbol.upper()}.[/dim]")
            return

        # Sort newest first
        orders.sort(key=lambda o: o.get("time", 0), reverse=True)

        table = Table(
            title=f"Order History -- {symbol.upper()} (last {len(orders)})",
            header_style="bold green",
            border_style="green",
        )
        table.add_column("Order ID", style="dim")
        table.add_column("Type")
        table.add_column("Side")
        table.add_column("Qty", justify="right")
        table.add_column("Price", justify="right")
        table.add_column("Executed", justify="right")
        table.add_column("Avg Price", justify="right")
        table.add_column("Status")
        table.add_column("Time")

        for o in orders:
            table.add_row(
                str(o.get("orderId", "")),
                o.get("type", ""),
                fmt_side(o.get("side", "")),
                fmt_quantity(o.get("origQty", "0")),
                fmt_price(o.get("price", "0")),
                fmt_quantity(o.get("executedQty", "0")),
                fmt_price(o.get("avgPrice", "0")),
                fmt_status(o.get("status", "")),
                fmt_timestamp(o.get("time")),
            )

        console.print()
        console.print(table)

    except (BinanceAPIError, BinanceNetworkError) as exc:
        _handle_error(exc)


# ------------------------------------------------------------------ #
#  Command: cancel                                                     #
# ------------------------------------------------------------------ #


@app.command()
def cancel(
    symbol: str = typer.Option(..., "--symbol", "-s", help="Trading pair"),
    order_id: int = typer.Option(..., "--order-id", help="Order ID to cancel"),
) -> None:
    """Cancel an open order."""
    print_banner()
    client = _get_client()

    try:
        with console.status(f"[bold cyan]Cancelling order {order_id}...[/bold cyan]"):
            result = client.cancel_order(symbol=symbol.upper(), order_id=order_id)

        console.print(
            Panel(
                f"[bold green]Order {result.get('orderId', order_id)} cancelled successfully![/bold green]\n"
                f"[dim]Symbol: {result.get('symbol', symbol)} | "
                f"Status: {result.get('status', 'CANCELED')}[/dim]",
                title="Cancelled",
                border_style="green",
            )
        )

    except (BinanceAPIError, BinanceNetworkError) as exc:
        _handle_error(exc)


# ------------------------------------------------------------------ #
#  Command: dashboard                                                  #
# ------------------------------------------------------------------ #


@app.command()
def dashboard(
    symbols: Optional[List[str]] = typer.Option(
        ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
        "--symbols",
        help="Symbols to watch in the dashboard",
    ),
) -> None:
    """Launch the full TUI dashboard with live data."""
    print_banner()
    from bot.dashboard import Dashboard

    client = _get_client()
    dash = Dashboard(client=client, watch_symbols=symbols)
    dash.run()


# ------------------------------------------------------------------ #
#  Entrypoint                                                          #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    app()
