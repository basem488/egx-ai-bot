import re,time
from typing import List,Dict
import pandas as pd
import requests,yfinance as yf
BANK_SYMBOLS={"COMI","QNBE","HDBK","ADIB","CANA","CIEB","FAIT","FAITA","EXPA","SAUD","UBEE","EGBE","SAIB"}
FALLBACK='TMGH ETEL SWDY ORAS HRHO BTFH EKHO PHDC ORWE ISPH EAST MFPC EMFD FWRY JUFO CCAP OFH KORA RUBX OIH TAQA CRST ORHD EGCH NAPR ACTF MPCO NIPH MAAL GTWL GIHD SKPC GBCO AMOC IEEC PHAR HELI MPCI ACAMD EGAL ATQA NCCW ZMID EGTS ABUK EFID MCRO EFIH ELEC RMDA MASR ADRI ARAB OCDI VLMR DTPP EFIC KRDI UEGC GDWA MOIL RAYA MBSC AMER AJWA ALCN LUTS DAPH BONY CLHO TALM SCEM NHPS INFI BINV INEG ADPC MHOT KABO ARCC SDTI NINH ACGC DSCW COPR MOED GOUR COSG AIH ELKA CIRA AIDC ASCM KZPC MICH MTIE MEPA SIPC ISMQ ELSH EEII ENGC BIOC SPMD AMII MPRC AALR PRCL LCSW ICFC AXPH TYCN MCQE SNFC GGCC SUGR OBRI OLFI ATLC AMIA GPIM AFMC PHGC AIFI KWIN IRON NARE ODIN GGRN UNIP CCRS EGAS CNFN ETRS IDRE ISMA RREI GRCA IFAP ALUM CAED ICID AFDI ECAP MOIN MIPH ZEOT AREH VALU RACC WKOL CSAG SPIN EALR CPME FERC EPCO EGREF SMFR EASB FNAR MILS TWSA PRMH ROTO UNIT DOMT RKAZ CPCI MBEG MENA OCPH GSSC UEFM MOSC DGTZ EBSC WCDF ACAP NAHO CEFM MFSC RTVC ADCI PHTV SCFM GTEX CICH IBCT SCTS BIGP LKGP SEIG ELWA TRTO EDFM APSW VERT FIRE UTOP NEDA TORA MMAT GMCI SUCE PACH EOSB AMPI FTNS SNFI UPMS ELNA EGSA CFGH ALEX RAKT DCRC NCGC GTHE APPC IRAX EITP SMPP EHDR ESRS EPPK ESAC FCMD GOCO HBCO HCFI'.split()
def discover_symbols():
    found=set(); headers={'User-Agent':'Mozilla/5.0 EGX AI Telegram bot'}
    for url in ['https://hesapegypt.com/en/stocks','https://directfn.com.eg/tradingData.aspx']:
        try:
            r=requests.get(url,headers=headers,timeout=15); r.raise_for_status()
            for s in re.findall(r'\b[A-Z]{2,5}\b',r.text.upper()):
                if s not in BANK_SYMBOLS: found.add(s)
        except Exception as e: print('universe source failed',url,e)
    return sorted(found) if len(found)>=50 else sorted(set(FALLBACK)-BANK_SYMBOLS)
def _flatten(df,symbol):
    if df is None or df.empty:return pd.DataFrame()
    if isinstance(df.columns,pd.MultiIndex):
        if symbol in df.columns.get_level_values(-1): df=df.xs(symbol,axis=1,level=-1,drop_level=True)
        elif symbol in df.columns.get_level_values(0): df=df.xs(symbol,axis=1,level=0,drop_level=True)
        else: df.columns=[c[0] if isinstance(c,tuple) else c for c in df.columns]
    df=df.reset_index(); df.columns=[str(c) for c in df.columns]
    rename={c.lower():c for c in df.columns}; req={}
    for want in ['Date','Open','High','Low','Close','Volume']:
        if want.lower() in rename:req[rename[want.lower()]]=want
    df=df.rename(columns=req); cols=['Date','Open','High','Low','Close','Volume']
    if not all(c in df.columns for c in cols): return pd.DataFrame()
    df=df[cols].dropna(subset=['Close']); df['Date']=pd.to_datetime(df.Date,errors='coerce').dt.tz_localize(None)
    for c in cols[1:]:df[c]=pd.to_numeric(df[c],errors='coerce')
    return df.dropna().sort_values('Date')
def fetch_history(symbols):
    out={}; symbols=[s for s in symbols if s not in BANK_SYMBOLS]
    for i in range(0,len(symbols),40):
        chunk=symbols[i:i+40]
        try:
            raw=yf.download([f'{s}.CA' for s in chunk],period='3y',interval='1d',auto_adjust=False,progress=False,threads=True,group_by='ticker',timeout=20)
            for s in chunk:
                d=_flatten(raw,f'{s}.CA')
                if len(d)>=220:out[s]=d
        except Exception as e: print('Yahoo batch failed',e)
        time.sleep(.5)
    return out
