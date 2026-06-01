# Binance Futures Testnet Trading Bot

A **production-grade** Python CLI application for placing orders on [Binance Futures Testnet](https://testnet.binancefuture.com) (USDT-M), featuring an interactive TUI dashboard, live WebSocket prices, and comprehensive error handling.

---

## Highlights

| Feature | Description |
|---|---|
| **7 CLI Commands** | `order`, `interactive`, `account`, `prices`, `history`, `cancel`, `dashboard` |
| **3 Order Types** | Market, Limit, Stop-Limit |
| **Live Price Feed** | Real-time WebSocket streaming with auto-reconnect |
| **TUI Dashboard** | Rich Live terminal UI with account, prices, positions, orders |
| **Interactive Mode** | Step-by-step guided order placement with live price context |
| **Retry + Backoff** | Exponential backoff (1s/2s/4s) for transient failures |
| **Rate Limiter** | Thread-safe sliding-window limiter (1200 req/min) |
| **Unit Tests** | pytest suite with mocked API for validators, client, and orders |
| **Structured Logging** | Rotating file handler with full request/response audit trail |
| **Modern Packaging** | `pyproject.toml` with entry points and dev dependency groups |

---

## Architecture

```
                         +------------------+
                         |     CLI Layer    |
                         |    (cli.py)      |
                         | 7 Typer commands |
                         +--------+---------+
                                  |
              +-------------------+-------------------+
              |                   |                   |
     +--------v--------+ +-------v--------+ +--------v--------+
     |   OrderManager  | |   Dashboard    | |   PriceFeed     |
     |   (orders.py)   | | (dashboard.py) | | (websocket.py)  |
     +--------+--------+ +-------+--------+ +--------+--------+
              |                   |                   |
              +-------------------+                   |
              |                                       |
     +--------v--------+                    +---------v--------+
     |  BinanceClient  |                    |  WebSocket API   |
     |  (client.py)    |                    |  (wss://stream)  |
     |  - HMAC signing |                    +------------------+
     |  - Retry/backoff|
     |  - Rate limiting|
     +--------+--------+
              |
     +--------v--------+
     | Binance Testnet  |
     | REST API (HTTPS) |
     +------------------+
```

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py           # Package marker (v2.0.0)
│   ├── client.py             # REST client: HMAC signing, retry, rate limit
│   ├── orders.py             # OrderManager + OrderResult dataclass
│   ├── validators.py         # Input validation with clear error messages
│   ├── logging_config.py     # Rotating file + console logging
│   ├── dashboard.py          # Rich Live TUI dashboard
│   ├── websocket_feed.py     # WebSocket price streaming
│   └── utils.py              # Banner, formatters, config helpers
├── tests/
│   ├── __init__.py
│   ├── test_validators.py    # 15+ parametrized test cases
│   ├── test_client.py        # Mocked HTTP, retry, rate limiter tests
│   └── test_orders.py        # Order placement with mocked client
├── sample_logs/
│   ├── market_order.log      # Sample MARKET order log
│   ├── limit_order.log       # Sample LIMIT order log
│   └── error_handling.log    # Retry, validation, API error logs
├── cli.py                    # Typer CLI entry point (7 commands)
├── pyproject.toml            # PEP 621 packaging + pytest config
├── requirements.txt          # Production dependencies
├── .env.example              # API credentials template
├── .gitignore
└── README.md
```

---

## Setup

### Prerequisites

- **Python 3.10+**
- A [Binance Futures Testnet](https://testnet.binancefuture.com) account
- Testnet API key & secret (generate from the testnet dashboard)

### Installation

```bash
git clone <repository-url>
cd trading_bot

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# (Optional) Install dev dependencies for testing
pip install -e ".[dev]"
```

### Configure API Credentials

```bash
# Copy the template
cp .env.example .env            # Linux/macOS
copy .env.example .env          # Windows

# Edit .env with your testnet credentials
BINANCE_API_KEY=your_testnet_api_key
BINANCE_API_SECRET=your_testnet_api_secret
```

> **Warning**: Never commit your `.env` file. It is already in `.gitignore`.

---

## Usage

All commands are run from the `trading_bot/` directory.

### Quick Reference

| Command | Description |
|---|---|
| `python cli.py order` | Place an order via CLI flags |
| `python cli.py interactive` | Guided step-by-step order placement |
| `python cli.py account` | View account balance and positions |
| `python cli.py prices` | View current market prices |
| `python cli.py prices --live` | Stream real-time prices via WebSocket |
| `python cli.py history` | View recent order history |
| `python cli.py cancel` | Cancel an open order |
| `python cli.py dashboard` | Launch full TUI dashboard |

---

### Place a Market Order

```bash
python cli.py order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01
```

### Place a Limit Order

```bash
python cli.py order --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.5 --price 3000
```

### Place a Stop-Limit Order

```bash
python cli.py order --symbol BTCUSDT --side BUY --type STOP_LIMIT \
  --quantity 0.01 --price 68000 --stop-price 67500
```

### Interactive Mode

Walk through order placement step-by-step with validation and live price context:

```bash
python cli.py interactive
```

```
Step 1/5: Trading Pair
  Enter symbol [BTCUSDT]:
  Current price: 67,532.10 USDT

Step 2/5: Order Side
  Select side (BUY/SELL) [BUY]:

Step 3/5: Order Type
  Select type (MARKET/LIMIT/STOP_LIMIT) [MARKET]:

Step 4/5: Quantity
  Enter quantity: 0.01

  Confirm order? [y/N]: y
```

### Account Dashboard

```bash
python cli.py account
```

Shows: total balance, available margin, unrealized PnL, asset breakdown, and open positions.

### Live Price Stream

```bash
# One-shot price check
python cli.py prices --symbols BTCUSDT ETHUSDT SOLUSDT

# Real-time WebSocket stream
python cli.py prices --symbols BTCUSDT ETHUSDT --live
```

### Order History

```bash
python cli.py history --symbol BTCUSDT --limit 10
```

### Cancel an Order

```bash
python cli.py cancel --symbol BTCUSDT --order-id 4820468061
```

### Full TUI Dashboard

```bash
python cli.py dashboard --symbols BTCUSDT ETHUSDT SOLUSDT
```

Launches a live terminal dashboard with four panels:
- **Account**: Balance, margin, unrealized PnL
- **Live Prices**: WebSocket real-time ticker
- **Positions**: Open positions with entry price and PnL
- **Recent Orders**: Latest orders across watched symbols

---

## Example Output

```
+-----------------------------------------------------------+
|                                                           |
|   _____ ____      _    ____  ___ _   _  ____   ____  ___ |
|  |_   _|  _ \    / \  |  _ \|_ _| \ | |/ ___| | __ )/ _ \|
|    | | | |_) |  / _ \ | | | || ||  \| | |  _  |  _ \| | ||
|    | | |  _ <  / ___ \| |_| || || |\  | |_| | | |_) | |_||
|    |_| |_| \_\/_/   \_\____/___|_| \_|\____| |____/ \___||
|                                                           |
|              v2.0.0 | Binance Futures Testnet | USDT-M    |
+-----------------------------------------------------------+

          Order Request
