from flask import Flask, request, render_template, send_file, abort
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

# ---------- Chart Data Preparation Functions ----------
def prepare_spx_data(date: str) -> pd.DataFrame:
    """
    Parse spx.csv and extract time/mark price data.
    Returns DataFrame with 'Time' and 'Mark Price' columns.
    """
    spx_path = os.path.join(DATA_BASE_DIR, date, SPX_CSV_NAME)
    
    if not os.path.exists(spx_path):
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(spx_path)
        
        # Validate required columns exist
        if 'Time' not in df.columns:
            print(f"Warning: 'Time' column not found in {spx_path}")
            return pd.DataFrame()
        
        # Handle Mark Price column - calculate from bid/ask if Mark Price is empty or missing
        mark_price_col = None
        if 'Mark Price' in df.columns and not df['Mark Price'].isna().all():
            mark_price_col = 'Mark Price'
        elif 'Bid Price' in df.columns and 'Ask Price' in df.columns:
            # Calculate mark price from bid/ask
            bid_prices = pd.to_numeric(df['Bid Price'], errors='coerce')
            ask_prices = pd.to_numeric(df['Ask Price'], errors='coerce')
            df['Mark Price'] = (bid_prices + ask_prices) / 2
            mark_price_col = 'Mark Price'
        
        if mark_price_col is None:
            print(f"Warning: No price data found in {spx_path}")
            return pd.DataFrame()
        
        # Convert Time to datetime and clean data
        df['Time'] = pd.to_datetime(df['Time'], errors='coerce')
        df = df.dropna(subset=['Time', mark_price_col])
        
        # Return only the columns we need
        return df[['Time', mark_price_col]].copy()
        
    except Exception as e:
        print(f"Error reading SPX data from {spx_path}: {e}")
        return pd.DataFrame()


def prepare_pnl_data(date: str) -> pd.DataFrame:
    """
    Parse pnl.csv and organize by fly body.
    Returns DataFrame with 'ts', 'body', 'pnl', 'total_pnl', 'realized_pnl' columns.
    """
    pnl_path = os.path.join(DATA_BASE_DIR, date, STRATEGY_FOLDER, PNL_IF_CSV_NAME)
    
    if not os.path.exists(pnl_path):
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(pnl_path)
        
        # Validate required columns exist
        required_cols = ['ts', 'body', 'pnl']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            print(f"Warning: Missing columns {missing_cols} in {pnl_path}")
            return pd.DataFrame()
        
        # Convert timestamp and clean data
        df['ts'] = pd.to_datetime(df['ts'], errors='coerce')
        df = df.dropna(subset=['ts', 'body', 'pnl'])
        
        # Ensure numeric columns are properly typed
        df['body'] = pd.to_numeric(df['body'], errors='coerce')
        df['pnl'] = pd.to_numeric(df['pnl'], errors='coerce')
        
        if 'total_pnl' in df.columns:
            df['total_pnl'] = pd.to_numeric(df['total_pnl'], errors='coerce')
        if 'realized_pnl' in df.columns:
            df['realized_pnl'] = pd.to_numeric(df['realized_pnl'], errors='coerce')
        
        return df.dropna(subset=['body', 'pnl'])
        
    except Exception as e:
        print(f"Error reading PnL data from {pnl_path}: {e}")
        return pd.DataFrame()


def get_current_pnl(date: str) -> float:
    """
    Extract latest total PnL including realized losses.
    Returns the most recent total_pnl value from pnl.csv.
    """
    pnl_df = prepare_pnl_data(date)
    
    if pnl_df.empty or 'total_pnl' not in pnl_df.columns:
        return 0.0
    
    try:
        # Get the latest timestamp and corresponding total_pnl
        latest_row = pnl_df.loc[pnl_df['ts'].idxmax()]
        return float(latest_row['total_pnl'])
    except Exception as e:
        print(f"Error extracting current PnL for {date}: {e}")
        return 0.0


