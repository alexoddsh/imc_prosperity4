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

st.set_page_config(page_title="Prosperity", layout="wide", initial_sidebar_state="collapsed")

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&display=swap');
* { font-family: 'IBM Plex Mono', monospace !important; border-radius: 0 !important; }
html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
    overflow: hidden !important; margin: 0 !important; padding: 0 !important;
}
/* hide sidebar completely — we use columns instead */
[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="stSidebarCollapseButton"],
button[kind="headerNoPadding"] { display: none !important; }
/* hide all streamlit chrome */
[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stBottomBlockContainer"],
[data-testid="stStatusWidget"],
div[data-testid="stAppDeployButton"],
section[data-testid="stSidebarNav"],
button[kind="header"],
iframe[title="streamlit_lottie"],
footer, header { display: none !important; }
/* main container */
[data-testid="stMainBlockContainer"] {
    padding: 0 !important; max-width: 100% !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] { gap: 0 !important; padding: 0 !important; }
div[data-testid="stVerticalBlock"] { gap: 0 !important; }
.stPlotlyChart { margin: 0 !important; padding: 0 !important; }
::-webkit-scrollbar { display: none !important; }
/* plotly modebar */
.modebar { top: 2px !important; right: 2px !important; }
.modebar-btn { font-size: 12px !important; padding: 2px !important; }
/* right panel custom styling */
.rpanel {
    font-family: 'IBM Plex Mono', monospace; font-size: 11px;
    padding: 4px 6px; overflow-y: auto; scrollbar-width: none;
    max-height: 100vh;
}
.rpanel::-webkit-scrollbar { display: none; }
.rpanel label { font-size: 10px !important; color: #666; margin-bottom: 1px; display: block; }
.info-box {
    font-size: 10px; line-height: 1.3; border: 1px solid #ccc;
    padding: 3px 5px; margin: 3px 0; background: #f8f8f8;
}
.info-box b { color: #000; }
.tgrid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 2px; margin: 3px 0; }
.tgrid-cell {
    font-size: 11px; font-weight: 700; text-align: center; padding: 4px 0;
    border: 1px solid #888;
}
.tgrid-cell.off { opacity: 0.15; text-decoration: line-through; }
.sec-label { font-size: 10px; color: #888; margin: 4px 0 1px 0; }
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
    hoverlabel=dict(font=dict(family=FONT, size=16), namelength=-1, bgcolor="white", bordercolor="#000"),
    dragmode="pan",
)

PLOTLY_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": [
        "select2d", "lasso2d", "autoScale2d", "toggleSpikelines",
        "hoverClosestCartesian", "hoverCompareCartesian", "toImage",
    ],
    "scrollZoom": True,
}

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

CAT_COLOR  = {"M": "#999999", "S": "#00FF00", "B": "#FF8C00", "I": "#FF0000", "F": "#FFD700"}
CAT_BG     = {"M": "#bbb",    "S": "#00FF00", "B": "#FF8C00", "I": "#FF0000", "F": "#FFD700"}
CAT_FG     = {"M": "#000",    "S": "#000",    "B": "#fff",    "I": "#fff",    "F": "#000"}
CAT_SYMBOL = {"M": "square", "S": "triangle-up", "B": "triangle-up", "I": "triangle-up", "F": "cross"}
CAT_SIZE   = {"M": 10, "S": 10, "B": 12, "I": 12, "F": 11}


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


def _buyer_cat(row):
    if row["buyer"] == "SUBMISSION":
        return "F"
    if row.get("category") == "M":
        return "M"
    if row["price"] >= row.get("ask_price_1", float("inf")):
        return row.get("category", "?")
    return "M"


def _seller_cat(row):
    if row["seller"] == "SUBMISSION":
        return "F"
    if row.get("category") == "M":
        return "M"
    if row["price"] <= row.get("bid_price_1", 0):
        return row.get("category", "?")
    return "M"


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


# ── Chart builders ───────────────────────────────────────────────────────────

