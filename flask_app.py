from flask import Flask, render_template_string, request
import os
import pandas as pd
import datetime
from typing import List
import pytz
import holidays

# Your existing GEX import
from greeks_gex import analyze_options_gex

# ----- Flask setup -----
app = Flask(__name__)

# ======== Existing GEX helpers ========

ROUND_KEYS = ["mid", "bid", "ask", "volatility", "delta", "gamma", "theta", "vega"]
us_holidays = holidays.UnitedStates()

def get_default_expiry():
    tz = pytz.timezone("US/Eastern")
    now = datetime.datetime.now(tz)
    today = now.date()
    is_weekday = today.weekday() < 5
    is_holiday = today in us_holidays
    before_3pm = now.hour < 15
    if is_weekday and not is_holiday and before_3pm:
        return today.isoformat()
    next_day = today + datetime.timedelta(days=1)
    while next_day.weekday() >= 5 or next_day in us_holidays:
        next_day += datetime.timedelta(days=1)
    return next_day.isoformat()

def round_fields_safe(item, decimals=2):
    try:
        obj_dict = vars(item)
    except TypeError:
        try:
            obj_dict = dict(item)
        except Exception:
            return item
    result = {}
    for key, value in obj_dict.items():
        if key in ROUND_KEYS:
            try:
                result[key] = round(float(value), decimals)
            except:
                result[key] = value
        else:
            result[key] = value
    return result

def format_result(result, decimals=2):
    if not result or not isinstance(result, dict):
        return result
    for key in ["calls_data", "puts_data"]:
        if key in result and isinstance(result[key], list):
            result[key] = [round_fields_safe(item, decimals) for item in result[key]]
    if "ticker_data" in result:
        result["ticker_data"] = round_fields_safe(result["ticker_data"], decimals)
    if "key_levels" in result and isinstance(result["key_levels"], list):
        for item in result["key_levels"]:
            try:
                item["total_gex"] = round(float(item["total_gex"]), decimals)
            except:
                pass
    if "zero_gamma_strikes" in result and isinstance(result["zero_gamma_strikes"], list):
        result["zero_gamma_strikes"] = [
            round(float(z), decimals) if isinstance(z, (float, int, str)) else z
            for z in result["zero_gamma_strikes"]
        ]
    if "gex_summary" in result:
        g = result["gex_summary"]
        for key in ["call_gex", "put_gex", "net_gex"]:
            try:
                g[key] = round(float(g[key]), decimals)
            except:
                pass
    return result

# ======== Strategy helpers ========

DATA_BASE_DIR = "Data"
STRATEGY_FOLDER = "SPX_9IF_0DTE"

def list_available_dates() -> List[str]:
    if not os.path.isdir(DATA_BASE_DIR):
        return []
    dates = []
    for name in os.listdir(DATA_BASE_DIR):
        p = os.path.join(DATA_BASE_DIR, name)
        try:
            datetime.datetime.strptime(name, "%Y-%m-%d")
            if os.path.isdir(p):
                dates.append(name)
        except:
            pass
    return sorted(dates, reverse=True)

def load_csv_if_exists(path):
    if os.path.exists(path):
        try:
            return pd.read_csv(path)
        except:
            return pd.DataFrame()
    return pd.DataFrame()

def read_text_if_exists(path):
    if os.path.exists(path):
        try:
            return open(path, encoding="utf-8", errors="ignore").read()
        except:
            return ""
    return ""

# ======== Templates ========

BASE_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Dashboard</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <script src="https://cdn.plot.ly/plotly-2.30.0.min.js"></script>
</head>
<body class="p-3">
  <ul class="nav nav-tabs">
    <li class="nav-item"><a href="/gex" class="nav-link {% if tab=='gex' %}active{% endif %}">GEX</a></li>
    <li class="nav-item"><a href="/strategy" class="nav-link {% if tab=='strategy' %}active{% endif %}">Strategy</a></li>
  </ul>
  <div class="mt-3">{% block content %}{% endblock %}</div>
</body>
</html>
"""

GEX_HTML = """
{% extends "base.html" %}
{% block content %}
<h4>GEX Dashboard</h4>
<form method="post">
  Ticker: <input name="ticker" value="SPX">
  Expiry: <input name="expiry" value="{{ expiry }}">
  Price Override: <input name="price_override" value="">
  <button type="submit" class="btn btn-primary">Run</button>
</form>
{% if error %}<div class="alert alert-danger">{{ error }}</div>{% endif %}
{% if result %}<pre>{{ result }}</pre>{% endif %}
{% endblock %}
"""

STRATEGY_HTML = """
{% extends "base.html" %}
{% block content %}
<h4>Strategy Dashboard</h4>
<form method="get">
  <label>Date:</label>
  <select name="date">
    {% for d in dates %}
    <option value="{{ d }}" {% if d==selected_date %}selected{% endif %}>{{ d }}</option>
    {% endfor %}
  </select>
  <button class="btn btn-sm btn-primary">Load</button>
