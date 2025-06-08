from flask import Flask, render_template, request
from greeks_gex import analyze_options_gex
import datetime
import pytz
import holidays

app = Flask(__name__)

ROUND_KEYS = ["mid", "bid", "ask", "volatility", "delta", "gamma", "theta", "vega"]

# US market holiday calendar
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

@app.route("/", methods=["GET", "POST"])
def index():
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

    return render_template("index.html", result=result, error=error, expiry=expiry)

if __name__ == "__main__":
    app.run(debug=True)
