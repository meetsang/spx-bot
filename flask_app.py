from flask import Flask, request, render_template
import os, json
import pandas as pd
from datetime import datetime
from typing import List

# Your existing GEX computation
from greeks_gex import analyze_options_gex

app = Flask(__name__)

# Configuration
DATA_BASE_DIR = "Data"
STRATEGY_FOLDER = "SPX_9IF_0DTE"
SPX_CSV_NAME = "spx.csv"
PNL_IF_CSV_NAME = "pnl.csv"
PNL_STRAT_CSV_NAME = "pnl_strategy.csv"
STATE_JSON_NAME = "state.json"


SPX_PRICE_COL_CANDIDATES = ["spx", "close", "price", "SPX"]

# ---------- Helpers ----------
def normalize_key_levels(result: dict) -> dict:
    """
    Normalize key_levels so template can safely display,
    compute distance_pct if missing, and round/drop decimals as requested.
    """
    levels = result.get("key_levels") or []
    norm = []

    # Get a reference price if gex_summary or ticker_data exists
    ref_price = None
    if result.get("ticker_data") and hasattr(result["ticker_data"], "price"):
        try:
            ref_price = float(result["ticker_data"].price)
        except Exception:
            pass
    elif isinstance(result.get("ticker_data"), dict) and "price" in result["ticker_data"]:
        try:
            ref_price = float(result["ticker_data"]["price"])
        except Exception:
            pass

    for lvl in levels:
        def getv(k, default=None):
            try:
                return lvl.get(k, default) if isinstance(lvl, dict) else getattr(lvl, k, default)
            except Exception:
                return default

        def to_float(x, default=0.0):
            try:
                return float(x)
            except Exception:
                return default

        strike_val = to_float(getv("strike"))

        # Distance & pct
        distance_val = to_float(getv("distance"))
        distance_pct_val = to_float(getv("distance_pct"))
        if (distance_pct_val == 0 or distance_pct_val is None) and ref_price:
            try:
                distance_pct_val = (distance_val / ref_price) * 100.0
            except Exception:
                distance_pct_val = 0.0

        norm.append({
            "strike": strike_val,
            "total_gex": round(to_float(getv("total_gex"))),  # INT
            "call_gex": round(to_float(getv("call_gex"))),
            "put_gex": round(to_float(getv("put_gex"))),
            "distance": int(round(distance_val)),             # INT
            "distance_pct": distance_pct_val,                 # keep float for % formatting
            "level_type": getv("level_type", "") or ""
        })

    # Sort levels by strike ascending
    norm = sorted(norm, key=lambda d: (d["strike"] is None, d["strike"]))
    result["key_levels"] = norm
    return result


# --- GEX table row builder ---
def zip_calls_puts(result):
    """
    Produce a list of {"call": call_row_or_None, "put": put_row_or_None}
    so template can iterate without using Python 'max' or 'range' in Jinja.
    """
    calls = result.get("calls_data") or []
    puts = result.get("puts_data") or []
    n = max(len(calls), len(puts))
    rows = []
    for i in range(n):
        c = calls[i] if i < len(calls) else None
        p = puts[i] if i < len(puts) else None
        rows.append({"call": c, "put": p})
    return rows


def list_available_dates() -> List[str]:
    if not os.path.isdir(DATA_BASE_DIR):
        return []
    out = []
    for name in os.listdir(DATA_BASE_DIR):
        p = os.path.join(DATA_BASE_DIR, name)
        try:
            datetime.strptime(name, "%Y-%m-%d")
            if os.path.isdir(p):
                out.append(name)
        except:
            pass
    return sorted(out, reverse=True)

def load_csv_if_exists(path: str) -> pd.DataFrame:
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            if "ts" in df.columns:
                df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
            return df
        except:
            return pd.DataFrame()
    return pd.DataFrame()

def read_text_if_exists(path: str) -> str:
    if os.path.exists(path):
        try:
            return open(path, "r", encoding="utf-8", errors="ignore").read()
        except:
            return ""
    return ""

def find_spx_price_column(df: pd.DataFrame) -> str:
    for c in SPX_PRICE_COL_CANDIDATES:
        if c in df.columns:
            return c
        for col in df.columns:
            if col.lower() == c.lower():
                return col
    # fallback: any numeric column (besides ts)
    for col in df.columns:
        if col != "ts":
            try:
                pd.to_numeric(df[col].dropna().head(1))
                return col
            except:
                continue
    return None

def strategy_folder_exists(date_str: str) -> bool:
    return os.path.isdir(os.path.join(DATA_BASE_DIR, date_str, STRATEGY_FOLDER))

