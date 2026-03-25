import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
from datetime import datetime
import subprocess
import json
import re
import os

st.set_page_config(page_title="Prosperity", layout="wide")

FONT = "IBM Plex Mono, monospace"
BASE_DIR = Path(__file__).parent
BACKTESTS_DIR = BASE_DIR / "backtests"
ALGOS_DIR = BASE_DIR / "algos"
BACKTESTS_DIR.mkdir(exist_ok=True)
ALGOS_DIR.mkdir(exist_ok=True)

CHART_LAYOUT = dict(
    font=dict(family=FONT, size=11),
    paper_bgcolor="white",
    plot_bgcolor="white",
    margin=dict(t=5, b=25, l=50, r=10),
    legend=dict(orientation="h", y=1.02, x=0, font=dict(size=10)),
    xaxis=dict(gridcolor="#E0E0E0", zeroline=False),
    yaxis=dict(gridcolor="#E0E0E0", zeroline=False),
)

# ── Parsing ──────────────────────────────────────────────────────────────────

def parse_log_file(path):
    """Parse combined .log output from prosperity4btx."""
    text = Path(path).read_text()

    # Find section boundaries
    activities_idx = text.find("Activities log:\n")
    trade_idx = text.find("Trade History:\n")

    if activities_idx == -1 or trade_idx == -1:
        return None, None

    # Parse activities (prices CSV)
    activities_text = text[activities_idx + len("Activities log:\n"):trade_idx].strip()
    from io import StringIO
    prices = pd.read_csv(StringIO(activities_text), sep=";")

    # Parse trade history (JSON with trailing commas)
    trade_text = text[trade_idx + len("Trade History:\n"):].strip()
    # Fix trailing commas in JSON (prosperity4btx outputs non-standard JSON)
    trade_text = re.sub(r',\s*}', '}', trade_text)
    trade_text = re.sub(r',\s*]', ']', trade_text)
    trades_list = json.loads(trade_text)
    trades = pd.DataFrame(trades_list) if trades_list else pd.DataFrame(
        columns=["timestamp", "buyer", "seller", "symbol", "currency", "price", "quantity"]
    )

    return prices, trades


def load_csv_pair(prices_path):
    """Load prices CSV and matching trades CSV."""
    prices = pd.read_csv(prices_path, sep=";")
    trades_path = Path(str(prices_path).replace("prices", "trades"))
    if trades_path.exists():
        trades = pd.read_csv(trades_path, sep=";")
    else:
        trades = pd.DataFrame(
            columns=["timestamp", "buyer", "seller", "symbol", "currency", "price", "quantity"]
        )
    return prices, trades


def discover_sources():
    """Find all available data sources: backtests and raw CSV round files."""
    sources = {}

    # Backtests
    for f in sorted(BACKTESTS_DIR.glob("*.log"), reverse=True):
        sources[f"backtest: {f.stem}"] = {"type": "log", "path": str(f)}

    # Raw CSV round files
    for prices_file in sorted(BASE_DIR.rglob("prices_round_*.csv")):
        rel = prices_file.relative_to(BASE_DIR)
        sources[f"csv: {rel}"] = {"type": "csv", "path": str(prices_file)}

    return sources


@st.cache_data
def load_source(source_type, source_path):
    if source_type == "log":
        return parse_log_file(source_path)
    else:
        return load_csv_pair(source_path)


# ── Indicators ───────────────────────────────────────────────────────────────

def compute_wallmid1(row):
    """VWAP of current order book levels."""
    total_pv = 0.0
    total_v = 0.0
    for i in range(1, 4):
        bp = row.get(f"bid_price_{i}")
        bv = row.get(f"bid_volume_{i}")
        if pd.notna(bp) and pd.notna(bv):
            total_pv += bp * abs(bv)
            total_v += abs(bv)
        ap = row.get(f"ask_price_{i}")
        av = row.get(f"ask_volume_{i}")
        if pd.notna(ap) and pd.notna(av):
            total_pv += ap * abs(av)
            total_v += abs(av)
    return total_pv / total_v if total_v > 0 else np.nan


