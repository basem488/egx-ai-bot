import pandas as pd
import numpy as np

def add(df,cfg):
    d=df.copy()
    for n in [20,50,200]: d[f'EMA{n}']=d.Close.ewm(span=n,adjust=False).mean()
    delta=d.Close.diff(); gain=delta.clip(lower=0); loss=-delta.clip(upper=0)
    rs=gain.ewm(alpha=1/14,adjust=False).mean()/loss.ewm(alpha=1/14,adjust=False).mean().replace(0,np.nan)
    d['RSI']=100-(100/(1+rs))
    tr=pd.concat([d.High-d.Low,(d.High-d.Close.shift()).abs(),(d.Low-d.Close.shift()).abs()],axis=1).max(axis=1)
    d['ATR']=tr.ewm(alpha=1/14,adjust=False).mean()
    d['VOL_RATIO']=d.Volume/d.Volume.rolling(20).mean()
    d['RES']=d.High.rolling(20).max().shift(1); d['SUP']=d.Low.rolling(20).min().shift(1)
    d['PEAK20']=d.Close.rolling(20).max(); d['LOW10']=d.Low.rolling(10).min(); d['HIGH5']=d.High.rolling(5).max().shift(1)
    d['EMA20_SLOPE5']=d.EMA20/d.EMA20.shift(5)-1
    d['REBOUND10']=d.Close/d.LOW10-1
    d['DRAWDOWN20']=d.Close/d.PEAK20-1
    d['RSI_PREV']=d.RSI.shift(1)
    ema12=d.Close.ewm(span=12,adjust=False).mean(); ema26=d.Close.ewm(span=26,adjust=False).mean()
    macd=ema12-ema26; signal=macd.ewm(span=9,adjust=False).mean()
    d['MACD_HIST']=macd-signal; d['MACD_HIST_PREV']=d.MACD_HIST.shift(1)
    return d
