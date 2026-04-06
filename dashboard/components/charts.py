"""
Reusable Plotly chart components for the risk dashboard.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

ASSET_CLASSES = ["equities", "fixed_income", "fx", "commodities"]
RISK_TYPES = ["credit", "market", "geopolitical", "operational", "liquidity"]

ASSET_LABELS = {
    "equities": "Equities",
    "fixed_income": "Fixed Income",
    "fx": "FX",
    "commodities": "Commodities",
}

SEVERITY_COLORSCALE = [
    [0.0,  "#1a1a2e"],
    [0.25, "#16213e"],
    [0.5,  "#F4A261"],
    [0.75, "#E76F51"],
    [1.0,  "#E63946"],
]

SENTIMENT_COLORS = {
    "equities": "#4CC9F0",
    "fixed_income": "#4361EE",
    "fx": "#7209B7",
    "commodities": "#F72585",
}


# ── Risk Heatmap ────────────────────────────────────────────────────────────

def render_heatmap(df: pd.DataFrame) -> go.Figure:
    """
    Build a risk heatmap (asset class × risk type), coloured by avg severity.
    df columns: asset_class, risk_type, avg_severity, event_count
    """
    # Build full pivot with zeros for empty cells
    pivot = pd.DataFrame(0.0, index=ASSET_CLASSES, columns=RISK_TYPES)
    count_pivot = pd.DataFrame(0, index=ASSET_CLASSES, columns=RISK_TYPES)

    if not df.empty:
        for _, row in df.iterrows():
            ac = row.get("asset_class")
            rt = row.get("risk_type")
            if ac in ASSET_CLASSES and rt in RISK_TYPES:
                pivot.at[ac, rt] = row.get("avg_severity", 0)
                count_pivot.at[ac, rt] = int(row.get("event_count", 0))

    # Build hover text
    text_matrix = []
    for ac in ASSET_CLASSES:
        row_texts = []
        for rt in RISK_TYPES:
            sev = pivot.at[ac, rt]
            cnt = count_pivot.at[ac, rt]
            row_texts.append(f"Severity: {sev:.1f}<br>Events: {cnt}")
        text_matrix.append(row_texts)

    fig = go.Figure(go.Heatmap(
        z=pivot.values.tolist(),
        x=[rt.replace("_", " ").title() for rt in RISK_TYPES],
        y=[ASSET_LABELS.get(ac, ac) for ac in ASSET_CLASSES],
        text=text_matrix,
        hovertemplate="%{y} × %{x}<br>%{text}<extra></extra>",
        colorscale=SEVERITY_COLORSCALE,
        zmin=0,
        zmax=5,
        colorbar=dict(
            title="Avg Severity",
            tickvals=[1, 2, 3, 4, 5],
            ticktext=["1 Low", "2", "3 Mod", "4", "5 High"],
            thickness=12,
        ),
    ))

    fig.update_layout(
        title="Risk Heatmap — Asset Class × Risk Type (7-day window)",
        xaxis_title="Risk Type",
        yaxis_title="Asset Class",
        plot_bgcolor="#0D1117",
        paper_bgcolor="#0D1117",
        font=dict(color="#C9D1D9", size=12),
        height=340,
        margin=dict(t=50, b=40, l=100, r=20),
    )
    return fig


# ── Sentiment Trend Lines ───────────────────────────────────────────────────

def render_sentiment_trends(df: pd.DataFrame) -> go.Figure:
    """
    Line chart of net sentiment (positive – negative) per asset class over time.
    df columns: date, asset_class, net_sentiment, event_count
    """
    fig = go.Figure()

    if df.empty:
        fig.add_annotation(text="No sentiment data yet — run ingestion pipeline.",
                           xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
                           font=dict(color="#888", size=14))
    else:
        for ac in ASSET_CLASSES:
            sub = df[df["asset_class"] == ac].copy()
            if sub.empty:
                continue
            sub["date"] = pd.to_datetime(sub["date"])
            sub = sub.sort_values("date")
            fig.add_trace(go.Scatter(
                x=sub["date"],
                y=sub["net_sentiment"],
                name=ASSET_LABELS.get(ac, ac),
                mode="lines+markers",
                line=dict(color=SENTIMENT_COLORS.get(ac, "#888"), width=2),
                marker=dict(size=5),
                hovertemplate=f"<b>{ASSET_LABELS.get(ac, ac)}</b><br>"
                              "%{x|%b %d}<br>Net sentiment: %{y:.3f}<extra></extra>",
            ))

    fig.add_hline(y=0, line_dash="dash", line_color="#444", line_width=1)
    fig.update_layout(
        title="Sentiment Trend — Net Score by Asset Class",
        xaxis_title="Date",
        yaxis_title="Net Sentiment (positive − negative)",
        plot_bgcolor="#0D1117",
        paper_bgcolor="#0D1117",
        font=dict(color="#C9D1D9", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=320,
        margin=dict(t=60, b=40, l=60, r=20),
        hovermode="x unified",
    )
    return fig


# ── Price / OHLCV chart ─────────────────────────────────────────────────────

def render_price_chart(ticker: str, name: str, hist: pd.DataFrame) -> go.Figure:
    """Candlestick chart with 20-day SMA and volume bars."""
    if hist.empty:
        fig = go.Figure()
        fig.add_annotation(text=f"No data for {ticker}", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False, font=dict(color="#888"))
        return fig

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.75, 0.25],
    )

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=hist.index,
        open=hist.get("Open", hist.get("Close")),
        high=hist.get("High", hist.get("Close")),
        low=hist.get("Low", hist.get("Close")),
        close=hist["Close"],
        name=ticker,
        increasing_line_color="#2A9D8F",
        decreasing_line_color="#E63946",
    ), row=1, col=1)

    # 20-day SMA
    if len(hist) >= 20:
        sma = hist["Close"].rolling(20).mean()
        fig.add_trace(go.Scatter(
            x=hist.index, y=sma, name="SMA 20",
            line=dict(color="#F4A261", width=1.5, dash="dot"),
        ), row=1, col=1)

    # Volume
    if "Volume" in hist.columns:
        colors = ["#2A9D8F" if c >= o else "#E63946"
                  for c, o in zip(hist["Close"], hist.get("Open", hist["Close"]))]
        fig.add_trace(go.Bar(
            x=hist.index, y=hist["Volume"],
            marker_color=colors, name="Volume", showlegend=False,
        ), row=2, col=1)

    fig.update_layout(
        title=f"{name} ({ticker}) — 30-Day Price",
        plot_bgcolor="#0D1117",
        paper_bgcolor="#0D1117",
        font=dict(color="#C9D1D9", size=11),
        xaxis_rangeslider_visible=False,
        height=420,
        margin=dict(t=50, b=30, l=60, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


# ── Volatility bar chart ────────────────────────────────────────────────────

def render_vol_bars(quotes_df: pd.DataFrame, asset_class: str) -> go.Figure:
    """Bar chart of 30-day annualised vol for tickers in an asset class."""
    sub = quotes_df[quotes_df["asset_class"] == asset_class].copy()

    fig = go.Figure(go.Bar(
        x=sub["name"] if not sub.empty else [],
        y=sub["vol_30d_ann"] if not sub.empty else [],
        marker_color="#4CC9F0",
        text=sub["vol_30d_ann"].round(1).astype(str) + "%" if not sub.empty else [],
        textposition="outside",
    ))
    fig.update_layout(
        title=f"30-Day Realised Volatility — {ASSET_LABELS.get(asset_class, asset_class)}",
        yaxis_title="Annualised Vol (%)",
        plot_bgcolor="#0D1117",
        paper_bgcolor="#0D1117",
        font=dict(color="#C9D1D9", size=12),
        height=280,
        margin=dict(t=50, b=60, l=60, r=20),
    )
    return fig


# ── Returns bar chart ───────────────────────────────────────────────────────

def render_returns_bars(quotes_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar chart of 30-day return across all tickers."""
    df = quotes_df.sort_values("period_return_pct", ascending=True).copy()
    colors = ["#E63946" if r < 0 else "#2A9D8F" for r in df["period_return_pct"]]

    fig = go.Figure(go.Bar(
        x=df["period_return_pct"],
        y=df["name"],
        orientation="h",
        marker_color=colors,
        text=df["period_return_pct"].round(2).astype(str) + "%",
        textposition="outside",
    ))
    fig.update_layout(
        title="30-Day Returns — Cross-Asset",
        xaxis_title="Return (%)",
        plot_bgcolor="#0D1117",
        paper_bgcolor="#0D1117",
        font=dict(color="#C9D1D9", size=11),
        height=500,
        margin=dict(t=50, b=40, l=150, r=80),
    )
    return fig


