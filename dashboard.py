import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path

st.set_page_config(page_title="Prosperity Dashboard", layout="wide")
st.title("IMC Prosperity — Team Dashboard")


# --- Data Loading ---
@st.cache_data
def discover_data():
    """Find all price/trade CSVs across round directories."""
    base = Path(__file__).parent
    rounds = {}
    for prices_file in sorted(base.rglob("prices_round_*.csv")):
        parts = prices_file.stem.split("_")  # prices_round_0_day_-1
        round_name = f"Round {parts[2]}"
        day = parts[4]
        trades_file = prices_file.parent / prices_file.name.replace("prices", "trades")
        if round_name not in rounds:
            rounds[round_name] = {}
        rounds[round_name][f"Day {day}"] = {
            "prices": str(prices_file),
            "trades": str(trades_file) if trades_file.exists() else None,
        }
    return rounds


@st.cache_data
def load_prices(path):
    df = pd.read_csv(path, sep=";")
    return df


@st.cache_data
def load_trades(path):
    df = pd.read_csv(path, sep=";")
    return df


rounds = discover_data()

if not rounds:
    st.warning("No data found. Place `prices_round_X_day_Y.csv` files in round directories.")
    st.stop()

# --- Sidebar Controls ---
st.sidebar.header("Controls")
round_name = st.sidebar.selectbox("Round", list(rounds.keys()))
day_name = st.sidebar.selectbox("Day", list(rounds[round_name].keys()))

data = rounds[round_name][day_name]
prices = load_prices(data["prices"])
trades = load_trades(data["trades"]) if data["trades"] else None

products = sorted(prices["product"].unique())
selected_product = st.sidebar.selectbox("Product", products)

# Filter to selected product
pdf = prices[prices["product"] == selected_product].copy()
pdf = pdf.sort_values("timestamp")

if trades is not None:
    tdf = trades[trades["symbol"] == selected_product].copy()
    tdf = tdf.sort_values("timestamp")
else:
    tdf = None

# --- KPI Row ---
col1, col2, col3, col4 = st.columns(4)
spread = pdf["ask_price_1"] - pdf["bid_price_1"]
col1.metric("Avg Mid Price", f"{pdf['mid_price'].mean():.2f}")
col2.metric("Avg Spread", f"{spread.mean():.2f}")
col3.metric("Final PnL", f"{pdf['profit_and_loss'].iloc[-1]:.2f}")
if tdf is not None and len(tdf) > 0:
    col4.metric("Total Trades", f"{len(tdf)}")
else:
    col4.metric("Total Trades", "0")

# --- Mid Price + Trades Chart ---
st.subheader(f"{selected_product} — Price Action")

fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3],
                    vertical_spacing=0.05)

# Mid price line
fig.add_trace(go.Scatter(
    x=pdf["timestamp"], y=pdf["mid_price"],
    name="Mid Price", line=dict(color="#2962FF", width=1.5),
), row=1, col=1)

# Bid/ask band
fig.add_trace(go.Scatter(
    x=pdf["timestamp"], y=pdf["bid_price_1"],
    name="Best Bid", line=dict(color="#26A69A", width=0.5, dash="dot"),
), row=1, col=1)
fig.add_trace(go.Scatter(
    x=pdf["timestamp"], y=pdf["ask_price_1"],
    name="Best Ask", line=dict(color="#EF5350", width=0.5, dash="dot"),
    fill="tonexty", fillcolor="rgba(239,83,80,0.08)",
), row=1, col=1)

# Trade markers
if tdf is not None and len(tdf) > 0:
    fig.add_trace(go.Scatter(
        x=tdf["timestamp"], y=tdf["price"],
        mode="markers", name="Trades",
        marker=dict(size=5, color="#FF6D00", opacity=0.7),
    ), row=1, col=1)

# Spread subplot
fig.add_trace(go.Scatter(
    x=pdf["timestamp"], y=spread,
    name="Spread", line=dict(color="#AB47BC", width=1),
    fill="tozeroy", fillcolor="rgba(171,71,188,0.15)",
), row=2, col=1)

fig.update_layout(height=500, margin=dict(t=20, b=20), legend=dict(orientation="h", y=1.08))
fig.update_xaxes(title_text="Timestamp", row=2, col=1)
fig.update_yaxes(title_text="Price", row=1, col=1)
fig.update_yaxes(title_text="Spread", row=2, col=1)
st.plotly_chart(fig, use_container_width=True)

# --- PnL Chart ---
st.subheader("Profit & Loss")
fig_pnl = go.Figure()
for product in products:
    p = prices[prices["product"] == product].sort_values("timestamp")
    fig_pnl.add_trace(go.Scatter(
        x=p["timestamp"], y=p["profit_and_loss"],
        name=product, mode="lines",
    ))
fig_pnl.update_layout(height=300, margin=dict(t=20, b=20), legend=dict(orientation="h", y=1.08))
fig_pnl.update_xaxes(title_text="Timestamp")
fig_pnl.update_yaxes(title_text="PnL")
st.plotly_chart(fig_pnl, use_container_width=True)

# --- Order Book Depth Snapshot ---
st.subheader("Order Book Depth (select timestamp)")
ts_options = pdf["timestamp"].unique()
selected_ts = st.select_slider("Timestamp", options=ts_options, value=ts_options[len(ts_options) // 2])

row = pdf[pdf["timestamp"] == selected_ts].iloc[0]

bids, asks = [], []
for i in range(1, 4):
    bp = row.get(f"bid_price_{i}")
    bv = row.get(f"bid_volume_{i}")
    if pd.notna(bp) and pd.notna(bv):
        bids.append((bp, bv))
    ap = row.get(f"ask_price_{i}")
    av = row.get(f"ask_volume_{i}")
    if pd.notna(ap) and pd.notna(av):
        asks.append((ap, av))

fig_ob = go.Figure()
if bids:
    fig_ob.add_trace(go.Bar(
        x=[b[1] for b in bids], y=[b[0] for b in bids],
        orientation="h", name="Bids", marker_color="#26A69A",
    ))
if asks:
    fig_ob.add_trace(go.Bar(
        x=[a[1] for a in asks], y=[a[0] for a in asks],
        orientation="h", name="Asks", marker_color="#EF5350",
    ))
fig_ob.update_layout(height=250, margin=dict(t=20, b=20), barmode="group",
                     yaxis_title="Price", xaxis_title="Volume")
st.plotly_chart(fig_ob, use_container_width=True)

# --- Raw Data ---
with st.expander("Raw Price Data"):
    st.dataframe(pdf, use_container_width=True)

if tdf is not None:
    with st.expander("Raw Trade Data"):
        st.dataframe(tdf, use_container_width=True)
