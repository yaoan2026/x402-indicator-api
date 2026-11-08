"""給 x402 Bazaar（服務目錄）看的說明：怎麼呼叫這個 API、會回傳什麼。

付款透過 Coinbase CDP facilitator 結算成功後，Bazaar 會依這裡的資料把服務收錄進去，
讓 AI 代理搜尋得到。內容只描述 API 本身（Bazaar 規定不能寫指示代理去做什麼的文字）。
"""

from __future__ import annotations

import math
from typing import Any

from service import ALL_INDICATORS, MAX_PRICES, IndicatorRequest, analyze

DESCRIPTION = (
    "Technical analysis for a price series. Send closing prices (oldest first, "
    f"up to {MAX_PRICES}) and get RSI, MACD, Bollinger Bands, SMA and EMA, plus a "
    "machine-readable summary: overbought/oversold state, MACD momentum and "
    "crossovers, and position relative to the bands."
)

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "prices": {
            "type": "array",
            "items": {"type": "number", "exclusiveMinimum": 0},
            "minItems": 2,
            "maxItems": MAX_PRICES,
            "description": "Closing prices, oldest first.",
        },
        "indicators": {
            "type": "array",
            "items": {"type": "string", "enum": list(ALL_INDICATORS)},
            "description": "Indicators to compute. Defaults to all.",
        },
        "params": {
            "type": "object",
            "description": (
                "Optional settings: sma_period, ema_period, rsi_period, macd_fast, "
                "macd_slow, macd_signal, bb_period, bb_std, rsi_overbought, rsi_oversold."
            ),
        },
        "full_series": {
            "type": "boolean",
            "description": "Return the full series instead of only the latest values.",
        },
    },
    "required": ["prices"],
}

EXAMPLE_INPUT: dict[str, Any] = {
    "prices": [round(100 + i * 0.4 + 3 * math.sin(i / 3), 2) for i in range(40)],
    "indicators": ["rsi", "macd", "bollinger"],
}

# 用真正的計算結果當範例輸出，保證和實際回應一致
EXAMPLE_OUTPUT: dict[str, Any] = analyze(IndicatorRequest(**EXAMPLE_INPUT))
