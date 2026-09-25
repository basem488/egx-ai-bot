import os,requests
from indicators import add
from data_source import discover_symbols,fetch_history,BANK_SYMBOLS
import config

def analyze(sym,raw):
    d=add(raw,config).dropna(subset=['EMA20','RSI','ATR','VOL_RATIO','SUP','LOW10','HIGH5','EMA20_SLOPE5','REBOUND10','DRAWDOWN20','RSI_PREV','MACD_HIST','MACD_HIST_PREV'])
    if len(d)<10:return None
    x=d.iloc[-1]; close=float(x.Close); atr=float(x.ATR); sup=float(x.SUP); low=float(x.LOW10); dd=float(x.DRAWDOWN20); reb=float(x.REBOUND10)
    correction=dd<=-config.MIN_CORRECTION_PCT; recent=reb>=config.MIN_REBOUND_PCT; above=close>float(x.EMA20); slope=float(x.EMA20_SLOPE5)>=config.MIN_EMA20_SLOPE; rsi=float(x.RSI)>=config.MIN_RSI and float(x.RSI)>float(x.RSI_PREV); macd=float(x.MACD_HIST)>float(x.MACD_HIST_PREV); vol=float(x.VOL_RATIO)>=config.MIN_VOLUME_RATIO; breakout=close>float(x.HIGH5); near=close<=sup*config.SUPPORT_ZONE_MULTIPLIER
    score=0; reasons=[]
    for ok,pts,msg in [(correction,20,f'تصحيح {abs(dd)*100:.1f}% من قمة 20 يوم'),(recent,15,f'ارتداد {reb*100:.1f}% من قاع 10 أيام'),(above,15,'السعر استعاد EMA20'),(slope,10,'ميل EMA20 بدأ يتحسن'),(rsi,10,f'RSI يتحسن ({float(x.RSI):.1f})'),(macd,10,'MACD Histogram يتحسن'),(vol,10,'حجم تداول مؤكد'),(breakout,10,'اختراق قمة آخر 5 أيام')]:
        if ok:score+=pts; reasons.append(msg)
    if not breakout and near:score+=5;reasons.append('قريب من منطقة دعم')
    reversal=correction and recent and above and rsi and macd and score>=config.REVERSAL_SCORE
    if breakout:lo,hi=close*.995,close*1.01
    else:lo,hi=max(float(x.EMA20),close-.5*atr),close*1.005
    stop=min(low-.25*atr,sup*.98,lo-config.STOP_ATR_MULTIPLIER*atr); risk=max(lo-stop,.01)
    return dict(symbol=sym,date=str(x.Date.date()),close=round(close,2),score=score,signal='REVERSAL' if reversal else ('WATCH' if score>=70 else 'NEUTRAL'),entry_low=round(lo,2),entry_high=round(hi,2),stop=round(stop,2),target1=round(lo+1.5*risk,2),target2=round(lo+2.5*risk,2),rsi=round(float(x.RSI),2),vol_ratio=round(float(x.VOL_RATIO),2),correction_pct=round(abs(dd)*100,2),rebound_pct=round(reb*100,2),reasons=reasons)
def telegram(method,**data):
    token=os.environ['TELEGRAM_BOT_TOKEN']; return requests.post(f'https://api.telegram.org/bot{token}/{method}',data=data,timeout=20).json()
def chat_id():
    r=telegram('getUpdates',timeout=0).get('result',[])
    ids=[]
    for u in r:
        m=u.get('message') or u.get('edited_message')
        if m and m.get('chat',{}).get('type')=='private': ids.append(m['chat']['id'])
    return ids[-1] if ids else None
def send(text):
    cid=chat_id()
    if not cid:
        print('No chat yet. Open the bot in Telegram and send /start, then rerun.'); return False
    telegram('sendMessage',chat_id=cid,text=text,parse_mode='HTML'); return True
def main():
    symbols=discover_symbols(); data=fetch_history(symbols); results=[]
    for s,d in data.items():
        try:
            x=analyze(s,d)
            if x:results.append(x)
        except Exception as e:print(s,e)
    rev=[x for x in results if x['signal']=='REVERSAL']; rev.sort(key=lambda x:x['score'],reverse=True)
    if rev:
        lines=['<b>🔄 EGX REVERSAL</b>','أسهم بدأت تنهي التصحيح وتظهر علامات ارتداد:','']
        for x in rev[:10]:
            lines += [f"<b>{x['symbol']}</b> | Score {x['score']}/100",f"السعر: {x['close']} | التصحيح: {x['correction_pct']}% | الارتداد: {x['rebound_pct']}%",f"🎯 دخول: {x['entry_low']} - {x['entry_high']}",f"🛑 وقف: {x['stop']}",f"🎯 T1: {x['target1']} | T2: {x['target2']}",f"RSI: {x['rsi']} | Volume: {x['vol_ratio']}x",'• '+'\n• '.join(x['reasons'][:5]),'']
        send('\n'.join(lines))
    else: send('🔎 فحص EGX اكتمل\nلا توجد حاليًا إشارات REVERSAL مطابقة للشروط.')
if __name__=='__main__':main()
