# Binance Futures Testnet Trading Bot

A Python CLI application for placing **Market**, **Limit**, and **Stop-Limit** orders on the [Binance Futures Testnet](https://testnet.binancefuture.com) (USDT-M).

## Features

- **Three order types**: Market, Limit, and Stop-Limit
- **Both sides**: BUY and SELL
- **Rich CLI output**: Coloured tables, spinners, and clear success/error messages
- **Structured logging**: Rotating log file with full API request/response audit trail
- **Input validation**: Strict checks before any data hits the network
- **Clean architecture**: Separate client → orders → CLI layers

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py          # Package marker
│   ├── client.py            # Binance REST client (HMAC signing, HTTP)
│   ├── orders.py            # Order placement logic & OrderResult dataclass
│   ├── validators.py        # Input validation with clear error messages
│   └── logging_config.py    # Rotating file + console logging setup
├── cli.py                   # Typer CLI entry point
├── .env.example             # Template for API credentials
├── .gitignore
├── requirements.txt
├── README.md
└── logs/                    # Auto-created; contains trading_bot.log
```

## Setup

### 1. Prerequisites

- Python 3.10+
- A Binance Futures Testnet account → [Register here](https://testnet.binancefuture.com)
- Testnet API key & secret → Generate from the testnet dashboard

### 2. Clone & Install

```bash
git clone <repository-url>
cd trading_bot

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure API Credentials

```bash
# Copy the template
cp .env.example .env

# Edit .env and fill in your testnet credentials
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
```

> **⚠️ Never commit your `.env` file.** It is already in `.gitignore`.

## Usage

All commands are run from the `trading_bot/` directory.

### Place a Market Order

```bash
python cli.py order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01
```

### Place a Limit Order

```bash
python cli.py order --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.5 --price 3000
```

### Place a Stop-Limit Order (Bonus)

```bash
python cli.py order \
  --symbol BTCUSDT \
  --side BUY \
  --type STOP_LIMIT \
  --quantity 0.01 \
  --price 68000 \
  --stop-price 67500
```

### View Help

```bash
python cli.py --help
python cli.py order --help
```

## Example Output

```
┏━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Parameter ┃ Value       ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ Symbol    │ BTCUSDT     │
│ Side      │ BUY         │
│ Type      │ MARKET      │
│ Quantity  │ 0.01        │
└───────────┴─────────────┘

┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┓
┃ Field        ┃ Value             ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━┩
│ Order ID     │ 123456789         │
│ Symbol       │ BTCUSDT           │
│ Side         │ BUY               │
│ Type         │ MARKET            │
│ Status       │ FILLED            │
│ Original Qty │ 0.01              │
│ Executed Qty │ 0.01              │
│ Avg Price    │ 67532.10          │
└──────────────┴───────────────────┘

╭─────────────────────────────────────────╮
│ Order 123456789 placed successfully!    │
╰─────────────────────────────────────────╯
```

## Logging

All API activity is logged to `logs/trading_bot.log` (auto-created).

- **File**: DEBUG level — full request params, response bodies, errors
- **Console**: INFO level — order confirmations and errors only
- **Rotation**: 5 MB per file, 3 backup files

### Sample Log Entry

```
2026-06-01 12:00:01 | INFO     | bot.orders | Placing MARKET BUY order: BTCUSDT qty=0.01
2026-06-01 12:00:01 | DEBUG    | bot.client | REQUEST  POST https://testnet.binancefuture.com/fapi/v1/order params={...}
2026-06-01 12:00:02 | DEBUG    | bot.client | RESPONSE 200 {"orderId":123456789,"status":"FILLED",...}
2026-06-01 12:00:02 | INFO     | bot.orders | Order placed — ID: 123456789, Status: FILLED
```

## Error Handling

The bot handles three categories of errors:

| Error Type | Example | Behaviour |
|---|---|---|
| **Validation** | Missing price for LIMIT order | Red error message, exit code 1 |
| **API Error** | Invalid symbol, insufficient balance | Shows Binance error code + message |
| **Network Error** | Timeout, DNS failure | Shows connection error details |

## Assumptions

1. **Testnet only** — the base URL is hardcoded to `https://testnet.binancefuture.com`. This bot is **not** intended for production trading.
2. **USDT-M futures** — symbol validation expects pairs ending in `USDT`.
3. **No position management** — the bot places orders but does not track or close positions.
4. **Time-in-force** defaults to `GTC` (Good Till Cancel) for Limit and Stop-Limit orders.
5. **No automatic retries** — transient network failures are reported immediately; the user can retry manually.

## Dependencies

| Package | Purpose |
|---|---|
| `requests` | HTTP client for REST API calls |
| `typer[all]` | CLI framework with auto-generated help |
| `rich` | Coloured terminal output, tables, panels |
| `python-dotenv` | Load API credentials from `.env` |

## License

This project is for educational / assessment purposes and is provided as-is.