# ── Macro history line chart ────────────────────────────────────────────────

def _hex_to_rgba(hex_color: str, alpha: float = 0.1) -> str:
    """Convert a #RRGGBB hex string to an rgba(...) string."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def render_macro_history(series: "pd.Series", title: str, color: str = "#4CC9F0") -> go.Figure:
    if color.startswith("#"):
        fill_color = _hex_to_rgba(color, alpha=0.1)
    elif color.startswith("rgb("):
        fill_color = color.replace("rgb(", "rgba(").replace(")", ", 0.1)")
    else:
        fill_color = color

    fig = go.Figure(go.Scatter(
        x=series.index,
        y=series.values,
        mode="lines",
        line=dict(color=color, width=2),
        fill="tozeroy",
        fillcolor=fill_color,
    ))
    fig.update_layout(
        title=title,
        plot_bgcolor="#0D1117",
        paper_bgcolor="#0D1117",
        font=dict(color="#C9D1D9", size=12),
        height=240,
        margin=dict(t=50, b=40, l=60, r=20),
        showlegend=False,
    )
    return fig


# ── Severity badge HTML ─────────────────────────────────────────────────────

SEV_COLORS = {1: "#555", 2: "#4361EE", 3: "#F4A261", 4: "#E76F51", 5: "#E63946"}
SEV_LABELS = {1: "LOW", 2: "WATCH", 3: "MODERATE", 4: "HIGH", 5: "CRITICAL"}


def severity_badge(severity: int | None) -> str:
    sev = int(severity) if severity is not None else 1
    color = SEV_COLORS.get(sev, "#555")
    label = SEV_LABELS.get(sev, "—")
    return (
        f'<span style="background:{color};color:#fff;padding:2px 7px;'
        f'border-radius:4px;font-size:0.7rem;font-weight:bold">{label}</span>'
    )


def direction_badge(direction: str | None) -> str:
    color = {"positive": "#2A9D8F", "negative": "#E63946", "neutral": "#888"}.get(
        (direction or "neutral").lower(), "#888"
    )
    label = (direction or "neutral").upper()
    return (
        f'<span style="background:{color};color:#fff;padding:2px 7px;'
        f'border-radius:4px;font-size:0.7rem;font-weight:bold">{label}</span>'
    )
