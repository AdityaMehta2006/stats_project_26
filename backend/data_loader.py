"""
data_loader.py
--------------
Downloads and caches market data from Yahoo Finance and FRED.
All data is cached as CSV in backend/data/raw/ to avoid repeated downloads.
Supports any ticker available on Yahoo Finance or any FRED series.
"""

import os
import re
import ssl
import pandas as pd
import numpy as np
from datetime import datetime

# ---------------------------------------------------------------------------
# SSL workaround for Anaconda environments with broken cert chains.
# Patches curl_cffi (used by yfinance), requests, and urllib.
# ---------------------------------------------------------------------------
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. Patch curl_cffi (used by yfinance 1.x) — MUST come before `import yfinance`
import curl_cffi.requests as _cffi_requests
_cffi_orig_init = _cffi_requests.Session.__init__
def _cffi_patched_init(self, *a, **kw):
    kw["verify"] = False
    _cffi_orig_init(self, *a, **kw)
_cffi_requests.Session.__init__ = _cffi_patched_init

# Now safe to import yfinance
import yfinance as yf

# 2. Patch requests (for pandas_datareader / FRED downloads)
import requests as _requests
_orig_request = _requests.Session.request
def _patched_request(self, *a, **kw):
    kw.setdefault("verify", False)
    return _orig_request(self, *a, **kw)
_requests.Session.request = _patched_request

# 3. Patch urllib (for pd.read_csv with https URL)
ssl._create_default_https_context = ssl._create_unverified_context

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "raw")
os.makedirs(DATA_DIR, exist_ok=True)

# Clean up any empty/corrupted cached CSVs from failed downloads
for f in os.listdir(DATA_DIR):
    fpath = os.path.join(DATA_DIR, f)
    if f.endswith(".csv") and os.path.getsize(fpath) < 50:
        os.remove(fpath)

START = "2015-01-01"
END = "2025-12-31"



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_filename(name: str) -> str:
    """Convert a ticker/name to a safe filename."""
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name)


def _cache_path(name: str) -> str:
    return os.path.join(DATA_DIR, f"{_safe_filename(name)}.csv")


def _load_or_download(name: str, downloader):
    """Load from CSV cache, or download and cache."""
    path = _cache_path(name)
    if os.path.exists(path):
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        # Ensure DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index, errors="coerce")
            df = df[df.index.notna()]
        if len(df) > 0:
            return df
        # Cached file is empty/corrupted, re-download
        os.remove(path)
    df = downloader()
    if df is None or len(df) == 0:
        raise ValueError(f"Download returned empty data for '{name}'")
    df.to_csv(path)
    return df


# ---------------------------------------------------------------------------
# Ticker validation & search
# ---------------------------------------------------------------------------

def validate_ticker(ticker: str) -> dict:
    """
    Validate a Yahoo Finance ticker. Returns info dict or raises.
    """
    try:
        info = yf.Ticker(ticker).info
        name = info.get("shortName") or info.get("longName") or ticker
        asset_type = info.get("quoteType", "UNKNOWN")
        currency = info.get("currency", "USD")
        exchange = info.get("exchange", "")
        return {
            "ticker": ticker,
            "name": name,
            "type": asset_type,
            "currency": currency,
            "exchange": exchange,
            "valid": True,
        }
    except Exception:
        return {"ticker": ticker, "valid": False, "error": "Ticker not found"}


def search_tickers(query: str) -> list:
    """
    Search for tickers using yfinance. Returns a list of matches.
    """
    try:
        results = yf.Search(query)
        quotes = results.quotes if hasattr(results, 'quotes') else []
        out = []
        for q in quotes[:15]:
            out.append({
                "ticker": q.get("symbol", ""),
                "name": q.get("shortname") or q.get("longname", ""),
                "type": q.get("quoteType", ""),
                "exchange": q.get("exchange", ""),
            })
        return out
    except Exception:
        # Fallback: try direct validation
        info = validate_ticker(query.upper())
        if info.get("valid"):
            return [info]
        return []


