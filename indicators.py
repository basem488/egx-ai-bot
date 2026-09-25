import numpy as np
import pandas as pd


def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def rsi(c, n=14):
    d = c.diff()
    g = d.clip(lower=0)
    l = -d.clip(upper=0)
    ag = g.ewm(alpha=1/n, adjust=False).mean()
    al = l.ewm(alpha=1/n, adjust=False).mean()
    rs = ag / al.replace(0, np.nan)
    return (100 - 100/(1+rs)).fillna(50)


def atr(d, n=14):
    pc = d.Close.shift(1)
    tr = pd.concat([
        d.High-d.Low,
        (d.High-pc).abs(),
        (d.Low-pc).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()


def add(d, cfg):
    d = d.copy()
    d["EMA20"] = ema(d.Close, cfg.EMA_FAST)
    d["EMA50"] = ema(d.Close, cfg.EMA_MID)
    d["EMA200"] = ema(d.Close, cfg.EMA_SLOW)
    d["RSI"] = rsi(d.Close, cfg.RSI_PERIOD)
    d["ATR"] = atr(d, cfg.ATR_PERIOD)

    m = ema(d.Close, 12) - ema(d.Close, 26)
    s = ema(m, 9)
    d["MACD"] = m
    d["MACD_SIGNAL"] = s
    d["MACD_HIST"] = m - s

    d["VOL_RATIO"] = d.Volume / d.Volume.rolling(cfg.VOLUME_PERIOD).mean()
    d["RES"] = d.High.rolling(cfg.BREAKOUT_LOOKBACK).max().shift(1)
    d["SUP"] = d.Low.rolling(cfg.BREAKOUT_LOOKBACK).min().shift(1)

    # Reversal/correction measurements.
    d["PEAK20"] = d.High.rolling(20).max().shift(1)
    d["LOW10"] = d.Low.rolling(10).min()
    d["HIGH5"] = d.High.rolling(5).max().shift(1)
    d["EMA20_SLOPE5"] = d.EMA20 / d.EMA20.shift(5) - 1
    d["REBOUND10"] = d.Close / d.LOW10 - 1
    d["DRAWDOWN20"] = d.Close / d.PEAK20 - 1
    d["RSI_PREV"] = d.RSI.shift(1)
    d["MACD_HIST_PREV"] = d.MACD_HIST.shift(1)
    return d