def compute_wallmid2(row):
    """Largest volume bid + largest volume ask / 2."""
    best_bid_price = np.nan
    best_bid_vol = 0
    best_ask_price = np.nan
    best_ask_vol = 0
    for i in range(1, 4):
        bp = row.get(f"bid_price_{i}")
        bv = row.get(f"bid_volume_{i}")
        if pd.notna(bp) and pd.notna(bv) and abs(bv) > best_bid_vol:
            best_bid_vol = abs(bv)
            best_bid_price = bp
        ap = row.get(f"ask_price_{i}")
        av = row.get(f"ask_volume_{i}")
        if pd.notna(ap) and pd.notna(av) and abs(av) > best_ask_vol:
            best_ask_vol = abs(av)
            best_ask_price = ap
    if pd.notna(best_bid_price) and pd.notna(best_ask_price):
        return (best_bid_price + best_ask_price) / 2
    return np.nan


def add_indicators(pdf):
    """Compute all indicators on the product dataframe."""
    pdf = pdf.copy()
    pdf["wallmid1"] = pdf.apply(compute_wallmid1, axis=1)
    pdf["wallmid2"] = pdf.apply(compute_wallmid2, axis=1)
    return pdf


# ── Trade classification ─────────────────────────────────────────────────────

def classify_trades(tdf, pdf):
    """Classify each trade into M/S/B/I/F categories."""
    if tdf is None or len(tdf) == 0:
        return tdf

    tdf = tdf.copy()
    tdf["is_own"] = (tdf["buyer"] == "SUBMISSION") | (tdf["seller"] == "SUBMISSION")

    # Determine taker vs maker
    # Merge best bid/ask at each timestamp
    if len(pdf) > 0:
        ob = pdf[["timestamp", "bid_price_1", "ask_price_1"]].drop_duplicates("timestamp")
        tdf = tdf.merge(ob, on="timestamp", how="left")
    else:
        tdf["bid_price_1"] = np.nan
        tdf["ask_price_1"] = np.nan

    # A trade at the ask = buyer is taker. A trade at the bid = seller is taker.
    tdf["is_taker"] = (tdf["price"] >= tdf["ask_price_1"]) | (tdf["price"] <= tdf["bid_price_1"])

    # Build price change lookup for informed detection
    price_changes = pdf[["timestamp", "mid_price"]].drop_duplicates("timestamp").sort_values("timestamp")
    price_changes["mid_next"] = price_changes["mid_price"].shift(-1)
    price_changes["mid_change"] = (price_changes["mid_next"] - price_changes["mid_price"]).abs()
    median_change = price_changes["mid_change"].median()
    significant_threshold = median_change * 3 if median_change > 0 else 1
    price_changes["significant_move"] = price_changes["mid_change"] > significant_threshold
    sig_map = price_changes.set_index("timestamp")["significant_move"].to_dict()

    categories = []
    for _, row in tdf.iterrows():
        if row["is_own"]:
            categories.append("F")
        elif not row["is_taker"]:
            categories.append("M")
        else:
            # Taker — classify by size and informed-ness
            qty = abs(row["quantity"])
            before_move = sig_map.get(row["timestamp"], False)
            if before_move and qty >= 5:
                categories.append("I")
            elif qty >= 20:
                categories.append("B")
            elif qty <= 5:
                categories.append("S")
            else:
                categories.append("S")  # 6-19 units: default small

    tdf["category"] = categories
    return tdf


# ── Position tracking ────────────────────────────────────────────────────────

def compute_position(tdf, product):
    """Compute net position over time from own trades."""
    if tdf is None or len(tdf) == 0:
        return pd.DataFrame(columns=["timestamp", "position"])

    own = tdf[tdf["is_own"]].sort_values("timestamp").copy()
    if len(own) == 0:
        return pd.DataFrame(columns=["timestamp", "position"])

    positions = []
    pos = 0
    for _, row in own.iterrows():
        if row["buyer"] == "SUBMISSION":
            pos += row["quantity"]
        else:
            pos -= row["quantity"]
        positions.append({"timestamp": row["timestamp"], "position": pos})

    return pd.DataFrame(positions)


