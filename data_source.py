import time
from typing import List, Dict

import pandas as pd
import yfinance as yf


# =========================
# EGX BANKS
# =========================

BANK_SYMBOLS = {
    "COMI",
    "QNBE",
    "HDBK",
    "ADIB",
    "CANA",
    "CIEB",
    "FAIT",
    "FAITA",
    "EXPA",
    "SAUD",
    "UBEE",
    "EGBE",
    "SAIB",
}


# =========================
# EGX SYMBOLS
# =========================

FALLBACK = """
TMGH ETEL SWDY ORAS HRHO BTFH EKHO PHDC ORWE ISPH EAST
MFPC EMFD FWRY JUFO CCAP OFH KORA RUBX OIH TAQA CRST
ORHD EGCH NAPR ACTF MPCO NIPH MAAL GTWL GIHD SKPC GBCO
AMOC IEEC PHAR HELI MPCI ACAMD EGAL ATQA NCCW ZMID EGTS
ABUK EFID MCRO EFIH ELEC RMDA MASR ADRI ARAB OCDI VLMR
DTPP EFIC KRDI UEGC GDWA MOIL RAYA MBSC AMER AJWA ALCN
LUTS DAPH BONY CLHO TALM SCEM NHPS INFI BINV INEG ADPC
MHOT KABO ARCC SDTI NINH ACGC DSCW COPR MOED GOUR COSG
AIH ELKA CIRA AIDC ASCM KZPC MICH MTIE MEPA SIPC ISMQ
ELSH EEII ENGC BIOC SPMD AMII MPRC AALR PRCL LCSW ICFC
AXPH TYCN MCQE SNFC GGCC SUGR OBRI OLFI ATLC AMIA GPIM
AFMC PHGC AIFI KWIN IRON NARE ODIN GGRN UNIP CCRS EGAS
CNFN ETRS IDRE ISMA RREI GRCA IFAP ALUM CAED ICID AFDI
ECAP MOIN MIPH ZEOT AREH VALU RACC WKOL CSAG SPIN EALR
CPME FERC EPCO EGREF SMFR EASB FNAR MILS TWSA PRMH ROTO
UNIT DOMT RKAZ CPCI MBEG MENA OCPH GSSC UEFM MOSC DGTZ
EBSC WCDF ACAP NAHO CEFM MFSC RTVC ADCI PHTV SCFM GTEX
CICH IBCT SCTS BIGP LKGP SEIG ELWA TRTO EDFM APSW VERT
FIRE UTOP NEDA TORA MMAT GMCI SUCE PACH EOSB AMPI FTNS
SNFI UPMS ELNA EGSA CFGH ALEX RAKT DCRC NCGC GTHE APPC
IRAX EITP SMPP EHDR ESRS EPPK ESAC FCMD GOCO HBCO HCFI
""".split()


# =========================
# GET UNIVERSE
# =========================

def discover_symbols() -> List[str]:
    """
    Return a fixed list of known EGX symbols.

    IMPORTANT:
    We intentionally do NOT scrape random uppercase words
    from websites because that produces fake symbols such as
    ADMIN, APPLE, HTML, STYLE, etc.
    """

    symbols = set(FALLBACK)
    symbols.update(BANK_SYMBOLS)

    return sorted(symbols)


# =========================
# FLATTEN YAHOO DATA
# =========================

