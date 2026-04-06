# Cross-Asset Risk Intelligence Dashboard
### Memorandum to the Chief Risk Officer

---

**To:** Chief Risk Officer  
**From:** Risk Technology, Quantitative Strategies  
**Subject:** Deployment Brief — Cross-Asset Risk Intelligence Platform  
**Classification:** Internal Use Only

---

## Executive Summary

This platform operationalises a real-time, NLP-driven risk monitoring capability across four asset classes (equities, fixed income, FX, and commodities) and five risk dimensions (credit, market, geopolitical, operational, and liquidity). It ingests financial news at source, scores sentiment using a domain-fine-tuned language model (FinBERT), applies a rule-based risk taxonomy classifier, and surfaces the results through an interactive dashboard backed by live market data and Federal Reserve macro indicators.

The intent is to reduce the lag between a newsworthy risk event and its appearance in the portfolio risk management workflow — from hours to minutes.

---

## Architecture Overview

```
NewsAPI ──► news_ingestion.py ──► SQLite (risk_dashboard.db)
                                        │
yfinance ──► market_data.py             │
                                        ▼
fredapi  ──► macro_data.py      nlp/finbert_pipeline.py  (ProsusAI/finbert)
                                        │
                                nlp/classifier.py         (rule-based)
                                        │
                                        ▼
                               dashboard/ (Streamlit, 4 pages)
```

### Data Sources
| Source | Coverage | Refresh |
|--------|----------|---------|
| **NewsAPI** | Financial headlines across 8 query themes, 9 premium domains | On-demand / scheduled |
| **yfinance** | SPY, QQQ, IWM, DIA, TLT, HYG, LQD, AGG, EUR/USD, GBP/USD, USD/JPY, AUD/USD, Gold, Oil, Silver, Copper | 15-min cache |
| **FRED (St. Louis Fed)** | VIX, 10Y–2Y spread, HY OAS, DXY, 10Y yield, Fed Funds | 15-min cache |

### NLP Pipeline
1. **FinBERT** (`ProsusAI/finbert`) — financial-domain BERT model returning positive / negative / neutral probabilities with confidence score
2. **Rule-based classifier** — keyword-weighted taxonomy assigning:
   - `risk_type`: credit · market · geopolitical · operational · liquidity
   - `asset_class`: equities · fixed_income · fx · commodities
   - `severity`: 1 (informational) → 5 (crisis)
   - `direction`: positive · negative · neutral for exposed positions

---

## Dashboard Pages

| Page | Purpose |
|------|---------|
| **Overview** | Risk heatmap (asset class × risk type), sentiment trend lines, live event feed with severity badges and filters |
| **Asset Drilldown** | Per-asset-class price charts, 30-day vol, 30-day returns, filtered event feed, one-click to Event Detail |
| **Event Detail** | Full FinBERT probability distribution, classification breakdown, regime context, similar event linkage |
| **Macro Backdrop** | Live FRED panel, 90-day historical charts, automated regime assessment (Risk-On / Elevated / Crisis) |

The macro panel (VIX, yield curve, HY spread, DXY) is surfaced in the sidebar on **every page** so the backdrop is always in view.

---

## Setup

### Prerequisites
- Python 3.10+
- ~1 GB free disk (FinBERT model download on first run)

### Installation

```bash
cd risk-dashboard
pip install -r requirements.txt
```

### Configuration

Edit `.env`:

```env
NEWS_API_KEY=55985387ad244aa6aa87cabe983d3007
FRED_API_KEY=<your_free_key_from_fred.stlouisfed.org>
```

> FRED API keys are free. Register at: https://fred.stlouisfed.org/docs/api/api_key.html

### Running the Pipeline

```bash
# Fetch headlines, run FinBERT, classify, persist to SQLite
python ingest.py

# Optional: specify lookback window
python ingest.py --days 7
```

**First run:** FinBERT model downloads from HuggingFace (~440 MB). Cached locally thereafter.

### Launching the Dashboard

```bash
streamlit run dashboard/app.py
```

Navigate to `http://localhost:8501` — the dashboard includes a one-click pipeline trigger on the landing page.

---

## Project Structure

```
risk-dashboard/
├── .env                          # API keys (not committed)
├── .streamlit/config.toml        # Dark theme + server config
├── requirements.txt
├── ingest.py                     # Master pipeline orchestrator
├── risk_dashboard.db             # SQLite (created on first ingest)
│
├── data/
│   ├── database.py               # Schema, insert helpers, query layer
│   ├── news_ingestion.py         # NewsAPI fetcher + deduplication
│   ├── market_data.py            # yfinance price/vol/returns
│   └── macro_data.py             # FRED series fetcher
│
├── nlp/
│   ├── finbert_pipeline.py       # FinBERT sentiment (batch + single)
│   └── classifier.py             # Rule-based risk taxonomy
│
└── dashboard/
    ├── app.py                    # Landing page + pipeline trigger
    ├── components/
    │   ├── macro_sidebar.py      # Always-visible macro panel
    │   └── charts.py             # All Plotly chart renderers
    └── pages/
        ├── 1_Overview.py
        ├── 2_Asset_Drilldown.py
        ├── 3_Event_Detail.py
        └── 4_Macro_Backdrop.py
```

---

## Operational Notes

**Severity Scale**

| Level | Label | Trigger Criteria |
|-------|-------|-----------------|
| 5 | CRITICAL | Systemic language: "collapse", "crisis", "contagion", "meltdown" |
| 4 | HIGH | "plunge", "surge", "shock", "warning", "alarm" |
| 3 | MODERATE | "risk", "concern", "pressure", "volatile", "uncertainty" |
| 2 | WATCH | "slight", "marginal", "modest" movement language |
| 1 | LOW | General financial reporting, no stress signals detected |

**Known Limitations**
- NewsAPI free tier returns up to 100 articles per query; premium tier recommended for production
- FinBERT runs on CPU by default; set `device=0` in `finbert_pipeline.py` for GPU acceleration
- FRED data has publication lag (typically T+1 to T+5 depending on series)
- Rule-based classifier is keyword-weighted; consider fine-tuning on labelled internal events for higher precision

**Recommended Schedule (via cron or task scheduler)**
```cron
# Fetch and process news every 2 hours during market hours
0 8,10,12,14,16,18 * * 1-5  cd /path/to/risk-dashboard && python ingest.py
```

---

*This platform is intended as a decision-support tool. All risk classifications should be reviewed by qualified risk personnel before informing portfolio or hedging decisions.*
