# Cross-Asset Risk Intelligence Dashboard

A live risk monitoring dashboard that reads financial news, scores sentiment with a finance trained language model, classifies events by asset class and risk type, and shows everything in one place alongside real time market and macroeconomic data.

**Live app:** [risk-dashboard.streamlit.app](https://risk-dashboard.streamlit.app) *(add your Streamlit Cloud URL here)*

---

## What It Does

Most risk teams find out about a market moving event from a colleague, a news alert, or an end of day report. By then the price has already moved. This dashboard is my attempt to close that gap.

Every time the app runs, it pulls the latest financial headlines, runs them through a sentiment model trained specifically on financial text, tags each story by asset class and risk type, groups duplicate stories from different outlets into a single event, and puts a composite risk score on it. The result is a live feed of ranked risk events that updates continuously, with six Federal Reserve indicators always visible in the sidebar so you never lose sight of the macro backdrop.

I built this to be something a portfolio manager or risk analyst can actually open in the morning and use — not a proof of concept, but a working tool.

---

## Screenshots

| Risk Events | Risk Trends | Market Summary |
|-------------|-------------|----------------|
| *(screenshot)* | *(screenshot)* | *(screenshot)* |

> To add screenshots: drop images into a `docs/` folder and replace the placeholders above with `![Risk Events](docs/risk_events.png)` etc.

---

## Pages

### Risk Events

This is the main feed. It shows every classified news event from the past several days, ranked by composite risk score. You can filter by asset class (equities, fixed income, FX, commodities), risk type (market, credit, geopolitical, operational, liquidity), severity band, region, and time window.

Each entry shows the FinBERT sentiment label, severity band, narrative theme, number of sources covering the same story, and a link to the original article. Stories reported by multiple outlets appear as a single clustered event with a higher composite score — so a banking stress story covered by Reuters, Bloomberg, and the FT will surface higher than a one source item with the same text.

### Risk Trends

Time series charts showing how the risk signal has evolved over the lookback window. This includes composite score over time, event volume by narrative theme, daily sentiment distribution, and severity distribution by day. It is useful for spotting whether a spike in risk events is a single day anomaly or a building regime shift.

### Market Summary

A cross asset snapshot covering sixteen instruments: four equity ETFs (SPY, QQQ, IWM, DIA), four fixed income ETFs (TLT, HYG, LQD, AGG), four currency pairs (EUR/USD, GBP/USD, USD/JPY, AUD/USD), and four commodities (Gold, Oil, Silver, Copper). Shows current price, 30 day return, and 30 day realized volatility. Gives context for reading the event feed — if oil is down 12% over 30 days and an energy supply story surfaces, the market is already pricing something in.

### Macro Sidebar (every page)

Six FRED indicators are always visible regardless of which page you are on: VIX, the 10 year minus 2 year Treasury spread, High Yield OAS, the trade weighted dollar index, the 10 year yield, and the Fed Funds rate. Each one is color coded: green for normal, amber for elevated, red for stress. Data refreshes every 15 minutes automatically.

---

## How It Works

### Data Ingestion

Headlines are fetched from NewsAPI across eight thematic queries — "financial risk", "market volatility", "central bank policy", "geopolitical risk", "credit markets", "energy markets", "banking sector", and "global recession". Results are restricted to nine premium financial domains. The full pipeline runs on demand via `ingest.py` and is also triggered automatically by an in process scheduler every six hours when the dashboard is running.

### Deduplication

Before any scoring happens, each article title is normalized (lowercased, punctuation stripped, stop words removed) and the top five remaining tokens are sorted and hashed with SHA1 to produce a cluster key. Any article with the same cluster key published within 48 hours of an existing cluster gets merged into that cluster rather than inserted as a new event. This prevents the same story from appearing twenty times because twenty outlets ran it.

The source count on each cluster is the number of distinct outlets that covered that story. It is one of the four inputs to the composite score.

### Sentiment Analysis

Each event goes through [ProsusAI/finbert](https://huggingface.co/ProsusAI/finbert), a BERT base model fine tuned on financial communication text including earnings calls, analyst reports, and financial news. It returns three probability scores: positive, negative, and neutral. The highest probability determines the label; the score itself is the confidence. Events are processed in batches of 32 with automatic truncation to 512 tokens.

### Severity Scoring

Sentiment alone does not tell you how bad something is. A story that says "the bank is facing challenges" and a story that says "the bank collapsed in the largest failure since 2008" will both score negative on sentiment, but they are not the same risk signal. The severity index combines four components:

| Component | Weight | How It Is Measured |
|-----------|--------|--------------------|
| Keyword tier | 40% | Crisis level terms (collapse, contagion, meltdown) score 3. Warning terms (plunge, shock, alarm) score 2. Watch terms (risk, pressure, concern) score 1. |
| Entity breadth | 25% | Count of named financial entities in the title and description |
| Dollar impact | 20% | Dollar amounts and percentage moves extracted from the text |
| Reach score | 15% | Proxy for systemic scope — global events score higher than regional ones |

The result is a 0 to 100 index mapped to four bands: LOW, MODERATE, HIGH, CRITICAL.

### Composite Score

Each event cluster gets a single composite risk score that combines all the signals:

```
composite = (0.40 × avg_severity_index)
          + (0.30 × avg_negative_sentiment × 100)
          + (0.20 × recency_decay × 100)
          + (0.10 × min(source_count / 10, 1.0) × 100)
```

Recency decay is exponential over 72 hours so older stories fade out as new ones come in:

```python
hours_old = (now - last_seen_utc).total_seconds() / 3600
recency_decay = exp(-hours_old / 72)
```

### Classification

Each event is tagged across three dimensions using a keyword weighted rule based classifier:

- **Asset class** (can be more than one): equities, fixed income, FX, commodities
- **Risk type** (can be more than one, with subtypes): market, credit, geopolitical, operational, liquidity
- **Region**: North America, Europe, Asia Pacific, Emerging Markets, Global
- **Direction**: positive, negative, or neutral from the perspective of an exposed position

I chose rule based classification here because it is fully transparent. A risk team can look at the keyword lists, understand exactly why an event was tagged a certain way, and adjust the lexicons without retraining a model.

### Narrative Labeling

Twelve recurring macro themes are tracked across the event stream:

Fed Policy Pivot · China Economic Slowdown · Banking Sector Stress · Energy Price Shock · Geopolitical Escalation · Inflation and Rate Path · Credit Market Stress · Tech Sector Volatility · Currency Crisis · Commodity Supercycle · Sovereign Debt Risk · Housing Market Stress

Each narrative tracks a running event count, rolling average severity, and rolling average negative sentiment, updated incrementally so historical data never needs to be reprocessed.

### Automated Refresh

The APScheduler library runs a background scheduler inside the Streamlit process. It re-triggers macro data fetches every six hours. FRED indicators in the sidebar cache for 15 minutes and refresh on their own. Market data via yfinance also caches for 15 minutes. The news ingestion pipeline can be run manually or scheduled externally via cron.

---

## Stack

| Layer | Tool |
|-------|------|
| Dashboard | Streamlit |
| Sentiment model | ProsusAI/finbert (HuggingFace Transformers + PyTorch) |
| Market data | yfinance |
| Macro data | FRED API via fredapi |
| News data | NewsAPI via newsapi-python |
| Database | Neon PostgreSQL (serverless, HTTPS) |
| Database driver | psycopg2 |
| Charts | Plotly |
| Scheduler | APScheduler |
| Data processing | Pandas, NumPy, SciPy |
| Config | python-dotenv |

---

## Setup

### Requirements

- Python 3.10 or later
- About 1 GB of disk space for the FinBERT model (downloaded once from HuggingFace and cached)
- Free API keys from [NewsAPI](https://newsapi.org) and [FRED](https://fred.stlouisfed.org/docs/api/api_key.html)
- A PostgreSQL database URL — [Neon](https://neon.tech) has a free tier that works well here

### Install

```bash
git clone https://github.com/Wanjiru-cynthia/Risk_Dashboard.git
cd Risk_Dashboard
pip install -r requirements.txt
```

### Configure

Create a `.env` file in the project root:

```env
NEWS_API_KEY=your_newsapi_key
FRED_API_KEY=your_fred_key
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require
```

For Streamlit Cloud, add these under **App Settings → Secrets** instead of committing the file.

### Seed the Database

```bash
# Pull the last 3 days of news and run the full pipeline
python ingest.py

# Or specify a longer lookback window
python ingest.py --days 7
```

The first run downloads FinBERT (~440 MB). Every run after that is incremental — only new unscored events are processed.

### Run the Dashboard

```bash
streamlit run dashboard/app.py
```

Open `http://localhost:8501`.

---

## Project Structure

```
risk-dashboard/
├── .env                          # API keys (not committed)
├── requirements.txt
├── ingest.py                     # Master pipeline — run this to seed or refresh
│
├── data/
│   ├── database.py               # Schema, query helpers, insert functions
│   ├── news_ingestion.py         # NewsAPI fetcher
│   ├── market_data.py            # yfinance price, vol, returns
│   └── macro_data.py             # FRED series fetcher
│
├── nlp/
│   ├── finbert_pipeline.py       # FinBERT sentiment, batched
│   ├── classifier.py             # Asset class and risk type classification
│   ├── severity.py               # Four component severity index
│   ├── composite_score.py        # Composite score with recency decay
│   ├── narratives.py             # Narrative theme labeling and tracking
│   └── deduplication.py          # SHA1 cluster key, 48 hour event grouping
│
└── dashboard/
    ├── app.py                    # Entry point
    ├── components/
    │   └── macro_sidebar.py      # Live FRED panel, shown on every page
    └── pages/
        ├── 1_Risk_Events.py
        ├── 2_Risk_Trends.py
        └── 3_Market_Summary.py
```

---

## Author

**Cynthia Wanjiru**
MS Quantitative Finance — Washington University in St. Louis
[GitHub: Wanjiru-cynthia](https://github.com/Wanjiru-cynthia)
