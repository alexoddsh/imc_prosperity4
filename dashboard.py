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
html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"]
    { margin: 0 !important; padding: 0 !important; }
[data-testid="stAppViewContainer"] { overflow: hidden !important; }
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
[data-testid="stSidebarCollapseButton"], button[kind="headerNoPadding"],
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stBottomBlockContainer"], [data-testid="stStatusWidget"],
div[data-testid="stAppDeployButton"], section[data-testid="stSidebarNav"],
button[kind="header"], iframe[title="streamlit_lottie"],
footer, header { display: none !important; }
[data-testid="stMainBlockContainer"] { padding: 0 !important; max-width: 100% !important; }
div[data-testid="stVerticalBlockBorderWrapper"] { gap: 0 !important; padding: 0 !important; }
.stPlotlyChart { margin: 0 !important; padding: 0 !important; }
::-webkit-scrollbar { display: none !important; }
.modebar { top: 2px !important; right: 2px !important; }
.modebar-btn { font-size: 12px !important; padding: 2px !important; }

/* ── chart column ── */
[data-testid="stColumn"]:first-child div[data-testid="stVerticalBlock"]
    { gap: 2px !important; }
[data-testid="stColumn"]:first-child { padding-left: 6px !important; }

/* ── control column ── */
[data-testid="stColumn"]:last-child
    { overflow-y: auto !important; max-height: 100vh !important; padding: 4px 6px !important; }
[data-testid="stColumn"]:last-child div[data-testid="stVerticalBlock"]
    { gap: 6px !important; }

/* shrink all widget chrome in ctrl column */
[data-testid="stColumn"]:last-child [data-baseweb="select"],
[data-testid="stColumn"]:last-child [data-baseweb="select"] span,
[data-testid="stColumn"]:last-child [data-baseweb="select"] div,
[data-testid="stColumn"]:last-child [data-baseweb="select"] input,
[data-testid="stColumn"]:last-child [data-baseweb="input"] input,
[data-testid="stColumn"]:last-child .stCheckbox label span,
[data-testid="stColumn"]:last-child [data-baseweb="tag"] span
    { font-size: 11px !important; }
[data-testid="stColumn"]:last-child [data-baseweb="select"] > div
    { min-height: 28px !important; display: flex !important; align-items: center !important; }
[data-testid="stColumn"]:last-child [data-baseweb="input"] input
    { padding: 3px 8px !important; font-size: 11px !important; }
[data-testid="stColumn"]:last-child button
    { font-size: 11px !important; padding: 2px 4px !important; min-height: 24px !important; }

/* info box */
.info-box { font-size: 12px; line-height: 1.4; border: 1px solid #ccc;
    padding: 5px 7px; margin: 0; background: #f8f8f8; }
.info-box b { color: #000; }

/* section labels */
.sl { font-size: 9px; color: #999; margin: 10px 0 1px 0;
    text-transform: uppercase; letter-spacing: 0.5px; }

/* ── category toggle row: the only 5-col horizontal block ── */
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]:nth-child(5):last-child)
    { gap: 2px !important; }
