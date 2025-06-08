import json
import asyncio
from tastytrade import Session, DXLinkStreamer
from tastytrade.dxfeed import Quote, Greeks
from tastytrade.instruments import get_option_chain
from datetime import datetime
from decimal import Decimal
import sys
import os

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super(DecimalEncoder, self).default(obj)

def establish_connection():
    """Establish connection to tastytrade"""
    with open('secrets.json', 'r') as file:
        secrets = json.load(file)
    session = Session(secrets['username'], secrets['password'])
    return session

async def get_quote(session, ticker):
    """Get current quote using streaming data"""
    try:
        async with DXLinkStreamer(session) as streamer:
            await streamer.subscribe(Quote, [ticker])
            print(f"Getting {ticker} quote...")

            quote = await streamer.get_event(Quote)
            if quote.event_symbol == ticker:
                if quote.bid_price and quote.ask_price:
                    mid_price = (quote.bid_price + quote.ask_price) / 2
                    return {
                        'price': mid_price,
                        'bid': quote.bid_price,
                        'ask': quote.ask_price,
                        'bid_size': quote.bid_size,
                        'ask_size': quote.ask_size
                    }
            return None

    except Exception as e:
        print(f"Error getting {ticker} quote: {e}")
        return None

async def get_option_data(session, option_symbols):
    """Get quotes and Greeks for option symbols with better error handling"""
    option_data = {}

    try:
        async with DXLinkStreamer(session) as streamer:
            # Subscribe to both quotes and Greeks
            await streamer.subscribe(Quote, option_symbols)
            print(f"Subscribed to quotes for {len(option_symbols)} options...")

            try:
                await streamer.subscribe(Greeks, option_symbols)
                print(f"Subscribed to Greeks for {len(option_symbols)} options...")
                greeks_available = True
            except Exception as e:
                print(f"Greeks subscription failed: {e}")
                greeks_available = False

            # Initialize data structure for all symbols
            for symbol in option_symbols:
                option_data[symbol] = {
                    'symbol': symbol,
                    'bid': None,
                    'ask': None,
                    'bid_size': None,
                    'ask_size': None,
                    'mid': None,
                    'greeks_price': None,
                    'volatility': None,
                    'delta': None,
                    'gamma': None,
                    'theta': None,
                    'rho': None,
                    'vega': None,
                    'has_quote': False,
                    'has_greeks': False
                }

            quotes_collected = 0
            greeks_collected = 0
            target_quotes = len(option_symbols)
            target_greeks = len(option_symbols) if greeks_available else 0

            print(f"Collecting data... Target: {target_quotes} quotes, {target_greeks} Greeks")

            # Collect data with longer timeout and better tracking
            timeout_counter = 0
            max_timeouts = 20  # Increased from 10
            consecutive_empty_cycles = 0
            max_empty_cycles = 5

            while (quotes_collected < target_quotes or greeks_collected < target_greeks) and timeout_counter < max_timeouts:
                events_this_cycle = 0
                
                try:
                    # Try to get Quote events with longer timeout
                    try:
                        quote = await asyncio.wait_for(streamer.get_event(Quote), timeout=3.0)  # Increased timeout
                        if quote.event_symbol in option_symbols and not option_data[quote.event_symbol]['has_quote']:
                            # Check if we actually have valid bid/ask data
                            if quote.bid_price is not None or quote.ask_price is not None:
                                option_data[quote.event_symbol].update({
                                    'bid': quote.bid_price,
                                    'ask': quote.ask_price,
                                    'bid_size': quote.bid_size,
                                    'ask_size': quote.ask_size,
                                    'mid': (quote.bid_price + quote.ask_price) / 2 if quote.bid_price and quote.ask_price else None,
                                    'has_quote': True
                                })
                                quotes_collected += 1
                                events_this_cycle += 1

                                # if quotes_collected % 10 == 0:
                                #     print(f"Collected {quotes_collected}/{target_quotes} quotes...")
                    except asyncio.TimeoutError:
                        pass

                    # Try to get Greeks events if available
                    if greeks_available:
                        try:
                            greeks = await asyncio.wait_for(streamer.get_event(Greeks), timeout=3.0)  # Increased timeout
                            if greeks.event_symbol in option_symbols and not option_data[greeks.event_symbol]['has_greeks']:
                                option_data[greeks.event_symbol].update({
                                    'greeks_price': greeks.price,
                                    'volatility': greeks.volatility,
                                    'delta': greeks.delta,
                                    'gamma': greeks.gamma,
                                    'theta': greeks.theta,
                                    'rho': greeks.rho,
                                    'vega': greeks.vega,
                                    'has_greeks': True
                                })
                                greeks_collected += 1
                                events_this_cycle += 1

                                # if greeks_collected % 10 == 0:
                                #     print(f"Collected {greeks_collected}/{target_greeks} Greeks...")
                        except asyncio.TimeoutError:
                            pass

                    # Track consecutive empty cycles
                    if events_this_cycle == 0:
                        consecutive_empty_cycles += 1
                        if consecutive_empty_cycles >= max_empty_cycles:
                            print(f"No new data for {max_empty_cycles} cycles, checking if we have enough...")
                            # More lenient completion criteria
                            if quotes_collected >= target_quotes * 1:  # Increased from 0.8
                                if not greeks_available or greeks_collected >= target_greeks * 1:  # Increased from 0.5
                                    print("Sufficient data collected, stopping...")
                                    break
                            consecutive_empty_cycles = 0  # Reset counter
                    else:
                        consecutive_empty_cycles = 0

                except Exception as e:
                    print(f"Error collecting data: {e}")
                    timeout_counter += 1

            print(f"Data collection complete: {quotes_collected}/{target_quotes} quotes, {greeks_collected}/{target_greeks} Greeks")
            
            # Print summary of missing data
            missing_quotes = [symbol for symbol, data in option_data.items() if not data['has_quote']]
            missing_greeks = [symbol for symbol, data in option_data.items() if not data['has_greeks']]
            
            if missing_quotes:
                print(f"Missing quotes for {len(missing_quotes)} symbols")
            if missing_greeks:
                print(f"Missing Greeks for {len(missing_greeks)} symbols")

    except Exception as e:
        print(f"Error getting option data: {e}")

    return option_data