# ---------- Routes ----------
@app.route("/", methods=["GET", "POST"])
@app.route("/gex", methods=["GET", "POST"])
def gex():
    result = None
    error = None
    expiry = datetime.now().strftime("%Y-%m-%d")
    ticker = None

    if request.method == "POST":
        ticker = request.form.get("ticker", "SPX")
        expiry = request.form.get("expiry") or expiry
        price_override_raw = request.form.get("price_override", "").strip()
        try:
            price_override = float(price_override_raw) if price_override_raw else 0.0
            analysis = analyze_options_gex(ticker, expiry, price_override)
            if analysis.get("success"):
                result = normalize_key_levels(analysis)  # pass dict directly; template renders fields
            else:
                error = analysis.get("error", "Unknown error")
        except Exception as e:
            error = str(e)

    return render_template("gex.html",
                           active_tab="gex",
                           result=result,
                           rows=zip_calls_puts(result) if result else [],
                           error=error,
                           expiry=expiry,
                           ticker=ticker or "SPX")

@app.route("/strategy")
def strategy():
    dates = list_available_dates()
    if not dates:
        return render_template("strategy.html",
                               active_tab="strategy",
                               dates=[],
                               selected_date="",
                               spx_available=False,
                               plotly_data="[]",
                               plotly_layout="{}",
                               strategy_found=False,
                               status_text="",
                               pnl_if_text="",
                               spx_path_display=os.path.join(DATA_BASE_DIR, "<date>", SPX_CSV_NAME))

    selected_date = request.args.get("date") or dates[0]

    # SPX
    spx_path = os.path.join(DATA_BASE_DIR, selected_date, SPX_CSV_NAME)
    spx_df = load_csv_if_exists(spx_path)
    spx_available = not spx_df.empty

    traces = []
    layout = {
        "title": f"SPX and Strategy PnL — {selected_date}",
        "xaxis": {"title": "Time"},
        "yaxis": {"title": "SPX"},
        "yaxis2": {"title": "PnL (SPX points)", "overlaying": "y", "side": "right"},
        "legend": {"orientation": "h"},
        "margin": {"l": 60, "r": 60, "t": 50, "b": 50}
    }

    if spx_available:
        x_spx = spx_df["ts"].astype(str).tolist() if "ts" in spx_df.columns else list(range(len(spx_df)))
        spx_col = find_spx_price_column(spx_df)
        if spx_col:
            traces.append({
                "type": "scatter",
                "mode": "lines",
                "name": "SPX",
                "x": x_spx,
                "y": spx_df[spx_col].tolist(),
                "line": {"color": "#1f77b4", "width": 2},
                "yaxis": "y"
            })

    # Strategy overlays (if present)
    strategy_found = strategy_folder_exists(selected_date)
    status_text = ""
    pnl_if_text = ""

    if strategy_found:
        strat_dir = os.path.join(DATA_BASE_DIR, selected_date, STRATEGY_FOLDER)
        pnl_if_df = load_csv_if_exists(os.path.join(strat_dir, PNL_IF_CSV_NAME))
        pnl_strat_df = load_csv_if_exists(os.path.join(strat_dir, PNL_STRAT_CSV_NAME))

        palette = [
            "#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b",
            "#e377c2", "#7f7f7f", "#bcbd22", "#17becf", "#000000"
        ]

        if not pnl_if_df.empty and "body" in pnl_if_df.columns:
            try:
                bodies = sorted(pnl_if_df["body"].unique().tolist())
            except Exception:
                bodies = []
            for idx, body in enumerate(bodies):
                sub = pnl_if_df[pnl_if_df["body"] == body].sort_values("ts")
                x = sub["ts"].astype(str).tolist() if "ts" in sub.columns else list(range(len(sub)))
                y = sub["pnl"].astype(float).tolist() if "pnl" in sub.columns else []
                traces.append({
                    "type": "scatter",
                    "mode": "lines",
                    "name": f"IF {body}",
                    "x": x,
                    "y": y,
                    "line": {"color": palette[idx % len(palette)], "width": 1.5},
                    "yaxis": "y2"
                })

        if not pnl_strat_df.empty and "strategy_total_pnl" in pnl_strat_df.columns:
            sub = pnl_strat_df.sort_values("ts")
            x = sub["ts"].astype(str).tolist() if "ts" in sub.columns else list(range(len(sub)))
            y = sub["strategy_total_pnl"].astype(float).tolist()
            traces.append({
                "type": "scatter",
                "mode": "lines",
                "name": "Strategy PnL",
                "x": x,
                "y": y,
                "line": {"color": palette[-1], "width": 2.5},
                "yaxis": "y2"
            })

        # Raw file displays
        status_text = read_text_if_exists(os.path.join(strat_dir, STATE_JSON_NAME))
        pnl_if_text = read_text_if_exists(os.path.join(strat_dir, PNL_IF_CSV_NAME))

    return render_template("strategy.html",
                           active_tab="strategy",
                           dates=dates,
                           selected_date=selected_date,
                           spx_available=spx_available,
                           plotly_data=json.dumps(traces, default=str),
                           plotly_layout=json.dumps(layout, default=str),
                           strategy_found=strategy_found,
                           status_text=status_text,
                           pnl_if_text=pnl_if_text,
                           spx_path_display=spx_path)

if __name__ == "__main__":
    # If running standalone (not via main.py), start the server
    app.run(host="0.0.0.0", port=5000, debug=True)