# ── Chart building ───────────────────────────────────────────────────────────

CATEGORY_COLORS = {
    "M": "#888888",  # grey - passive makers
    "S": "#4CAF50",  # green - small takers
    "B": "#FF9800",  # orange - big takers
    "I": "#F44336",  # red - informed
    "F": "#000000",  # black - our trades
}

CATEGORY_SYMBOLS = {
    "M": "square",
    "S": "triangle-up",
    "B": "triangle-up",
    "I": "triangle-up",
    "F": "cross",
}

CATEGORY_LABELS = {
    "M": "Maker (passive)",
    "S": "Small taker",
    "B": "Big taker",
    "I": "Informed taker",
    "F": "Own trades",
}


def build_main_chart(pdf, tdf, show_ob_levels, show_categories, qty_range,
                     indicators, normalize_by):
    """Build the main price chart with trade markers."""

    # Normalization
    norm_map = None
    if normalize_by == "WallMid1":
        norm_map = pdf.set_index("timestamp")["wallmid1"].to_dict()
    elif normalize_by == "WallMid2":
        norm_map = pdf.set_index("timestamp")["wallmid2"].to_dict()
    elif normalize_by == "Mid":
        norm_map = pdf.set_index("timestamp")["mid_price"].to_dict()

    def norm(values, timestamps):
        """Subtract normalization reference. timestamps is a Series of timestamp values."""
        if norm_map is None:
            return values
        ref = np.array([norm_map.get(t, np.nan) for t in timestamps])
        ref = np.where(ref == 0, np.nan, ref)
        return np.asarray(values) - ref

    fig = go.Figure()

    ts = pdf["timestamp"]

    # Ask line (red) — step style
    fig.add_trace(go.Scatter(
        x=ts, y=norm(pdf["ask_price_1"], ts),
        name="Ask L1", line=dict(color="#D32F2F", width=1, shape="hv"),
        hoverinfo="skip",
    ))

    # Bid line (blue) — step style
    fig.add_trace(go.Scatter(
        x=ts, y=norm(pdf["bid_price_1"], ts),
        name="Bid L1", line=dict(color="#1565C0", width=1, shape="hv"),
        hoverinfo="skip",
    ))

    # Additional OB levels
    if show_ob_levels:
        for i in [2, 3]:
            bcol = f"bid_price_{i}"
            acol = f"ask_price_{i}"
            if bcol in pdf.columns:
                fig.add_trace(go.Scatter(
                    x=ts, y=norm(pdf[bcol], ts),
                    name=f"Bid L{i}", line=dict(color="#1565C0", width=0.5, dash="dot", shape="hv"),
                    hoverinfo="skip",
                ))
            if acol in pdf.columns:
                fig.add_trace(go.Scatter(
                    x=ts, y=norm(pdf[acol], ts),
                    name=f"Ask L{i}", line=dict(color="#D32F2F", width=0.5, dash="dot", shape="hv"),
                    hoverinfo="skip",
                ))

    # Indicators
    if "WallMid1" in indicators:
        fig.add_trace(go.Scatter(
            x=ts, y=norm(pdf["wallmid1"], ts),
            name="WallMid1", line=dict(color="#7B1FA2", width=1.5, shape="hv"),
            hoverinfo="skip",
        ))
    if "WallMid2" in indicators:
        fig.add_trace(go.Scatter(
            x=ts, y=norm(pdf["wallmid2"], ts),
            name="WallMid2", line=dict(color="#00695C", width=1.5, shape="hv"),
            hoverinfo="skip",
        ))
    if "Mid" in indicators:
        fig.add_trace(go.Scatter(
            x=ts, y=norm(pdf["mid_price"], ts),
            name="Mid", line=dict(color="#555555", width=1, dash="dash", shape="hv"),
            hoverinfo="skip",
        ))

    # Trade markers
    if tdf is not None and len(tdf) > 0:
        for cat in ["M", "S", "B", "I", "F"]:
            if cat not in show_categories:
                continue
            subset = tdf[tdf["category"] == cat]
            if qty_range:
                subset = subset[(subset["quantity"] >= qty_range[0]) & (subset["quantity"] <= qty_range[1])]
            if len(subset) == 0:
                continue

            trade_y = norm(subset["price"].values, subset["timestamp"])

            # Build hover text
            hover = []
            for _, r in subset.iterrows():
                owner = "You" if r["is_own"] else "Market"
                role = "Maker" if cat == "M" else "Taker"
                buyer_str = r["buyer"] if r["buyer"] else "?"
                seller_str = r["seller"] if r["seller"] else "?"
                hover.append(
                    f"t={r['timestamp']}<br>"
                    f"price={r['price']}<br>"
                    f"qty={r['quantity']}<br>"
                    f"{buyer_str} ← {seller_str}<br>"
                    f"Owner: {owner} | Role: {role}"
                )

            fig.add_trace(go.Scatter(
                x=subset["timestamp"],
                y=trade_y,
                mode="markers",
                name=CATEGORY_LABELS[cat],
                marker=dict(
                    size=7 if cat == "F" else 5,
                    color=CATEGORY_COLORS[cat],
                    symbol=CATEGORY_SYMBOLS[cat],
                    line=dict(width=0.5, color="#333") if cat == "F" else dict(width=0),
                ),
                text=hover,
                hoverinfo="text",
            ))

    layout = {**CHART_LAYOUT}
    layout["height"] = 380
    y_title = "Price" if normalize_by == "None" else f"Price - {normalize_by}"
    layout["yaxis"] = {**layout.get("yaxis", {}), "title": y_title}
    fig.update_layout(**layout)
    return fig


