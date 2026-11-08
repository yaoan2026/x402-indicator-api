"""端到端冒煙測試（smoke test）：實際啟動「開啟 x402 收費」的伺服器來檢查。

檢查項目：
  1. 伺服器能在開啟收費的狀態下啟動（x402 套件和設定都正確）
  2. 免費端點正常回 200
  3. 付費端點不付錢會回 402，而且付款要求正確（網路、收款地址、金額）
  4. 用 x402 client 走一次付款流程
     - .env 有 BUYER_PRIVATE_KEY（錢包裡有測試 USDC）→ 預期付款成功、回 200
     - 沒有 → 用一個沒錢的臨時錢包，預期付款被簽名送出後，因為餘額不足被拒絕

一律使用 Base Sepolia 測試網，不會動到真錢。
用法：python smoke_test.py
（輸出用英文，避免 Windows 終端機的編碼問題）
"""

from __future__ import annotations

import asyncio
import base64
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import httpx
from dotenv import dotenv_values
from eth_account import Account

HERE = Path(__file__).resolve().parent
PORT = int(os.getenv("SMOKE_PORT", "4021"))
BASE = f"http://127.0.0.1:{PORT}"
NETWORK = "eip155:84532"  # Base Sepolia 測試網
FACILITATOR_URL = "https://x402.org/facilitator"
PRICE = "$0.001"
EXPECTED_AMOUNT = "1000"  # USDC 有 6 位小數，0.001 USDC = 1000

ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
KEY_RE = re.compile(r"^(0x)?[0-9a-fA-F]{64}$")

_env_file = HERE / ".env"
CFG = {k: (v or "").strip() for k, v in dotenv_values(_env_file).items()} if _env_file.exists() else {}

results: list[tuple[str, bool]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, bool(ok)))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""), flush=True)


def info(msg: str) -> None:
    print(f"       {msg}", flush=True)


def new_key() -> str:
    return "0x" + Account.create().key.hex().removeprefix("0x")


def decode_b64_json(value: str | None):
    if not value:
        return None
    try:
        return json.loads(base64.b64decode(value + "=" * (-len(value) % 4)))
    except Exception:
        return {"undecodable": value[:120]}


def payment_required(resp: httpx.Response) -> dict:
    """x402 v2 把付款要求放在 PAYMENT-REQUIRED 標頭；v1 放在 JSON 內容。"""
    data = decode_b64_json(resp.headers.get("payment-required"))
    if data is None:
        try:
            data = resp.json()
        except ValueError:
            data = None
    return data if isinstance(data, dict) else {}


def sample_prices(n: int = 60) -> list[float]:
    return [round(100 + i * 0.4 + 3 * math.sin(i / 3), 2) for i in range(n)]