def safe_float_format(value, decimal_places=2, default_display="N/A"):
    """Safely format float values, handling None and zero cases"""
    if value is None:
        return default_display.ljust(6)
    try:
        if isinstance(value, (int, float, Decimal)):
            if value == 0:
                return "0.00".ljust(6)
            return f"{float(value):.{decimal_places}f}".ljust(6)
        return default_display.ljust(6)
    except (ValueError, TypeError):
        return default_display.ljust(6)

def calculate_gex(calls_data, puts_data, price):
    """
    Calculate Gamma Exposure (GEX) for each strike
    """
    gex_data = {}

    print(f"\nCalculating Gamma Exposure (GEX)...")
    print(f"Using Price: ${price:.2f}")

    # Convert price to float to ensure consistent types
    price = float(price)

    # Process calls
    for call in calls_data:
        strike = float(call['strike'])  # Convert Decimal to float
        gamma = call.get('gamma', 0) or 0
        gamma = float(gamma) if gamma is not None else 0.0

        # Estimate relative activity based on bid/ask spread and sizes
        bid = call.get('bid', 0) or 0
        ask = call.get('ask', 0) or 0
        bid_size = call.get('bid_size', 0) or 0
        ask_size = call.get('ask_size', 0) or 0

        # Convert to float
        bid = float(bid) if bid is not None else 0.0
        ask = float(ask) if ask is not None else 0.0
        bid_size = float(bid_size) if bid_size is not None else 0.0
        ask_size = float(ask_size) if ask_size is not None else 0.0

        if bid > 0 and ask > 0:
            spread = ask - bid
            mid = (bid + ask) / 2
            spread_pct = spread / mid if mid > 0 else 1

            # Estimate relative volume proxy (lower spread % + higher sizes = more volume)
            volume_proxy = (bid_size + ask_size) / max(spread_pct, 0.01)
        else:
            volume_proxy = 1  # Default minimal volume

        # Calculate Call GEX (positive gamma exposure for dealers when they're short calls)
        call_gex = gamma * volume_proxy * 100 * (price ** 2) / 1000000  # Scale down for readability

        if strike not in gex_data:
            gex_data[strike] = {'call_gex': 0, 'put_gex': 0, 'total_gex': 0, 'call_gamma': 0, 'put_gamma': 0}

        gex_data[strike]['call_gex'] = call_gex
        gex_data[strike]['call_gamma'] = gamma

    # Process puts
    for put in puts_data:
        strike = float(put['strike'])  # Convert Decimal to float
        gamma = put.get('gamma', 0) or 0
        gamma = float(gamma) if gamma is not None else 0.0

        # Estimate relative activity
        bid = put.get('bid', 0) or 0
        ask = put.get('ask', 0) or 0
        bid_size = put.get('bid_size', 0) or 0
        ask_size = put.get('ask_size', 0) or 0

        # Convert to float
        bid = float(bid) if bid is not None else 0.0
        ask = float(ask) if ask is not None else 0.0
        bid_size = float(bid_size) if bid_size is not None else 0.0
        ask_size = float(ask_size) if ask_size is not None else 0.0

        if bid > 0 and ask > 0:
            spread = ask - bid
            mid = (bid + ask) / 2
            spread_pct = spread / mid if mid > 0 else 1
            volume_proxy = (bid_size + ask_size) / max(spread_pct, 0.01)
        else:
            volume_proxy = 1

        # Calculate Put GEX (negative gamma exposure for dealers when they're short puts)
        put_gex = -gamma * volume_proxy * 100 * (price ** 2) / 1000000  # Negative for puts

        if strike not in gex_data:
            gex_data[strike] = {'call_gex': 0, 'put_gex': 0, 'total_gex': 0, 'call_gamma': 0, 'put_gamma': 0}

        gex_data[strike]['put_gex'] = put_gex
        gex_data[strike]['put_gamma'] = gamma

    # Calculate total GEX for each strike
    for strike in gex_data:
        gex_data[strike]['total_gex'] = gex_data[strike]['call_gex'] + gex_data[strike]['put_gex']

    return gex_data

