"""請求格式驗證 + 指標計算邏輯（和 FastAPI、x402 無關，方便單獨測試）。

API 對外的欄位與訊息用英文，因為付費呼叫的多半是世界各地的 AI 代理。
"""

from __future__ import annotations

import math
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

import indicators as ind

MAX_PRICES = 5000
PREVIEW_MAX_PRICES = 100
ALL_INDICATORS = ("sma", "ema", "rsi", "macd", "bollinger")
IndicatorName = Literal["sma", "ema", "rsi", "macd", "bollinger"]

DISCLAIMER = "Computed indicators only. Not financial advice."


class IndicatorParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sma_period: int = Field(20, ge=1, le=500)
    ema_period: int = Field(20, ge=1, le=500)
    rsi_period: int = Field(14, ge=1, le=500)
    macd_fast: int = Field(12, ge=1, le=500)
    macd_slow: int = Field(26, ge=2, le=500)
    macd_signal: int = Field(9, ge=1, le=500)
    bb_period: int = Field(20, ge=2, le=500)
    bb_std: float = Field(2.0, gt=0, le=10)
    rsi_overbought: float = Field(70, gt=0, lt=100)
    rsi_oversold: float = Field(30, gt=0, lt=100)

    @model_validator(mode="after")
    def _check_relations(self) -> "IndicatorParams":
        if self.macd_fast >= self.macd_slow:
            raise ValueError("macd_fast must be smaller than macd_slow")
        if self.rsi_oversold >= self.rsi_overbought:
            raise ValueError("rsi_oversold must be smaller than rsi_overbought")
        return self


class IndicatorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prices: list[float] = Field(
        ...,
        min_length=2,
        max_length=MAX_PRICES,
        description="Closing prices, oldest first.",
    )
    indicators: list[IndicatorName] = Field(
        default_factory=lambda: list(ALL_INDICATORS),
        description="Which indicators to compute. Defaults to all.",
    )
    params: IndicatorParams = Field(default_factory=IndicatorParams)
    full_series: bool = Field(
        False, description="Return the whole series, not only the latest values."
    )

    @field_validator("prices")
    @classmethod
    def _prices_must_be_positive(cls, v: list[float]) -> list[float]:
        for i, p in enumerate(v):
            if not math.isfinite(p) or p <= 0:
                raise ValueError(f"prices[{i}] must be a positive finite number")
        return v

    @field_validator("indicators")
    @classmethod
    def _dedupe(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("indicators must not be empty")
        return list(dict.fromkeys(v))


def _r(x: Optional[float]) -> Optional[float]:
    """四捨五入到 8 位小數；保留 None。"""
    return None if x is None else round(x, 8)


def _rs(series: list[Optional[float]]) -> list[Optional[float]]:
    return [_r(x) for x in series]


def _crossed(hist: list[Optional[float]], price_scale: float) -> Optional[str]:
    """看 MACD 柱狀體最後兩根有沒有翻正或翻負。

    浮點運算會讓「其實是 0」的值變成 1e-16 之類，所以低於價格 1e-10 倍的值當作 0。
    """
    vals = [h for h in hist[-2:] if h is not None]
    if len(vals) < 2:
        return None
    eps = abs(price_scale) * 1e-10
    prev, cur = vals
    if prev <= eps and cur > eps:
        return "bullish_cross"
    if prev >= -eps and cur < -eps:
        return "bearish_cross"
    return None


def analyze(req: IndicatorRequest) -> dict[str, Any]:
    """付費端點：計算所請求的所有指標，加上一段機器好讀的摘要。"""
    prices = req.prices
    p = req.params
    last_price = prices[-1]

    latest: dict[str, Any] = {}
    summary: dict[str, Any] = {}
    series: dict[str, Any] = {}
    warnings: list[str] = []

    def need(name: str, n: int) -> None:
        if len(prices) < n:
            warnings.append(f"{name} needs at least {n} prices; got {len(prices)}")

    if "sma" in req.indicators:
        need("sma", p.sma_period)
        s = ind.sma(prices, p.sma_period)
        v = ind.last_value(s)
        latest["sma"] = _r(v)
        if v is not None:
            summary["price_vs_sma"] = "above" if last_price > v else "below"
        if req.full_series:
            series["sma"] = _rs(s)

    if "ema" in req.indicators:
        need("ema", p.ema_period)
        s = ind.ema(prices, p.ema_period)
        v = ind.last_value(s)
        latest["ema"] = _r(v)
        if v is not None:
            summary["price_vs_ema"] = "above" if last_price > v else "below"
        if req.full_series:
            series["ema"] = _rs(s)

    if "rsi" in req.indicators:
        need("rsi", p.rsi_period + 1)
        s = ind.rsi(prices, p.rsi_period)
        v = ind.last_value(s)
        latest["rsi"] = _r(v)
        if v is not None:
            if v >= p.rsi_overbought:
                summary["rsi_state"] = "overbought"
            elif v <= p.rsi_oversold:
                summary["rsi_state"] = "oversold"
            else:
                summary["rsi_state"] = "neutral"
        if req.full_series:
            series["rsi"] = _rs(s)

    if "macd" in req.indicators:
        need("macd", p.macd_slow + p.macd_signal - 1)
        m = ind.macd(prices, p.macd_fast, p.macd_slow, p.macd_signal)
        latest["macd"] = {k: _r(ind.last_value(v)) for k, v in m.items()}
        line, sig = ind.last_value(m["macd"]), ind.last_value(m["signal"])
        if line is not None and sig is not None:
            summary["macd_momentum"] = "bullish" if line > sig else "bearish"
            cross = _crossed(m["histogram"], last_price)
            if cross:
                summary["macd_cross"] = cross
        if req.full_series:
            series["macd"] = {k: _rs(v) for k, v in m.items()}

    if "bollinger" in req.indicators:
        need("bollinger", p.bb_period)
        b = ind.bollinger(prices, p.bb_period, p.bb_std)
        latest["bollinger"] = {k: _r(ind.last_value(v)) for k, v in b.items()}
        up, lo = ind.last_value(b["upper"]), ind.last_value(b["lower"])
        if up is not None and lo is not None:
            if last_price > up:
                summary["bollinger_position"] = "above_upper"
            elif last_price < lo:
                summary["bollinger_position"] = "below_lower"
            else:
                summary["bollinger_position"] = "inside"
        if req.full_series:
            series["bollinger"] = {k: _rs(v) for k, v in b.items()}

    result: dict[str, Any] = {
        "count": len(prices),
        "latest_price": last_price,
        "latest": latest,
        "summary": summary,
    }
    if req.full_series:
        result["series"] = series
    if warnings:
        result["warnings"] = warnings
    result["disclaimer"] = DISCLAIMER
    return result


def preview(req: IndicatorRequest) -> dict[str, Any]:
    """免費試用端點：只回傳最新的 RSI，最多吃 100 筆價格。"""
    if len(req.prices) > PREVIEW_MAX_PRICES:
        raise ValueError(
            f"preview accepts at most {PREVIEW_MAX_PRICES} prices; "
            "use POST /v1/indicators for more"
        )
    period = req.params.rsi_period
    v = ind.last_value(ind.rsi(req.prices, period))
    return {
        "count": len(req.prices),
        "latest": {"rsi": _r(v)},
        "note": (
            "Free preview returns RSI only. POST /v1/indicators returns SMA, EMA, "
            "RSI, MACD, Bollinger Bands and a signal summary (paid via x402)."
        ),
        "disclaimer": DISCLAIMER,
    }
