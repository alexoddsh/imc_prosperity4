import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime
import subprocess
import json
import re
import os

st.set_page_config(page_title="Prosperity", layout="wide")

# ── CSS: right sidebar, no rounded edges, no scrollbars, compact ─────────────
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap');
* { font-family: 'IBM Plex Mono', monospace !important; border-radius: 0 !important; }
html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
    overflow: hidden !important; margin: 0 !important; padding: 0 !important;
}
[data-testid="stSidebar"] {
    order: 2 !important; left: auto !important; right: 0 !important;
    width: 240px !important; min-width: 240px !important; max-width: 240px !important;
    padding: 4px 6px !important; overflow-y: auto !important;
    scrollbar-width: none !important;
}
[data-testid="stSidebar"]::-webkit-scrollbar { display: none !important; }
[data-testid="stSidebar"] [data-testid="stMarkdown"] p {
    font-size: 11px !important; margin: 0 !important; padding: 0 !important; line-height: 1.2 !important;
}
[data-testid="stSidebar"] .stSelectbox, [data-testid="stSidebar"] .stMultiSelect,
[data-testid="stSidebar"] .stTextInput, [data-testid="stSidebar"] .stNumberInput {
    margin-bottom: 2px !important;
}
[data-testid="stSidebar"] .stSelectbox > div > div,
[data-testid="stSidebar"] .stMultiSelect > div > div,
[data-testid="stSidebar"] .stTextInput > div > div > input,
[data-testid="stSidebar"] .stNumberInput > div > div > input {
    font-size: 10px !important; padding: 2px 4px !important; min-height: 24px !important;
}
[data-testid="stSidebar"] label {
    font-size: 10px !important; margin: 0 !important; padding: 0 !important;
}
[data-testid="stSidebar"] .stCheckbox { margin: 0 !important; padding: 0 !important; }
[data-testid="stSidebar"] .stCheckbox label span {
    font-size: 10px !important; padding: 0 !important;
}
[data-testid="stSidebar"] .stCheckbox label div[data-testid="stCheckboxCheck"] {
    width: 14px !important; height: 14px !important;
}
[data-testid="stSidebar"] button {
    font-size: 10px !important; padding: 2px 6px !important; min-height: 24px !important;
    height: 24px !important; line-height: 1 !important;
}
[data-testid="stSidebar"] .stSlider { margin: 0 !important; padding: 0 !important; }
[data-testid="stSidebar"] hr { margin: 4px 0 !important; }
[data-testid="stMainBlockContainer"] {
    padding: 0 2px 0 2px !important; max-width: 100% !important;
}
.stPlotlyChart { margin: 0 !important; padding: 0 !important; }
[data-testid="stHeader"] { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stBottomBlockContainer"] { display: none !important; }
div[data-testid="stVerticalBlockBorderWrapper"] { gap: 0 !important; padding: 0 !important; }
div[data-testid="stVerticalBlock"] { gap: 0 !important; }
::-webkit-scrollbar { display: none !important; }
</style>""", unsafe_allow_html=True)

FONT = "IBM Plex Mono, monospace"
BASE_DIR = Path(__file__).parent
BACKTESTS_DIR = BASE_DIR / "backtests"
ALGOS_DIR = BASE_DIR / "algos"
BACKTESTS_DIR.mkdir(exist_ok=True)
ALGOS_DIR.mkdir(exist_ok=True)

CHART_LAYOUT = dict(
    font=dict(family=FONT, size=10),
    paper_bgcolor="white",
    plot_bgcolor="white",
    margin=dict(t=0, b=18, l=40, r=0),
    showlegend=False,
    xaxis=dict(gridcolor="#E8E8E8", zeroline=False, tickfont=dict(size=9)),
    yaxis=dict(gridcolor="#E8E8E8", zeroline=False, tickfont=dict(size=9)),
)

# ── Parsing ──────────────────────────────────────────────────────────────────

def parse_log_file(path):
    text = Path(path).read_text()
    activities_idx = text.find("Activities log:\n")
    trade_idx = text.find("Trade History:\n")
    if activities_idx == -1 or trade_idx == -1:
        return None, None
    from io import StringIO
    activities_text = text[activities_idx + len("Activities log:\n"):trade_idx].strip()
    prices = pd.read_csv(StringIO(activities_text), sep=";")
    trade_text = text[trade_idx + len("Trade History:\n"):].strip()
    trade_text = re.sub(r',\s*}', '}', trade_text)
    trade_text = re.sub(r',\s*]', ']', trade_text)
    trades_list = json.loads(trade_text)
    trades = pd.DataFrame(trades_list) if trades_list else pd.DataFrame(
        columns=["timestamp", "buyer", "seller", "symbol", "currency", "price", "quantity"])
    return prices, trades


def load_csv_pair(prices_path):
    prices = pd.read_csv(prices_path, sep=";")
    trades_path = Path(str(prices_path).replace("prices", "trades"))
    if trades_path.exists():
        trades = pd.read_csv(trades_path, sep=";")
    else:
        trades = pd.DataFrame(
            columns=["timestamp", "buyer", "seller", "symbol", "currency", "price", "quantity"])
    return prices, trades


def discover_sources():
    sources = {}
    for f in sorted(BACKTESTS_DIR.glob("*.log"), reverse=True):
        sources[f"bt: {f.stem}"] = {"type": "log", "path": str(f)}
    for prices_file in sorted(BASE_DIR.rglob("prices_round_*.csv")):
        rel = prices_file.relative_to(BASE_DIR)
        sources[f"csv: {rel}"] = {"type": "csv", "path": str(prices_file)}
    return sources


@st.cache_data
def load_source(source_type, source_path):
    if source_type == "log":
        return parse_log_file(source_path)
    return load_csv_pair(source_path)


# ── Indicators ───────────────────────────────────────────────────────────────

def compute_wallmid1(row):
    total_pv, total_v = 0.0, 0.0
    for i in range(1, 4):
        bp, bv = row.get(f"bid_price_{i}"), row.get(f"bid_volume_{i}")
        if pd.notna(bp) and pd.notna(bv):
            total_pv += bp * abs(bv); total_v += abs(bv)
        ap, av = row.get(f"ask_price_{i}"), row.get(f"ask_volume_{i}")
        if pd.notna(ap) and pd.notna(av):
            total_pv += ap * abs(av); total_v += abs(av)
    return total_pv / total_v if total_v > 0 else np.nan


def compute_wallmid2(row):
    bb_p, bb_v, ba_p, ba_v = np.nan, 0, np.nan, 0
    for i in range(1, 4):
        bp, bv = row.get(f"bid_price_{i}"), row.get(f"bid_volume_{i}")
        if pd.notna(bp) and pd.notna(bv) and abs(bv) > bb_v:
            bb_v = abs(bv); bb_p = bp
        ap, av = row.get(f"ask_price_{i}"), row.get(f"ask_volume_{i}")
        if pd.notna(ap) and pd.notna(av) and abs(av) > ba_v:
            ba_v = abs(av); ba_p = ap
    return (bb_p + ba_p) / 2 if pd.notna(bb_p) and pd.notna(ba_p) else np.nan


def add_indicators(pdf):
    pdf = pdf.copy()
    pdf["wallmid1"] = pdf.apply(compute_wallmid1, axis=1)
    pdf["wallmid2"] = pdf.apply(compute_wallmid2, axis=1)
    return pdf


# ── Trade classification ─────────────────────────────────────────────────────

def classify_trades(tdf, pdf):
    if tdf is None or len(tdf) == 0:
        return tdf
    tdf = tdf.copy()
    tdf["is_own"] = (tdf["buyer"] == "SUBMISSION") | (tdf["seller"] == "SUBMISSION")
    if len(pdf) > 0:
        ob = pdf[["timestamp", "bid_price_1", "ask_price_1"]].drop_duplicates("timestamp")
        tdf = tdf.merge(ob, on="timestamp", how="left")
    else:
        tdf["bid_price_1"] = np.nan
        tdf["ask_price_1"] = np.nan
    tdf["is_taker"] = (tdf["price"] >= tdf["ask_price_1"]) | (tdf["price"] <= tdf["bid_price_1"])

    pc = pdf[["timestamp", "mid_price"]].drop_duplicates("timestamp").sort_values("timestamp")
    pc["mid_next"] = pc["mid_price"].shift(-1)
    pc["mid_change"] = (pc["mid_next"] - pc["mid_price"]).abs()
    med = pc["mid_change"].median()
    threshold = med * 3 if med > 0 else 1
    pc["sig"] = pc["mid_change"] > threshold
    sig_map = pc.set_index("timestamp")["sig"].to_dict()

    cats = []
    for _, row in tdf.iterrows():
        if row["is_own"]:
            cats.append("F")
        elif not row["is_taker"]:
            cats.append("M")
        else:
            qty = abs(row["quantity"])
            if sig_map.get(row["timestamp"], False) and qty >= 5:
                cats.append("I")
            elif qty >= 20:
                cats.append("B")
            else:
                cats.append("S")
    tdf["category"] = cats
    return tdf


# ── Position tracking ────────────────────────────────────────────────────────

def compute_position(tdf):
    if tdf is None or len(tdf) == 0:
        return pd.DataFrame(columns=["timestamp", "position"])
    own = tdf[tdf["is_own"]].sort_values("timestamp").copy()
    if len(own) == 0:
        return pd.DataFrame(columns=["timestamp", "position"])
    positions, pos = [], 0
    for _, row in own.iterrows():
        pos += row["quantity"] if row["buyer"] == "SUBMISSION" else -row["quantity"]
        positions.append({"timestamp": row["timestamp"], "position": pos})
    return pd.DataFrame(positions)


# ── Colors ───────────────────────────────────────────────────────────────────

CAT_COLOR = {"M": "#999999", "S": "#00FF00", "B": "#FF8C00", "I": "#FF0000", "F": "#FFD700"}
CAT_SYMBOL = {"M": "square", "S": "triangle-up", "B": "triangle-up", "I": "triangle-up", "F": "cross"}


# ── Chart builders ───────────────────────────────────────────────────────────

def build_main_chart(pdf, tdf, show_ob, show_cats, qty_range, indicators, norm_by, h):
    norm_map = None
    if norm_by == "WallMid1":
        norm_map = pdf.set_index("timestamp")["wallmid1"].to_dict()
    elif norm_by == "WallMid2":
        norm_map = pdf.set_index("timestamp")["wallmid2"].to_dict()
    elif norm_by == "Mid":
        norm_map = pdf.set_index("timestamp")["mid_price"].to_dict()

    def norm(vals, ts):
        if norm_map is None: return vals
        ref = np.array([norm_map.get(t, np.nan) for t in ts])
        ref = np.where(ref == 0, np.nan, ref)
        return np.asarray(vals) - ref

    fig = go.Figure()
    ts = pdf["timestamp"]

    # Ask (red), Bid (blue) — screaming colors
    fig.add_trace(go.Scatter(x=ts, y=norm(pdf["ask_price_1"], ts),
        line=dict(color="#FF0000", width=1, shape="hv"), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=ts, y=norm(pdf["bid_price_1"], ts),
        line=dict(color="#0000FF", width=1, shape="hv"), hoverinfo="skip"))

    if show_ob:
        for i in [2, 3]:
            bc, ac = f"bid_price_{i}", f"ask_price_{i}"
            if bc in pdf.columns:
                fig.add_trace(go.Scatter(x=ts, y=norm(pdf[bc], ts),
                    line=dict(color="#0000FF", width=0.5, dash="dot", shape="hv"), hoverinfo="skip"))
            if ac in pdf.columns:
                fig.add_trace(go.Scatter(x=ts, y=norm(pdf[ac], ts),
                    line=dict(color="#FF0000", width=0.5, dash="dot", shape="hv"), hoverinfo="skip"))

    if "WallMid1" in indicators:
        fig.add_trace(go.Scatter(x=ts, y=norm(pdf["wallmid1"], ts),
            line=dict(color="#AA00FF", width=1.5, shape="hv"), hoverinfo="skip"))
    if "WallMid2" in indicators:
        fig.add_trace(go.Scatter(x=ts, y=norm(pdf["wallmid2"], ts),
            line=dict(color="#00BFA5", width=1.5, shape="hv"), hoverinfo="skip"))
    if "Mid" in indicators:
        fig.add_trace(go.Scatter(x=ts, y=norm(pdf["mid_price"], ts),
            line=dict(color="#000000", width=1, dash="dash", shape="hv"), hoverinfo="skip"))

    if tdf is not None and len(tdf) > 0:
        for cat in ["M", "S", "B", "I", "F"]:
            if cat not in show_cats: continue
            sub = tdf[tdf["category"] == cat]
            if qty_range:
                sub = sub[(sub["quantity"] >= qty_range[0]) & (sub["quantity"] <= qty_range[1])]
            if len(sub) == 0: continue
            ty = norm(sub["price"].values, sub["timestamp"])
            hover = []
            for _, r in sub.iterrows():
                own = "You" if r["is_own"] else "Mkt"
                role = "M" if cat == "M" else "T"
                hover.append(f"t={r['timestamp']} p={r['price']} q={r['quantity']} {own}/{role}")
            fig.add_trace(go.Scatter(
                x=sub["timestamp"], y=ty, mode="markers",
                marker=dict(size=8 if cat == "F" else 6, color=CAT_COLOR[cat],
                    symbol=CAT_SYMBOL[cat],
                    line=dict(width=0.5, color="#000") if cat == "F" else dict(width=0)),
                text=hover, hoverinfo="text"))

    layout = {**CHART_LAYOUT, "height": h}
    fig.update_layout(**layout)
    return fig


def build_pnl_chart(pdf, h):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=pdf["timestamp"], y=pdf["profit_and_loss"],
        line=dict(color="#000000", width=1.5),
        fill="tozeroy", fillcolor="rgba(0,200,0,0.06)"))
    fig.update_layout(**{**CHART_LAYOUT, "height": h})
    return fig


def build_pos_chart(pos_df, h):
    fig = go.Figure()
    if len(pos_df) > 0:
        fig.add_trace(go.Scatter(x=pos_df["timestamp"], y=pos_df["position"],
            line=dict(color="#000000", width=1.5, shape="hv"),
            fill="tozeroy", fillcolor="rgba(255,140,0,0.06)"))
    fig.update_layout(**{**CHART_LAYOUT, "height": h})
    return fig


# ── Sidebar (renders on right via CSS) ───────────────────────────────────────

sources = discover_sources()
if not sources:
    st.warning("No data. Run a backtest or place CSVs in round dirs.")
    st.stop()

sb = st.sidebar
selected_source = sb.selectbox("src", list(sources.keys()), label_visibility="collapsed")
src = sources[selected_source]
prices, trades = load_source(src["type"], src["path"])

if prices is None or len(prices) == 0:
    st.warning("No data.")
    st.stop()

products = sorted(prices["product"].unique())
selected_product = sb.selectbox("prod", products, label_visibility="collapsed")

pdf = prices[prices["product"] == selected_product].copy().sort_values("timestamp")
pdf = add_indicators(pdf)

if trades is not None and len(trades) > 0:
    tdf = trades[trades["symbol"] == selected_product].copy().sort_values("timestamp")
    tdf = classify_trades(tdf, pdf)
else:
    tdf = None

ind_options = ["Mid", "WallMid1", "WallMid2"]
show_ind = sb.multiselect("ind", ind_options, default=[], label_visibility="collapsed")
norm_by = sb.selectbox("norm", ["None"] + ind_options, index=0, label_visibility="collapsed")

sb.markdown("---")
cat_opts = {"M": "M", "S": "S", "B": "B", "I": "I", "F": "F"}
show_cats = []
cc = sb.columns(5)
for i, (cat, lbl) in enumerate(cat_opts.items()):
    if cc[i].checkbox(lbl, value=True, key=f"c_{cat}"):
        show_cats.append(cat)

show_ob = sb.checkbox("OB 2-3", value=False)

max_q = int(tdf["quantity"].max()) if tdf is not None and len(tdf) > 0 else 100
qty_range = sb.slider("qty", 0, max(max_q, 1), (0, max(max_q, 1)), label_visibility="collapsed")

sb.markdown("---")
algo_files = sorted(ALGOS_DIR.glob("*.py"))
algo_choices = {"algo.py": BASE_DIR / "algo.py"}
for f in algo_files:
    if f.name != "datamodel.py":
        algo_choices[f.name] = f
sel_algo = sb.selectbox("algo", list(algo_choices.keys()), label_visibility="collapsed")
round_input = sb.text_input("round", value="0", label_visibility="collapsed")

c1, c2 = sb.columns(2)
run_bt = c1.button("Run")
run_pip = c2.button("pip -U")

if run_pip:
    with st.spinner("..."):
        r = subprocess.run(["pipenv", "run", "pip", "install", "-U", "prosperity4btx"],
            capture_output=True, text=True, cwd=str(BASE_DIR))
        sb.success("OK" if r.returncode == 0 else "FAIL")

if run_bt:
    algo_path = algo_choices[sel_algo].resolve()
    algo_dir = algo_path.parent
    dm_link = algo_dir / "datamodel.py"
    dm_src = BASE_DIR / "datamodel.py"
    if algo_dir != BASE_DIR and not dm_link.exists() and dm_src.exists():
        os.symlink(str(dm_src), str(dm_link))
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_name = f"{ts_str}_{algo_path.stem}_r{round_input.replace(' ', '_')}.log"
    out_path = BACKTESTS_DIR / out_name
    cmd = ["pipenv", "run", "prosperity4btx", str(algo_path)] + round_input.split() + ["--out", str(out_path)]
    with st.spinner("..."):
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR), timeout=120)
        if r.returncode == 0:
            sb.success(out_name)
            st.cache_data.clear()
            st.rerun()
        else:
            sb.error("FAIL")
            sb.code(r.stderr[-300:] if r.stderr else r.stdout[-300:])

# ── Main charts — fill viewport ──────────────────────────────────────────────

# Height ratios: price 60%, pnl 20%, pos 20% of ~viewport
# Approximate viewport height minus minimal chrome
VH = 760  # will be stretched by plotly
H_PRICE = int(VH * 0.60)
H_PNL = int(VH * 0.20)
H_POS = int(VH * 0.20)

fig_main = build_main_chart(pdf, tdf, show_ob, show_cats, qty_range, show_ind, norm_by, H_PRICE)
st.plotly_chart(fig_main, width="stretch", config={"displayModeBar": False})

fig_pnl = build_pnl_chart(pdf, H_PNL)
st.plotly_chart(fig_pnl, width="stretch", config={"displayModeBar": False})

pos_df = compute_position(tdf)
fig_pos = build_pos_chart(pos_df, H_POS)
st.plotly_chart(fig_pos, width="stretch", config={"displayModeBar": False})
