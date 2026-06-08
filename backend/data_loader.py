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
    import time

    def _dl():
        errors = []
        # Method 1: pandas_datareader (uses requests — patched for SSL)
        try:
            from pandas_datareader import data as pdr
            df = pdr.DataReader(series_id, "fred", START, END)
            if len(df) > 0:
                return df
        except Exception as e:
            errors.append(f"pdr: {e}")

        # Method 2: direct CSV from FRED (with retries)
        for attempt in range(3):
            try:
                url = (
                    f"https://fred.stlouisfed.org/graph/fredgraph.csv"
                    f"?id={series_id}&cosd={START}&coed={END}"
                )
                df = pd.read_csv(url, index_col=0, parse_dates=True)
                df.columns = [series_id]
                if len(df) > 0:
                    return df
            except Exception as e:
                errors.append(f"csv attempt {attempt}: {e}")
                time.sleep(2 ** attempt)

        raise ValueError(f"Could not download FRED series '{series_id}': {'; '.join(errors[-2:])}")

    return _load_or_download(name, _dl)


def get_fed_funds_rate() -> pd.DataFrame:
    """Effective Federal Funds Rate (monthly)."""
    return _download_fred("FEDFUNDS", "fed_funds_rate")


def get_cpi() -> pd.DataFrame:
    """Consumer Price Index for All Urban Consumers (monthly)."""
    return _download_fred("CPIAUCSL", "cpi")


def get_treasury_10y_fred() -> pd.DataFrame:
    """10-Year Treasury Constant Maturity Rate (daily) from FRED."""
    return _download_fred("DGS10", "treasury_10y_fred")


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
    "USDTWD": "USDTWD=X", "USDCNY": "USDCNY=X", "USDBRL": "USDTRY=X",
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
    return _load_or_download(cache_key, _dl)


# ---------------------------------------------------------------------------
# Composite dataset builders — dynamic ticker support
# ---------------------------------------------------------------------------

def build_macro_dataset(ticker: str = "^GSPC") -> pd.DataFrame:
    """
    Build a monthly-frequency dataset for any equity ticker:
      - Ticker monthly log return
      - VIX monthly average
      - Oil monthly return
      - Fed Funds Rate
      - CPI monthly % change (inflation proxy)
      - 10Y Treasury yield
      - Unemployment rate
    """
    # Equity monthly returns
    eq = get_equity_data(ticker)["Close"].resample("ME").last()
    eq_ret = np.log(eq / eq.shift(1)).dropna()
    eq_ret.name = "Equity_Return"

    # VIX monthly average
    vix = get_vix()["Close"].resample("ME").mean()
    vix.name = "VIX"

    # Oil monthly return
    oil = get_oil()["Close"].resample("ME").last()
    oil_ret = np.log(oil / oil.shift(1)).dropna()
    oil_ret.name = "Oil_Return"

    # FRED series (already monthly or daily → resample)
    ffr = get_fed_funds_rate()
    ffr = ffr.resample("ME").last()
    ffr.columns = ["FedFunds"]

    cpi = get_cpi()
    cpi = cpi.resample("ME").last()
    cpi_chg = cpi.pct_change().dropna()
    cpi_chg.columns = ["CPI_Change"]

    t10y = get_treasury_10y_fred()
    t10y = t10y.resample("ME").last()
    t10y.columns = ["Treasury10Y"]

    unemp = get_unemployment()
    unemp = unemp.resample("ME").last()
    unemp.columns = ["Unemployment"]

    # Merge all
    df = pd.concat(
        [eq_ret, vix, oil_ret, ffr, cpi_chg, t10y, unemp],
        axis=1, join="inner"
    )
    df.dropna(inplace=True)
    return df


def build_equity_returns(ticker: str = "^GSPC") -> pd.Series:
    """Daily log returns of any equity ticker."""
    eq = get_equity_data(ticker)["Close"]
    returns = np.log(eq / eq.shift(1)).dropna()
    returns.name = f"{ticker}_LogReturn"
    return returns
