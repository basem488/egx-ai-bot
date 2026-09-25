import io
import re
import time
from typing import List, Dict

import pandas as pd
import requests
import yfinance as yf

UNIVERSE_URLS = [
    "https://hesapegypt.com/en/stocks",
    "https://directfn.com.eg/tradingData.aspx",
]

# The EGX bank-sector classification currently contains these 13 listings.
BANK_SYMBOLS = {
    "COMI", "QNBE", "HDBK", "ADIB", "CANA", "CIEB", "FAIT", "FAITA",
    "EXPA", "SAUD", "UBEE", "EGBE", "SAIB",
}

# Used only if the public universe pages cannot be reached.
FALLBACK_SYMBOLS = """
TMGH ETEL SWDY ORAS HRHO BTFH EKHO PHDC ORWE ISPH EAST MFPC EMFD FWRY JUFO
CCAP OFH KORA RUBX OIH TAQA CRST ORHD EGCH NAPR ACTF MPCO NIPH MAAL GTWL GIHD
SKPC GBCO AMOC IEEC PHAR HELI MPCI ACAMD EGAL ATQA NCCW ZMID EGTS ABUK EFID MCRO
EFIH ELEC RMDA MASR ADRI ARAB OCDI VLMR DTPP EFIC KRDI UEGC GDWA MOIL RAYA MBSC AMER
AJWA ALCN LUTS DAPH BONY CLHO TALM SCEM NHPS INFI BINV INEG ADPC MHOT KABO ARCC SDTI
NINH ACGC DSCW COPR MOED GOUR COSG AIH ELKA CIRA AIDC ASCM KZPC MICH MTIE MEPA SIPC
ISMQ ELSH EEII ENGC BIOC SPMD AMII MPRC AALR PRCL LCSW ICFC AXPH TYCN VLMR MCQE SNFC
GGCC SUGR OBRI OLFI ATLC AMIA GPIM AFMC PHGC AIFI KWIN IRON NARE ODIN GGRN UNIP CCRS
EGAS CNFN ETRS IDRE ISMA RREI GRCA IFAP ALUM CAED ICID AFDI ECAP MOIN MIPH ZEOT AREH
VALU RACC WKOL CSAG SPIN EALR CPME FERC EPCO EGREF SMFR EASB FNAR MILS TWSA PRMH ROTO
UNIT DOMT RKAZ CPCI MBEG MENA OCPH GSSC UEFM MOSC DGTZ EBSC WCDF ACAP NAHO CEFM MFSC
RTVC ADCI PHTV SCFM GTEX CICH IBCT SCTS BIGP LKGP SEIG ELWA TRTO EDFM APSW VERT FIRE
UTOP NEDA TORA MMAT GMCI SUCE PACH EOSB AMPI FTNS SNFI UPMS ELNA EGSA CFGH ALEX RAKT
DCRC NCGC GTHE APPC IRAX EITP SMPP EHDR ESRS EPPK ESAC FCMD GOCO HBCO HCFI
""".split()


def _valid_symbol(s: str) -> bool:
    s = s.strip().upper()
    return bool(re.fullmatch(r"[A-Z]{2,5}", s)) and s not in BANK_SYMBOLS


def discover_symbols() -> List[str]:
    found = set()
    headers = {"User-Agent": "Mozilla/5.0 EGX-AI research app"}
    for url in UNIVERSE_URLS:
        try:
            r = requests.get(url, headers=headers, timeout=15)
            r.raise_for_status()
            # These public pages render a table containing the exchange symbols.
            text = r.text.upper()
            for sym in re.findall(r"\b[A-Z]{2,5}\b", text):
                if _valid_symbol(sym):
                    found.add(sym)
        except Exception as exc:
            print(f"universe source failed {url}: {exc}")
    if len(found) >= 50:
        return sorted(found)
    return sorted({s for s in FALLBACK_SYMBOLS if _valid_symbol(s)})


def _flatten(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        # yfinance returns either (field, ticker) or (ticker, field).
        if symbol in df.columns.get_level_values(-1):
            df = df.xs(symbol, axis=1, level=-1, drop_level=True)
        elif symbol in df.columns.get_level_values(0):
            df = df.xs(symbol, axis=1, level=0, drop_level=True)
        else:
            # Single-ticker downloads can still have a one-item MultiIndex.
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    df = df.reset_index()
    rename = {str(c).lower(): c for c in df.columns}
    required = {}
    for want in ["Date", "Open", "High", "Low", "Close", "Volume"]:
        for k, original in rename.items():
            if k == want.lower():
                required[original] = want
                break
    df = df.rename(columns=required)
    cols = [c for c in ["Date", "Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    if len(cols) < 6:
        return pd.DataFrame()
    df = df[cols].dropna(subset=["Close"])
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.tz_localize(None)
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["Date", "Open", "High", "Low", "Close"]).sort_values("Date")


def fetch_history(symbols: List[str], period: str = "3y") -> Dict[str, pd.DataFrame]:
    out = {}
    symbols = [s for s in symbols if s not in BANK_SYMBOLS]
    # Yahoo uses .CA for EGX equities. Batch in modest chunks to reduce rate-limit risk.
    for i in range(0, len(symbols), 40):
        chunk = symbols[i:i+40]
        tickers = [f"{s}.CA" for s in chunk]
        try:
            raw = yf.download(
                tickers=tickers,
                period=period,
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=True,
                group_by="ticker",
                timeout=20,
            )
            for s in chunk:
                try:
                    d = _flatten(raw, f"{s}.CA")
                    if len(d) >= 220:
                        out[s] = d
                except Exception as exc:
                    print(f"normalize failed {s}: {exc}")
        except Exception as exc:
            print(f"Yahoo batch failed ({i}:{i+len(chunk)}): {exc}")
        time.sleep(0.5)
    return out