def format_spx_trace(spx_df: pd.DataFrame) -> dict:
    """
    Structure SPX data for Plotly.
    Returns a Plotly trace dictionary for SPX price data.
    """
    if spx_df.empty:
        return {
            "type": "scatter",
            "mode": "lines",
            "name": "SPX",
            "x": [],
            "y": [],
            "line": {"color": "#1f77b4", "width": 2},
            "yaxis": "y"
        }
    
    try:
        # Use the Mark Price column (should be available after prepare_spx_data)
        price_col = 'Mark Price'
        if price_col not in spx_df.columns:
            print("Warning: Mark Price column not found in SPX data")
            return {"type": "scatter", "mode": "lines", "name": "SPX", "x": [], "y": []}
        
        return {
            "type": "scatter",
            "mode": "lines",
            "name": "SPX",
            "x": spx_df['Time'].dt.strftime('%H:%M:%S').tolist(),
            "y": spx_df[price_col].tolist(),
            "line": {"color": "#1f77b4", "width": 2},
            "yaxis": "y"
        }
    except Exception as e:
        print(f"Error formatting SPX trace: {e}")
        return {"type": "scatter", "mode": "lines", "name": "SPX", "x": [], "y": []}


def format_fly_traces(pnl_df: pd.DataFrame) -> list:
    """
    Structure individual fly PnL data with color coding.
    Returns a list of Plotly trace dictionaries for each fly position.
    """
    if pnl_df.empty:
        return []
    
    # Enhanced color palette for 9 fly positions with distinct, vibrant colors
    color_palette = [
        "#FF6B6B",  # Red
        "#4ECDC4",  # Teal
        "#45B7D1",  # Blue
        "#96CEB4",  # Green
        "#FFEAA7",  # Yellow
        "#DDA0DD",  # Plum
        "#98D8C8",  # Mint
        "#F7DC6F",  # Light Yellow
        "#BB8FCE"   # Light Purple
    ]
    
    traces = []
    
    try:
        # Get unique fly bodies (strike prices) and sort them
        bodies = sorted(pnl_df['body'].unique())
        
        for idx, body in enumerate(bodies):
            # Filter data for this specific fly
            fly_data = pnl_df[pnl_df['body'] == body].sort_values('ts')
            
            if fly_data.empty:
                continue
            
            # Create trace for this fly
            trace = {
                "type": "scatter",
                "mode": "lines+markers",
                "name": f"IF {body:.0f}",
                "x": fly_data['ts'].dt.strftime('%H:%M:%S').tolist(),
                "y": fly_data['pnl'].tolist(),
                "line": {
                    "color": color_palette[idx % len(color_palette)], 
                    "width": 2
                },
                "marker": {
                    "size": 4,
                    "color": color_palette[idx % len(color_palette)]
                },
                "yaxis": "y2",
                "hovertemplate": f"<b>IF {body:.0f}</b><br>" +
                               "Time: %{x}<br>" +
                               "PnL: %{y:.2f}<br>" +
                               "<extra></extra>"
            }
            traces.append(trace)
            
    except Exception as e:
        print(f"Error formatting fly traces: {e}")
        return []
    
    return traces


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

def generate_download_url(date: str, file_type: str) -> str:
    """Generate download URL for specific date and file type"""
    return f"/download/{date}/{file_type}"

