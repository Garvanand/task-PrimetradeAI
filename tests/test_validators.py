"""
Tests for ``bot.validators`` module.

Covers every public validator with both valid (happy-path) and invalid
(error) inputs.  Uses ``pytest.mark.parametrize`` wherever a validator
accepts multiple discrete values.
"""

from __future__ import annotations

import pytest

from bot.validators import (
    ValidationError,
    validate_order_type,
    validate_price,
    validate_quantity,
    validate_side,
    validate_stop_price,
    validate_symbol,
)


# ================================================================== #
#  validate_symbol                                                     #
# ================================================================== #


class TestValidateSymbol:
    """Tests for ``validate_symbol``."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("BTCUSDT", "BTCUSDT"),
            ("ETHUSDT", "ETHUSDT"),
            ("SOLUSDT", "SOLUSDT"),
            ("btcusdt", "BTCUSDT"),       # lowercase input normalised
            ("ethusdt", "ETHUSDT"),
            ("  BTCUSDT  ", "BTCUSDT"),   # whitespace stripped
            ("XRPUSDT", "XRPUSDT"),
            ("DOGEUSDT", "DOGEUSDT"),
        ],
        ids=[
            "BTCUSDT-uppercase",
            "ETHUSDT-uppercase",
            "SOLUSDT-uppercase",
            "lowercase-btcusdt",
            "lowercase-ethusdt",
            "whitespace-stripped",
            "XRPUSDT-uppercase",
            "DOGEUSDT-uppercase",
        ],
    )
    def test_valid_symbols(self, raw: str, expected: str) -> None:
        """Valid USDT-M pairs are accepted and returned uppercased."""
        assert validate_symbol(raw) == expected

    @pytest.mark.parametrize(
        "bad_symbol",
        [
            "",                # empty string
            "USDT",            # too short — no base asset (needs 2+ chars before USDT)
            "12345",           # numbers only
            "BTC",             # no USDT suffix
            "BTCEUR",          # wrong quote asset
            "AUSDT",           # base part too short (1 char)
        ],
        ids=[
            "empty-string",
            "only-USDT",
            "numbers-only",
            "no-USDT-suffix",
            "wrong-quote-asset",
            "single-char-base",
        ],
    )
    def test_invalid_symbols(self, bad_symbol: str) -> None:
        """Invalid symbols raise ``ValidationError``."""
        with pytest.raises(ValidationError):
            validate_symbol(bad_symbol)


# ================================================================== #
#  validate_side                                                       #
# ================================================================== #


class TestValidateSide:
    """Tests for ``validate_side``."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("BUY", "BUY"),
            ("SELL", "SELL"),
            ("buy", "BUY"),
            ("sell", "SELL"),
            ("  BUY  ", "BUY"),
            ("  sell  ", "SELL"),
        ],
        ids=[
            "BUY-upper",
            "SELL-upper",
            "buy-lower",
            "sell-lower",
            "BUY-whitespace",
            "sell-whitespace",
        ],
    )
    def test_valid_sides(self, raw: str, expected: str) -> None:
        """BUY and SELL (case-insensitive) are accepted."""
        assert validate_side(raw) == expected

    @pytest.mark.parametrize(
        "bad_side",
        ["HOLD", "LONG", "SHORT", "", "123"],
        ids=["HOLD", "LONG", "SHORT", "empty", "numeric"],
    )
    def test_invalid_sides(self, bad_side: str) -> None:
        """Anything other than BUY / SELL raises ``ValidationError``."""
        with pytest.raises(ValidationError):
            validate_side(bad_side)


# ================================================================== #
#  validate_order_type                                                 #
# ================================================================== #


