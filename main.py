"""技術指標 API 伺服器：免費端點 + 用 x402 收費的端點。

啟動：uvicorn main:app --port 4021
設定都放在 .env（參考 .env.example）。
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from discovery import DESCRIPTION
from service import (
    MAX_PRICES,
    PREVIEW_MAX_PRICES,
    IndicatorRequest,
    analyze,
    preview,
)

load_dotenv()

PAY_TO = os.getenv("PAY_TO", "").strip()
NETWORK = os.getenv("NETWORK", "eip155:84532").strip()  # 預設 Base Sepolia 測試網
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://x402.org/facilitator").strip()
PRICE = os.getenv("PRICE", "$0.001").strip()
PAYMENTS_ENABLED = os.getenv("PAYMENTS_ENABLED", "true").strip().lower() != "false"
USE_CDP_FACILITATOR = os.getenv("USE_CDP_FACILITATOR", "false").strip().lower() == "true"
# 在付費路由上宣告 Bazaar 說明，透過 CDP facilitator 收到第一筆款後就會被收錄進服務目錄
ENABLE_BAZAAR = os.getenv("ENABLE_BAZAAR", "true").strip().lower() != "false"

PAID_ROUTE = "POST /v1/indicators"

app = FastAPI(
    title="Technical Indicator API",
    description=(
        "Send closing prices, get RSI, MACD, Bollinger Bands, SMA and EMA plus a "
        "machine-readable signal summary. Pay per call in USDC via x402."
    ),
    version="1.0.0",
)


def _setup_payments(app: FastAPI) -> None:
    """把 x402 付款中介軟體掛到付費路由上。"""
    if not PAY_TO:
        raise RuntimeError(
            "PAY_TO 沒有設定：請在 .env 填入你的收款錢包地址，"
            "或設 PAYMENTS_ENABLED=false 先在本機免付費測試。"
        )

    from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
    from x402.http.middleware.fastapi import PaymentMiddlewareASGI
    from x402.http.types import RouteConfig
    from x402.mechanisms.evm.exact import ExactEvmServerScheme
    from x402.server import x402ResourceServer

    if USE_CDP_FACILITATOR:
        # 主網用 Coinbase 的 facilitator，需要 CDP API 金鑰（見 README）
        if not (os.getenv("CDP_API_KEY_ID") and os.getenv("CDP_API_KEY_SECRET")):
            raise RuntimeError(
                "USE_CDP_FACILITATOR=true，但沒有設定 CDP_API_KEY_ID / CDP_API_KEY_SECRET"
            )
        from cdp.x402 import create_facilitator_config

        facilitator = HTTPFacilitatorClient(create_facilitator_config())
    else:
        facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=FACILITATOR_URL))

    server = x402ResourceServer(facilitator)
    server.register(NETWORK, ExactEvmServerScheme())

    route_extras: dict = {}
    if ENABLE_BAZAAR:
        try:
            from x402.extensions.bazaar import (
                OutputConfig,
                bazaar_resource_server_extension,
                declare_discovery_extension,
            )
        except ImportError as e:
            # Bazaar 只影響「被搜尋到」，不影響收款；套件缺少時照常啟動，只是不宣告
            print(f"WARNING: Bazaar discovery disabled ({e})", flush=True)
        else:
            import discovery

            server.register_extension(bazaar_resource_server_extension)
            route_extras["extensions"] = declare_discovery_extension(
                input=discovery.EXAMPLE_INPUT,
                input_schema=discovery.INPUT_SCHEMA,
                body_type="json",
                output=OutputConfig(example=discovery.EXAMPLE_OUTPUT),
            )

    routes = {
        PAID_ROUTE: RouteConfig(
            accepts=[
                PaymentOption(
                    scheme="exact", pay_to=PAY_TO, price=PRICE, network=NETWORK
                )
            ],
            mime_type="application/json",
            description=DESCRIPTION,
            **route_extras,
        ),
    }
    app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)


if PAYMENTS_ENABLED:
    _setup_payments(app)


@app.get("/")
async def info() -> dict:
    """服務說明（給人和 AI 代理看的）。"""
    return {
        "name": "Technical Indicator API",
        "payments": {
            "protocol": "x402",
            "enabled": PAYMENTS_ENABLED,
            "price_per_call": PRICE,
            "network": NETWORK,
            "pay_to": PAY_TO or None,
        },
        "endpoints": {
            "GET /health": "free",
            "POST /v1/preview": f"free, RSI only, up to {PREVIEW_MAX_PRICES} prices",
            PAID_ROUTE: f"paid ({PRICE}), all indicators, up to {MAX_PRICES} prices",
            "GET /docs": "interactive API docs",
        },
        "example_body": {
            "prices": [101.2, 102.5, 101.9, 103.4, 104.1],
            "indicators": ["rsi", "macd", "bollinger"],
            "full_series": False,
        },
    }


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/preview")
async def free_preview(req: IndicatorRequest) -> dict:
    try:
        return preview(req)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/v1/indicators")
async def paid_indicators(req: IndicatorRequest) -> dict:
    return analyze(req)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "4021")))