def build_pnl_chart(pdf):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=pdf["timestamp"], y=pdf["profit_and_loss"],
        name="PnL", line=dict(color="#2E7D32", width=1.5),
        fill="tozeroy", fillcolor="rgba(46,125,50,0.08)",
    ))
    layout = {**CHART_LAYOUT}
    layout["height"] = 140
    layout["yaxis"] = {**layout.get("yaxis", {}), "title": "PnL"}
    fig.update_layout(**layout)
    return fig


def build_position_chart(pos_df):
    fig = go.Figure()
    if len(pos_df) > 0:
        fig.add_trace(go.Scatter(
            x=pos_df["timestamp"], y=pos_df["position"],
            name="Position", line=dict(color="#E65100", width=1.5, shape="hv"),
            fill="tozeroy", fillcolor="rgba(230,81,0,0.08)",
        ))
    layout = {**CHART_LAYOUT}
    layout["height"] = 140
    layout["yaxis"] = {**layout.get("yaxis", {}), "title": "Pos"}
    fig.update_layout(**layout)
    return fig


# ── Sidebar ──────────────────────────────────────────────────────────────────

sources = discover_sources()
if not sources:
    st.warning("No data. Run a backtest or place CSV files in round directories.")
    st.stop()

st.sidebar.markdown("**Data**")
selected_source = st.sidebar.selectbox("Source", list(sources.keys()), label_visibility="collapsed")
src = sources[selected_source]
prices, trades = load_source(src["type"], src["path"])

if prices is None or len(prices) == 0:
    st.warning("Failed to parse selected source.")
    st.stop()

products = sorted(prices["product"].unique())
selected_product = st.sidebar.selectbox("Product", products)

# Filter to product
pdf = prices[prices["product"] == selected_product].copy().sort_values("timestamp")
pdf = add_indicators(pdf)

if trades is not None and len(trades) > 0:
    tdf = trades[trades["symbol"] == selected_product].copy().sort_values("timestamp")
    tdf = classify_trades(tdf, pdf)
else:
    tdf = None

# Indicators
st.sidebar.markdown("**Indicators**")
ind_options = ["Mid", "WallMid1", "WallMid2"]
show_indicators = st.sidebar.multiselect("Overlay", ind_options, default=[], label_visibility="collapsed")

