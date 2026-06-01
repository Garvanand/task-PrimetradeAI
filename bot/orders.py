"""
Order placement logic.

``OrderManager`` validates inputs, builds API parameters, and delegates
to ``BinanceClient``.  Results are returned as ``OrderResult`` dataclass
instances for structured downstream consumption.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from bot.client import BinanceClient
from bot.validators import (
    ORDER_TYPE_API_MAP,
    validate_order_type,
    validate_price,
    validate_quantity,
    validate_side,
    validate_stop_price,
    validate_symbol,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
#  Result dataclass                                                    #
# ------------------------------------------------------------------ #


@dataclass
class OrderResult:
    """Structured representation of an order response."""

    order_id: int
    symbol: str
    side: str
    order_type: str
    status: str
    orig_qty: str
    executed_qty: str
    avg_price: str
    price: str
    stop_price: str = ""
    time_in_force: str = ""
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "OrderResult":
        return cls(
            order_id=data.get("orderId", 0),
            symbol=data.get("symbol", ""),
            side=data.get("side", ""),
            order_type=data.get("type", ""),
            status=data.get("status", ""),
            orig_qty=str(data.get("origQty", "")),
            executed_qty=str(data.get("executedQty", "")),
            avg_price=str(data.get("avgPrice", "0")),
            price=str(data.get("price", "0")),
            stop_price=str(data.get("stopPrice", "")),
            time_in_force=str(data.get("timeInForce", "")),
            raw=data,
        )


# ------------------------------------------------------------------ #
#  Order Manager                                                       #
# ------------------------------------------------------------------ #


class OrderManager:
    """High-level order placement facade.

    Parameters
    ----------
    client:
        An initialised ``BinanceClient`` instance.
    """

    def __init__(self, client: BinanceClient) -> None:
        self._client = client

    # ----- public methods ------------------------------------------ #

    def market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
    ) -> OrderResult:
        """Place a MARKET order."""
        symbol = validate_symbol(symbol)
        side = validate_side(side)
        quantity = validate_quantity(quantity)

        params = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": quantity,
        }

        logger.info("Placing MARKET %s order: %s qty=%s", side, symbol, quantity)
        data = self._client.place_order(**params)
        result = OrderResult.from_api_response(data)
        logger.info("Order placed — ID: %s, Status: %s", result.order_id, result.status)
        return result

    def limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        time_in_force: str = "GTC",
    ) -> OrderResult:
        """Place a LIMIT order."""
        symbol = validate_symbol(symbol)
        side = validate_side(side)
        quantity = validate_quantity(quantity)
        price = validate_price(price, "LIMIT")

        params = {
            "symbol": symbol,
            "side": side,
            "type": "LIMIT",
            "quantity": quantity,
            "price": price,
            "timeInForce": time_in_force,
        }

        logger.info(
            "Placing LIMIT %s order: %s qty=%s price=%s",
            side, symbol, quantity, price,
        )
        data = self._client.place_order(**params)
        result = OrderResult.from_api_response(data)
        logger.info("Order placed — ID: %s, Status: %s", result.order_id, result.status)
        return result

    def stop_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        stop_price: float,
        time_in_force: str = "GTC",
    ) -> OrderResult:
        """Place a STOP-LIMIT (STOP) order on Binance Futures."""
        symbol = validate_symbol(symbol)
        side = validate_side(side)
        quantity = validate_quantity(quantity)
        price = validate_price(price, "STOP_LIMIT")
        stop_price = validate_stop_price(stop_price, "STOP_LIMIT")

        params = {
            "symbol": symbol,
            "side": side,
            "type": "STOP",  # Binance Futures uses "STOP" for stop-limit
            "quantity": quantity,
            "price": price,
            "stopPrice": stop_price,
            "timeInForce": time_in_force,
        }

        logger.info(
            "Placing STOP_LIMIT %s order: %s qty=%s price=%s stop=%s",
            side, symbol, quantity, price, stop_price,
        )
        data = self._client.place_order(**params)
        result = OrderResult.from_api_response(data)
        logger.info("Order placed — ID: %s, Status: %s", result.order_id, result.status)
        return result

    # ----- dispatcher ---------------------------------------------- #

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> OrderResult:
        """Dispatch to the correct order method based on ``order_type``."""
        order_type = validate_order_type(order_type)

        if order_type == "MARKET":
            return self.market_order(symbol, side, quantity)
        elif order_type == "LIMIT":
            return self.limit_order(symbol, side, quantity, price)  # type: ignore[arg-type]
        elif order_type == "STOP_LIMIT":
            return self.stop_limit_order(symbol, side, quantity, price, stop_price)  # type: ignore[arg-type]
        else:
            raise ValueError(f"Unsupported order type: {order_type}")
