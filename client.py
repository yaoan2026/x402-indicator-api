"""買方測試腳本：用測試錢包自動付款，呼叫付費端點。

用法：
    python client.py                     # 呼叫本機 http://localhost:4021
    python client.py https://你的網址     # 呼叫已部署的服務

需要在 .env 設 BUYER_PRIVATE_KEY（只用測試錢包！）。
"""

from __future__ import annotations

import asyncio
import base64
import json
import math
import os
import sys

import httpx
from dotenv import load_dotenv
from eth_account import Account

from x402 import x402Client
from x402.http.clients import x402HttpxClient
from x402.mechanisms.evm import EthAccountSigner
from x402.mechanisms.evm.exact import ExactEvmScheme

load_dotenv()

NETWORK = os.getenv("NETWORK", "eip155:84532")


def sample_prices(n: int = 60) -> list[float]:
    """產生一段有上漲趨勢加波動的假價格，用來測試。"""
    return [round(100 + i * 0.4 + 3 * math.sin(i / 3), 2) for i in range(n)]


def _decode_payment_response(value: str | None) -> dict | None:
    """x402 會在 PAYMENT-RESPONSE 標頭放 base64 編碼的結算結果（含交易 hash）。"""
    if not value:
        return None
    try:
        return json.loads(base64.b64decode(value))
    except Exception:
        return {"raw": value}


async def main() -> None:
    base_url = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:4021").rstrip("/")
    private_key = os.getenv("BUYER_PRIVATE_KEY", "").strip()
    if not private_key:
        sys.exit("請先在 .env 設定 BUYER_PRIVATE_KEY（用 new_wallet.py 產生一個測試錢包）")

    account = Account.from_key(private_key)
    signer = EthAccountSigner(account)
    print(f"付款錢包：{signer.address}")

    # Render 免費方案閒置 15 分鐘會休眠，第一次連線要等它醒來（約 1 分鐘）
    print(f"連線到 {base_url} …（雲端伺服器休眠中的話要等約 1 分鐘）")
    try:
        async with httpx.AsyncClient(timeout=150) as warm:
            info = (await warm.get(f"{base_url}/")).json()
        server_network = info.get("payments", {}).get("network")
        print(f"伺服器收款網路：{server_network}，價格：{info.get('payments', {}).get('price_per_call')}")
        if server_network and server_network != NETWORK:
            sys.exit(f"網路不一致：伺服器用 {server_network}，你的 .env 是 {NETWORK}")
    except httpx.HTTPError as e:
        sys.exit(f"連不到伺服器：{e}")

    payment_client = x402Client()
    payment_client.register(NETWORK, ExactEvmScheme(signer))

    body = {"prices": sample_prices(), "indicators": ["rsi", "macd", "bollinger", "sma"]}

    try:  # 結算要等鏈上確認，逾時拉長到 60 秒
        http_client = x402HttpxClient(payment_client, timeout=60)
    except TypeError:
        http_client = x402HttpxClient(payment_client)

    async with http_client as http:
        response = await http.post(f"{base_url}/v1/indicators", json=body)
        await response.aread()

    print(f"HTTP {response.status_code}")
    receipt = _decode_payment_response(
        response.headers.get("payment-response") or response.headers.get("x-payment-response")
    )
    if receipt:
        print("付款結算：", json.dumps(receipt, ensure_ascii=False, indent=2))
    try:
        print(json.dumps(response.json(), ensure_ascii=False, indent=2))
    except ValueError:
        print(response.text)


if __name__ == "__main__":
    asyncio.run(main())
