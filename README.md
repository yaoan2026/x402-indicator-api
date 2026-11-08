# Technical Indicator API (pay-per-call with x402)

English | [繁體中文](README.zh-TW.md)

Send a list of closing prices, get back **RSI, MACD, Bollinger Bands, SMA and EMA** plus a machine-readable signal summary: overbought/oversold, MACD momentum and crossovers, and position relative to the bands.

No sign-up and no API key. Each call costs **$0.01 in USDC on Base**, paid automatically through the [x402](https://x402.org) protocol, so AI agents can use it on their own.

- **Live endpoint:** `https://x402-indicator-api.onrender.com`
- **Price:** $0.01 per call (USDC, Base mainnet `eip155:8453`)
- **Interactive docs:** [`/docs`](https://x402-indicator-api.onrender.com/docs)

> Hosted on a free tier: after 15 idle minutes the first request can take about a minute while the server wakes up.

## Endpoints

| Endpoint | Price | What it does |
|---|---|---|
| `GET /` | free | Service info, price, network, pay-to address |
| `POST /v1/preview` | free | RSI only, up to 100 prices |
| `POST /v1/indicators` | **$0.01** | All indicators + summary, up to 5,000 prices |

## Try it for free

```bash
curl -X POST https://x402-indicator-api.onrender.com/v1/preview \
  -H 'Content-Type: application/json' \
  -d '{"prices":[100,101,102,101,103,104,103,105,106,105,107,108,107,109,110,111]}'
```

Calling the paid endpoint without paying returns `402 Payment Required`, with the payment requirements in the `PAYMENT-REQUIRED` header.

## Paid call with an x402 client (Python)

```bash
pip install "x402[evm,httpx]" eth-account
```

```python
import asyncio
from eth_account import Account
from x402 import x402Client
from x402.http.clients import x402HttpxClient
from x402.mechanisms.evm import EthAccountSigner
from x402.mechanisms.evm.exact import ExactEvmScheme

async def main():
    signer = EthAccountSigner(Account.from_key("0x...your private key..."))  # wallet holding USDC on Base
    client = x402Client()
    client.register("eip155:8453", ExactEvmScheme(signer))
    async with x402HttpxClient(client, timeout=60) as http:
        r = await http.post(
            "https://x402-indicator-api.onrender.com/v1/indicators",
            json={"prices": [101.2, 102.5, 101.9, 103.4, 104.1] * 8, "indicators": ["rsi", "macd"]},
        )
        print(r.json())

asyncio.run(main())
```

Any x402 v2 client works, including the TypeScript ones. The endpoint is also described for the x402 Bazaar discovery service.

## Request

```json
{
  "prices": [101.2, 102.5, 101.9, 103.4, 104.1],
  "indicators": ["rsi", "macd", "bollinger", "sma", "ema"],
  "params": {
    "rsi_period": 14,
    "macd_fast": 12, "macd_slow": 26, "macd_signal": 9,
    "bb_period": 20, "bb_std": 2,
    "sma_period": 20, "ema_period": 20,
    "rsi_overbought": 70, "rsi_oversold": 30
  },
  "full_series": false
}
```

Only `prices` (oldest first) is required. `full_series: true` returns the whole series instead of only the latest values.

## Response

```json
{
  "count": 60,
  "latest_price": 125.79,
  "latest": {
    "rsi": 86.35531084,
    "macd": { "macd": 2.86744954, "signal": 2.53597332, "histogram": 0.33147623 },
    "bollinger": { "middle": 119.922, "upper": 124.44480267, "lower": 115.39919733, "percent_b": 1.1487128, "bandwidth": 0.07542907 }
  },
  "summary": {
    "rsi_state": "overbought",
    "macd_momentum": "bullish",
    "bollinger_position": "above_upper"
  },
  "disclaimer": "Computed indicators only. Not financial advice."
}
```

| Summary field | Values |
|---|---|
| `rsi_state` | `overbought`, `oversold`, `neutral` |
| `macd_momentum` | `bullish`, `bearish` |
| `macd_cross` | `bullish_cross`, `bearish_cross` (only on the bar where it happens) |
| `bollinger_position` | `above_upper`, `below_lower`, `inside` |
| `price_vs_sma` / `price_vs_ema` | `above`, `below` |

RSI uses Wilder smoothing and is checked against the StockCharts reference data. Indicators that need more data than you sent come back as `null` with a `warnings` entry.

## Run it yourself

Python 3.10+, FastAPI and the x402 Python SDK. See [README.zh-TW.md](README.zh-TW.md) for the full setup (testnet wallets, tests, Render deployment); the short version:

```bash
pip install -r requirements.txt
cp .env.example .env   # set PAY_TO to your wallet address
uvicorn main:app --port 4021
pytest
```