</form>

{% if spx_data %}
<div id="chart" style="height:600px;"></div>
<script>
var data = {{ chart_data|safe }};
var layout = {{ chart_layout|safe }};
Plotly.newPlot('chart', data, layout);
</script>
{% else %}
<div class="alert alert-warning">No SPX data for {{ selected_date }}</div>
{% endif %}

{% if strat_found %}
<hr>
<h5>status.csv</h5>
<pre>{{ status_text }}</pre>
<h5>pnl.csv</h5>
<pre>{{ pnl_text }}</pre>
{% endif %}
{% endblock %}
"""

app.jinja_loader.mapping = {
    'base.html': BASE_HTML,
    'gex.html': GEX_HTML,
    'strategy.html': STRATEGY_HTML
}

# ======== Routes ========

@app.route("/", methods=["GET", "POST"])
@app.route("/gex", methods=["GET", "POST"])
def gex():
    result = None
    error = None
    default_expiry = get_default_expiry()
    expiry = default_expiry
    if request.method == "POST":
        ticker = request.form.get("ticker", "SPX")
        expiry = request.form.get("expiry") or default_expiry
        price = request.form.get("price_override", "0")
        try:
            price_override = float(price) if price else 0
            analysis = analyze_options_gex(ticker, expiry, price_override)
            if analysis["success"]:
                result = format_result(analysis)
            else:
                error = analysis["error"]
        except Exception as e:
            error = str(e)
    return render_template_string(GEX_HTML, tab="gex", result=result, error=error, expiry=expiry)

@app.route("/strategy")
def strategy():
    dates = list_available_dates()
    selected_date = request.args.get("date") or (dates[0] if dates else "")
    spx_df = load_csv_if_exists(os.path.join(DATA_BASE_DIR, selected_date, "spx.csv"))
    chart_data = []
    chart_layout = {
        "title": f"SPX and Strategy PnL — {selected_date}",
        "xaxis":{"title":"Time"},
        "yaxis":{"title":"SPX"},
        "yaxis2":{"title":"PnL", "overlaying":"y", "side":"right"}
    }
    if not spx_df.empty:
        if "ts" in spx_df.columns:
            spx_df["ts"] = pd.to_datetime(spx_df["ts"], errors="coerce")
            x = spx_df["ts"].astype(str).tolist()
        else:
            x = list(range(len(spx_df)))
        ycol = next((c for c in spx_df.columns if c.lower() in ["spx","close","price"]), None)
        if ycol:
            chart_data.append({"x":x, "y":spx_df[ycol].tolist(),
                               "type":"scatter","mode":"lines","name":"SPX","yaxis":"y"})
    strat_path = os.path.join(DATA_BASE_DIR, selected_date, STRATEGY_FOLDER)
    strat_found = os.path.isdir(strat_path)
    if strat_found:
        pnl_df = load_csv_if_exists(os.path.join(strat_path,"pnl.csv"))
        pnl_strat_df = load_csv_if_exists(os.path.join(strat_path,"pnl_strategy.csv"))
        colors = ["#d62728","#2ca02c","#ff7f0e","#9467bd","#8c564b",
                  "#e377c2","#7f7f7f","#bcbd22","#17becf","#000000"]
        if not pnl_df.empty:
            for idx, body in enumerate(sorted(pnl_df["body"].unique())):
                sub = pnl_df[pnl_df["body"]==body].sort_values("ts")
                chart_data.append({"x":sub["ts"].astype(str).tolist(),
                                   "y":sub["pnl"].tolist(),
                                   "type":"scatter","mode":"lines",
                                   "name":f"IF {body}","yaxis":"y2",
                                   "line":{"color":colors[idx%len(colors)]}})
        if not pnl_strat_df.empty:
            sub = pnl_strat_df.sort_values("ts")
            chart_data.append({"x":sub["ts"].astype(str).tolist(),
                               "y":sub["strategy_total_pnl"].tolist(),
                               "type":"scatter","mode":"lines","name":"Strategy PnL",
                               "yaxis":"y2","line":{"color":colors[-1],"width":2}})
        status_text = read_text_if_exists(os.path.join(strat_path,"status.csv"))
        pnl_text = read_text_if_exists(os.path.join(strat_path,"pnl.csv"))
    else:
        status_text = ""; pnl_text = ""
    return render_template_string(STRATEGY_HTML, tab="strategy",
                                  dates=dates, selected_date=selected_date,
                                  spx_data=not spx_df.empty,
                                  chart_data=json.dumps(chart_data),
                                  chart_layout=json.dumps(chart_layout),
                                  strat_found=strat_found,
                                  status_text=status_text, pnl_text=pnl_text)

if __name__ == "__main__":
    app.run(debug=True)
