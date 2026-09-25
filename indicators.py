import numpy as np
def ema(s,n): return s.ewm(span=n,adjust=False).mean()
def rsi(c,n=14):
 d=c.diff(); g=d.clip(lower=0); l=-d.clip(upper=0)
 ag=g.ewm(alpha=1/n,adjust=False).mean(); al=l.ewm(alpha=1/n,adjust=False).mean()
 return (100-100/(1+ag/al.replace(0,np.nan))).fillna(50)
def atr(d,n=14):
 pc=d.Close.shift(1)
 tr=__import__("pandas").concat([d.High-d.Low,(d.High-pc).abs(),(d.Low-pc).abs()],axis=1).max(axis=1)
 return tr.ewm(alpha=1/n,adjust=False).mean()
def add(d,cfg):
 d=d.copy(); d["EMA20"]=ema(d.Close,cfg.EMA_FAST); d["EMA50"]=ema(d.Close,cfg.EMA_MID); d["EMA200"]=ema(d.Close,cfg.EMA_SLOW)
 d["RSI"]=rsi(d.Close,cfg.RSI_PERIOD); d["ATR"]=atr(d,cfg.ATR_PERIOD)
 m=ema(d.Close,12)-ema(d.Close,26); s=ema(m,9); d["MACD"]=m; d["MACD_SIGNAL"]=s
 d["VOL_RATIO"]=d.Volume/d.Volume.rolling(cfg.VOLUME_PERIOD).mean()
 d["RES"]=d.High.rolling(cfg.BREAKOUT_LOOKBACK).max().shift(1); d["SUP"]=d.Low.rolling(cfg.BREAKOUT_LOOKBACK).min().shift(1)
 return d