def _hover_html(row):
    bc = _buyer_cat(row)
    sc = _seller_cat(row)
    q = int(row["quantity"])
    p = int(row["price"])
    t = int(row["timestamp"])
    bc_bg, sc_bg = CAT_BG.get(bc, "#eee"), CAT_BG.get(sc, "#eee")
    bc_fg, sc_fg = CAT_FG.get(bc, "#000"), CAT_FG.get(sc, "#000")
    return (
        f'<span style="background:{bc_bg};color:{bc_fg};padding:2px 6px;font-weight:700;font-size:15px">{bc}</span>'
        f'<span style="font-size:15px;font-weight:700;padding:0 4px">{q}</span>'
        f'<span style="background:{sc_bg};color:{sc_fg};padding:2px 6px;font-weight:700;font-size:15px">{sc}</span>'
        f'<span style="font-size:15px;font-weight:700;padding:0 4px">@ {p}</span>'
        f'<br><span style="color:#888;font-size:11px">t={t}</span>'
    )


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
            hover = [_hover_html(r) for _, r in sub.iterrows()]
            fig.add_trace(go.Scatter(
                x=sub["timestamp"], y=ty, mode="markers",
                marker=dict(size=CAT_SIZE[cat], color=CAT_COLOR[cat], symbol=CAT_SYMBOL[cat],
                    line=dict(width=1, color="#000") if cat == "F" else dict(width=0.5, color="#333")),
                hovertext=hover, hoverinfo="text",
            ))

    fig.update_layout(**{**CHART_LAYOUT, "height": h})
    return fig


def build_pnl_chart(pdf, h):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=pdf["timestamp"], y=pdf["profit_and_loss"],
        line=dict(color="#000000", width=1.5),
        fill="tozeroy", fillcolor="rgba(0,200,0,0.06)", hoverinfo="skip"))
    fig.update_layout(**{**CHART_LAYOUT, "height": h})
    return fig


def build_pos_chart(pos_df, h):
    fig = go.Figure()
    if len(pos_df) > 0:
        fig.add_trace(go.Scatter(x=pos_df["timestamp"], y=pos_df["position"],
            line=dict(color="#000000", width=1.5, shape="hv"),
            fill="tozeroy", fillcolor="rgba(255,140,0,0.06)", hoverinfo="skip"))
    fig.update_layout(**{**CHART_LAYOUT, "height": h})
    return fig


# ── Layout: charts left, controls right ──────────────────────────────────────

sources = discover_sources()
if not sources:
    st.warning("No data. Run a backtest or place CSVs in round dirs.")
    st.stop()

# Two columns: charts (wide) | controls (narrow)
chart_col, ctrl_col = st.columns([5, 1], gap="small")