# ---------------------------------------------------------------------------
# Yahoo Finance downloads — dynamic ticker support
# ---------------------------------------------------------------------------

def get_equity_data(ticker: str = "^GSPC") -> pd.DataFrame:
    """Download daily OHLCV for any Yahoo Finance ticker."""
    cache_name = f"equity_{_safe_filename(ticker)}"
    def _dl():
        data = yf.download(ticker, start=START, end=END, progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    return _load_or_download(cache_name, _dl)


def get_vix() -> pd.DataFrame:
    """CBOE VIX daily."""
    return get_equity_data("^VIX")


def get_oil() -> pd.DataFrame:
    """WTI Crude Oil futures daily."""
    return get_equity_data("CL=F")


# ---------------------------------------------------------------------------
# FRED macro data via pandas_datareader
# ---------------------------------------------------------------------------

def _download_fred(series_id: str, name: str) -> pd.DataFrame:
    """Download a FRED series with retry logic."""
    import io
    import time

    # FRED's public CSV endpoint rejects the default Python-urllib User-Agent
    # with HTTP 403, so we must send a browser-like UA. requests is already
    # patched above to skip SSL verification (Anaconda cert workaround).
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    url = (
        f"https://fred.stlouisfed.org/graph/fredgraph.csv"
        f"?id={series_id}&cosd={START}&coed={END}"
    )

    def _dl():
        errors = []
        # Method 1: direct CSV from FRED via requests with a browser UA (with retries)
        for attempt in range(3):
            try:
                resp = _requests.get(url, headers=headers, timeout=30)
                resp.raise_for_status()
                # FRED encodes missing observations as "." — treat as NaN.
                df = pd.read_csv(
                    io.StringIO(resp.text),
                    index_col=0,
                    parse_dates=True,
                    na_values=["."],
                )
                df.columns = [series_id]
                df[series_id] = pd.to_numeric(df[series_id], errors="coerce")
                df = df.dropna()
                if len(df) > 0:
                    return df
                errors.append(f"csv attempt {attempt}: empty after parse")
            except Exception as e:
                errors.append(f"csv attempt {attempt}: {e}")
                time.sleep(2 ** attempt)

        # Method 2: DBnomics — free FRED mirror, no API key, JSON API.
        try:
            db_url = f"https://api.db.nomics.world/v22/series/FRED/{series_id}?observations=1"
            resp = _requests.get(db_url, headers=headers, timeout=30)
            resp.raise_for_status()
            doc = resp.json()["series"]["docs"][0]
            s = pd.Series(doc["value"], index=pd.to_datetime(doc["period"]))
            s = pd.to_numeric(s, errors="coerce").dropna()
            s = s[(s.index >= START) & (s.index <= END)]
            if len(s) > 0:
                return s.to_frame(series_id)
        except Exception as e:
            errors.append(f"dbnomics: {e}")

        # Method 3: pandas_datareader fallback
        try:
            from pandas_datareader import data as pdr
            df = pdr.DataReader(series_id, "fred", START, END)
            if len(df) > 0:
                return df
        except Exception as e:
            errors.append(f"pdr: {e}")

        raise ValueError(f"Could not download FRED series '{series_id}': {'; '.join(errors[-3:])}")

    return _load_or_download(name, _dl)


def get_fed_funds_rate() -> pd.DataFrame:
    """Effective Federal Funds Rate (monthly)."""
    return _download_fred("FEDFUNDS", "fed_funds_rate")


def get_cpi() -> pd.DataFrame:
    """Consumer Price Index for All Urban Consumers (monthly)."""
    return _download_fred("CPIAUCSL", "cpi")


def get_treasury_10y_fred() -> pd.DataFrame:
    """
    10-Year Treasury yield (daily), returned as a single 'Treasury10Y' column.

    Primary source is Yahoo Finance ^TNX (CBOE 10-Year T-Note Yield) because it
    rides our reliable yfinance pipeline. FRED's daily DGS10 endpoint is prone to
    504s, so it is only used as a fallback if Yahoo returns nothing.
    """
    # Primary: Yahoo ^TNX
    try:
        tnx = get_equity_data("^TNX")["Close"].dropna()
        if len(tnx) > 0:
            df = tnx.to_frame("Treasury10Y")
            # ^TNX is quoted directly in percent (e.g. 4.25). Guard against the
            # occasional ×10 quoting convention so the yield stays realistic.
            if df["Treasury10Y"].median() > 25:
                df = df / 10.0
            return df
    except Exception:
        pass
    # Fallback: FRED DGS10
    df = _download_fred("DGS10", "treasury_10y_fred")
    df.columns = ["Treasury10Y"]
    return df


def get_unemployment() -> pd.DataFrame:
    """US Unemployment Rate (monthly)."""
    return _download_fred("UNRATE", "unemployment")


# ---------------------------------------------------------------------------
# Forex data — dynamic pair support
# ---------------------------------------------------------------------------

DEFAULT_FOREX_PAIRS = {
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCHF": "USDCHF=X",
    "EURGBP": "EURGBP=X",
}

# Extended list of all commonly available forex pairs
ALL_FOREX_PAIRS = {
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X", "USDCHF": "USDCHF=X", "EURGBP": "EURGBP=X",
    "USDCAD": "USDCAD=X", "NZDUSD": "NZDUSD=X", "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X", "EURCHF": "EURCHF=X", "AUDJPY": "AUDJPY=X",
    "EURAUD": "EURAUD=X", "GBPAUD": "GBPAUD=X", "GBPCAD": "GBPCAD=X",
    "EURCAD": "EURCAD=X", "AUDCAD": "AUDCAD=X", "NZDJPY": "NZDJPY=X",
    "AUDNZD": "AUDNZD=X", "CADJPY": "CADJPY=X", "CHFJPY": "CHFJPY=X",
    "GBPCHF": "GBPCHF=X", "GBPNZD": "GBPNZD=X", "EURNZD": "EURNZD=X",
    "AUDCHF": "AUDCHF=X", "CADCHF": "CADCHF=X", "NZDCAD": "NZDCAD=X",
    "NZDCHF": "NZDCHF=X", "USDINR": "USDINR=X", "USDSGD": "USDSGD=X",
    "USDHKD": "USDHKD=X", "USDMXN": "USDMXN=X", "USDZAR": "USDZAR=X",
    "USDTRY": "USDTRY=X", "USDNOK": "USDNOK=X", "USDSEK": "USDSEK=X",
    "USDDKK": "USDDKK=X", "USDPLN": "USDPLN=X", "USDHUF": "USDHUF=X",
    "USDCZK": "USDCZK=X", "USDTHB": "USDTHB=X", "USDKRW": "USDKRW=X",
    "USDTWD": "USDTWD=X", "USDCNY": "USDCNY=X", "USDBRL": "USDBRL=X",
}


def get_available_forex() -> list:
    """Return list of all available forex pairs."""
    return [{"label": k, "ticker": v} for k, v in ALL_FOREX_PAIRS.items()]


def get_forex(pair_labels: list = None) -> pd.DataFrame:
    """
    Download forex pairs, return DataFrame of daily Close prices.
    pair_labels: list of friendly names like ["EURUSD", "GBPUSD", ...].
                 If None, uses DEFAULT_FOREX_PAIRS.
    """
    if pair_labels is None:
        pairs_map = DEFAULT_FOREX_PAIRS
    else:
        pairs_map = {}
        for label in pair_labels:
            label_upper = label.upper().replace("/", "").replace(" ", "")
            if label_upper in ALL_FOREX_PAIRS:
                pairs_map[label_upper] = ALL_FOREX_PAIRS[label_upper]
            else:
                # Try as raw yfinance ticker (e.g., "EURUSD=X")
                clean = label_upper.replace("=X", "")
                pairs_map[clean] = f"{clean}=X" if "=X" not in label_upper else label_upper

    cache_key = "forex_" + "_".join(sorted(pairs_map.keys()))
    def _dl():
        tickers = list(pairs_map.values())
        data = yf.download(tickers, start=START, end=END, progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            close = data["Close"]
        else:
            close = data[["Close"]]
            close.columns = ["Close"]
        reverse_map = {v: k for k, v in pairs_map.items()}
        close.columns = [reverse_map.get(c, c) for c in close.columns]
        return close
    df = _load_or_download(cache_key, _dl)
    # Drop any pair that came back entirely empty (e.g. a ticker yfinance
    # failed to fetch). Otherwise a single dead column makes the downstream
    # .dropna() wipe out every row, leaving an empty frame.
    df = df.dropna(axis=1, how="all")
    return df


# ---------------------------------------------------------------------------
# Composite dataset builders — dynamic ticker support
# ---------------------------------------------------------------------------

def _monthly_log_return(ticker: str) -> pd.Series:
    """Monthly log return of a Yahoo ticker's Close price."""
    px = get_equity_data(ticker)["Close"].resample("ME").last()
    return np.log(px / px.shift(1)).dropna()


def build_macro_dataset(ticker: str = "^GSPC") -> pd.DataFrame:
    """
    Build a monthly-frequency dataset for any equity ticker.

    Each macro factor is fetched defensively: if a single data source is
    unavailable, that factor is skipped (with a log line) rather than failing
    the whole dataset. Only the equity return is mandatory.

    Factors:
      - VIX monthly average            (Yahoo)
      - Oil monthly return             (Yahoo, CL=F)
      - Gold monthly return            (Yahoo, GC=F)
      - US Dollar Index monthly return (Yahoo, DX-Y.NYB)
      - 10Y Treasury yield             (Yahoo ^TNX, FRED DGS10 fallback)
      - Fed Funds Rate                 (FRED)
      - CPI monthly % change           (FRED, inflation proxy)
      - Unemployment rate              (FRED)
    """
    # Equity monthly returns (required)
    eq_ret = _monthly_log_return(ticker)
    eq_ret.name = "Equity_Return"
    frames = [eq_ret]

    def _add(name: str, fn):
        try:
            s = fn()
            s.name = name
            frames.append(s)
        except Exception as e:  # noqa: BLE001 — skip any factor that won't load
            print(f"[build_macro_dataset] skipping factor '{name}': {e}")

    # Market factors (Yahoo Finance)
    _add("VIX",           lambda: get_vix()["Close"].resample("ME").mean())
    _add("Oil_Return",    lambda: _monthly_log_return("CL=F"))
    _add("Gold_Return",   lambda: _monthly_log_return("GC=F"))
    _add("Dollar_Return", lambda: _monthly_log_return("DX-Y.NYB"))
    _add("Treasury10Y",   lambda: get_treasury_10y_fred().resample("ME").last().iloc[:, 0])

    # Macro factors (FRED)
    _add("FedFunds",      lambda: get_fed_funds_rate().resample("ME").last().iloc[:, 0])
    _add("CPI_Change",    lambda: get_cpi().resample("ME").last().pct_change(fill_method=None).dropna().iloc[:, 0])
    _add("Unemployment",  lambda: get_unemployment().resample("ME").last().iloc[:, 0])

    # Merge all available factors on common dates
    df = pd.concat(frames, axis=1, join="inner")
    df.dropna(inplace=True)
    return df


def build_equity_returns(ticker: str = "^GSPC") -> pd.Series:
    """Daily log returns of any equity ticker."""
    eq = get_equity_data(ticker)["Close"]
    returns = np.log(eq / eq.shift(1)).dropna()
    returns.name = f"{ticker}_LogReturn"
    return returns