</style>""", unsafe_allow_html=True)

FONT = "IBM Plex Mono, monospace"
BASE_DIR = Path(__file__).parent
BACKTESTS_DIR = BASE_DIR / "backtests"
ALGOS_DIR = BASE_DIR / "algos"
BACKTESTS_DIR.mkdir(exist_ok=True)
ALGOS_DIR.mkdir(exist_ok=True)

CHART_LAYOUT = dict(
    font=dict(family=FONT, size=10),
    paper_bgcolor="white", plot_bgcolor="white",
    margin=dict(t=0, b=18, l=40, r=0), showlegend=False,
    xaxis=dict(gridcolor="#E8E8E8", zeroline=False, tickfont=dict(size=9), tickformat=","),
    yaxis=dict(gridcolor="#E8E8E8", zeroline=False, tickfont=dict(size=9), tickformat=","),
    hoverlabel=dict(font=dict(family=FONT, size=16), namelength=-1, bgcolor="white", bordercolor="#000"),
    dragmode="pan",
)

PLOTLY_CONFIG = {
    "displayModeBar": True, "displaylogo": False,
    "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d", "toggleSpikelines",
        "hoverClosestCartesian", "hoverCompareCartesian", "toImage"],
    "scrollZoom": True,
}

# ── Parsing ──────────────────────────────────────────────────────────────────

def parse_log_file(path):
    text = Path(path).read_text()
    ai = text.find("Activities log:\n")
    ti = text.find("Trade History:\n")
    if ai == -1 or ti == -1: return None, None
    from io import StringIO
    prices = pd.read_csv(StringIO(text[ai + len("Activities log:\n"):ti].strip()), sep=";")
    tt = text[ti + len("Trade History:\n"):].strip()
    tt = re.sub(r',\s*}', '}', tt); tt = re.sub(r',\s*]', ']', tt)
    tl = json.loads(tt)
    trades = pd.DataFrame(tl) if tl else pd.DataFrame(
        columns=["timestamp", "buyer", "seller", "symbol", "currency", "price", "quantity"])
    return prices, trades

def load_csv_pair(pp):
    prices = pd.read_csv(pp, sep=";")
    tp = Path(str(pp).replace("prices", "trades"))
    trades = pd.read_csv(tp, sep=";") if tp.exists() else pd.DataFrame(
        columns=["timestamp", "buyer", "seller", "symbol", "currency", "price", "quantity"])
    return prices, trades

def discover_sources():
    s = {}
    for f in sorted(BACKTESTS_DIR.glob("*.log"), reverse=True):
        s[f"bt: {f.stem}"] = {"type": "log", "path": str(f)}
    for pf in sorted(BASE_DIR.rglob("prices_round_*.csv")):
        s[f"csv: {pf.relative_to(BASE_DIR)}"] = {"type": "csv", "path": str(pf)}
    return s

@st.cache_data
def load_source(st_type, st_path):
    return parse_log_file(st_path) if st_type == "log" else load_csv_pair(st_path)

# ── Indicators ───────────────────────────────────────────────────────────────

def compute_indicators(pdf):
    """Vectorized wallmid1/wallmid2 computation."""
    pdf = pdf.copy()
    tpv, tv = np.zeros(len(pdf)), np.zeros(len(pdf))
    for i in range(1, 4):
        for side, pcol, vcol in [("bid", f"bid_price_{i}", f"bid_volume_{i}"),
                                  ("ask", f"ask_price_{i}", f"ask_volume_{i}")]:
            if pcol in pdf.columns and vcol in pdf.columns:
                p = pdf[pcol].values.astype(float)
                v = np.abs(pdf[vcol].values.astype(float))
                valid = np.isfinite(p) & np.isfinite(v)
                tpv += np.where(valid, p * v, 0)
                tv += np.where(valid, v, 0)
    pdf["wallmid1"] = np.where(tv > 0, tpv / tv, np.nan)

    best_bid_p, best_bid_v = np.full(len(pdf), np.nan), np.zeros(len(pdf))
    best_ask_p, best_ask_v = np.full(len(pdf), np.nan), np.zeros(len(pdf))
    for i in range(1, 4):
        bp_col, bv_col = f"bid_price_{i}", f"bid_volume_{i}"
        ap_col, av_col = f"ask_price_{i}", f"ask_volume_{i}"
        if bp_col in pdf.columns and bv_col in pdf.columns:
            bp = pdf[bp_col].values.astype(float)
            bv = np.abs(pdf[bv_col].values.astype(float))
            mask = np.isfinite(bp) & np.isfinite(bv) & (bv > best_bid_v)
            best_bid_p = np.where(mask, bp, best_bid_p)
            best_bid_v = np.where(mask, bv, best_bid_v)
        if ap_col in pdf.columns and av_col in pdf.columns:
            ap = pdf[ap_col].values.astype(float)
            av = np.abs(pdf[av_col].values.astype(float))
            mask = np.isfinite(ap) & np.isfinite(av) & (av > best_ask_v)
            best_ask_p = np.where(mask, ap, best_ask_p)
            best_ask_v = np.where(mask, av, best_ask_v)
    both_valid = np.isfinite(best_bid_p) & np.isfinite(best_ask_p)
    pdf["wallmid2"] = np.where(both_valid, (best_bid_p + best_ask_p) / 2, np.nan)
    return pdf

def toxic_buyer(pdf, tdf):
    min_price, max_price = tdf["price"].min(), tdf["price"].max()
    if len(tdf[tdf["price"] == min_price]) == 1 and len(tdf[tdf["price"] == max_price]) == 1:
        min_qty = tdf[tdf["price"] == min_price]["quantity"].item()
        max_qty = tdf[tdf["price"] == max_price]["quantity"].item()
        min_time = tdf[tdf["price"] == min_price]["timestamp"].item()
        max_time = tdf[tdf["price"] == max_price]["timestamp"].item()
        if min_qty == max_qty:
            if min_price == pdf[pdf["timestamp"] == min_time]["ask_price_1"] and max_price == pdf[pdf["timestamp"] == max_time]["bid_price_1"]:
                return pd.Series({min_time: min_price, max_time: max_price})
    else:
        return pd.Series(dtype=float)

def add_indicators(pdf, tdf):
    pdf = compute_indicators(pdf)
    signals = toxic_buyer(pdf, tdf)
    pdf["toxic_price"] = pdf["timestamp"].map(signals)
    return pdf

# ── Trade classification ─────────────────────────────────────────────────────

CAT_COLOR  = {"M": "#FF8C00", "S": "#00FF00", "B": "#FF8C00", "I": "#FF0000", "F": "#FFD700"}
CAT_BG     = {"M": "#FF8C00", "S": "#00FF00", "B": "#FF8C00", "I": "#FF0000", "F": "#FFD700"}
CAT_FG     = {"M": "#fff",    "S": "#000",    "B": "#fff",    "I": "#fff",    "F": "#000"}
CAT_SYMBOL = {"M": "square", "S": "triangle-up", "B": "triangle-up", "I": "triangle-up", "F": "cross"}
CAT_SIZE   = {"M": 10, "S": 10, "B": 12, "I": 12, "F": 11}

def classify_trades(tdf, pdf):
    """Vectorized trade classification."""
    if tdf is None or len(tdf) == 0: return tdf
    tdf = tdf.copy()
    tdf["is_own"] = (tdf["buyer"] == "SUBMISSION") | (tdf["seller"] == "SUBMISSION")
    if len(pdf) > 0:
        ob = pdf[["timestamp", "bid_price_1", "ask_price_1"]].drop_duplicates("timestamp")
        tdf = tdf.merge(ob, on="timestamp", how="left")
    else:
        tdf["bid_price_1"] = np.nan; tdf["ask_price_1"] = np.nan
    tdf["is_taker"] = (tdf["price"] > tdf["ask_price_1"]) | (tdf["price"] < tdf["bid_price_1"])

    pc = pdf[["timestamp", "mid_price"]].drop_duplicates("timestamp").sort_values("timestamp")
    mc = (pc["mid_price"].shift(-1) - pc["mid_price"]).abs()
    med = mc.median(); thr = med * 3 if med > 0 else 1
    sig_map = (mc > thr).set_axis(pc["timestamp"])
    tdf["sig"] = tdf["timestamp"].map(sig_map).fillna(False)
    qty = tdf["quantity"].abs()

    cat = pd.Series("S", index=tdf.index)
    cat = cat.where(tdf["is_taker"], "M")
    cat = cat.where(~(tdf["is_taker"] & tdf["sig"] & (qty >= 5)), "I")
    cat = cat.where(~(tdf["is_taker"] & ~(tdf["sig"] & (qty >= 5)) & (qty >= 20)), "B")
    cat = cat.where(~tdf["is_own"], "F")
    tdf["category"] = cat
    tdf.drop(columns=["sig"], inplace=True)
    return tdf

def classify_sides(tdf):
    """Vectorized buyer/seller side classification."""
    buyer_cat = pd.Series("M", index=tdf.index)
    taker_buy = (tdf["category"] != "M") & (tdf["price"] >= tdf["ask_price_1"])
    buyer_cat = buyer_cat.where(~taker_buy, tdf["category"])
    buyer_cat = buyer_cat.where(tdf["buyer"] != "SUBMISSION", "F")

    seller_cat = pd.Series("M", index=tdf.index)
    taker_sell = (tdf["category"] != "M") & (tdf["price"] <= tdf["bid_price_1"])
    seller_cat = seller_cat.where(~taker_sell, tdf["category"])
    seller_cat = seller_cat.where(tdf["seller"] != "SUBMISSION", "F")
    return buyer_cat, seller_cat

def compute_position(tdf):
    if tdf is None or len(tdf) == 0: return pd.DataFrame(columns=["timestamp", "position"])
    own = tdf[tdf["is_own"]].sort_values("timestamp")
    if len(own) == 0: return pd.DataFrame(columns=["timestamp", "position"])
    qty = own["quantity"].values.copy().astype(float)
    qty[own["seller"].values == "SUBMISSION"] *= -1
    return pd.DataFrame({"timestamp": own["timestamp"].values, "position": qty.cumsum()})

# ── Chart builders ───────────────────────────────────────────────────────────

def _hover_texts(sub):
    """Vectorized hover text generation."""
    texts = []
    for _, r in sub.iterrows():
        bc, sc = r["buyer_cat"], r["seller_cat"]
        q, p, t = int(r["quantity"]), int(r["price"]), int(r["timestamp"])
        bbg, sbg = CAT_BG.get(bc, "#eee"), CAT_BG.get(sc, "#eee")
        bfg, sfg = CAT_FG.get(bc, "#000"), CAT_FG.get(sc, "#000")
        texts.append(
            f'<span style="background:{bbg};color:{bfg};padding:2px 6px;font-weight:700;font-size:15px">{bc}</span>'
            f'<span style="font-size:15px;font-weight:700;padding:0 4px">{q}</span>'
            f'<span style="background:{sbg};color:{sfg};padding:2px 6px;font-weight:700;font-size:15px">{sc}</span>'
            f'<span style="font-size:15px;font-weight:700;padding:0 4px">@ {p}</span>'
            f'<br><span style="color:#888;font-size:11px">t={t}</span>'
        )
    return texts

def build_main_chart(pdf, tdf, show_ob, show_cats, qty_range, indicators, norm_by, h):
    nm = None
    if norm_by == "WallMid1": nm = pdf.set_index("timestamp")["wallmid1"].to_dict()
    elif norm_by == "WallMid2": nm = pdf.set_index("timestamp")["wallmid2"].to_dict()
    elif norm_by == "Mid": nm = pdf.set_index("timestamp")["mid_price"].to_dict()
    def norm(v, t):
        if nm is None: return v
        ref = np.array([nm.get(x, np.nan) for x in t])
        ref = np.where(ref == 0, np.nan, ref)
        return np.asarray(v) - ref
    fig = go.Figure()
    ts = pdf["timestamp"]
    fig.add_trace(go.Scatter(x=ts, y=norm(pdf["ask_price_1"], ts), line=dict(color="#FF0000", width=1, shape="hv"), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=ts, y=norm(pdf["bid_price_1"], ts), line=dict(color="#0000FF", width=1, shape="hv"), hoverinfo="skip"))
    if show_ob:
        for i in [2, 3]:
            bc2, ac2 = f"bid_price_{i}", f"ask_price_{i}"
            if bc2 in pdf.columns:
                fig.add_trace(go.Scatter(x=ts, y=norm(pdf[bc2], ts), line=dict(color="#0000FF", width=0.5, dash="dot", shape="hv"), hoverinfo="skip"))
            if ac2 in pdf.columns:
                fig.add_trace(go.Scatter(x=ts, y=norm(pdf[ac2], ts), line=dict(color="#FF0000", width=0.5, dash="dot", shape="hv"), hoverinfo="skip"))
    if "WallMid1" in indicators:
        fig.add_trace(go.Scatter(x=ts, y=norm(pdf["wallmid1"], ts), line=dict(color="#AA00FF", width=1.5, shape="hv"), hoverinfo="skip"))
    if "WallMid2" in indicators:
        fig.add_trace(go.Scatter(x=ts, y=norm(pdf["wallmid2"], ts), line=dict(color="#00BFA5", width=1.5, shape="hv"), hoverinfo="skip"))
    if "Mid" in indicators:
        fig.add_trace(go.Scatter(x=ts, y=norm(pdf["mid_price"], ts), line=dict(color="#000000", width=1, dash="dash", shape="hv"), hoverinfo="skip"))
    if tdf is not None and len(tdf) > 0:
        sub = tdf.copy()
        if qty_range: sub = sub[(sub["quantity"] >= qty_range[0]) & (sub["quantity"] <= qty_range[1])]
        if len(sub) > 0:
            sub["buyer_cat"], sub["seller_cat"] = classify_sides(sub)
            ty = norm(sub["price"].values, sub["timestamp"])
            hover = _hover_texts(sub)
            for cat in ["M", "S", "B", "I", "F"]:
                if cat not in show_cats: continue
                mask = ((sub["buyer_cat"] == cat) | (sub["seller_cat"] == cat)).values
                if not mask.any(): continue
                fig.add_trace(go.Scatter(x=sub["timestamp"][mask], y=ty[mask], mode="markers",
                    marker=dict(size=CAT_SIZE[cat], color=CAT_COLOR[cat], symbol=CAT_SYMBOL[cat],
                        line=dict(width=1, color="#000") if cat == "F" else dict(width=0.5, color="#333")),
                    hovertext=[h for h, m in zip(hover, mask) if m], hoverinfo="text"))
    fig.update_layout(**{**CHART_LAYOUT, "height": h})
    return fig

def build_pnl_chart(pdf, h):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=pdf["timestamp"], y=pdf["profit_and_loss"],
        line=dict(color="#000000", width=1.5), fill="tozeroy", fillcolor="rgba(0,200,0,0.06)", hoverinfo="skip"))
    fig.update_layout(**{**CHART_LAYOUT, "height": h})
    return fig

def build_pos_chart(pos_df, h):
    fig = go.Figure()
    if len(pos_df) > 0:
        fig.add_trace(go.Scatter(x=pos_df["timestamp"], y=pos_df["position"],
            line=dict(color="#000000", width=1.5, shape="hv"), fill="tozeroy", fillcolor="rgba(255,140,0,0.06)", hoverinfo="skip"))
    fig.update_layout(**{**CHART_LAYOUT, "height": h})
    return fig

# ── Layout ───────────────────────────────────────────────────────────────────

sources = discover_sources()
if not sources:
    st.warning("No data. Run a backtest or place CSVs in round dirs.")
    st.stop()

chart_col, ctrl_col = st.columns([5, 1], gap="small")

with ctrl_col:
    selected_source = st.selectbox("Source", list(sources.keys()), label_visibility="collapsed")
    src = sources[selected_source]
    prices, trades = load_source(src["type"], src["path"])
    if prices is None or len(prices) == 0:
        st.warning("No data."); st.stop()
    products = sorted(prices["product"].unique())
    selected_product = st.selectbox("Product", products, label_visibility="collapsed")

    pdf = prices[prices["product"] == selected_product].copy().sort_values("timestamp")
    tdf = None
    if trades is not None and len(trades) > 0:
        tdf = trades[trades["symbol"] == selected_product].copy().sort_values("timestamp")
        tdf = classify_trades(tdf, pdf)
    pdf = add_indicators(pdf, tdf)

    # ── Summary (top, above all other controls) ──
    nt = len(tdf) if tdf is not None else 0
    no = len(tdf[tdf["is_own"]]) if tdf is not None and nt > 0 else 0
    fp = pdf["profit_and_loss"].iloc[-1] if len(pdf) > 0 else 0
    tr = f"{int(pdf['timestamp'].min())}–{int(pdf['timestamp'].max())}" if len(pdf) > 0 else "–"
    st.markdown(f'<div class="info-box"><b>{selected_product}</b> | {tr}<br>'
                f'trades: {nt} (own: {no})<br>Pnl: <b>{fp:.0f}</b></div>', unsafe_allow_html=True)

    # ── Indicators ──
    st.markdown('<div class="sl">indicators</div>', unsafe_allow_html=True)
    ind_opts = ["Mid", "WallMid1", "WallMid2"]
    show_ind = st.multiselect("i", ind_opts, default=[], label_visibility="collapsed")

    # ── Normalize ──
    st.markdown('<div class="sl">normalize</div>', unsafe_allow_html=True)
    norm_by = st.selectbox("n", ["None"] + ind_opts, index=0, label_visibility="collapsed")

    # ── Traders ──
    st.markdown('<div class="sl">traders</div>', unsafe_allow_html=True)
    show_ob = st.checkbox("OB", value=False)

    # ── Category toggles — colored buttons ──
    all_cats = [("M", "#FF8C00", "#fff"), ("S", "#00FF00", "#000"),
                ("B", "#FF8C00", "#fff"), ("I", "#FF0000", "#fff"), ("F", "#FFD700", "#000")]
    for cat, _, _ in all_cats:
        if f"cat_{cat}" not in st.session_state:
            st.session_state[f"cat_{cat}"] = True

    # dynamic CSS: color each button by nth-child in the 5-col row
    cat_css = ('[data-testid="stHorizontalBlock"]'
               ':has(> [data-testid="stColumn"]:nth-child(5):last-child)'
               ' > [data-testid="stColumn"] button'
               ' { font-weight:700 !important; font-size:11px !important;'
               ' padding:1px 0 !important; min-height:0 !important; height:22px !important;'
               ' border:1px solid #666 !important; }\n')
    for i, (cat, bg, fg) in enumerate(all_cats, 1):
        op = "1" if st.session_state[f"cat_{cat}"] else "0.2"
        cat_css += (f'[data-testid="stHorizontalBlock"]'
                    f':has(> [data-testid="stColumn"]:nth-child(5):last-child)'
                    f' > [data-testid="stColumn"]:nth-child({i}) button'
                    f' {{ background:{bg} !important; color:{fg} !important; opacity:{op} !important; }}\n')
    st.markdown(f'<style>{cat_css}</style>', unsafe_allow_html=True)

    cat_cols = st.columns(len(all_cats))
    show_cats = []
    for col, (cat, _, _) in zip(cat_cols, all_cats):
        if col.button(cat, key=f"cat_{cat}_btn", use_container_width=True):
            st.session_state[f"cat_{cat}"] = not st.session_state[f"cat_{cat}"]
            st.rerun()
        if st.session_state[f"cat_{cat}"]:
            show_cats.append(cat)

    # ── Qty filter ──
    st.markdown('<div class="sl">qty filter</div>', unsafe_allow_html=True)
    max_q = int(tdf["quantity"].max()) if tdf is not None and len(tdf) > 0 else 100
    qty_range = st.slider("q", 0, max(max_q, 1), (0, max(max_q, 1)), label_visibility="collapsed")

    # ── Algo / backtest ──
    st.markdown('<div class="sl">algo</div>', unsafe_allow_html=True)
    algo_files = sorted(ALGOS_DIR.glob("*.py"))
    algo_choices = {"algo.py": BASE_DIR / "algo.py"}
    for f in algo_files:
        if f.name != "datamodel.py": algo_choices[f.name] = f
    sel_algo = st.selectbox("a", list(algo_choices.keys()), label_visibility="collapsed")
    st.markdown('<div class="sl">round</div>', unsafe_allow_html=True)
    round_input = st.text_input("r", value="0", label_visibility="collapsed")
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
        ad = algo_path.parent; dl = ad / "datamodel.py"; ds = BASE_DIR / "datamodel.py"
        if ad != BASE_DIR and not dl.exists() and ds.exists(): os.symlink(str(ds), str(dl))
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        on = f"{ts_str}_{algo_path.stem}_r{round_input.replace(' ', '_')}.log"
        op = BACKTESTS_DIR / on
        cmd = ["pipenv", "run", "prosperity4btx", str(algo_path)] + round_input.split() + ["--out", str(op)]
        with st.spinner("..."):
            r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR), timeout=120)
            if r.returncode == 0:
                st.success(on); st.cache_data.clear(); st.rerun()
            else:
                st.error("FAIL"); st.code(r.stderr[-300:] if r.stderr else r.stdout[-300:])

# ── Charts ───────────────────────────────────────────────────────────────────

with chart_col:
    VH = 760
    fig_main = build_main_chart(pdf, tdf, show_ob, show_cats, qty_range, show_ind, norm_by, int(VH * 0.60))
    st.plotly_chart(fig_main, width="stretch", config=PLOTLY_CONFIG)
    fig_pnl = build_pnl_chart(pdf, int(VH * 0.20))
    st.plotly_chart(fig_pnl, width="stretch", config=PLOTLY_CONFIG)
    pos_df = compute_position(tdf)
    fig_pos = build_pos_chart(pos_df, int(VH * 0.20))
    st.plotly_chart(fig_pos, width="stretch", config=PLOTLY_CONFIG)