with ctrl_col:
    selected_source = st.selectbox("Source", list(sources.keys()), label_visibility="collapsed")
    src = sources[selected_source]
    prices, trades = load_source(src["type"], src["path"])

    if prices is None or len(prices) == 0:
        st.warning("No data.")
        st.stop()

    products = sorted(prices["product"].unique())
    selected_product = st.selectbox("Product", products, label_visibility="collapsed")

    pdf = prices[prices["product"] == selected_product].copy().sort_values("timestamp")
    pdf = add_indicators(pdf)

    if trades is not None and len(trades) > 0:
        tdf = trades[trades["symbol"] == selected_product].copy().sort_values("timestamp")
        tdf = classify_trades(tdf, pdf)
    else:
        tdf = None

    # Info box
    n_trades = len(tdf) if tdf is not None else 0
    n_own = len(tdf[tdf["is_own"]]) if tdf is not None and n_trades > 0 else 0
    final_pnl = pdf["profit_and_loss"].iloc[-1] if len(pdf) > 0 else 0
    ts_range = f"{int(pdf['timestamp'].min())}–{int(pdf['timestamp'].max())}" if len(pdf) > 0 else "–"
    st.markdown(
        f'<div class="info-box">'
        f'<b>{selected_product}</b> | {ts_range}<br>'
        f'trades: {n_trades} (own: {n_own})<br>PnL: <b>{final_pnl:.0f}</b>'
        f'</div>',
        unsafe_allow_html=True
    )

    # Indicators
    st.markdown('<div class="sec-label">Indicators</div>', unsafe_allow_html=True)
    ind_options = ["Mid", "WallMid1", "WallMid2"]
    show_ind = st.multiselect("ind", ind_options, default=[], label_visibility="collapsed")

    st.markdown('<div class="sec-label">Normalize</div>', unsafe_allow_html=True)
    norm_by = st.selectbox("norm", ["None"] + ind_options, index=0, label_visibility="collapsed")

    # Trader grid
    st.markdown('<div class="sec-label">Traders</div>', unsafe_allow_html=True)
    show_ob = st.checkbox("OB", value=False)
    all_on = st.checkbox("All", value=True)

    CAT_GRID = [("M", "#bbb", "#000"), ("S", "#00FF00", "#000"), ("B", "#FF8C00", "#fff"),
                ("I", "#FF0000", "#fff"), ("F", "#FFD700", "#000")]

    show_cats = []
    gc = st.columns(5)
    for i, (cat, bg, fg) in enumerate(CAT_GRID):
        if gc[i].checkbox(cat, value=all_on, key=f"c_{cat}"):
            show_cats.append(cat)

    # Colored strip
    cells = ""
    for cat, bg, fg in CAT_GRID:
        cls = "" if cat in show_cats else " off"
        cells += f'<div class="tgrid-cell{cls}" style="background:{bg};color:{fg}">{cat}</div>'
    st.markdown(f'<div class="tgrid">{cells}</div>', unsafe_allow_html=True)

    # Qty filter
    st.markdown('<div class="sec-label">Qty filter</div>', unsafe_allow_html=True)
    max_q = int(tdf["quantity"].max()) if tdf is not None and len(tdf) > 0 else 100
    qty_range = st.slider("qty", 0, max(max_q, 1), (0, max(max_q, 1)), label_visibility="collapsed")

    # Backtest
    st.markdown('<div class="sec-label">Backtest</div>', unsafe_allow_html=True)
    algo_files = sorted(ALGOS_DIR.glob("*.py"))
    algo_choices = {"algo.py": BASE_DIR / "algo.py"}
    for f in algo_files:
        if f.name != "datamodel.py":
            algo_choices[f.name] = f
    sel_algo = st.selectbox("algo", list(algo_choices.keys()), label_visibility="collapsed")
    round_input = st.text_input("round", value="0", label_visibility="collapsed")

    bc1, bc2 = st.columns(2)
    run_bt = bc1.button("Run")
    run_pip = bc2.button("pip -U")

    if run_pip:
        with st.spinner("..."):
            r = subprocess.run(["pipenv", "run", "pip", "install", "-U", "prosperity4btx"],
                capture_output=True, text=True, cwd=str(BASE_DIR))
            st.success("OK" if r.returncode == 0 else "FAIL")

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
                st.success(out_name)
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("FAIL")
                st.code(r.stderr[-300:] if r.stderr else r.stdout[-300:])

# ── Charts in left column ────────────────────────────────────────────────────

with chart_col:
    VH = 760
    H_PRICE = int(VH * 0.60)
    H_PNL = int(VH * 0.20)
    H_POS = int(VH * 0.20)

    fig_main = build_main_chart(pdf, tdf, show_ob, show_cats, qty_range, show_ind, norm_by, H_PRICE)
    st.plotly_chart(fig_main, width="stretch", config=PLOTLY_CONFIG)

    fig_pnl = build_pnl_chart(pdf, H_PNL)
    st.plotly_chart(fig_pnl, width="stretch", config=PLOTLY_CONFIG)

    pos_df = compute_position(tdf)
    fig_pos = build_pos_chart(pos_df, H_POS)
    st.plotly_chart(fig_pos, width="stretch", config=PLOTLY_CONFIG)
