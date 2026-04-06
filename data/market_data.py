"""
Market data layer — live price/vol data via yfinance.
"""

import logging
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

TICKERS: dict[str, dict[str, str]] = {
    "equities": {
        "SPY": "S&P 500 ETF",
        "QQQ": "NASDAQ 100 ETF",
        "IWM": "Russell 2000 ETF",
        "DIA": "Dow Jones ETF",
    },
    "fixed_income": {
        "TLT": "20Y US Treasury",
        "HYG": "High Yield Corp Bond",
        "LQD": "Investment Grade Corp",
        "AGG": "Aggregate Bond ETF",
    },
    "fx": {
        "EURUSD=X": "EUR/USD",
        "GBPUSD=X": "GBP/USD",
        "USDJPY=X": "USD/JPY",
        "AUDUSD=X": "AUD/USD",
    },
    "commodities": {
        "GC=F":  "Gold",
        "CL=F":  "Crude Oil (WTI)",
        "SI=F":  "Silver",
        "HG=F":  "Copper",
    },
}

ALL_TICKERS: list[str] = [t for group in TICKERS.values() for t in group]


def fetch_price_history(ticker: str, period: str = "30d", interval: str = "1d") -> pd.DataFrame:
    """Return OHLCV history for a single ticker."""
    try:
        data = yf.download(ticker, period=period, interval=interval,
                           progress=False, auto_adjust=True)
        data.columns = [c[0] if isinstance(c, tuple) else c for c in data.columns]
        return data
    except Exception as exc:
        logger.warning("yfinance download failed for %s: %s", ticker, exc)
        return pd.DataFrame()


def fetch_latest_quotes(asset_class: str | None = None) -> pd.DataFrame:
    """
    Return a summary DataFrame with latest price, 1-day return, and
    30-day realised volatility for all tickers (or a single asset class).
    """
    groups = {asset_class: TICKERS[asset_class]} if asset_class and asset_class in TICKERS else TICKERS
    rows = []

    for ac, ticker_map in groups.items():
        for ticker, name in ticker_map.items():
            try:
                hist = yf.download(ticker, period="35d", interval="1d",
                                   progress=False, auto_adjust=True)
                hist.columns = [c[0] if isinstance(c, tuple) else c for c in hist.columns]
                if hist.empty or len(hist) < 2:
                    continue

                close = hist["Close"].dropna()
                returns = close.pct_change().dropna()
                last_price = float(close.iloc[-1])
                day_return = float(returns.iloc[-1]) if len(returns) >= 1 else 0.0
                vol_30d = float(returns.std() * (252 ** 0.5)) if len(returns) >= 5 else 0.0
                ytd_return = float((close.iloc[-1] / close.iloc[0]) - 1) if len(close) >= 2 else 0.0

                rows.append({
                    "asset_class": ac,
                    "ticker": ticker,
                    "name": name,
                    "last_price": round(last_price, 4),
                    "day_return_pct": round(day_return * 100, 2),
                    "vol_30d_ann": round(vol_30d * 100, 2),
                    "period_return_pct": round(ytd_return * 100, 2),
                })
            except Exception as exc:
                logger.warning("Quote fetch failed for %s: %s", ticker, exc)

    return pd.DataFrame(rows)


def get_ticker_name(ticker: str) -> str:
    for group in TICKERS.values():
        if ticker in group:
            return group[ticker]
    return ticker
