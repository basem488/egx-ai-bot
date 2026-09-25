import os,json
from pathlib import Path
import pandas as pd,requests
import config
from indicators import add

SUBS=Path("subscriptions.json")
def analyze(sym,raw):
 d=add(raw,config)
 if len(d)<220: raise ValueError("need 220 daily rows")
 x=d.iloc[-1]; close=float(x.Close); score=0; reasons=[]
 if close>x.EMA20: score+=10; reasons.append("price>EMA20")
 if x.EMA20>x.EMA50: score+=15; reasons.append("EMA20>EMA50")
 if x.EMA50>x.EMA200: score+=15; reasons.append("EMA50>EMA200")
 if 50<=x.RSI<=68: score+=15; reasons.append("RSI constructive")
 elif x.RSI>70: score-=5; reasons.append("RSI overbought")
 if x.MACD>x.MACD_SIGNAL: score+=15; reasons.append("MACD positive")
 if x.VOL_RATIO>=1.2: score+=10; reasons.append("volume confirmation")
 breakout=close>x.RES; near=close<=x.SUP*1.06
 if breakout: score+=20; reasons.append("20d breakout")
 elif near: score+=8; reasons.append("near support")
 score=max(0,min(100,score)); atr=float(x.ATR); sup=float(x.SUP)
 if breakout: lo,hi=close,close*1.01
 elif near: lo,hi=max(sup,close-.5*atr),min(close,sup+.5*atr)
 else: lo,hi=close*.985,close*.995
 stop=min(lo-config.STOP_ATR_MULTIPLIER*atr,sup*.98); risk=max(lo-stop,.01)
 return {"symbol":sym,"date":str(x.Date.date()),"close":round(close,2),"score":score,
 "signal":"WATCH" if score>=config.WATCH_SCORE else ("NEUTRAL" if score>=55 else "AVOID"),
 "entry_low":round(lo,2),"entry_high":round(hi,2),"stop":round(stop,2),
 "target1":round(lo+config.TARGET1_RR*risk,2),"target2":round(lo+config.TARGET2_RR*risk,2),
 "rsi":round(float(x.RSI),2),"vol_ratio":round(float(x.VOL_RATIO),2),"reasons":reasons}

def load_signals():
 out=[]
 data_dir=Path("data")
 data_dir.mkdir(exist_ok=True)
 # Scan every stock CSV available in data/, excluding banks.
 for p in sorted(data_dir.glob("*.csv")):
  s=p.stem.upper()
  if s in config.BANK_SYMBOLS:
   continue
  try:
   out.append(analyze(s,pd.read_csv(p,parse_dates=["Date"])))
  except Exception as e:
   print(s,e)
 return sorted(out,key=lambda x:x["score"],reverse=True)

def send_push(payload):
 if not SUBS.exists(): return
 try:
  from pywebpush import webpush
  subs=json.loads(SUBS.read_text())
  private=os.getenv("VAPID_PRIVATE_KEY"); email=os.getenv("VAPID_CLAIMS_EMAIL","mailto:admin@example.com")
  if not private: return
  for sub in subs:
   webpush(subscription_info=sub,data=json.dumps(payload),vapid_private_key=private,vapid_claims={"sub":email})
 except Exception as e: print("push error:",e)

if __name__=="__main__":
 sig=load_signals()
 Path("reports").mkdir(exist_ok=True)
 Path("reports/signals.json").write_text(json.dumps(sig,ensure_ascii=False,indent=2))
 for x in sig:
  if x["signal"]=="WATCH": send_push({"title":f'EGX {x["symbol"]} — WATCH',"body":f'Entry {x["entry_low"]}-{x["entry_high"]} | Stop {x["stop"]} | T1 {x["target1"]} | T2 {x["target2"]}'})
 print(json.dumps(sig,ensure_ascii=False,indent=2))
