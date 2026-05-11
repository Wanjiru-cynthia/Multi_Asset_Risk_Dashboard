# Cross-Asset Risk Intelligence Dashboard

A live risk monitoring dashboard that reads financial news, scores sentiment with a finance trained language model, classifies events by asset class and risk type, and shows everything in one place alongside real time market and macroeconomic data.

**[Live App](https://riskdasboard-4idry9bpmxmlsy7l2ubfgz.streamlit.app/Risk_Events)**

---

## What It Does

Most risk teams find out about a market moving event from a colleague, a news alert, or an end of day report. By then the price has already moved. This dashboard is my attempt to close that gap.

Every time the app runs, it pulls the latest financial headlines, runs them through a sentiment model trained specifically on financial text, tags each story by asset class and risk type, and groups duplicate stories from different outlets into a single event. The result is a live feed of ranked risk events that updates continuously, with six Federal Reserve indicators always visible in the sidebar so you never lose sight of the macro backdrop.

I built this to be something a portfolio manager or risk analyst can actually open in the morning and use — not a proof of concept, but a working tool.

---

## Pages

### Risk Events

This is the main feed. It shows every classified news event from the past several days (3,7,14,30), ranked by severity index. You can filter by asset class (equities, fixed income, FX, commodities), risk type (market, credit, geopolitical, operational, liquidity), severity band, region, and time window.

Each entry shows the FinBERT sentiment label, severity band, narrative theme, number of sources covering the same story, and a link to the original article. Stories reported by multiple outlets appear as a single clustered event, so a banking stress story covered by Reuters, Bloomberg, and the FT will surface higher than a one source item with the same text.

### Risk Trends

Time series charts showing how the risk signal has evolved over the lookback window. This includes event volume by narrative theme, daily sentiment distribution, and severity distribution by day. It is useful for spotting whether a spike in risk events is a single day anomaly or a building regime shift.

### Market Summary

A cross asset snapshot covering sixteen instruments: four equity ETFs (SPY, QQQ, IWM, DIA), four fixed income ETFs (TLT, HYG, LQD, AGG), four currency pairs (EUR/USD, GBP/USD, USD/JPY, AUD/USD), and four commodities (Gold, Oil, Silver, Copper). Shows current price, 30 day return, and 30 day realized volatility. Gives context for reading the event feed for instance, if oil is down 12% over 30 days and an energy supply story surfaces, the market is already pricing something in.

### Macro Sidebar (every page)

Six FRED indicators are always visible regardless of which page you are on: VIX, the 10 year minus 2 year Treasury spread, High Yield OAS, the trade weighted dollar index, the 10 year yield, and the Fed Funds rate. Each one is color coded: green for normal, amber for elevated, red for stress. Data refreshes every 15 minutes automatically.

---

## How It Works

### Data Ingestion

Headlines are fetched from NewsAPI across eight thematic queries — "financial risk", "market volatility", "central bank policy", "geopolitical risk", "credit markets", "energy markets", "banking sector", and "global recession". Results are restricted to nine premium financial domains. The full pipeline runs on demand via `ingest.py` and is also triggered automatically by an in process scheduler every six hours when the dashboard is running.

### Deduplication

Before any scoring happens, each article title is normalized (lowercased, punctuation stripped, stop words removed) and the top five remaining tokens are sorted and hashed with SHA1 to produce a cluster key. Any article with the same cluster key published within 48 hours of an existing cluster gets merged into that cluster rather than inserted as a new event. This prevents the same story from appearing twenty times because twenty outlets ran it.

The source count on each cluster is the number of distinct outlets that covered that story.

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

## Author

**Cynthia Wanjiru**
MS Quantitative Finance Washington University in St. Louis

