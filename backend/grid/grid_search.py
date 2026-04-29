import os
import sys
import csv
import time
import random
import argparse
import subprocess
import itertools
from io import StringIO
from pathlib import Path
from datetime import datetime
import yaml
import pandas as pd
from dotenv import load_dotenv
import platform
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

BASE_DIR = Path(__file__).resolve().parent.parent
ALGOS_DIR = BASE_DIR / "algos"
TMP_ALGO = ALGOS_DIR / "_grid_tmp.py"
TMP_LOG = BASE_DIR / "logs" / "_grid_tmp.log"

PARAM_START = "# --- GRID PARAMS ---"
PARAM_END = "# --- END GRID PARAMS ---"


def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def parse_template(algo_path: Path) -> tuple[str, str, str, dict]:
    text = algo_path.read_text()

    start = text.find(PARAM_START)
    end = text.find(PARAM_END)
    if start == -1 or end == -1:
        print(f"[GRID] ERROR: Could not find GRID PARAMS block in {algo_path.name}")
        print(f"[GRID] Add '{PARAM_START}' and '{PARAM_END}' markers around your constants")
        sys.exit(1)

    end += len(PARAM_END)
    before = text[:start]
    block = text[start:end]
    after = text[end:]

    defaults = {}
    for line in block.splitlines():
        line = line.strip()
        if line.startswith("#") or not line or "=" not in line:
            continue
        name, val = line.split("=", 1)
        name = name.strip()
        val = val.strip()
        try:
            defaults[name] = eval(val)
        except Exception:
            defaults[name] = val

    return before, block, after, defaults


def build_param_block(params: dict) -> str:
    lines = [PARAM_START]
    for name, val in params.items():
        lines.append(f"{name} = {val}")
    lines.append(PARAM_END)
    return "\n".join(lines)


def write_tmp_algo(before: str, after: str, params: dict):
    block = build_param_block(params)
    TMP_ALGO.write_text(before + block + after)


def extract_pnl(log_path: Path) -> tuple[float, dict[str, float]]:
    text = log_path.read_text()

    ai = text.find("Activities log:\n")
    ti = text.find("Trade History:\n")
    if ai == -1 or ti == -1:
        return 0.0, {}

    csv_str = text[ai + len("Activities log:\n"):ti].strip()
    prices = pd.read_csv(StringIO(csv_str), sep=";")

    eod = prices[prices["timestamp"] % 1000000 == 999900]

    eod = eod.copy()
    eod["day_idx"] = eod["timestamp"] // 1000000
    last_ts_per_day = eod.groupby("day_idx")["timestamp"].max()

    total = 0.0
    product_totals = {}
    for ts in last_ts_per_day.values:
        rows = eod[eod["timestamp"] == ts]
        for _, row in rows.iterrows():
            p = row["product"]
            pnl = row["profit_and_loss"]
            total += pnl
            product_totals[p] = product_totals.get(p, 0.0) + pnl

    return total, product_totals


def run_single(year: int, round_id: str, combo_params: dict, before: str, after: str) -> tuple[float, dict[str, float], float]:
    write_tmp_algo(before, after, combo_params)
    os.makedirs(TMP_LOG.parent, exist_ok=True)

    if platform.system() == 'Linux':
        data_input = f"/home/victor/notes/imc_prosperity4/backend/backtester/resources-{year}"
    else:
        data_input = f"/Users/alexoddsh/prosperity/backend/backtester/resources-{year}"

    cmd = [
        sys.executable, "-m", "backtester",
        str(TMP_ALGO),
        round_id,
        "--data", data_input,
        "--no-progress",
        "--out", str(TMP_LOG),
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{ALGOS_DIR}:{env.get('PYTHONPATH', '')}"

    t0 = time.time()
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(ALGOS_DIR.parent),
        env=env,
    )
    duration = time.time() - t0

    if proc.returncode != 0:
        print(f"[GRID] Binary failed (exit {proc.returncode})")
        if proc.stderr:
            print(f"[GRID] STDERR: {proc.stderr[:500]}")
        if proc.stdout:
            print(f"[GRID] STDOUT (last 500): {proc.stdout[-500:]}")
        print(f"[GRID] CMD: {' '.join(cmd)}")
        print("[GRID] TMP_ALGO first 30 lines:")
        for i, line in enumerate(TMP_ALGO.read_text().splitlines()[:30]):
            print(f"  {i+1}: {line}")
        return 0.0, {}, duration

    if not TMP_LOG.exists():
        print(f"[GRID] WARNING: Log file not created at {TMP_LOG}")
        return 0.0, {}, duration

    total_pnl, product_pnls = extract_pnl(TMP_LOG)

    if total_pnl == 0.0:
        # debug: check what's in the log
        text = TMP_LOG.read_text()
        has_activities = "Activities log:" in text
        has_trades = "Trade History:" in text
        print(f"[GRID] DEBUG: log size={len(text)}, has_activities={has_activities}, has_trades={has_trades}")

    if TMP_LOG.exists():
        TMP_LOG.unlink()

    return total_pnl, product_pnls, duration


