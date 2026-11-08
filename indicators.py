"""純 Python 技術指標計算（不需要 numpy）。

所有函式回傳的 list 長度都和輸入的 prices 一樣，
資料還不夠算出數值的位置會是 None，方便和原始價格一一對齊。
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

Series = list[Optional[float]]


def _check_period(period: int) -> None:
    if not isinstance(period, int) or period < 1:
        raise ValueError(f"period 必須是正整數，收到 {period!r}")


def sma(prices: Sequence[float], period: int) -> Series:
    """簡單移動平均（Simple Moving Average）。"""
    _check_period(period)
    out: Series = [None] * len(prices)
    window_sum = 0.0
    for i, p in enumerate(prices):
        window_sum += p
        if i >= period:
            window_sum -= prices[i - period]
        if i >= period - 1:
            out[i] = window_sum / period
    return out


def ema(prices: Sequence[Optional[float]], period: int) -> Series:
    """指數移動平均（Exponential Moving Average）。

    以前 period 筆的 SMA 當起始值，之後用 alpha = 2 / (period + 1) 平滑。
    輸入開頭可以有 None（例如 MACD 線），會從第一個非 None 值開始算。
    """
    _check_period(period)
    out: Series = [None] * len(prices)
    start = next((i for i, p in enumerate(prices) if p is not None), None)
    if start is None:
        return out
    values = prices[start:]
    if any(v is None for v in values):
        raise ValueError("ema 的輸入只能在開頭出現 None")
    if len(values) < period:
        return out

    alpha = 2.0 / (period + 1)
    prev = sum(values[:period]) / period  # type: ignore[arg-type]
    out[start + period - 1] = prev
    for j in range(period, len(values)):
        prev = alpha * values[j] + (1 - alpha) * prev  # type: ignore[operator]
        out[start + j] = prev
    return out


def rsi(prices: Sequence[float], period: int = 14) -> Series:
    """相對強弱指標（Wilder 平滑法，和多數看盤軟體一致）。"""
    _check_period(period)
    out: Series = [None] * len(prices)
    if len(prices) <= period:
        return out

    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [max(c, 0.0) for c in changes]
    losses = [max(-c, 0.0) for c in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    out[period] = _rsi_value(avg_gain, avg_loss)

    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out[i + 1] = _rsi_value(avg_gain, avg_loss)
    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def macd(
    prices: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> dict[str, Series]:
    """MACD：快線 EMA − 慢線 EMA，訊號線是 MACD 線的 EMA，柱狀體是兩者差。"""
    _check_period(fast)
    _check_period(slow)
    _check_period(signal)
    if fast >= slow:
        raise ValueError("macd 的 fast 必須小於 slow")

    ema_fast = ema(prices, fast)
    ema_slow = ema(prices, slow)
    line: Series = [
        f - s if f is not None and s is not None else None
        for f, s in zip(ema_fast, ema_slow)
    ]
    signal_line = ema(line, signal)
    hist: Series = [
        m - s if m is not None and s is not None else None
        for m, s in zip(line, signal_line)
    ]
    return {"macd": line, "signal": signal_line, "histogram": hist}


def bollinger(
    prices: Sequence[float], period: int = 20, num_std: float = 2.0
) -> dict[str, Series]:
    """布林通道：中軌是 SMA，上下軌是中軌 ± num_std 個標準差（母體標準差）。

    另外回傳 %B（價格在通道中的位置，0 = 下軌、1 = 上軌）
    和 bandwidth（通道寬度 ÷ 中軌）。
    """
    _check_period(period)
    if num_std <= 0:
        raise ValueError("num_std 必須大於 0")

    n = len(prices)
    middle = sma(prices, period)
    upper: Series = [None] * n
    lower: Series = [None] * n
    percent_b: Series = [None] * n
    bandwidth: Series = [None] * n

    for i in range(period - 1, n):
        window = prices[i - period + 1 : i + 1]
        mean = middle[i]
        assert mean is not None
        std = math.sqrt(sum((p - mean) ** 2 for p in window) / period)
        up = mean + num_std * std
        lo = mean - num_std * std
        upper[i] = up
        lower[i] = lo
        width = up - lo
        percent_b[i] = (prices[i] - lo) / width if width > 0 else 0.5
        bandwidth[i] = width / mean if mean != 0 else None

    return {
        "middle": middle,
        "upper": upper,
        "lower": lower,
        "percent_b": percent_b,
        "bandwidth": bandwidth,
    }


def last_value(series: Sequence[Optional[float]]) -> Optional[float]:
    """取得序列最後一個值（資料不足時是 None）。"""
    return series[-1] if series else None