def validate_download_request(date: str, file_type: str) -> tuple[bool, str, str]:
    """
    Validate download request parameters and return (is_valid, file_path, error_message)
    """
    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return False, "", "Invalid date format. Expected YYYY-MM-DD."
    
    # Validate file_type
    allowed_file_types = ["pnl", "quotes"]
    if file_type not in allowed_file_types:
        return False, "", f"Invalid file type. Allowed types: {', '.join(allowed_file_types)}"
    
    # Map file_type to actual filename
    file_mapping = {
        "pnl": PNL_IF_CSV_NAME,
        "quotes": "quotes.csv"
    }
    
    filename = file_mapping[file_type]
    file_path = os.path.join(DATA_BASE_DIR, date, STRATEGY_FOLDER, filename)
    
    # Security check: ensure the resolved path is within DATA_BASE_DIR
    abs_data_dir = os.path.abspath(DATA_BASE_DIR)
    abs_file_path = os.path.abspath(file_path)
    
    if not abs_file_path.startswith(abs_data_dir):
        return False, "", "Invalid file path."
    
    # Check if file exists
    if not os.path.exists(file_path):
        return False, "", f"File {filename} not found for date {date}."
    
    return True, file_path, ""

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
        return render_template("SPX_9IF_0DTE.html",
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

    # Prepare chart data using new functions
    spx_df = prepare_spx_data(selected_date)
    pnl_df = prepare_pnl_data(selected_date)
    current_pnl = get_current_pnl(selected_date)
    
    spx_available = not spx_df.empty
    strategy_found = strategy_folder_exists(selected_date)

    # Create chart traces
    traces = []
    
    # Add SPX trace
    if spx_available:
        spx_trace = format_spx_trace(spx_df)
        if spx_trace.get('x'):  # Only add if we have data
            traces.append(spx_trace)
    
    # Add fly traces
    if strategy_found and not pnl_df.empty:
        fly_traces = format_fly_traces(pnl_df)
        traces.extend(fly_traces)

    # Chart layout with proper dual y-axis configuration and current PnL display
    layout = {
        "title": {
            "text": f"SPX and Strategy PnL — {selected_date}",
            "x": 0.5,
            "xanchor": "center"
        },
        "xaxis": {
            "title": "Time",
            "type": "category",
            "tickangle": -45
        },
        "yaxis": {
            "title": "SPX Price",
            "side": "left",
            "showgrid": True,
            "zeroline": False
        },
        "yaxis2": {
            "title": "PnL (SPX points)",
            "overlaying": "y",
            "side": "right",
            "showgrid": False,
            "zeroline": True,
            "zerolinecolor": "rgba(0,0,0,0.3)",
            "zerolinewidth": 1
        },
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1
        },
        "margin": {"l": 80, "r": 80, "t": 80, "b": 80},
        "hovermode": "x unified",
        "showlegend": True,
        "annotations": [
            {
                "text": f"Current PnL: {current_pnl:.2f}",
                "xref": "paper",
                "yref": "paper",
                "x": 0.02,
                "y": 0.98,
                "xanchor": "left",
                "yanchor": "top",
                "showarrow": False,
                "font": {
                    "size": 16, 
                    "color": "red" if current_pnl < 0 else "green",
                    "family": "Arial, sans-serif"
                },
                "bgcolor": "rgba(255,255,255,0.9)",
                "bordercolor": "red" if current_pnl < 0 else "green",
                "borderwidth": 2,
                "borderpad": 4
            }
        ] if current_pnl != 0.0 else []
    }

    # Raw file displays for debugging
    status_text = ""
    pnl_if_text = ""
    if strategy_found:
        strat_dir = os.path.join(DATA_BASE_DIR, selected_date, STRATEGY_FOLDER)
        status_text = read_text_if_exists(os.path.join(strat_dir, STATE_JSON_NAME))
        pnl_if_text = read_text_if_exists(os.path.join(strat_dir, PNL_IF_CSV_NAME))

    # Generate download URLs for the template
    pnl_download_url = generate_download_url(selected_date, "pnl") if strategy_found else None
    quotes_download_url = generate_download_url(selected_date, "quotes") if strategy_found else None
    
    # Check if files actually exist for download buttons
    pnl_file_exists = False
    quotes_file_exists = False
    if strategy_found:
        pnl_path = os.path.join(DATA_BASE_DIR, selected_date, STRATEGY_FOLDER, PNL_IF_CSV_NAME)
        quotes_path = os.path.join(DATA_BASE_DIR, selected_date, STRATEGY_FOLDER, "quotes.csv")
        pnl_file_exists = os.path.exists(pnl_path)
        quotes_file_exists = os.path.exists(quotes_path)

    return render_template("SPX_9IF_0DTE.html",
                           active_tab="strategy",
                           dates=dates,
                           selected_date=selected_date,
                           spx_available=spx_available,
                           plotly_data=json.dumps(traces, default=str),
                           plotly_layout=json.dumps(layout, default=str),
                           strategy_found=strategy_found,
                           status_text=status_text,
                           pnl_if_text=pnl_if_text,
                           spx_path_display=os.path.join(DATA_BASE_DIR, selected_date, SPX_CSV_NAME),
                           pnl_download_url=pnl_download_url,
                           quotes_download_url=quotes_download_url,
                           pnl_file_exists=pnl_file_exists,
                           quotes_file_exists=quotes_file_exists)

@app.route("/download/<date>/<file_type>")
def download_file(date: str, file_type: str):
    """Serve CSV files for download with proper validation and error handling"""
    
    # Validate the download request
    is_valid, file_path, error_message = validate_download_request(date, file_type)
    
    if not is_valid:
        abort(404, description=error_message)
    
    try:
        # Generate appropriate filename for download
        file_mapping = {
            "pnl": f"pnl_{date}.csv",
            "quotes": f"quotes_{date}.csv"
        }
        download_name = file_mapping.get(file_type, f"{file_type}_{date}.csv")
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=download_name,
            mimetype='text/csv'
        )
    except Exception as e:
        abort(500, description=f"Error serving file: {str(e)}")

if __name__ == "__main__":
    # If running standalone (not via main.py), start the server
    app.run(host="0.0.0.0", port=5000, debug=True)