def analyze_gex_levels(gex_data, price, top_n=10):
    """
    Analyze GEX levels to identify key support/resistance levels
    """
    print(f"\n{'='*80}")
    print(f"GAMMA EXPOSURE (GEX) ANALYSIS")
    print(f"{'='*80}")

    # Convert price to float for consistency
    price = float(price)

    # Sort strikes by total GEX magnitude
    sorted_strikes = sorted(gex_data.items(), key=lambda x: abs(x[1]['total_gex']), reverse=True)

    print(f"\nTop {top_n} Strikes by GEX Magnitude:")
    print(f"{'Strike':<8} {'Total GEX':<12} {'Call GEX':<12} {'Put GEX':<12} {'Distance':<10} {'Level Type':<15}")
    print("-" * 85)

    key_levels = []

    for i, (strike, data) in enumerate(sorted_strikes[:top_n]):
        distance = strike - price
        distance_pct = (distance / price) * 100

        # Determine level type
        if data['total_gex'] > 0:
            level_type = "Support" if strike < price else "Resistance"
        else:
            level_type = "Weak Support" if strike < price else "Weak Resistance"

        print(f"{strike:<8.0f} {data['total_gex']:<12.4f} {data['call_gex']:<12.4f} {data['put_gex']:<12.4f} {distance:+7.0f} ({distance_pct:+5.1f}%) {level_type:<15}")

        key_levels.append({
            'strike': strike,
            'total_gex': data['total_gex'],
            'distance': distance,
            'level_type': level_type
        })

    # Find zero gamma level (where total GEX crosses zero)
    zero_gamma_strikes = []
    sorted_by_strike = sorted(gex_data.items())

    for i in range(len(sorted_by_strike) - 1):
        current_strike, current_data = sorted_by_strike[i]
        next_strike, next_data = sorted_by_strike[i + 1]

        if (current_data['total_gex'] >= 0 and next_data['total_gex'] < 0) or \
           (current_data['total_gex'] < 0 and next_data['total_gex'] >= 0):
            # Linear interpolation to find approximate zero crossing
            if next_data['total_gex'] != current_data['total_gex']:
                zero_strike = current_strike + (next_strike - current_strike) * \
                             (-current_data['total_gex'] / (next_data['total_gex'] - current_data['total_gex']))
                zero_gamma_strikes.append(zero_strike)

    if zero_gamma_strikes:
        print(f"\nZero Gamma Levels (GEX crosses zero):")
        for zero_strike in zero_gamma_strikes:
            distance = zero_strike - price
            distance_pct = (distance / price) * 100
            print(f"  ${zero_strike:.0f} (Distance: {distance:+.0f}, {distance_pct:+.1f}%)")

    # Calculate net GEX
    total_call_gex = sum(data['call_gex'] for data in gex_data.values())
    total_put_gex = sum(data['put_gex'] for data in gex_data.values())
    net_gex = total_call_gex + total_put_gex

    print(f"\nOverall GEX Summary:")
    print(f"  Total Call GEX: {total_call_gex:.4f}")
    print(f"  Total Put GEX:  {total_put_gex:.4f}")
    print(f"  Net GEX:        {net_gex:.4f}")

    if net_gex > 0:
        print(f"  Market Regime: Positive GEX - Stabilizing/Mean Reverting")
    else:
        print(f"  Market Regime: Negative GEX - Trend Following/Momentum")

    #return key_levels, zero_gamma_strikes
    return key_levels, zero_gamma_strikes, {
    "call_gex": total_call_gex,
    "put_gex": total_put_gex,
    "net_gex": net_gex,
    "regime": "Positive GEX - Stabilizing/Mean Reverting" if net_gex > 0 else "Negative GEX - Trend Following/Momentum"
    }