def _flatten(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    try:
        # Yahoo may return MultiIndex columns when downloading
        # several symbols at once.
        if isinstance(df.columns, pd.MultiIndex):

            if symbol in df.columns.get_level_values(-1):
                df = df.xs(
                    symbol,
                    axis=1,
                    level=-1,
                    drop_level=True
                )

            elif symbol in df.columns.get_level_values(0):
                df = df.xs(
                    symbol,
                    axis=1,
                    level=0,
                    drop_level=True
                )

            else:
                df.columns = [
                    c[0] if isinstance(c, tuple) else c
                    for c in df.columns
                ]

        df = df.reset_index()

        df.columns = [str(c) for c in df.columns]

        rename = {
            c.lower(): c
            for c in df.columns
        }

        req = {}

        for wanted in [
            "Date",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]:
            if wanted.lower() in rename:
                req[rename[wanted.lower()]] = wanted

        df = df.rename(columns=req)

        required = [
            "Date",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]

        if not all(c in df.columns for c in required):
            return pd.DataFrame()

        df = df[required]

        df = df.dropna(
            subset=["Close"]
        )

        # Date
        df["Date"] = pd.to_datetime(
            df["Date"],
            errors="coerce"
        )

        try:
            df["Date"] = df["Date"].dt.tz_localize(None)
        except Exception:
            pass

        # Numeric columns
        for col in [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )

        df = df.dropna()

        df = df.sort_values("Date")

        return df

    except Exception as e:
        print(
            f"Flatten failed for {symbol}: {e}"
        )
        return pd.DataFrame()


# =========================
# DOWNLOAD HISTORY
# =========================

def fetch_history(symbols: List[str]) -> Dict[str, pd.DataFrame]:
    """
    Download historical data for EGX symbols.

    Yahoo EGX ticker format:
        COMI -> COMI.CA
        TMGH -> TMGH.CA
    """

    out = {}

    # Clean symbols
    cleaned = []

    for symbol in symbols:
        if not symbol:
            continue

        symbol = str(symbol).strip().upper()

        if symbol:
            cleaned.append(symbol)

    # Remove duplicates while keeping order
    symbols = list(dict.fromkeys(cleaned))

    # Smaller batches reduce Yahoo failures/rate limits
    batch_size = 20

    for i in range(0, len(symbols), batch_size):

        chunk = symbols[
            i:i + batch_size
        ]

        yahoo_symbols = [
            f"{s}.CA"
            for s in chunk
        ]

        print(
            f"Downloading batch "
            f"{i + 1}-{i + len(chunk)} "
            f"of {len(symbols)}"
        )

        try:

            raw = yf.download(
                yahoo_symbols,
                period="3y",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=True,
                group_by="ticker",
                timeout=30,
            )

            if raw is None or raw.empty:
                print(
                    "No data returned for this batch."
                )
                time.sleep(1)
                continue

            for symbol in chunk:

                yahoo_symbol = f"{symbol}.CA"

                data = _flatten(
                    raw,
                    yahoo_symbol
                )

                # We need enough history
                # for indicators to work properly.
                if len(data) >= 220:

                    out[symbol] = data

                    print(
                        f"OK: {symbol} "
                        f"({len(data)} rows)"
                    )

                else:

                    print(
                        f"SKIP: {symbol} "
                        f"only {len(data)} rows"
                    )

        except Exception as e:

            print(
                f"Yahoo batch failed: {e}"
            )

        # Small delay between batches
        time.sleep(1)

    print(
        f"Downloaded successfully: "
        f"{len(out)} / {len(symbols)} symbols"
    )

    return out


# =========================
# SINGLE STOCK
# =========================

def fetch_single_history(symbol: str) -> pd.DataFrame:
    """
    Download one specific EGX stock.

    Example:
        fetch_single_history("COMI")
    """

    if not symbol:
        return pd.DataFrame()

    symbol = str(symbol).strip().upper()

    # Remove .CA if user accidentally includes it
    if symbol.endswith(".CA"):
        symbol = symbol[:-3]

    yahoo_symbol = f"{symbol}.CA"

    print(
        f"Downloading single stock: "
        f"{yahoo_symbol}"
    )

    try:

        raw = yf.download(
            yahoo_symbol,
            period="3y",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
            group_by="ticker",
            timeout=30,
        )

        data = _flatten(
            raw,
            yahoo_symbol
        )

        if len(data) >= 220:
            return data

        print(
            f"Not enough data for {symbol}: "
            f"{len(data)} rows"
        )

        return pd.DataFrame()

    except Exception as e:

        print(
            f"Single stock download failed "
            f"for {symbol}: {e}"
        )

        return pd.DataFrame()
