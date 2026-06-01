"""
WebSocket price feed for Binance Futures Testnet.

Connects to the Binance Futures WebSocket stream and provides
real-time ticker data (price, 24h change, volume) via callbacks.
Supports multiple symbol subscriptions and automatic reconnection.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Binance Futures Testnet WebSocket endpoint
WS_BASE_URL = "wss://stream.binancefuture.com/ws"


@dataclass
class TickerData:
    """Snapshot of a single symbol's ticker."""

    symbol: str = ""
    price: float = 0.0
    price_change: float = 0.0
    price_change_pct: float = 0.0
    high_24h: float = 0.0
    low_24h: float = 0.0
    volume_24h: float = 0.0
    quote_volume_24h: float = 0.0
    last_update: float = 0.0

    @classmethod
    def from_ws_message(cls, data: Dict[str, Any]) -> "TickerData":
        """Parse a 24hr ticker WebSocket message."""
        return cls(
            symbol=data.get("s", ""),
            price=float(data.get("c", 0)),
            price_change=float(data.get("p", 0)),
            price_change_pct=float(data.get("P", 0)),
            high_24h=float(data.get("h", 0)),
            low_24h=float(data.get("l", 0)),
            volume_24h=float(data.get("v", 0)),
            quote_volume_24h=float(data.get("q", 0)),
            last_update=time.time(),
        )


class PriceFeed:
    """Real-time price feed using Binance WebSocket streams.

    Parameters
    ----------
    symbols:
        List of trading pairs to subscribe to (e.g., ["BTCUSDT", "ETHUSDT"]).
    on_ticker:
        Optional callback invoked with a ``TickerData`` on each update.
    """

    def __init__(
        self,
        symbols: List[str],
        on_ticker: Optional[Callable[[TickerData], None]] = None,
    ) -> None:
        self._symbols = [s.lower() for s in symbols]
        self._on_ticker = on_ticker
        self._tickers: Dict[str, TickerData] = {}
        self._ws = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

    @property
    def tickers(self) -> Dict[str, TickerData]:
        """Current ticker snapshots keyed by uppercase symbol."""
        with self._lock:
            return dict(self._tickers)

    def get_price(self, symbol: str) -> Optional[float]:
        """Get the latest price for a symbol, or None."""
        with self._lock:
            ticker = self._tickers.get(symbol.upper())
            return ticker.price if ticker else None

    def start(self) -> None:
        """Start the WebSocket feed in a background thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Price feed started for symbols: %s", self._symbols)

    def stop(self) -> None:
        """Stop the WebSocket feed."""
        self._running = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("Price feed stopped.")

    def _run(self) -> None:
        """Main WebSocket loop with reconnection."""
        try:
            import websocket
        except ImportError:
            logger.error(
                "websocket-client package not installed. "
                "Install with: pip install websocket-client"
            )
            self._running = False
            return

        streams = "/".join(f"{s}@ticker" for s in self._symbols)
        url = f"{WS_BASE_URL}/{streams}"

        while self._running:
            try:
                logger.debug("Connecting to WebSocket: %s", url)
                self._ws = websocket.WebSocketApp(
                    url,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                    on_open=self._on_open,
                )
                self._ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception as exc:
                logger.error("WebSocket error: %s", exc)

            if self._running:
                logger.info("Reconnecting in 3 seconds...")
                time.sleep(3)

    def _on_open(self, ws: Any) -> None:
        logger.info("WebSocket connected.")

    def _on_message(self, ws: Any, message: str) -> None:
        try:
            data = json.loads(message)

            # Handle combined stream format
            if "data" in data:
                data = data["data"]

            if "e" in data and data["e"] == "24hrTicker":
                ticker = TickerData.from_ws_message(data)
                with self._lock:
                    self._tickers[ticker.symbol] = ticker

                if self._on_ticker:
                    self._on_ticker(ticker)

        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.debug("Failed to parse WebSocket message: %s", exc)

    def _on_error(self, ws: Any, error: Any) -> None:
        logger.error("WebSocket error: %s", error)

    def _on_close(self, ws: Any, close_status: Any = None, close_msg: Any = None) -> None:
        logger.info("WebSocket closed (status=%s, msg=%s)", close_status, close_msg)
