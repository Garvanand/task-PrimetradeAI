"""
Input validators for order parameters.

Each validator raises ``ValidationError`` with a human-readable message
when the input is invalid.  They are intentionally strict so that bad
data never reaches the Binance API.
"""

from __future__ import annotations

import re


class ValidationError(Exception):
    """Raised when user input fails validation."""


# ------------------------------------------------------------------ #
#  Symbol                                                              #
# ------------------------------------------------------------------ #

_SYMBOL_RE = re.compile(r"^[A-Z]{2,10}USDT$")


def validate_symbol(symbol: str) -> str:
    """Return the uppercased symbol if it looks like a valid USDT-M pair.

    Accepts strings like ``BTCUSDT``, ``ETHUSDT``, ``SOLUSDT``.
    """
    symbol = symbol.strip().upper()
    if not _SYMBOL_RE.match(symbol):
        raise ValidationError(
            f"Invalid symbol '{symbol}'. "
            "Expected an uppercase USDT-M pair like BTCUSDT or ETHUSDT."
        )
    return symbol


# ------------------------------------------------------------------ #
#  Side                                                                #
# ------------------------------------------------------------------ #

_VALID_SIDES = {"BUY", "SELL"}


def validate_side(side: str) -> str:
    """Return the uppercased side if it is BUY or SELL."""
    side = side.strip().upper()
    if side not in _VALID_SIDES:
        raise ValidationError(
            f"Invalid side '{side}'. Must be BUY or SELL."
        )
    return side


# ------------------------------------------------------------------ #
#  Order type                                                          #
# ------------------------------------------------------------------ #

_VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_LIMIT"}

# Binance API uses "STOP" for stop-limit on futures
ORDER_TYPE_API_MAP = {
    "MARKET": "MARKET",
    "LIMIT": "LIMIT",
    "STOP_LIMIT": "STOP",
}


def validate_order_type(order_type: str) -> str:
    """Return the uppercased order type if it is MARKET, LIMIT, or STOP_LIMIT."""
    order_type = order_type.strip().upper()
    if order_type not in _VALID_ORDER_TYPES:
        raise ValidationError(
            f"Invalid order type '{order_type}'. "
            "Must be MARKET, LIMIT, or STOP_LIMIT."
        )
    return order_type


# ------------------------------------------------------------------ #
#  Quantity                                                            #
# ------------------------------------------------------------------ #


def validate_quantity(quantity: float) -> float:
    """Return quantity if it is a positive number."""
    if quantity is None or quantity <= 0:
        raise ValidationError(
            f"Invalid quantity '{quantity}'. Must be a positive number."
        )
    return float(quantity)


# ------------------------------------------------------------------ #
#  Price                                                               #
# ------------------------------------------------------------------ #


def validate_price(price: float | None, order_type: str) -> float | None:
    """Validate price based on order type.

    - MARKET orders: price must be None (ignored).
    - LIMIT / STOP_LIMIT orders: price must be a positive number.
    """
    if order_type == "MARKET":
        return None  # price is irrelevant for market orders

    if price is None or price <= 0:
        raise ValidationError(
            f"Price is required and must be positive for {order_type} orders."
        )
    return float(price)


# ------------------------------------------------------------------ #
#  Stop price                                                          #
# ------------------------------------------------------------------ #


def validate_stop_price(stop_price: float | None, order_type: str) -> float | None:
    """Validate stop price — required only for STOP_LIMIT orders."""
    if order_type != "STOP_LIMIT":
        return None

    if stop_price is None or stop_price <= 0:
        raise ValidationError(
            "Stop price is required and must be positive for STOP_LIMIT orders."
        )
    return float(stop_price)