+---------------------------+
| Parameter | Value         |
|-----------+---------------|
| Symbol    | BTCUSDT       |
| Side      | BUY           |
| Type      | MARKET        |
| Quantity  | 0.0100        |
+---------------------------+

          Order Response
+-------------------------------+
| Field        | Value          |
|--------------+----------------|
| Order ID     | 4820468061     |
| Symbol       | BTCUSDT        |
| Side         | BUY            |
| Type         | MARKET         |
| Status       | FILLED         |
| Original Qty | 0.010          |
| Executed Qty | 0.010          |
| Avg Price    | 67532.10       |
+-------------------------------+

+--------------------------------------------+
| Success                                    |
|   Order 4820468061 placed successfully!    |
+--------------------------------------------+
```

---

## Testing

```bash
# Install dev dependencies
pip install pytest pytest-mock pytest-cov

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=bot --cov-report=term-missing
```

### Test Coverage

| Module | Tests |
|---|---|
| `validators.py` | 15+ cases: symbols, sides, types, quantities, prices |
| `client.py` | HMAC signing, HTTP errors, retry, timeout, rate limiter |
| `orders.py` | Market/Limit/Stop-Limit orders, dispatcher, validation |

---

## Logging

All API activity is logged to `logs/trading_bot.log` (auto-created).

| Handler | Level | Purpose |
|---|---|---|
| File (rotating) | DEBUG | Full request/response audit trail |
| Console | INFO | Order confirmations and errors only |

- **Rotation**: 5 MB per file, 3 backup files
- **Format**: `timestamp | level | module | message`

### Sample Logs

Pre-generated sample logs are available in `sample_logs/`:
- `market_order.log` — Successful MARKET BUY
- `limit_order.log` — LIMIT SELL placement
- `error_handling.log` — Validation, API, network, and retry scenarios

---

## Error Handling

| Category | Mechanism | Example |
|---|---|---|
| **Input Validation** | `ValidationError` before API call | Missing price for LIMIT |
| **API Errors** | `BinanceAPIError` with code + message | Invalid symbol (-1121) |
| **Network Failures** | `BinanceNetworkError` | Timeout, DNS failure |
| **Transient Errors** | Retry with exponential backoff | 500/502/503/429 responses |
| **Rate Limits** | Local sliding-window limiter | 1200 requests/minute cap |

---

## Production-Grade Features

### Retry with Exponential Backoff
- 3 retries with 1s, 2s, 4s delays
- Retries on: HTTP 429, 500, 502, 503, 504
- Retries on: `ConnectionError`, `Timeout`
- Fresh timestamp/signature on each retry attempt

### Rate Limiter
- Thread-safe sliding-window algorithm
- Configurable limit (default: 1200 requests/minute)
- Proactive blocking before hitting Binance server limits

### WebSocket Price Feed
- Real-time 24hr ticker data (price, change, volume)
- Multi-symbol subscription
- Automatic reconnection with 3-second backoff
- Thread-safe ticker data access

---

## Assumptions

1. **Testnet only** — base URL is `https://testnet.binancefuture.com` (not for production)
2. **USDT-M futures** — symbol validation expects pairs ending in USDT
3. **No position management** — places orders but does not auto-close positions
4. **Time-in-force** defaults to GTC (Good Till Cancel) for Limit/Stop-Limit
5. **Single-user** — designed for single-user CLI usage, not concurrent

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `requests` | >=2.31.0 | HTTP client for REST API |
| `typer[all]` | >=0.9.0 | CLI framework with rich help |
| `rich` | >=13.0.0 | Terminal UI: tables, panels, live display |
| `python-dotenv` | >=1.0.0 | Load `.env` credentials |
| `websocket-client` | >=1.6.0 | WebSocket streaming for live prices |

### Dev Dependencies
| Package | Purpose |
|---|---|
| `pytest` | Test framework |
| `pytest-mock` | Mock fixtures |
| `pytest-cov` | Coverage reporting |

---

## License

This project is for educational / assessment purposes and is provided as-is.
