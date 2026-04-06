import streamlit as st

st.set_page_config(
    page_title="Risk Intelligence Dashboard",
    page_icon="⚠",
    layout="wide",
)

st.title("Cross-Asset Risk Intelligence Dashboard")
st.markdown(
    "Real-time financial news scoring with **FinBERT** NLP — "
    "covering equities, fixed income, FX, and commodities across "
    "credit, market, geopolitical, operational, and liquidity risk dimensions."
)
st.markdown("---")
st.markdown("""
Use the **sidebar** to navigate:

- **Overview** — risk heatmap, sentiment trends, live event feed
- **Asset Drilldown** — price charts and vol metrics by asset class
- **Event Detail** — full FinBERT scores and classification per event
- **Macro Backdrop** — live FRED indicators: VIX, yield curve, credit spreads, DXY
""")