class TestValidateOrderType:
    """Tests for ``validate_order_type``."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("MARKET", "MARKET"),
            ("LIMIT", "LIMIT"),
            ("STOP_LIMIT", "STOP_LIMIT"),
            ("market", "MARKET"),
            ("limit", "LIMIT"),
            ("stop_limit", "STOP_LIMIT"),
        ],
        ids=[
            "MARKET-upper",
            "LIMIT-upper",
            "STOP_LIMIT-upper",
            "market-lower",
            "limit-lower",
            "stop_limit-lower",
        ],
    )
    def test_valid_order_types(self, raw: str, expected: str) -> None:
        """Recognised order types (case-insensitive) are accepted."""
        assert validate_order_type(raw) == expected

    @pytest.mark.parametrize(
        "bad_type",
        ["STOP", "TRAILING_STOP", "OCO", "", "FOK"],
        ids=["STOP", "TRAILING_STOP", "OCO", "empty", "FOK"],
    )
    def test_invalid_order_types(self, bad_type: str) -> None:
        """Unsupported order types raise ``ValidationError``."""
        with pytest.raises(ValidationError):
            validate_order_type(bad_type)


# ================================================================== #
#  validate_quantity                                                   #
# ================================================================== #


class TestValidateQuantity:
    """Tests for ``validate_quantity``."""

    @pytest.mark.parametrize(
        "qty",
        [0.001, 1.0, 100, 0.5, 999.99],
        ids=["tiny", "one", "hundred", "half", "large"],
    )
    def test_positive_quantities(self, qty: float) -> None:
        """Positive numbers are returned as floats."""
        result = validate_quantity(qty)
        assert result == float(qty)
        assert isinstance(result, float)

    @pytest.mark.parametrize(
        "bad_qty",
        [0, -1, -0.001],
        ids=["zero", "negative-int", "negative-float"],
    )
    def test_non_positive_quantities(self, bad_qty: float) -> None:
        """Zero and negative values raise ``ValidationError``."""
        with pytest.raises(ValidationError):
            validate_quantity(bad_qty)

    def test_none_quantity(self) -> None:
        """None raises ``ValidationError``."""
        with pytest.raises(ValidationError):
            validate_quantity(None)  # type: ignore[arg-type]


# ================================================================== #
#  validate_price                                                      #
# ================================================================== #


class TestValidatePrice:
    """Tests for ``validate_price``."""

    def test_market_order_returns_none(self) -> None:
        """MARKET orders ignore the price and return None."""
        assert validate_price(None, "MARKET") is None
        assert validate_price(12345.0, "MARKET") is None

    @pytest.mark.parametrize(
        "price",
        [0.01, 100.0, 67000.50],
        ids=["penny", "hundred", "btc-price"],
    )
    def test_positive_price_for_limit(self, price: float) -> None:
        """LIMIT orders accept positive prices."""
        result = validate_price(price, "LIMIT")
        assert result == float(price)

    @pytest.mark.parametrize(
        "price",
        [0.01, 100.0, 67000.50],
        ids=["penny", "hundred", "btc-price"],
    )
    def test_positive_price_for_stop_limit(self, price: float) -> None:
        """STOP_LIMIT orders accept positive prices."""
        result = validate_price(price, "STOP_LIMIT")
        assert result == float(price)

    def test_none_price_for_limit_raises(self) -> None:
        """Missing price for LIMIT raises ``ValidationError``."""
        with pytest.raises(ValidationError):
            validate_price(None, "LIMIT")

    def test_none_price_for_stop_limit_raises(self) -> None:
        """Missing price for STOP_LIMIT raises ``ValidationError``."""
        with pytest.raises(ValidationError):
            validate_price(None, "STOP_LIMIT")

    @pytest.mark.parametrize(
        "bad_price, order_type",
        [
            (0, "LIMIT"),
            (-10.0, "LIMIT"),
            (0, "STOP_LIMIT"),
            (-5, "STOP_LIMIT"),
        ],
        ids=["zero-LIMIT", "negative-LIMIT", "zero-STOP_LIMIT", "negative-STOP_LIMIT"],
    )
    def test_non_positive_prices_raise(self, bad_price: float, order_type: str) -> None:
        """Zero / negative prices raise ``ValidationError``."""
        with pytest.raises(ValidationError):
            validate_price(bad_price, order_type)


# ================================================================== #
#  validate_stop_price                                                 #
# ================================================================== #


class TestValidateStopPrice:
    """Tests for ``validate_stop_price``."""

    @pytest.mark.parametrize(
        "price",
        [0.01, 100.0, 65000.0],
        ids=["penny", "hundred", "btc-stop"],
    )
    def test_positive_stop_price_for_stop_limit(self, price: float) -> None:
        """STOP_LIMIT orders accept positive stop prices."""
        result = validate_stop_price(price, "STOP_LIMIT")
        assert result == float(price)

    def test_none_stop_price_for_stop_limit_raises(self) -> None:
        """Missing stop price for STOP_LIMIT raises ``ValidationError``."""
        with pytest.raises(ValidationError):
            validate_stop_price(None, "STOP_LIMIT")

    @pytest.mark.parametrize(
        "bad_price",
        [0, -1.0, -100],
        ids=["zero", "negative-float", "negative-int"],
    )
    def test_non_positive_stop_price_raises(self, bad_price: float) -> None:
        """Zero / negative stop prices raise ``ValidationError``."""
        with pytest.raises(ValidationError):
            validate_stop_price(bad_price, "STOP_LIMIT")

    @pytest.mark.parametrize(
        "order_type",
        ["MARKET", "LIMIT"],
        ids=["MARKET", "LIMIT"],
    )
    def test_ignored_for_non_stop_limit_orders(self, order_type: str) -> None:
        """Stop price is ignored (returns None) for non-STOP_LIMIT orders."""
        assert validate_stop_price(100.0, order_type) is None
        assert validate_stop_price(None, order_type) is None