def start_server(pay_to: str):
    env = os.environ.copy()
    env.update(
        PAYMENTS_ENABLED="true",
        PAY_TO=pay_to,
        NETWORK=NETWORK,
        FACILITATOR_URL=FACILITATOR_URL,
        PRICE=PRICE,
        USE_CDP_FACILITATOR="false",
        ENABLE_BAZAAR="true",
    )
    log = open(HERE / "smoke_server.log", "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=HERE,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    deadline = time.time() + 45
    while time.time() < deadline:
        if proc.poll() is not None:
            return proc, log, False
        try:
            if httpx.get(f"{BASE}/health", timeout=2, trust_env=False).status_code == 200:
                return proc, log, True
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    return proc, log, False


async def paid_call(private_key: str) -> httpx.Response:
    from x402 import x402Client
    from x402.http.clients import x402HttpxClient
    from x402.mechanisms.evm import EthAccountSigner
    from x402.mechanisms.evm.exact import ExactEvmScheme

    signer = EthAccountSigner(Account.from_key(private_key))
    client = x402Client()
    client.register(NETWORK, ExactEvmScheme(signer))
    try:
        http = x402HttpxClient(client, timeout=60)
    except TypeError:
        http = x402HttpxClient(client)
    async with http:
        resp = await http.post(f"{BASE}/v1/indicators", json={"prices": sample_prices()})
        await resp.aread()
    return resp


def run_checks(pay_to: str, buyer_key: str, funded: bool) -> None:
    with httpx.Client(base_url=BASE, timeout=15, trust_env=False) as h:
        r = h.get("/")
        check("GET / returns service info", r.status_code == 200 and r.json()["payments"]["enabled"] is True)

        r = h.post("/v1/preview", json={"prices": sample_prices(30)})
        check(
            "POST /v1/preview (free) returns RSI",
            r.status_code == 200 and r.json()["latest"]["rsi"] is not None,
            f"status {r.status_code}",
        )

        r = h.post("/v1/indicators", json={"prices": sample_prices()})
        check("POST /v1/indicators without payment -> 402", r.status_code == 402, f"status {r.status_code}")
        pr = payment_required(r)
        accepts = pr.get("accepts") or []
        a = accepts[0] if accepts else {}
        info(f"x402Version: {pr.get('x402Version')}")
        info("requirements: " + json.dumps(a, ensure_ascii=True)[:700])
        amount = str(a.get("amount", a.get("maxAmountRequired", "")))
        ok = (
            a.get("network") == NETWORK
            and str(a.get("payTo", "")).lower() == pay_to.lower()
            and amount == EXPECTED_AMOUNT
        )
        check("402 requirements match (network, payTo, 0.001 USDC)", ok, f"amount={amount}")
        ext = pr.get("extensions") or {}
        check("402 advertises Bazaar discovery metadata", "bazaar" in ext, f"extensions={list(ext)}")

    # 公開的測試網 facilitator 偶爾會結算失敗（例如它自己的交易 nonce 衝突），真付款時最多重試 3 次。
    # 每次重試都會重新簽一筆新的付款授權；結算失敗的那筆不會扣款。
    attempts = 3 if funded else 1
    for attempt in range(1, attempts + 1):
        try:
            r = asyncio.run(paid_call(buyer_key))
        except Exception as e:  # noqa: BLE001
            check("x402 client signs and sends a payment", False, f"{type(e).__name__}: {e}")
            return
        info(f"paid call (attempt {attempt}) -> status {r.status_code}")
        if not funded or r.status_code == 200 or attempt == attempts:
            break
        failed = decode_b64_json(r.headers.get("payment-response") or r.headers.get("x-payment-response")) or {}
        info(f"not settled ({failed.get('errorReason')!r}); retrying in 5s")
        time.sleep(5)

    if funded:
        receipt = decode_b64_json(r.headers.get("payment-response") or r.headers.get("x-payment-response"))
        check("real testnet payment with BUYER_PRIVATE_KEY -> 200", r.status_code == 200)
        if receipt:
            info("settlement: " + json.dumps(receipt, ensure_ascii=True)[:700])
        if r.status_code != 200:
            info("body: " + r.text[:500])
    else:
        pr = payment_required(r)
        err = str(pr.get("error") or "")
        info(f"rejection reason: {err!r}")
        info("body: " + r.text[:300])
        check(
            "payment signed, sent, and rejected for an empty wallet (expected)",
            r.status_code == 402 and bool(err),
        )


def main() -> int:
    print(f"x402 smoke test | network={NETWORK} | facilitator={FACILITATOR_URL}", flush=True)

    pay_to = CFG.get("PAY_TO", "")
    if not ADDR_RE.match(pay_to):
        pay_to = Account.create().address
        info(f"PAY_TO not set in .env -> using a throwaway address {pay_to}")

    buyer_key = CFG.get("BUYER_PRIVATE_KEY", "")
    funded = bool(KEY_RE.match(buyer_key))
    if funded:
        info(f"using BUYER_PRIVATE_KEY from .env ({Account.from_key(buyer_key).address})")
    else:
        buyer_key = new_key()
        info(f"BUYER_PRIVATE_KEY not set -> using an empty throwaway wallet ({Account.from_key(buyer_key).address})")

    proc, log, up = start_server(pay_to)
    try:
        check("server starts with x402 payments enabled", up)
        if up:
            run_checks(pay_to, buyer_key, funded)
        else:
            log.flush()
            text = (HERE / "smoke_server.log").read_text(encoding="utf-8", errors="replace")
            print("----- server log (tail) -----")
            print(text[-4000:])
    except Exception as e:  # noqa: BLE001
        check("smoke test ran without crashing", False, f"{type(e).__name__}: {e}")
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()

    passed = sum(ok for _, ok in results)
    print(f"\nSMOKE RESULT: {passed}/{len(results)} passed", flush=True)
    if passed != len(results):
        text = (HERE / "smoke_server.log").read_text(encoding="utf-8", errors="replace")
        print("----- server log (tail) -----")
        print(text[-3000:])
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
