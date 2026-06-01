#!/usr/bin/env python3
"""
CLI entry point for the Binance Futures Testnet Trading Bot.

Uses Typer for argument parsing and Rich for coloured, tabular output.

Usage examples
--------------
  python cli.py order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01
  python cli.py order --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.5 --price 3000
  python cli.py order --symbol BTCUSDT --side BUY --type STOP_LIMIT --quantity 0.01 --price 68000 --stop-price 67500
"""

from __future__ import annotations

import os
import sys

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from bot.client import BinanceAPIError, BinanceClient, BinanceNetworkError
from bot.logging_config import setup_logging
from bot.orders import OrderManager
from bot.validators import ValidationError

# ------------------------------------------------------------------ #
#  Bootstrap                                                           #
# ------------------------------------------------------------------ #

load_dotenv()
setup_logging()

console = Console()
app = typer.Typer(
    name="trading-bot",
    help="Binance Futures Testnet Trading Bot — place MARKET, LIMIT, and STOP_LIMIT orders.",
    add_completion=False,
    rich_markup_mode="rich",
)


def _get_client() -> BinanceClient:
    """Build a ``BinanceClient`` from environment variables."""
    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    if not api_key or not api_secret:
        console.print(
            "[bold red]Error:[/bold red] BINANCE_API_KEY and BINANCE_API_SECRET "
            "must be set in the environment or in a .env file."
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
        title="📋 Order Request",
        show_header=True,
        header_style="bold cyan",
        border_style="cyan",
    )
    table.add_column("Parameter", style="bold")
    table.add_column("Value")

    table.add_row("Symbol", symbol.upper())
    side_colour = "green" if side.upper() == "BUY" else "red"
    table.add_row("Side", f"[{side_colour}]{side.upper()}[/{side_colour}]")
    table.add_row("Type", order_type.upper())
    table.add_row("Quantity", str(quantity))
    if price is not None:
        table.add_row("Price", str(price))
    if stop_price is not None:
        table.add_row("Stop Price", str(stop_price))

    console.print()
    console.print(table)


def _print_response(result) -> None:  # noqa: ANN001
    """Render the API response in a rich table."""
    table = Table(
        title="✅ Order Response",
        show_header=True,
        header_style="bold green",
        border_style="green",
    )
    table.add_column("Field", style="bold")
    table.add_column("Value")

    table.add_row("Order ID", str(result.order_id))
    table.add_row("Symbol", result.symbol)

    side_colour = "green" if result.side == "BUY" else "red"
    table.add_row("Side", f"[{side_colour}]{result.side}[/{side_colour}]")
    table.add_row("Type", result.order_type)
    table.add_row("Status", f"[bold yellow]{result.status}[/bold yellow]")
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
            border_style="green",
        )
    )


# ------------------------------------------------------------------ #
#  CLI command                                                         #
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
    # --- Show request summary -----------------------------------------
    _print_request_summary(symbol, side, order_type, quantity, price, stop_price)

    # --- Build client & manager ---------------------------------------
    client = _get_client()
    manager = OrderManager(client)

    # --- Place order --------------------------------------------------
    try:
        with console.status("[bold cyan]Placing order on Binance Futures Testnet…[/bold cyan]"):
            result = manager.place_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                stop_price=stop_price,
            )
        _print_response(result)

    except ValidationError as exc:
        console.print(f"\n[bold red]Validation Error:[/bold red] {exc}")
        raise typer.Exit(code=1)

    except BinanceAPIError as exc:
        console.print(f"\n[bold red]API Error ({exc.code}):[/bold red] {exc.message}")
        raise typer.Exit(code=1)

    except BinanceNetworkError as exc:
        console.print(f"\n[bold red]Network Error:[/bold red] {exc}")
        raise typer.Exit(code=1)


# ------------------------------------------------------------------ #
#  Entrypoint                                                          #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    app()