def get_nearest_strikes(chain, current_price, num_strikes=20):
    """Get the nearest strikes around the current price"""
    if not chain:
        return []

    current_price_decimal = Decimal(str(current_price))
    all_strikes = sorted([option.strike_price for option in chain])

    closest_idx = min(range(len(all_strikes)),
                     key=lambda i: abs(all_strikes[i] - current_price_decimal))

    half_range = num_strikes // 2
    start_idx = max(0, closest_idx - half_range)
    end_idx = min(len(all_strikes), closest_idx + half_range + 1)

    selected_strikes = all_strikes[start_idx:end_idx]
    return [option for option in chain if option.strike_price in selected_strikes]

async def display_option_chain_with_greeks(session, ticker_data, ticker, expiry_date, price_override):
    """Get and display option chain with Greeks for 0DTE options with better formatting"""
    try:
        print(f"\n{'='*120}")
        print(f"{ticker} 0DTE OPTION CHAIN WITH GREEKS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{ticker} Price: ${ticker_data['price']:.2f} (Bid: ${ticker_data['bid']:.2f}, Ask: ${ticker_data['ask']:.2f})")
        print(f"{'='*120}")

        chain = get_option_chain(session, ticker)
        if expiry_date not in chain:
            print(f"No options found for expiration {expiry_date}")
            return [], []

        # Get nearest strikes around current price
        nearest_options = get_nearest_strikes(chain[expiry_date], ticker_data['price'], 100)

        if not nearest_options:
            print("No options found in the chain")
            return [], []

        option_symbols = [opt.streamer_symbol for opt in nearest_options]
        print(f"Fetching quotes and Greeks for {len(option_symbols)} options...")

        # Get live quotes and Greeks for all options
        option_data = await get_option_data(session, option_symbols)

        # Separate calls and puts with their data
        calls_data = []
        puts_data = []

        for option in nearest_options:
            data = option_data.get(option.streamer_symbol, {})
            option_info = {
                'strike': float(option.strike_price),
                'symbol': option.streamer_symbol,
                'bid': data.get('bid'),
                'ask': data.get('ask'),
                'mid': data.get('mid'),
                'bid_size': data.get('bid_size'),
                'ask_size': data.get('ask_size'),
                'delta': data.get('delta'),
                'gamma': data.get('gamma'),
                'theta': data.get('theta'),
                'vega': data.get('vega'),
                'volatility': data.get('volatility'),
                'has_quote': data.get('has_quote', False),
                'has_greeks': data.get('has_greeks', False)
            }

            if option.option_type == 'C':
                calls_data.append(option_info)
            else:
                puts_data.append(option_info)

        # Sort by strike price
        calls_data.sort(key=lambda x: x['strike'])
        puts_data.sort(key=lambda x: x['strike'])

        # Display header
        print(f"\n{'CALLS':<80} {'PUTS':<80}")
        print(f"{'Mid':<6} {'Bid':<6} {'Ask':<6} {'Vol':<4} {'Δ':<6} {'Γ':<6} {'Θ':<6} {'V':<6} | {'Strike':<6} | {'Mid':<6} {'Bid':<6} {'Ask':<6} {'Vol':<4} {'Δ':<6} {'Γ':<6} {'Θ':<6} {'V':<6}")
        print("-" * 165)

        # Display side by side with better formatting
        max_len = max(len(calls_data), len(puts_data))
        no_data_strikes = []

        for i in range(max_len):
            call_line = ""
            put_line = ""
            strike_display = ""

            if i < len(calls_data):
                c = calls_data[i]
                # Check if we have actual data
                if not c['has_quote']:
                    call_line = f"{'N/A':<6} {'N/A':<6} {'N/A':<6} {'N/A':<4} {'N/A':<6} {'N/A':<6} {'N/A':<6} {'N/A':<6}"
                    no_data_strikes.append(f"C{c['strike']}")
                else:
                    call_line = f"{safe_float_format(c['mid'])} {safe_float_format(c['bid'])} {safe_float_format(c['ask'])} {safe_float_format(c['volatility'], 0, 'N/A'):<4} {safe_float_format(c['delta'], 3)} {safe_float_format(c['gamma'], 3)} {safe_float_format(c['theta'])} {safe_float_format(c['vega'])}"
                
                strike_display = f"{c['strike']:<6.0f}"
            else:
                call_line = " " * 50
                if i < len(puts_data):
                    p = puts_data[i]
                    strike_display = f"{p['strike']:<6.0f}"
                else:
                    strike_display = " " * 6

            if i < len(puts_data):
                p = puts_data[i]
                # Check if we have actual data
                if not p['has_quote']:
                    put_line = f"{'N/A':<6} {'N/A':<6} {'N/A':<6} {'N/A':<4} {'N/A':<6} {'N/A':<6} {'N/A':<6} {'N/A':<6}"
                    no_data_strikes.append(f"P{p['strike']}")
                else:
                    put_line = f"{safe_float_format(p['mid'])} {safe_float_format(p['bid'])} {safe_float_format(p['ask'])} {safe_float_format(p['volatility'], 0, 'N/A'):<4} {safe_float_format(p['delta'], 3)} {safe_float_format(p['gamma'], 3)} {safe_float_format(p['theta'])} {safe_float_format(p['vega'])}"
            else:
                put_line = " " * 50

            print(f"{call_line} | {strike_display} | {put_line}")

        print(f"\nTotal options displayed: {len(calls_data)} calls, {len(puts_data)} puts")
        if no_data_strikes:
            print(f"Strikes with no market data: {', '.join(no_data_strikes[:10])}" + 
                  (f" and {len(no_data_strikes)-10} more..." if len(no_data_strikes) > 10 else ""))
        
        print("Legend: Mid=Mid Price, Bid=Bid Price, Ask=Ask Price, Vol=IV%, Δ=Delta, Γ=Gamma, Θ=Theta, V=Vega")
        print("N/A = No market data available")

        gex_price = ticker_data['price'] if price_override == 0 else price_override
        # Calculate and display GEX analysis (only for options with data)
        valid_calls = [c for c in calls_data if c['has_quote'] and c['gamma'] is not None]
        valid_puts = [p for p in puts_data if p['has_quote'] and p['gamma'] is not None]
        
        print(f"\nUsing {len(valid_calls)} calls and {len(valid_puts)} puts for GEX calculation")
        gex_data = calculate_gex(valid_calls, valid_puts, gex_price)
        #key_levels, zero_gamma_strikes = analyze_gex_levels(gex_data, ticker_data['price'], top_n=15)
        key_levels, zero_gamma_strikes, gex_summary = analyze_gex_levels(gex_data, ticker_data['price'], top_n=15)

        return key_levels, zero_gamma_strikes, calls_data, puts_data,gex_summary

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        filename = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        line_number = exc_tb.tb_lineno
        print(f"Error getting option chain: {e}. Exception: {exc_type} in File: {filename} on Line Number: {line_number}.")
        return [], []