# Normalization
normalize_by = st.sidebar.selectbox("Normalize by", ["None"] + ind_options, index=0)

# Trade filters
st.sidebar.markdown("**Trade filters**")
cat_options = {"M": "M Makers", "S": "S Small", "B": "B Big", "I": "I Informed", "F": "F Own"}
show_categories = []
cols = st.sidebar.columns(5)
for i, (cat, label) in enumerate(cat_options.items()):
    if cols[i].checkbox(label, value=True, key=f"cat_{cat}"):
        show_categories.append(cat)

show_ob_levels = st.sidebar.checkbox("OB levels 2-3", value=False)

max_qty = int(tdf["quantity"].max()) if tdf is not None and len(tdf) > 0 else 100
qty_range = st.sidebar.slider("Qty range", 0, max(max_qty, 1), (0, max(max_qty, 1)))

# Backtesting
st.sidebar.markdown("---")
st.sidebar.markdown("**Backtest**")

algo_files = sorted(ALGOS_DIR.glob("*.py"))
algo_choices = {"algo.py (root)": BASE_DIR / "algo.py"}
for f in algo_files:
    if f.name != "datamodel.py":
        algo_choices[f"algos/{f.name}"] = f
selected_algo = st.sidebar.selectbox("Algorithm", list(algo_choices.keys()))

round_input = st.sidebar.text_input("Round args", value="0", help="e.g. '1-0', '1--1 1-0', '1 2', '1 --merge-pnl'")

col_bt1, col_bt2 = st.sidebar.columns(2)
run_backtest = col_bt1.button("Run")
run_pip = col_bt2.button("pip install -U")

if run_pip:
    with st.spinner("Updating prosperity4btx..."):
        result = subprocess.run(
            ["pipenv", "run", "pip", "install", "-U", "prosperity4btx"],
            capture_output=True, text=True, cwd=str(BASE_DIR)
        )
        if result.returncode == 0:
            st.sidebar.success("Updated")
        else:
            st.sidebar.error(result.stderr[-300:] if result.stderr else "Failed")

if run_backtest:
    algo_path = algo_choices[selected_algo].resolve()
    # Ensure datamodel.py is accessible from algo's directory
    algo_dir = algo_path.parent
    dm_link = algo_dir / "datamodel.py"
    dm_source = BASE_DIR / "datamodel.py"
    if algo_dir != BASE_DIR and not dm_link.exists() and dm_source.exists():
        os.symlink(str(dm_source), str(dm_link))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    algo_stem = algo_path.stem
    out_name = f"{ts}_{algo_stem}_r{round_input.replace(' ', '_')}.log"
    out_path = BACKTESTS_DIR / out_name

    cmd = ["pipenv", "run", "prosperity4btx", str(algo_path)] + round_input.split() + ["--out", str(out_path)]
    with st.spinner(f"Running: {' '.join(cmd)}"):
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR), timeout=120)
        if result.returncode == 0:
            # Extract profit summary from stdout
            lines = result.stdout.strip().split("\n")
            profit_lines = [l for l in lines if "profit" in l.lower() or ":" in l]
            st.sidebar.success(f"Saved: {out_name}")
            for l in profit_lines[-5:]:
                st.sidebar.text(l)
            st.cache_data.clear()
            st.rerun()
        else:
            st.sidebar.error("Backtest failed")
            st.sidebar.code(result.stderr[-500:] if result.stderr else result.stdout[-500:])


# ── Main area ────────────────────────────────────────────────────────────────

fig_main = build_main_chart(pdf, tdf, show_ob_levels, show_categories, qty_range,
                            show_indicators, normalize_by)
st.plotly_chart(fig_main, width="stretch", config={"displayModeBar": False})

fig_pnl = build_pnl_chart(pdf)
st.plotly_chart(fig_pnl, width="stretch", config={"displayModeBar": False})

pos_df = compute_position(tdf, selected_product)
fig_pos = build_position_chart(pos_df)
st.plotly_chart(fig_pos, width="stretch", config={"displayModeBar": False})