def plot_results(csv_path: Path, param_names: list[str]):
    df = pd.read_csv(csv_path)
    n = len(param_names)
    plot_path = csv_path.with_suffix(".png")

    if n == 1:
        p = param_names[0]
        grouped = df.groupby(p)["total_pnl"].mean().reset_index().sort_values(p)
        fig, ax = plt.subplots(figsize=(max(6, len(grouped) * 0.6), 5))
        colors = ["#d73027" if v < 0 else "#1a9850" for v in grouped["total_pnl"]]
        bars = ax.bar(grouped[p].astype(str), grouped["total_pnl"], color=colors, edgecolor="white", linewidth=0.5)
        ax.axhline(0, color="white", linewidth=0.8, alpha=0.5)
        ax.set_xlabel(p, color="white")
        ax.set_ylabel("PnL", color="white")
        ax.set_title(f"PnL by {p}", color="white", fontweight="bold")
        ax.tick_params(colors="white")
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")
        fig.patch.set_facecolor("#1e1e2e")
        ax.set_facecolor("#2a2a3e")
        fig.tight_layout()
        fig.savefig(plot_path, dpi=130)
        plt.close(fig)
        print(f"[GRID] Heatmap saved: {plot_path}")
        return

    # build all pairs for heatmaps
    pairs = list(itertools.combinations(param_names, 2))
    ncols = min(3, len(pairs))
    nrows = (len(pairs) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(7 * ncols, 6 * nrows), squeeze=False)
    fig.patch.set_facecolor("#1e1e2e")

    for idx, (px, py) in enumerate(pairs):
        ax = axes[idx // ncols][idx % ncols]
        pivot = df.groupby([px, py])["total_pnl"].mean().reset_index()
        xs = sorted(pivot[px].unique())
        ys = sorted(pivot[py].unique())
        matrix = np.full((len(ys), len(xs)), np.nan)
        xi_map = {v: i for i, v in enumerate(xs)}
        yi_map = {v: i for i, v in enumerate(ys)}
        for _, row in pivot.iterrows():
            matrix[yi_map[row[py]], xi_map[row[px]]] = row["total_pnl"]

        vmax = np.nanmax(np.abs(matrix)) or 1
        im = ax.imshow(matrix, cmap="RdYlGn", vmin=-vmax, vmax=vmax, aspect="auto", origin="lower")

        ax.set_xticks(range(len(xs)))
        ax.set_xticklabels([str(x) for x in xs], rotation=45, ha="right", color="white", fontsize=8)
        ax.set_yticks(range(len(ys)))
        ax.set_yticklabels([str(y) for y in ys], color="white", fontsize=8)
        ax.set_xlabel(px, color="white", fontsize=9)
        ax.set_ylabel(py, color="white", fontsize=9)
        title = f"{px} vs {py}"
        if n > 2:
            title += "\n(avg over other params)"
        ax.set_title(title, color="white", fontsize=10, fontweight="bold")
        ax.set_facecolor("#2a2a3e")

        # annotate cells
        for yi in range(len(ys)):
            for xi in range(len(xs)):
                v = matrix[yi, xi]
                if not np.isnan(v):
                    text_color = "black" if abs(v) < vmax * 0.6 else "white"
                    ax.text(xi, yi, f"{v:.0f}", ha="center", va="center", fontsize=7, color=text_color)

        cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        cb.ax.yaxis.set_tick_params(color="white")
        plt.setp(cb.ax.yaxis.get_ticklabels(), color="white")

    # hide unused axes
    for idx in range(len(pairs), nrows * ncols):
        axes[idx // ncols][idx % ncols].set_visible(False)

    fig.suptitle("Grid Search — PnL Heatmap", color="white", fontsize=14, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(plot_path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"[GRID] Heatmap saved: {plot_path}")


def main():
    parser = argparse.ArgumentParser(description="Grid search over algo parameters")
    parser.add_argument("--config", help="Path to YAML config file")
    parser.add_argument("--max-runs", type=int, default=0, help="Cap total combinations (random sample)")
    parser.add_argument("--output", type=str, default="", help="Custom output CSV path")
    args = parser.parse_args()

    config_path = Path(__file__).parent.joinpath(f"configs/{args.config.split("/")[-1] if "/" in args.config else args.config}") 
    config = load_config(config_path.__str__())
    algo_file = config["algo_file"]
    round_id = str(config["round"])
    year = str(config["year"])
    search_params = config["params"]

    algo_path = ALGOS_DIR / algo_file

    before, _, after, defaults = parse_template(algo_path)

    # validate config params exist in the algo's GRID PARAMS block
    for k in search_params:
        if k not in defaults:
            print(f"[GRID] ERROR: param '{k}' not found in {algo_file}'s GRID PARAMS block")
            print(f"[GRID] Available params: {list(defaults.keys())}")
            sys.exit(1)

    param_names = list(search_params.keys())
    param_values = [search_params[k] for k in param_names]
    all_combos = list(itertools.product(*param_values))

    if args.max_runs and len(all_combos) > args.max_runs:
        random.shuffle(all_combos)
        all_combos = all_combos[:args.max_runs]

    total_runs = len(all_combos)

    if args.output:
        out_path = Path(__file__).parent.joinpath(f"results/{args.output.split("/")[-1] if "/" in args.output else args.output}")
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = Path(__file__).resolve().parent / "results"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"{algo_file.replace('.py', '')}_{ts}.csv"

    print(f"[GRID] Config: {args.config}")
    print(f"[GRID] Algo: {algo_file} | Round: {round_id} | Year: {year}")
    print(f"[GRID] Params: {param_names}")
    print(f"[GRID] Total combinations: {total_runs}")
    print()

    # first run to discover products for CSV header
    first_combo_params = {**defaults}
    for i, name in enumerate(param_names):
        first_combo_params[name] = all_combos[0][i]

    total_pnl, product_pnls, duration = run_single(year, round_id, first_combo_params, before, after)
    products = sorted(product_pnls.keys())

    combo_str = ", ".join(f"{k}={first_combo_params[k]}" for k in param_names)
    print(f"[GRID] Run 1/{total_runs} | {{{combo_str}}} | PNL: {total_pnl:.1f} | {duration:.1f}s")

    fieldnames = ["run_id"] + param_names + ["total_pnl"] + [f"pnl_{p}" for p in products] + ["duration_s"]

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        row = {"run_id": 1, "total_pnl": total_pnl, "duration_s": round(duration, 2)}
        for i, name in enumerate(param_names):
            row[name] = all_combos[0][i]
        for p in products:
            row[f"pnl_{p}"] = product_pnls.get(p, 0.0)
        writer.writerow(row)

    best_pnl, best_combo, best_id = total_pnl, dict(first_combo_params), 1

    with open(out_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        for idx, combo in enumerate(all_combos[1:], start=2):
            combo_params = {**defaults}
            for i, name in enumerate(param_names):
                combo_params[name] = combo[i]

            total_pnl, product_pnls, duration = run_single(year, round_id, combo_params, before, after)

            row = {"run_id": idx, "total_pnl": total_pnl, "duration_s": round(duration, 2)}
            for i, name in enumerate(param_names):
                row[name] = combo[i]
            for p in products:
                row[f"pnl_{p}"] = product_pnls.get(p, 0.0)
            writer.writerow(row)
            f.flush()

            combo_str = ", ".join(f"{k}={combo_params[k]}" for k in param_names)
            print(f"[GRID] Run {idx}/{total_runs} | {{{combo_str}}} | PNL: {total_pnl:.1f} | {duration:.1f}s")

            if total_pnl > best_pnl:
                best_pnl = total_pnl
                best_combo = dict(combo_params)
                best_id = idx

    if TMP_ALGO.exists():
        TMP_ALGO.unlink()

    print()
    best_str = ", ".join(f"{k}={best_combo[k]}" for k in param_names)
    print(f"[GRID] Done. Best: run {best_id} | PNL: {best_pnl:.1f} | {{{best_str}}}")
    print(f"[GRID] Results: {out_path}")

    plot_results(out_path, param_names)


if __name__ == "__main__":
    main()