async def run_gex_analysis(ticker, expiry_date, price_override=0):
    """Main function to fetch and display data with Greeks - now returns results instead of just printing"""
    try:
        print("Connecting to tastytrade...")
        session = establish_connection()
        print("Connected successfully!")

        print(f"\nFetching {ticker} quote...")
        ticker_data = await get_quote(session, ticker)

        if ticker_data:
            key_levels, zero_gamma_strikes, calls_data, puts_data, gex_summary = await display_option_chain_with_greeks(
                session, ticker_data, ticker, expiry_date, price_override
            )
            print(f"\nGEX Analysis Complete!")
            print(f"Key levels identified: {len(key_levels)}")
            print(f"Zero gamma crossings: {len(zero_gamma_strikes)}")
            
            return {
                'success': True,
                'ticker_data': ticker_data,
                'key_levels': key_levels,
                'zero_gamma_strikes': zero_gamma_strikes,
                'calls_data': calls_data,
                'puts_data': puts_data,
                "gex_summary" : gex_summary
            }
        else:
            print(f"Failed to get {ticker} price")
            return {'success': False, 'error': f"Failed to get {ticker} price"}

    except Exception as e:
        print(f"Error in run_gex_analysis: {e}")
        return {'success': False, 'error': str(e)}

# Convenience function for direct usage
def analyze_options_gex(ticker, expiry_date_str, price_override=0):
    """
    Convenience function to run GEX analysis without needing to handle asyncio directly
    
    Args:
        ticker (str): Ticker symbol (e.g., 'SPX', 'AAPL')
        expiry_date_str (str): Expiry date in 'YYYY-MM-DD' format
        price_override (float): Optional price override for GEX calculation
    
    Returns:
        dict: Analysis results with success status, ticker data, key levels, and zero gamma strikes
    """
    expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
    return asyncio.run(run_gex_analysis(ticker, expiry_date, price_override))

# Example usage for testing
if __name__ == "__main__":
    # For testing - can be called directly. Last parameter is current price if running before/after market
    result = analyze_options_gex("SPX", "2025-06-09", 5925)
    if result['success']:
        print(f"\nAnalysis completed successfully!")
        print(f"Found {len(result['key_levels'])} key levels")
        print(f"Found {len(result['zero_gamma_strikes'])} zero gamma crossings")
    else:
        print(f"Analysis failed: {result['error']}")
